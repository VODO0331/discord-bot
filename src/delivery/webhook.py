"""
Discord Webhook 派發模組 (src/delivery/webhook.py)
負責將生成的 Embed 字典分流發送至指定頻道，並實作指數退避重試機制與 204 狀態碼驗證。
"""

import json
import logging
import time
from typing import Any, Dict
import requests
from src.config import config

logger = logging.getLogger(__name__)


def get_webhook_url_for_mode(mode: str) -> str:
    """根據模式決定發送的頻道 Webhook URL"""
    if mode == "alert":
        return config.discord_webhook_alert_url
    else:
        # morning, wrap, weekly 皆派發至每日頻道 (Daily Channel)
        return config.discord_webhook_daily_url


def dispatch_webhook(payload: Dict[str, Any], mode: str, max_retries: int = 3) -> bool:
    """
    發送 Webhook 請求至 Discord。
    若回傳狀態碼為 204 視為成功。
    遇到連線異常或 5xx / 429 錯誤時進行指數退避重試。
    """
    webhook_url = get_webhook_url_for_mode(mode)
    if not webhook_url:
        env_var_name = "DISCORD_WEBHOOK_ALERT_URL" if mode == "alert" else "DISCORD_WEBHOOK_DAILY_URL"
        logger.error(
            f"❌ 模式 [{mode}] 缺少對應的 Discord Webhook URL！\n"
            f"請確認 GitHub Repository Settings -> Secrets 中是否已正確設定 '{env_var_name}'。"
        )
        return False

    # 遮蔽部分字串，僅用於確認 URL 是否正確載入
    masked_url = webhook_url[:35] + "..." if len(webhook_url) > 35 else webhook_url
    logger.info(f"準備發送 Webhook 至: {masked_url} (模式: {mode})")

    headers = {"Content-Type": "application/json"}
    backoff_delay = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"正在發送 Webhook (模式: {mode}, 第 {attempt}/{max_retries} 次嘗試)...")
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=15,
            )

            # Discord Webhook 成功建立通常回傳 204 No Content (或 200 OK)
            if response.status_code in [200, 204]:
                logger.info(f"✅ Webhook 訊息派發成功！(HTTP {response.status_code})")
                return True
            elif response.status_code == 429:
                # Rate limited
                retry_after = response.json().get("retry_after", backoff_delay)
                logger.warning(f"遭遇 Discord Rate Limit (429)，等待 {retry_after} 秒後重試...")
                time.sleep(float(retry_after))
            else:
                logger.error(f"❌ Webhook 發送失敗！HTTP 狀態碼: {response.status_code}, Discord 回應: {response.text}")
                time.sleep(backoff_delay)
                backoff_delay *= 2.0
        except Exception as e:
            logger.warning(f"發送 Webhook 遭遇異常: {e}，等待 {backoff_delay} 秒後重試...")
            time.sleep(backoff_delay)
            backoff_delay *= 2.0

    logger.error(f"達到最大重試次數 ({max_retries})，Webhook 派發失敗")
    return False
