"""Collectors. Each returns a list[Item] and never raises: one dead source must not stop a run."""
import re
import time
import logging
import requests

import config
from models import Item

log = logging.getLogger("sources")
HEADERS = {"User-Agent": config.USER_AGENT}


def _get(url, **kw):
    kw.setdefault("timeout", config.HTTP_TIMEOUT)
    kw.setdefault("headers", HEADERS)
    r = requests.get(url, **kw)
    r.raise_for_status()
    return r


def _num(s) -> float:
    """'200K+' -> 200000, '2M+' -> 2000000, '5,000+' -> 5000."""
    if not s:
        return 0.0
    s = str(s).upper().replace(",", "").replace("+", "").strip()
    m = re.match(r"([\d.]+)\s*([KMB]?)", s)
    if not m:
        return 0.0
    mult = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]
    return float(m.group(1)) * mult


def google_trends(geo: str) -> list[Item]:
    import feedparser
    feed = feedparser.parse(f"https://trends.google.com/trending/rss?geo={geo}")
    entries = feed.entries[:25]
    out = []
    for i, e in enumerate(entries, 1):
        out.append(Item(
            source=f"google_trends:{geo}", title=e.title, rank=i, total=len(entries),
            heat=_num(e.get("ht_approx_traffic")),
            url=e.get("link", ""), region=geo,
        ))
    return out


def google_news(geo: str) -> list[Item]:
    import feedparser
    lang = {"KR": "ko", "JP": "ja"}.get(geo, "en")
    url = f"https://news.google.com/rss?hl={lang}-{geo}&gl={geo}&ceid={geo}:{lang}"
    feed = feedparser.parse(url)
    entries = feed.entries[:15]
    return [Item(source=f"google_news:{geo}", title=e.title, rank=i, total=len(entries),
                 url=e.get("link", ""), region=geo, lang=lang)
            for i, e in enumerate(entries, 1)]


def weibo() -> list[Item]:
    data = _get("https://weibo.com/ajax/side/hotSearch").json()
    rows = data["data"]["realtime"][:25]
    return [Item(source="weibo", title=r["word"], rank=i, total=len(rows),
                 heat=float(r.get("num", 0)), lang="zh", region="CN",
                 url="https://s.weibo.com/weibo?q=%23" + requests.utils.quote(r["word"]) + "%23")
            for i, r in enumerate(rows, 1)]


def baidu() -> list[Item]:
    data = _get("https://top.baidu.com/api/board?platform=wise&tab=realtime").json()
    cards = data["data"]["cards"]
    content = cards[0]["content"]
    if content and isinstance(content[0], dict) and "content" in content[0]:  # nested layout
        content = content[0]["content"]
    content = content[:25]
    return [Item(source="baidu", title=r.get("word") or r.get("query", ""), rank=i, total=len(content),
                 heat=float(r.get("hotScore", 0) or 0), lang="zh", region="CN",
                 url=r.get("url") or r.get("rawUrl", ""))
            for i, r in enumerate(content, 1)]


def reddit() -> list[Item]:
    """Reddit gives real score + age, so we get a true velocity (points per hour)."""
    data = _get("https://www.reddit.com/r/all/rising.json?limit=25").json()
    posts = [c["data"] for c in data["data"]["children"]]
    now = time.time()
    out = []
    for i, p in enumerate(posts, 1):
        age_h = max((now - p["created_utc"]) / 3600, 0.25)
        heat = p["score"] + 3 * p["num_comments"]
        out.append(Item(source="reddit", title=p["title"], rank=i, total=len(posts),
                        heat=heat, velocity=heat / age_h,
                        url="https://reddit.com" + p["permalink"]))
    return out


def x_trends(woeid: str) -> list[Item]:
    r = _get(f"https://api.x.com/2/trends/by/woeid/{woeid}",
             headers={**HEADERS, "Authorization": f"Bearer {config.X_BEARER_TOKEN}"})
    rows = r.json().get("data", [])[:25]
    return [Item(source=f"x:{woeid}", title=t["trend_name"], rank=i, total=len(rows),
                 heat=float(t.get("tweet_count", 0) or 0), region=woeid,
                 url="https://x.com/search?q=" + requests.utils.quote(t["trend_name"]))
            for i, t in enumerate(rows, 1)]


def collect_all() -> list[Item]:
    jobs = []
    for g in config.GEOS:
        jobs += [(f"google_trends:{g}", lambda g=g: google_trends(g)),
                 (f"google_news:{g}", lambda g=g: google_news(g))]
    if config.ENABLE_WEIBO:
        jobs.append(("weibo", weibo))
    if config.ENABLE_BAIDU:
        jobs.append(("baidu", baidu))
    if config.ENABLE_REDDIT:
        jobs.append(("reddit", reddit))
    if config.X_BEARER_TOKEN:
        jobs += [(f"x:{w}", lambda w=w: x_trends(w)) for w in config.X_WOEIDS]

    items, ok, failed = [], 0, []
    for name, fn in jobs:
        try:
            got = fn()
            items += got
            ok += 1
            log.info("%-22s %d items", name, len(got))
        except Exception as e:  # noqa: BLE001
            failed.append(name)
            log.warning("%-22s FAILED: %s", name, e)
    log.info("sources ok=%d failed=%d %s", ok, len(failed), failed)
    return items


def mock_items() -> list[Item]:
    """Offline fixtures for testing the pipeline end to end."""
    return [
        Item("google_trends:NG", "Lagos flood", 1, 10, heat=500_000, region="NG", url="https://example.com/a"),
        Item("google_trends:US", "Lagos flood", 4, 10, heat=100_000, region="US"),
        Item("reddit", "Massive flood hits Lagos, thousands stranded", 2, 25, heat=40_000, velocity=9_000,
             url="https://reddit.com/r/x"),
        Item("weibo", "拉各斯洪水", 3, 25, heat=2_300_000, lang="zh", region="CN"),
        Item("baidu", "某明星官宣结婚", 1, 25, heat=7_800_000, lang="zh", region="CN"),
        Item("google_trends:KR", "아이돌 컴백 발표", 2, 10, heat=200_000, lang="ko", region="KR"),
        Item("google_news:GB", "Local council approves new bus lanes", 9, 15, region="GB"),
        Item("google_trends:NG", "Weather tomorrow", 9, 10, heat=2_000, region="NG"),
    ]
