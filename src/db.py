"""
Supabase 資料庫互動模組 (src/db.py)
負責 URL SHA-256 去重比對、寫入推播紀錄、查詢近期文章以及過期清理。
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from src.config import config

logger = logging.getLogger(__name__)

# Supabase 客戶端單例
_supabase_client = None


def get_url_hash(url: str) -> str:
    """計算 URL 的標準化 SHA-256 雜湊值 (移除前後空格並轉小寫)"""
    normalized_url = url.strip().lower()
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def get_supabase_client():
    """延遲初始化 Supabase 客戶端"""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not config.supabase_url or not config.supabase_key:
        logger.warning("未偵測到完整的 SUPABASE_URL 或 SUPABASE_KEY，將無法持久化儲存")
        return None

    try:
        from supabase import create_client, Client
        _supabase_client = create_client(config.supabase_url, config.supabase_key)
        return _supabase_client
    except Exception as e:
        logger.error(f"初始化 Supabase 客戶端失敗: {e}")
        return None


def is_article_processed(url_hash: str) -> bool:
    """
    檢查指定 URL Hash 是否已經存在於 processed_articles 資料表中。
    若資料庫未連線，預設回傳 False (允許後續處理)。
    """
    client = get_supabase_client()
    if not client:
        return False

    try:
        response = (
            client.table("processed_articles")
            .select("id")
            .eq("url_hash", url_hash)
            .limit(1)
            .execute()
        )
        return bool(response.data and len(response.data) > 0)
    except Exception as e:
        logger.warning(f"查詢文章去重狀態失敗 (url_hash: {url_hash}): {e}")
        return False


def record_article(article_dict: Dict[str, Any]) -> bool:
    """
    將已推播的文章記錄存入 processed_articles 資料表。
    article_dict 應包含:
    - url_hash (若無則自動由 url 產生)
    - title
    - source
    - published_at (選填)
    - category (選填)
    - summary_markdown (選填)
    """
    client = get_supabase_client()
    if not client:
        return False

    url_hash = article_dict.get("url_hash")
    if not url_hash and "url" in article_dict:
        url_hash = get_url_hash(article_dict["url"])

    if not url_hash:
        logger.error("寫入文章紀錄失敗: 缺少 url 或 url_hash")
        return False

    payload = {
        "url_hash": url_hash,
        "title": article_dict.get("title", ""),
        "source": article_dict.get("source", "未知來源"),
        "category": article_dict.get("category", "general"),
        "summary_markdown": article_dict.get("summary_markdown", ""),
    }

    if "published_at" in article_dict and article_dict["published_at"]:
        payload["published_at"] = str(article_dict["published_at"])

    try:
        response = client.table("processed_articles").insert(payload).execute()
        logger.info(f"成功記錄已處理文章: {payload['title'][:30]}")
        return True
    except Exception as e:
        logger.error(f"寫入文章紀錄至 Supabase 失敗: {e}")
        return False


def get_recent_articles(days: int = 7) -> List[Dict[str, Any]]:
    """
    撈取過去 N 天內記錄的文章，用於週末產業週報 (Weekly Deep-dive) 的跨事件宏觀歸納。
    """
    client = get_supabase_client()
    if not client:
        return []

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        response = (
            client.table("processed_articles")
            .select("title, source, published_at, category, summary_markdown, created_at")
            .gte("created_at", cutoff_date)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        return response.data or []
    except Exception as e:
        logger.error(f"撈取近 {days} 天歷史文章失敗: {e}")
        return []


def prune_old_records(days: int = 30) -> int:
    """
    定時清理超過 N 天以前的舊記錄，避免資料庫累積過多無效歷史。
    回傳已清理筆數（若 API 支援回傳）。
    """
    client = get_supabase_client()
    if not client:
        return 0

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        response = (
            client.table("processed_articles")
            .delete()
            .lt("created_at", cutoff_date)
            .execute()
        )
        logger.info(f"已清理 {cutoff_date} 之前的過期文章記錄")
        return len(response.data) if response.data else 0
    except Exception as e:
        logger.warning(f"清理舊文章記錄失敗: {e}")
        return 0
