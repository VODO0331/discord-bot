#!/usr/bin/env python3
"""
Discord 市場與產業資訊自動推播系統主入口 (main.py)
支援 CLI 模式切換與本機 --dry-run 偵錯。
"""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List

from src.config import config
from src.data_sources.extractor import extract_article_content
from src.data_sources.market import get_morning_market_data, get_wrap_market_data
from src.data_sources.rss import fetch_all_rss_articles
from src.db import (
    get_recent_articles,
    get_url_hash,
    is_article_processed,
    prune_old_records,
    record_article,
)
from src.delivery.webhook import dispatch_webhook
from src.pipeline.filter import deduplicate_batch_articles, stage_one_filter
from src.pipeline.formatter import (
    format_alert_embed,
    format_morning_embed,
    format_weekly_embed,
    format_wrap_embed,
)
from src.pipeline.summarizer import (
    summarize_alert,
    summarize_morning,
    summarize_weekly,
    summarize_wrap,
)

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def handle_alert_mode(dry_run: bool = False):
    """處理突發快訊模式 (Breaking Alert)"""
    logger.info(">>> 啟動模式: 突發快訊掃描 (alert) <<<")

    # 1. 抓取 RSS 來源最新文章
    raw_articles = fetch_all_rss_articles(max_per_feed=10)
    if not raw_articles:
        logger.info("未抓取到任何 RSS 新聞，結束流程")
        return

    # 2. 第一階段規則過濾（零 Token 消耗）
    matched_candidates: List[Dict[str, Any]] = []
    for art in raw_articles:
        passed, tags = stage_one_filter(art)
        if passed:
            art["matched_tags"] = tags
            matched_candidates.append(art)

    logger.info(f"第一階段過濾完成，共有 {len(matched_candidates)} 篇候選文章命中規則")
    if not matched_candidates:
        logger.info("無任何文章命中重大實體與事件關鍵字，略過後續處理")
        return

    # 3. 批次內標題去重
    deduped_candidates = deduplicate_batch_articles(matched_candidates)

    # 4. 逐篇比對 Supabase 資料庫 URL 去重，並進行 AI 提煉
    alerts_dispatched = 0
    for article in deduped_candidates:
        url = article["link"]
        url_hash = get_url_hash(url)

        # 比對資料庫去重
        if not dry_run and is_article_processed(url_hash):
            logger.info(f"文章已推播過，略過: {article['title'][:30]}")
            continue

        # 5. 抓取正文內文（具備降級機制）
        full_content = extract_article_content(article)

        # 6. Gemini Flash 提煉與評分
        summary_result = summarize_alert(article["title"], full_content)
        score = summary_result.get("significance_score", 0)
        logger.info(f"文章評估完成: [{article['title'][:25]}] -> 震撼度: {score}/5")

        # 7. 門檻過濾 (>= alert_min_score)
        if score < config.alert_min_score:
            logger.info(f"震撼度評分未達門檻 ({score} < {config.alert_min_score})，不予推播")
            continue

        # 8. 卡片排版
        payload = format_alert_embed(article, summary_result, article.get("matched_tags", []))

        if dry_run:
            print("\n" + "=" * 30 + " [DRY-RUN ALERT EMBED PAYLOAD] " + "=" * 30)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            print("=" * 80 + "\n")
        else:
            # 9. 發送 Webhook
            success = dispatch_webhook(payload, mode="alert")
            if success:
                article_record = {
                    "url_hash": url_hash,
                    "title": article["title"],
                    "source": article["source"],
                    "published_at": article.get("published_at"),
                    "category": article.get("category", "alert"),
                    "summary_markdown": summary_result.get("core_event", ""),
                }
                record_article(article_record)
                alerts_dispatched += 1

    logger.info(f"突發快訊處理完成，共發送/產出 {alerts_dispatched} 則快訊")


