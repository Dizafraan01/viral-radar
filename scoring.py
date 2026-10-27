"""Turns raw trending lists into scored clusters.

Score (0-100) = best single-item score + cross-platform spread bonus.
Item score = rank position (0-35) + heat (0-25) + velocity (0-20).
Velocity comes from Reddit's points/hour, or from how fast a topic climbed
compared with the previous run (state.json).
"""
import math
import re
import time

from models import Item, Cluster

_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def _tokens(title: str) -> set[str]:
    t = re.sub(r"[^\w\s]", " ", title.lower())
    if _CJK.search(t):
        chars = re.sub(r"\s+", "", t)
        return {chars[i:i + 2] for i in range(len(chars) - 1)} or {chars}
    return {w for w in t.split() if len(w) > 2}


def _similar(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    if inter / len(a | b) >= 0.5:
        return True
    # short headline fully contained in a longer one ("Lagos flood" vs "Massive flood hits Lagos...")
    return min(len(a), len(b)) >= 2 and inter / min(len(a), len(b)) >= 0.99


def key_of(title: str) -> str:
    return re.sub(r"\W+", "", title.lower())[:80]


def item_score(it: Item, prev: dict | None) -> tuple[float, list[str]]:
    reasons = []
    rank_pts = 35 * (1 - (it.rank - 1) / max(it.total, 1))
    heat_pts = min(25, 5 * math.log10(it.heat + 1)) if it.heat else 0
    vel_pts = 0.0
    if it.velocity:
        vel_pts = min(20, 6 * math.log10(it.velocity + 1))
        reasons.append(f"{int(it.velocity):,} pts/hour on Reddit")
    if prev is None and it.rank <= 10:
        vel_pts = max(vel_pts, 15)
        reasons.append(f"new at #{it.rank} on {it.source}")
    elif prev is not None:
        climb = prev["rank"] - it.rank
        if climb >= 5:
            vel_pts = max(vel_pts, min(15, climb))
            reasons.append(f"climbed {climb} places on {it.source}")
    if it.heat >= 100_000:
        reasons.append(f"{int(it.heat):,} searches/mentions on {it.source}")
    return rank_pts + heat_pts + vel_pts, reasons


def build_clusters(items: list[Item], state: dict) -> list[Cluster]:
    seen = state.get("seen", {})
    scored = []
    for it in items:
        prev = seen.get(f"{it.source}|{key_of(it.title)}")
        s, why = item_score(it, prev)
        scored.append((s, why, it))
    scored.sort(key=lambda x: -x[0])

    clusters: list[tuple[Cluster, set[str]]] = []
    for s, why, it in scored:
        toks = _tokens(it.title)
        for c, ctoks in clusters:
            if _similar(toks, ctoks):
                c.items.append(it)
                c.reasons += why
                ctoks |= toks
                break
        else:
            c = Cluster(items=[it], score=s, reasons=list(why))
            clusters.append((c, set(toks)))

    out = []
    for c, _ in clusters:
        best = max(item_score(i, seen.get(f"{i.source}|{key_of(i.title)}"))[0] for i in c.items)
        n_src = len({i.source.split(":")[0] + ":" + i.region for i in c.items})
        spread = min(24, 12 * (n_src - 1))
        if spread:
            c.reasons.append(f"showing up in {n_src} different feeds")
        c.score = min(100.0, best + spread)
        out.append(c)
    return sorted(out, key=lambda c: -c.score)


def update_state(state: dict, items: list[Item]) -> None:
    now = time.time()
    seen = state.setdefault("seen", {})
    for it in items:
        seen[f"{it.source}|{key_of(it.title)}"] = {"rank": it.rank, "ts": now}
    # forget anything older than 3 days
    state["seen"] = {k: v for k, v in seen.items() if now - v["ts"] < 3 * 86400}
    alerted = state.setdefault("alerted", {})
    state["alerted"] = {k: v for k, v in alerted.items() if now - v["ts"] < 3 * 86400}
