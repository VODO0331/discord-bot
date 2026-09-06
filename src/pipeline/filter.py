"""
規則過濾模組 (src/pipeline/filter.py)
實作雙階段過濾之第一階段：
1. 關鍵詞與實體匹配（零 Token 消耗）
2. 批次內候選文章標題字元 Jaccard 相似度去重
"""

import logging
import re
from typing import Any, Dict, List, Set, Tuple
from src.config import config

from datetime import datetime, timezone, timedelta
import dateutil.parser

logger = logging.getLogger(__name__)


def is_article_fresh(article: Dict[str, Any], max_age_hours: int = 24) -> bool:
    """
    檢查文章發布時間是否在指定時限內 (預設 24 小時內)。
    超過時限的陳舊新聞直接排除，避免發送過期歷史快訊。
    """
    pub_str = article.get("published_at")
    if not pub_str:
        return True

    try:
        pub_dt = dateutil.parser.isoparse(pub_str)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        age = now - pub_dt
        if age > timedelta(hours=max_age_hours):
            logger.info(f"⏳ 排除過期新聞 (發布於 {pub_dt.strftime('%Y-%m-%d %H:%M')}, 距今 {age.total_seconds() / 3600:.1f} 小時): {article.get('title', '')[:35]}")
            return False
        return True
    except Exception as e:
        logger.warning(f"解析文章時間失敗 ({pub_str}): {e}")
        return True


def extract_bigrams(text: str) -> Set[str]:
    """將文字分割為 2-gram 集合以進行字元級 Jaccard 相似度計算"""
    cleaned = re.sub(r"[^\w]", "", text.lower())
    if len(cleaned) < 2:
        return set(cleaned)
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def calculate_title_similarity(title_a: str, title_b: str) -> float:
    """計算兩篇標題的 Jaccard 相似度 (0.0 ~ 1.0)"""
    bigrams_a = extract_bigrams(title_a)
    bigrams_b = extract_bigrams(title_b)
    if not bigrams_a or not bigrams_b:
        return 0.0
    intersection = bigrams_a.intersection(bigrams_b)
    union = bigrams_a.union(bigrams_b)
    return len(intersection) / len(union)


def stage_one_filter(article: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    第一階段規則過濾（零 Token 消耗）。
    條件：
    1. 發布時間必須在時效內 (預設 24 小時內，杜絕陳舊歷史新聞)
    2. 命中至少一個實體關鍵字 (entities)
    3. 命中至少一個重大動作詞 (actions)
    
    回傳: (是否通過, 命中的標籤列表)
    """
    # 1. 時效性過濾
    if not is_article_fresh(article, max_age_hours=config.alert_max_age_hours):
        return False, []

    title = article.get("title", "")
    summary = article.get("summary", "")
    content = f"{title} {summary}".lower()

    matched_entities = [
        ent for ent in config.alert_entities if ent.lower() in content
    ]
    matched_actions = [
        act for act in config.alert_actions if act.lower() in content
    ]

    # 必須同時具備追蹤實體與重大動作詞
    is_passed = bool(matched_entities and matched_actions)
    matched_tags = list(set(matched_entities + matched_actions))

    if is_passed:
        logger.debug(f"文章通過第一階段過濾 [{title[:25]}...] 命中: {matched_tags}")
    return is_passed, matched_tags


def deduplicate_batch_articles(articles: List[Dict[str, Any]], similarity_threshold: float = 0.65) -> List[Dict[str, Any]]:
    """
    批次內新聞標題相似度比對。
    若同一批抓取有多家媒體報導同一事件，僅保留內文長度較長或首發的報導。
    """
    unique_articles: List[Dict[str, Any]] = []

    for candidate in articles:
        cand_title = candidate.get("title", "")
        is_duplicate = False

        for existing in unique_articles:
            exist_title = existing.get("title", "")
            sim = calculate_title_similarity(cand_title, exist_title)
            if sim >= similarity_threshold:
                is_duplicate = True
                logger.info(f"偵測到重複報導 (相似度 {sim:.2f}): '{cand_title}' 與 '{exist_title}'，保留前者")
                break

        if not is_duplicate:
            unique_articles.append(candidate)

    return unique_articles