def handle_morning_mode(dry_run: bool = False):
    """處理開盤晨報模式 (Morning Brief)"""
    logger.info(">>> 啟動模式: 開盤晨報 (morning) <<<")

    # 1. 抓取行情數據
    market_data = get_morning_market_data()

    # 2. 抓取最新精選焦點新聞
    raw_articles = fetch_all_rss_articles(max_per_feed=5)
    # 取前 5 則去重後的焦點新聞
    top_articles = deduplicate_batch_articles(raw_articles)[:5]

    # 3. AI 晨報重點提煉
    ai_summary = summarize_morning(market_data, top_articles)

    # 4. 卡片排版
    payload = format_morning_embed(market_data, ai_summary)

    if dry_run:
        print("\n" + "=" * 30 + " [DRY-RUN MORNING EMBED PAYLOAD] " + "=" * 30)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("=" * 80 + "\n")
    else:
        success = dispatch_webhook(payload, mode="morning")
        if not success:
            logger.error("開盤晨報派發失敗！請檢查 Webhook 設定。")
            sys.exit(1)

    logger.info("開盤晨報處理完成")


def handle_wrap_mode(dry_run: bool = False):
    """處理盤後綜述模式 (Market Wrap)"""
    logger.info(">>> 啟動模式: 盤後綜述 (wrap) <<<")

    # 1. 抓取台股行情與焦點股票
    market_data = get_wrap_market_data()

    # 2. 抓取今日焦點新聞
    raw_articles = fetch_all_rss_articles(max_per_feed=5)
    top_articles = deduplicate_batch_articles(raw_articles)[:5]

    # 3. AI 盤後與晚間前瞻提煉
    ai_summary = summarize_wrap(market_data, top_articles)

    # 4. 卡片排版
    payload = format_wrap_embed(market_data, ai_summary)

    if dry_run:
        print("\n" + "=" * 30 + " [DRY-RUN WRAP EMBED PAYLOAD] " + "=" * 30)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("=" * 80 + "\n")
    else:
        success = dispatch_webhook(payload, mode="wrap")
        if not success:
            logger.error("盤後綜述派發失敗！請檢查 Webhook 設定。")
            sys.exit(1)

    logger.info("盤後綜述處理完成")


def handle_weekly_mode(dry_run: bool = False):
    """處理週末產業週報模式 (Weekly Deep-dive)"""
    logger.info(">>> 啟動模式: 週末產業週報 (weekly) <<<")

    # 1. 自 Supabase 撈取過去 7 天記錄
    recent_articles = get_recent_articles(days=7)
    
    # 若為 dry-run 或資料庫無資料時提供模擬新聞清單進行測試
    if not recent_articles:
        logger.info("資料庫近 7 天無紀錄，使用即時 RSS 文章作為週報素材")
        rss_articles = fetch_all_rss_articles(max_per_feed=5)
        recent_articles = [
            {
                "title": a["title"],
                "source": a["source"],
                "summary_markdown": a["summary"][:100],
                "link": a["link"],
            }
            for a in rss_articles[:10]
        ]

    # 2. AI 跨事件宏觀歸納提煉
    ai_summary = summarize_weekly(recent_articles)

    # 3. 卡片排版
    payload = format_weekly_embed(ai_summary, recent_articles)

    if dry_run:
        print("\n" + "=" * 30 + " [DRY-RUN WEEKLY EMBED PAYLOAD] " + "=" * 30)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("=" * 80 + "\n")
    else:
        success = dispatch_webhook(payload, mode="weekly")
        if not success:
            logger.error("週末產業週報派發失敗！請檢查 Webhook 設定。")
            sys.exit(1)
        # 清理 30 天以前的過期記錄
        prune_old_records(days=30)

    logger.info("週末產業週報處理完成")


def main():
    parser = argparse.ArgumentParser(
        description="Discord 市場與產業資訊自動推播系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=["alert", "morning", "wrap", "weekly"],
        help="執行模式: alert (突發快訊), morning (開盤晨報), wrap (盤後綜述), weekly (週末週報)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="偵錯旗標: 執行完整流程，但跳過 Webhook 發送與 Supabase 寫入，直接將 Embed JSON 印出於終端機",
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("【注意】已啟用 --dry-run 模式：將跳過 Discord POST 與 Supabase 寫入")

    if args.mode == "alert":
        handle_alert_mode(dry_run=args.dry_run)
    elif args.mode == "morning":
        handle_morning_mode(dry_run=args.dry_run)
    elif args.mode == "wrap":
        handle_wrap_mode(dry_run=args.dry_run)
    elif args.mode == "weekly":
        handle_weekly_mode(dry_run=args.dry_run)
    else:
        logger.error(f"未知模式: {args.mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
