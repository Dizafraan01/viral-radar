"""All settings come from environment variables so no secrets live in code."""
import os


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


# --- Telegram (required unless --dry-run) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- LLM (optional but recommended: summaries, translation, virality judgement) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")

# --- X API (optional, paid tier needed for the trends endpoint) ---
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")
X_WOEIDS = _list("X_WOEIDS", "1,23424908")  # 1 = worldwide, 23424908 = Nigeria

# --- Where to look ---
# Google Trends / Google News country codes
GEOS = _list("GEOS", "NG,US,GB,KR,JP,IN,ZA")
ENABLE_WEIBO = os.getenv("ENABLE_WEIBO", "1") == "1"      # proxy for WeChat / Xiaohongshu
ENABLE_BAIDU = os.getenv("ENABLE_BAIDU", "1") == "1"      # proxy for WeChat / Xiaohongshu
ENABLE_REDDIT = os.getenv("ENABLE_REDDIT", "1") == "1"    # real velocity data (score per hour)

# --- Alerting ---
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "60"))  # 0-100, lower = more alerts
MAX_ALERTS_PER_RUN = int(os.getenv("MAX_ALERTS_PER_RUN", "5"))
REALERT_AFTER_HOURS = float(os.getenv("REALERT_AFTER_HOURS", "12"))
# Categories you care about. "all" disables filtering (needs the LLM to work otherwise).
TOPICS = [t.lower() for t in _list("TOPICS", "all")]
# e.g. TOPICS=breaking,entertainment,tech,sports,politics,africa

# --- Memecoin mode: MODE=memecoin ---
# Looks for stories with "meme potential", then checks whether tokens already exist behind them.
MODE = os.getenv("MODE", "general")                              # "general" or "memecoin"
MEME_MIN_SCORE = float(os.getenv("MEME_MIN_SCORE", "6"))         # LLM meme-potential, 0-10
MEME_MIN_LIQUIDITY = float(os.getenv("MEME_MIN_LIQUIDITY", "5000"))  # USD; ignore dust pools
CHAINS = _list("CHAINS", "solana,base,bsc,ethereum")

STATE_FILE = os.getenv("STATE_FILE", "state.json")
HTTP_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; viral-radar/1.0)"
