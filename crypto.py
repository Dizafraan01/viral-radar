"""Memecoin layer: given a viral story, look for tokens already launched behind it.

Uses DexScreener's free search API (no key). It matches on token name/symbol, so it will
miss tokens whose names don't reuse the story's keywords.
"""
import logging
import math
import re
import time

import requests

import config
from models import Cluster

log = logging.getLogger("crypto")

STOP = {"the", "and", "for", "with", "from", "that", "this", "after", "over", "into", "about", "new",
        "says", "said", "amid", "its", "are", "was", "has", "have", "will", "what", "how", "why", "who",
        "his", "her", "their", "than", "more", "most", "live", "news", "update", "video", "watch"}
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOP]


def keywords_for(c: Cluster) -> list[str]:
    """Up to 3 keywords from the cleanest Latin-script headline (LLM English title if we have one)."""
    base = c.title_en
    if not base:
        latin = [i.title for i in c.items if re.search(r"[A-Za-z]", i.title) and not _CJK.search(i.title)]
        base = min(latin, key=len) if latin else ""
    return _words(base)[:3]


def _search(query: str) -> list[dict]:
    r = requests.get("https://api.dexscreener.com/latest/dex/search", params={"q": query},
                     headers={"User-Agent": config.USER_AGENT}, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json().get("pairs") or []


def _matches(pair: dict, kws: list[str]) -> bool:
    b = pair.get("baseToken") or {}
    hay = re.sub(r"[^a-z0-9]", "", (b.get("name", "") + b.get("symbol", "")).lower())
    need = max(1, math.ceil(len(kws) * 0.6))
    return sum(1 for k in kws if k in hay) >= need


def _summarise(p: dict) -> dict:
    liq = (p.get("liquidity") or {}).get("usd") or 0
    vol = (p.get("volume") or {}).get("h24") or 0
    fdv = p.get("fdv") or 0
    created = p.get("pairCreatedAt")
    age_h = (time.time() * 1000 - created) / 3.6e6 if created else None
    tx = (p.get("txns") or {}).get("h24") or {}
    buys, sells = tx.get("buys", 0), tx.get("sells", 0)

    flags = []
    if liq < 10_000:
        flags.append("thin liquidity")
    if age_h is not None and age_h < 1:
        flags.append("under 1h old")
    if sells > 2 * max(buys, 1):
        flags.append("heavy selling")
    if liq and fdv / liq > 200:
        flags.append(f"FDV {fdv / liq:.0f}x liquidity (hard to exit)")
    b = p.get("baseToken") or {}
    return {
        "symbol": b.get("symbol", "?"), "name": b.get("name", "?"), "address": b.get("address", ""),
        "chain": p.get("chainId", "?"), "url": p.get("url", ""), "liq": liq, "vol": vol, "fdv": fdv,
        "age_h": age_h, "chg24": (p.get("priceChange") or {}).get("h24"), "flags": flags,
    }


def attach_tokens(clusters: list[Cluster], mock: bool = False) -> None:
    for c in clusters:
        kws = keywords_for(c)
        if not kws:
            continue  # e.g. a Chinese headline with no English title: can't search by name
        try:
            pairs = mock_pairs() if mock else _search(" ".join(kws))
        except Exception as e:  # noqa: BLE001
            log.warning("DexScreener search failed for %r: %s", kws, e)
            continue
        matched = [p for p in pairs if p.get("chainId") in config.CHAINS and _matches(p, kws)]
        best: dict[str, dict] = {}
        for p in matched:  # one entry per token, keep its deepest pool
            addr = (p.get("baseToken") or {}).get("address", "")
            liq = (p.get("liquidity") or {}).get("usd") or 0
            if addr not in best or liq > ((best[addr].get("liquidity") or {}).get("usd") or 0):
                best[addr] = p
        good = [_summarise(p) for p in best.values()
                if ((p.get("liquidity") or {}).get("usd") or 0) >= config.MEME_MIN_LIQUIDITY]
        c.tokens = sorted(good, key=lambda t: -t["liq"])[:3]
        c.token_total = len(best)
        c.tokens_checked = True


def mock_pairs() -> list[dict]:
    now = time.time() * 1000
    mk = lambda name, sym, chain, liq, vol, fdv, age_h, buys, sells: {  # noqa: E731
        "chainId": chain, "url": f"https://dexscreener.com/{chain}/{sym.lower()}",
        "baseToken": {"address": f"addr_{sym}", "name": name, "symbol": sym},
        "liquidity": {"usd": liq}, "volume": {"h24": vol}, "fdv": fdv,
        "pairCreatedAt": now - age_h * 3.6e6, "priceChange": {"h24": 180.0},
        "txns": {"h24": {"buys": buys, "sells": sells}},
    }
    return [
        mk("Lagos Flood", "FLOOD", "solana", 42_000, 310_000, 900_000, 3, 1200, 800),
        mk("Flood Lagos Inu", "FLINU", "base", 6_500, 20_000, 2_000_000, 0.5, 90, 300),
        mk("Lagos Flood Coin", "LFC", "bsc", 2_000, 1_500, 50_000, 20, 10, 12),
        mk("Unrelated Token", "UNREL", "solana", 90_000, 1_000_000, 5_000_000, 100, 500, 400),
    ]
