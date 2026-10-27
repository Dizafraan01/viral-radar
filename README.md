# viral-radar

Watches trending lists across platforms every 15 minutes and sends you a Telegram alert when something is going viral, looks shocking, or is likely to blow up.

## What it watches

| Platform you asked for | What this actually reads | Why |
|---|---|---|
| X (Twitter) | X API trends (optional, needs a paid API token) plus Google Trends and Reddit rising | X has no free trends feed |
| Instagram | Not directly. Covered indirectly by Google Trends and Reddit | Instagram has no public trending API |
| WeChat, Xiaohongshu | Weibo hot search and Baidu hot list | Both are closed apps; scraping them breaks their terms and gets blocked |
| KakaoTalk | Google Trends and Google News for Korea (`KR`) | KakaoTalk is private messaging, so there is nothing public to read |

Topics that show up on several feeds at once get a higher score. The LLM step translates Chinese, Korean and Japanese titles and writes a one-line summary.

## Setup (about 10 minutes)

1. **Create the bot.** In Telegram, message `@BotFather`, send `/newbot`, and copy the token.
2. **Get your chat id.** Send any message to your new bot, then run:
   ```
   pip install -r requirements.txt
   export TELEGRAM_BOT_TOKEN=123:abc
   python main.py --get-chat-id
   ```
3. **Test it.** `export TELEGRAM_CHAT_ID=<id>` then `python main.py --test`. You should get a message.
4. **Optional LLM key.** `ANTHROPIC_API_KEY` enables summaries, translation and virality judgement. Without it the bot still works on rules alone, with raw titles.
5. **Try it offline.** `python main.py --mock --dry-run` prints sample alerts without needing internet.

## Run it for free in the cloud (GitHub Actions)

1. Push this folder to a GitHub repo. Use a **public** repo: scheduled runs are unlimited there. A private repo has 2,000 free minutes a month, which a 15-minute schedule exceeds. For private, change the cron to `*/30`.
2. Repo Settings > Secrets and variables > Actions > add secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `ANTHROPIC_API_KEY`, `X_BEARER_TOKEN`.
3. Optional variables (same page, Variables tab): `ALERT_THRESHOLD`, `GEOS`, `TOPICS`.
4. Actions tab > viral-radar > Run workflow to test, then it runs on its own.

Or run it on any server with cron: `*/15 * * * * cd /path/viral-radar && python main.py`

## Memecoin mode

Set `MODE=memecoin` (a repo variable on GitHub, or an environment variable locally).

1. The usual pipeline finds stories that are spreading.
2. The LLM rates each for **meme potential** (0-10) and writes a one-line lore angle. Tragedies and dry news score low on purpose. This needs `ANTHROPIC_API_KEY`; without it the bot falls back to the plain viral score.
3. For stories that pass, it searches DexScreener (free, no key) for tokens whose name or symbol matches, on Solana, Base, BSC and Ethereum.
4. Your alert says either **no token found yet** (you may be early) or lists the top tokens by liquidity with age, volume, risk flags and chart links, plus a Rugcheck link for Solana tokens.

Settings: `MEME_MIN_SCORE` (default 6), `MEME_MIN_LIQUIDITY` (default $5,000, hides dust pools), `CHAINS`.

Things to know:
- Matching is by name only. A token whose name doesn't reuse the story's words won't be found, and "no token found" never proves none exists.
- Stories often get dozens of lookalike tokens. The alert counts them, but picking the community's real one is on you.
- The risk flags are rough heuristics (thin liquidity, brand-new pool, heavy selling, huge FDV versus liquidity). They don't detect honeypots or hidden mint/ownership tricks. Check the contract yourself.
- Chinese and Korean stories only get a token search if the LLM produced an English title for them.
- This is a monitoring tool, not financial advice. Most new memecoins go to zero or are outright scams.

## Tuning

| Setting | Default | Meaning |
|---|---|---|
| `ALERT_THRESHOLD` | 60 | Lower for more alerts, higher for fewer |
| `GEOS` | NG,US,GB,KR,JP,IN,ZA | Countries for Google Trends/News |
| `TOPICS` | all | e.g. `breaking,entertainment,tech,africa` |
| `MAX_ALERTS_PER_RUN` | 5 | Caps alert floods |
| `REALERT_AFTER_HOURS` | 12 | Same topic is not re-sent sooner unless its score jumps by 15+ |

## How scoring works

Each item scores up to 100: position on its list (up to 35), size of the heat number (up to 25), velocity (up to 20, from Reddit points per hour or from climbing the ranks since the last run), plus up to 24 for appearing on several feeds. The LLM then judges the top candidates for virality and shock value, and filters out routine noise like weather.

## Limits worth knowing

- Unofficial endpoints (Weibo, Baidu, Reddit) can change or block cloud IPs. Each source fails on its own without stopping the run, and the log shows which ones failed.
- "Projected to go viral" is an estimate from early velocity and cross-platform spread. It will miss some and over-flag others.
- Data is only as fast as the schedule: expect alerts within roughly 15-30 minutes of a topic surfacing.
