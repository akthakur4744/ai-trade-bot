"""News feed ingestion — RSS feeds from Indian financial news sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

import feedparser
import structlog

logger = structlog.get_logger(__name__)

# Indian financial news RSS feeds
DEFAULT_FEEDS = [
    {
        "name": "MoneyControl",
        "url": "https://www.moneycontrol.com/rss/latestnews.xml",
        "reliability": 0.8,
    },
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "reliability": 0.8,
    },
    {
        "name": "LiveMint",
        "url": "https://www.livemint.com/rss/markets",
        "reliability": 0.75,
    },
    {
        "name": "Business Standard",
        "url": "https://www.business-standard.com/rss/markets-106.rss",
        "reliability": 0.75,
    },
]


@dataclass
class NewsItem:
    """A single news headline with metadata."""

    title: str
    source: str
    url: str = ""
    published: Optional[datetime] = None
    summary: str = ""
    reliability: float = 0.5
    # Populated by the Researcher agent
    affected_symbols: List[str] = field(default_factory=list)
    sentiment: str = ""
    impact_score: float = 0.0


class NewsFeed:
    """Fetches and aggregates news from multiple RSS sources."""

    def __init__(self, feeds: Optional[List[dict]] = None) -> None:
        self._feeds = feeds or DEFAULT_FEEDS
        self._cache: List[NewsItem] = []
        self._last_fetch: Optional[datetime] = None

    def fetch(self, max_age_hours: int = 6) -> List[NewsItem]:
        """Fetch latest headlines from all configured feeds.

        Args:
            max_age_hours: Ignore articles older than this.

        Returns:
            List of NewsItem sorted by recency.
        """
        items: List[NewsItem] = []
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        for feed_config in self._feeds:
            try:
                feed_items = self._parse_feed(feed_config, cutoff)
                items.extend(feed_items)
            except Exception as e:
                logger.warning(
                    "feed_parse_error",
                    source=feed_config["name"],
                    error=str(e),
                )

        # Deduplicate by title similarity
        items = self._deduplicate(items)

        # Sort by recency
        items.sort(key=lambda x: x.published or datetime.min, reverse=True)

        self._cache = items
        self._last_fetch = datetime.utcnow()

        logger.info("news_fetched", count=len(items))
        return items

    def get_cached(self) -> List[NewsItem]:
        """Return cached headlines without re-fetching."""
        return self._cache

    def filter_by_symbol(self, symbol: str) -> List[NewsItem]:
        """Filter cached news for a specific symbol."""
        return [
            item for item in self._cache
            if symbol.upper() in [s.upper() for s in item.affected_symbols]
            or symbol.upper() in item.title.upper()
        ]

    def _parse_feed(self, feed_config: dict, cutoff: datetime) -> List[NewsItem]:
        """Parse a single RSS feed."""
        parsed = feedparser.parse(feed_config["url"])
        items = []

        for entry in parsed.entries:
            # Parse publication date
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6])

            if pub_date and pub_date < cutoff:
                continue

            items.append(
                NewsItem(
                    title=entry.get("title", "").strip(),
                    source=feed_config["name"],
                    url=entry.get("link", ""),
                    published=pub_date,
                    summary=entry.get("summary", "")[:500],
                    reliability=feed_config.get("reliability", 0.5),
                )
            )

        return items

    def _deduplicate(self, items: List[NewsItem]) -> List[NewsItem]:
        """Remove duplicate headlines (exact title match)."""
        seen_titles: set = set()
        unique = []
        for item in items:
            normalized = item.title.lower().strip()
            if normalized not in seen_titles:
                seen_titles.add(normalized)
                unique.append(item)
        return unique
