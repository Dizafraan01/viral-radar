from dataclasses import dataclass, field


@dataclass
class Item:
    source: str            # e.g. "google_trends:NG", "weibo", "reddit"
    title: str
    rank: int              # 1 = top of that source's list
    total: int             # size of that source's list
    url: str = ""
    heat: float = 0.0      # traffic / hot score if the source gives one
    velocity: float = 0.0  # growth per hour if computable (Reddit)
    region: str = ""
    lang: str = "en"


@dataclass
class Cluster:
    items: list[Item] = field(default_factory=list)
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    # filled by the LLM step
    summary: str = ""
    title_en: str = ""
    viral: float | None = None
    shocking: bool = False
    category: str = ""
    # memecoin mode
    meme: float | None = None
    lore: str = ""
    tokens: list = field(default_factory=list)
    token_total: int = 0
    tokens_checked: bool = False

    @property
    def title(self) -> str:
        return self.title_en or self.items[0].title

    @property
    def sources(self) -> set[str]:
        return {i.source.split(":")[0] for i in self.items}

    @property
    def url(self) -> str:
        for i in self.items:
            if i.url:
                return i.url
        return ""
