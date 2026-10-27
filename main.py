"""Run once per invocation (cron / GitHub Actions calls it every 15 min).

python main.py              normal run, sends Telegram alerts
python main.py --dry-run    prints alerts instead of sending
python main.py --mock       uses built-in fake data (no internet needed)
python main.py --test       sends one test message to Telegram
python main.py --get-chat-id
"""
import argparse
import json
import logging
import os
import time

import config
import crypto
import llm
import notifier
import scoring
import sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")


def load_state() -> dict:
    try:
        with open(config.STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    tmp = config.STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, config.STATE_FILE)


def should_alert(c, has_llm: bool) -> bool:
    if config.TOPICS != ["all"] and has_llm and c.category and c.category not in config.TOPICS:
        return False
    if config.MODE == "memecoin":
        if has_llm and c.meme is not None:
            return (c.meme >= config.MEME_MIN_SCORE and (c.viral or 0) >= 4
                    and c.score >= config.ALERT_THRESHOLD - 20)
        return c.score >= config.ALERT_THRESHOLD
    if c.score < config.ALERT_THRESHOLD - 10:
        return False
    if not has_llm or c.viral is None:
        return c.score >= config.ALERT_THRESHOLD
    if c.shocking and c.score >= config.ALERT_THRESHOLD - 10:
        return True
    if c.score >= config.ALERT_THRESHOLD:
        return c.viral >= 5
    return c.viral >= 8  # slightly below threshold but the LLM is confident it will explode


def run(dry: bool, mock: bool) -> None:
    state = load_state()
    items = sources.mock_items() if mock else sources.collect_all()
    if not items:
        log.error("No data collected from any source; aborting without touching state.")
        return

    clusters = scoring.build_clusters(items, state)
    floor = config.ALERT_THRESHOLD - (20 if config.MODE == "memecoin" else 10)
    candidates = [c for c in clusters if c.score >= floor][:15]
    has_llm = llm.enrich(candidates)

    now = time.time()
    sent = 0
    for c in candidates:
        if sent >= config.MAX_ALERTS_PER_RUN or not should_alert(c, has_llm):
            continue
        k = scoring.key_of(c.items[0].title)
        last = state.get("alerted", {}).get(k)
        if last and now - last["ts"] < config.REALERT_AFTER_HOURS * 3600 and c.score < last["score"] + 15:
            continue
        if config.MODE == "memecoin":
            crypto.attach_tokens([c], mock=mock)
        text = notifier.format_alert(c)
        if dry:
            print("-" * 60 + "\n" + text + "\n")
        else:
            notifier.send(text)
        state.setdefault("alerted", {})[k] = {"ts": now, "score": c.score}
        sent += 1

    scoring.update_state(state, items)
    save_state(state)
    log.info("done: %d items, %d clusters, %d candidates, %d alerts (llm=%s)",
             len(items), len(clusters), len(candidates), sent, has_llm)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--get-chat-id", action="store_true")
    a = ap.parse_args()
    if a.get_chat_id:
        notifier.get_chat_id()
    elif a.test:
        notifier.send("✅ viral-radar is connected. You'll get alerts here.")
    else:
        run(dry=a.dry_run, mock=a.mock)
