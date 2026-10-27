"""One batched LLM call: translate, summarise, categorise and judge virality."""
import json
import logging
import re

import config
from models import Cluster

log = logging.getLogger("llm")

PROMPT = """You are a viral-news analyst. For each numbered topic below (titles may be Chinese, Korean or Japanese),
return a JSON array, one object per topic, in the same order, with:
- "i": the topic number
- "title_en": short English headline (translate if needed)
- "summary": one plain sentence (max 30 words) saying what is happening and why people care.
   If you are not sure what the topic is, say so; do not invent details.
- "category": one of breaking, entertainment, tech, sports, politics, business, africa, social, other
- "viral": 0-10, how likely this is to keep spreading widely in the next 24 hours
- "shocking": true only for genuinely shocking or high-impact news (disasters, deaths of major figures, major scandals)
- "noise": true if it is routine (weather, scores, generic evergreen searches)
{extra}Return ONLY the JSON array.

Topics:
{topics}
"""

MEME_EXTRA = """- "meme_potential": 0-10, how likely crypto traders would build a memecoin narrative around this.
   Absurd, funny, tribal, animal, celebrity, catchphrase and underdog stories score high; tragedies,
   hard news and dry policy score low.
- "lore": one sentence on the story angle a memecoin community would rally around. Use only facts from the
   topic text or that you reliably know; if you don't recognise it, write "lore unclear".
"""


def enrich(clusters: list[Cluster]) -> bool:
    """Fills LLM fields in place. Returns False if the LLM was unavailable."""
    if not config.ANTHROPIC_API_KEY or not clusters:
        return False
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        lines = []
        for n, c in enumerate(clusters, 1):
            titles = " | ".join(dict.fromkeys(i.title for i in c.items))[:300]
            lines.append(f"{n}. {titles}  [feeds: {', '.join(sorted(c.sources))}; signals: {'; '.join(c.reasons[:3])}]")
        msg = client.messages.create(
            model=config.LLM_MODEL, max_tokens=4000,
            messages=[{"role": "user", "content": PROMPT.format(
                topics="\n".join(lines),
                extra=MEME_EXTRA if config.MODE == "memecoin" else "")}],
        )
        text = msg.content[0].text
        rows = json.loads(re.search(r"\[.*\]", text, re.S).group(0))
        for r in rows:
            c = clusters[int(r["i"]) - 1]
            c.title_en = r.get("title_en", "")
            c.summary = r.get("summary", "")
            c.category = str(r.get("category", "other")).lower()
            c.viral = float(r.get("viral", 0))
            c.shocking = bool(r.get("shocking", False))
            if "meme_potential" in r:
                c.meme = float(r["meme_potential"])
                c.lore = r.get("lore", "")
            if r.get("noise"):
                c.viral = min(c.viral or 0, 2)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("LLM step failed, falling back to rules only: %s", e)
        return False
