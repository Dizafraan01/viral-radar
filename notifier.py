import html
import requests

import config
from models import Cluster


def _money(x: float) -> str:
    return f"${x / 1e6:.1f}M" if x >= 1e6 else f"${x / 1e3:.0f}k" if x >= 1e3 else f"${x:.0f}"


def _token_lines(c: Cluster) -> list[str]:
    if not c.tokens_checked:
        return []
    if not c.tokens:
        extra = f" ({c.token_total} tiny pool(s) ignored)" if c.token_total else ""
        return ["", "🪙 <b>No token with a matching name found yet</b>" + extra
                + ". It may be early, or the token uses a different name or spelling."]
    hidden = c.token_total - len(c.tokens)
    note = f" ({hidden} more, tiny or lower-liquidity, not shown)" if hidden > 0 else ""
    out = ["", f"🪙 <b>{c.token_total} token(s) found</b>{note}, top by liquidity:"]
    for t in c.tokens:
        age = "?" if t["age_h"] is None else (f"{t['age_h'] * 60:.0f}m" if t["age_h"] < 1 else
                                              f"{t['age_h']:.0f}h" if t["age_h"] < 48 else f"{t['age_h'] / 24:.0f}d")
        line = (f"• ${html.escape(t['symbol'])} ({html.escape(t['chain'])}) liq {_money(t['liq'])} · "
                f"vol24 {_money(t['vol'])} · age {age}")
        if t["flags"]:
            line += " · ⚠ " + html.escape(", ".join(t["flags"]))
        out.append(line)
        if t["url"]:
            out.append(f'  <a href="{html.escape(t["url"], quote=True)}">chart</a>')
        if t["chain"] == "solana" and t["address"]:
            out.append(f'  <a href="https://rugcheck.xyz/tokens/{html.escape(t["address"], quote=True)}">rugcheck</a>')
    if c.token_total > 3:
        out.append(f"⚠ {c.token_total} lookalikes exist. Only one is the community's real one; verify before anything.")
    return out


def format_alert(c: Cluster) -> str:
    badge = "🚨 SHOCKING" if c.shocking else "🔥 TRENDING"
    lines = [f"<b>{badge}: {html.escape(c.title)}</b>"]
    if c.summary:
        lines.append(html.escape(c.summary))
    if c.lore and c.lore.lower() != "lore unclear":
        lines.append("🎭 Lore: " + html.escape(c.lore))
    lines += _token_lines(c)
    lines.append("")
    lines.append(f"Score {c.score:.0f}/100" + (f" · viral {c.viral:.0f}/10" if c.viral is not None else "")
                 + (f" · {html.escape(c.category)}" if c.category else ""))
    lines.append("Seen on: " + html.escape(", ".join(sorted(c.sources))))
    if c.reasons:
        lines.append("Why: " + html.escape("; ".join(dict.fromkeys(c.reasons))[:250]))
    if c.url:
        lines.append(f'<a href="{html.escape(c.url, quote=True)}">Open source</a>')
    if config.MODE == "memecoin":
        lines.append("<i>Not financial advice. Most new memecoins fail or are scams: check the contract and lookalikes.</i>")
    return "\n".join(lines)


def send(text: str) -> None:
    r = requests.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=config.HTTP_TIMEOUT,
    )
    r.raise_for_status()


def get_chat_id() -> None:
    """Message your bot once in Telegram, then run `python main.py --get-chat-id`."""
    r = requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates",
                     timeout=config.HTTP_TIMEOUT).json()
    ids = {u["message"]["chat"]["id"] for u in r.get("result", []) if "message" in u}
    print("Your chat id(s):", ids or "none found, send your bot a message first")
