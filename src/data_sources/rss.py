"""
RSS 新聞擷取模組 (src/data_sources/rss.py)
使用 feedparser 批次抓取國際與台灣科技/財經 RSS，並正規化資料結構。
"""

import logging
from datetime import datetime, timezone
import email.utils
from typing import Any, Dict, List
import feedparser
from src.config import config

logger = logging.getLogger(__name__)


def parse_published_time(entry: Any) -> str:
    """嘗試解析 RSS 項目的發布時間為 ISO 8601 格式字串"""
    for field in ["published_parsed", "updated_parsed"]:
        time_struct = getattr(entry, field, None)
        if time_struct:
            try:
                dt = datetime(*time_struct[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass

    for field in ["published", "pubDate", "updated"]:
        raw_val = getattr(entry, field, None)
        if raw_val and isinstance(raw_val, str):
            try:
                dt = email.utils.parsedate_to_datetime(raw_val)
                return dt.isoformat()
            except Exception:
                pass

    return datetime.now(timezone.utc).isoformat()


def fetch_feed_entries(feed_info: Dict[str, str], max_entries: int = 15) -> List[Dict[str, Any]]:
    """
    抓取單一 RSS Feed 並標準化回傳項目列表。
    """
    feed_name = feed_info.get("name", "未命名來源")
    feed_url = feed_info.get("url", "")
    category = feed_info.get("category", "general")

    if not feed_url:
        return []

    articles = []
    try:
        # feedparser 支援直接傳入 URL
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            logger.warning(f"RSS 解析異常 ({feed_name}): {feed.bozo_exception}")
            return []

        for entry in feed.entries[:max_entries]:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            summary = summary.strip()
            published_at = parse_published_time(entry)

            if not title or not link:
                continue

            articles.append({
                "title": title,
                "link": link,
                "summary": summary,
                "source": feed_name,
                "category": category,
                "published_at": published_at,
            })
    except Exception as e:
        logger.error(f"抓取 RSS 來源失敗 ({feed_name} - {feed_url}): {e}")

    return articles


def fetch_all_rss_articles(max_per_feed: int = 10) -> List[Dict[str, Any]]:
    """
    依序抓取 config.yaml 中所有宣告的 RSS 來源並合併回傳。
    """
    all_articles = []
    for feed_info in config.rss_feeds:
        entries = fetch_feed_entries(feed_info, max_entries=max_per_feed)
        all_articles.extend(entries)

    logger.info(f"成功從 {len(config.rss_feeds)} 個 RSS 來源擷取共 {len(all_articles)} 則文章")
    return all_articles
