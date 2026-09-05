"""
新聞內文萃取模組 (src/data_sources/extractor.py)
整合 trafilatura 進行正文萃取，並實作優雅降級回退至 RSS 摘要。
"""

import html
import logging
import re
from typing import Dict, Optional
import trafilatura
from src.config import config

logger = logging.getLogger(__name__)


def clean_html(text: str) -> str:
    """清理文字中的 HTML 標籤與特殊字元"""
    if not text:
        return ""
    # 去除 HTML tag
    clean = re.sub(r"<[^>]+>", "", text)
    # 解碼 HTML entities
    clean = html.unescape(clean)
    # 壓縮多餘空白
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def extract_article_content(article: Dict[str, str], max_length: int = 3000) -> str:
    """
    自文章連結抓取新聞完整純文字內文。
    若抓取失敗或提取結果為空，自動降級使用 RSS 提供的 summary 欄位。
    """
    url = article.get("link", "")
    fallback_text = clean_html(article.get("summary", ""))

    if not url:
        return fallback_text

    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted_text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_recall=True,
            )
            if extracted_text and len(extracted_text.strip()) > 50:
                full_text = extracted_text.strip()
                # 控制送入 LLM 的文本長度以節省 Token
                return full_text[:max_length]
    except Exception as e:
        logger.warning(f"使用 trafilatura 擷取 {url} 失敗: {e}，將降級回退使用 RSS 摘要")

    # 降級使用 RSS 摘要
    logger.debug(f"文章 {url} 採用 RSS 摘要降級")
    return fallback_text[:max_length]
