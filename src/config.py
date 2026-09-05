"""
專案全域配置模組 (src/config.py)
負責讀取 config.yaml 與系統環境變數 (.env 或 GitHub Secrets)。
"""

import os
from pathlib import Path
from typing import Any, Dict, List
import yaml

# 嘗試載入 .env 檔案（本機開發使用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 專案根目錄路徑
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_YAML_PATH = BASE_DIR / "config.yaml"


class AppConfig:
    """應用程式設定容器"""

    def __init__(self, raw_yaml: Dict[str, Any]):
        self.raw_yaml = raw_yaml

        # 觀察清單
        watchlist = raw_yaml.get("watchlist", {})
        self.us_indices: List[Dict[str, str]] = watchlist.get("us_indices", [])
        self.us_stocks: List[Dict[str, str]] = watchlist.get("us_stocks", [])
        self.tw_stocks: List[Dict[str, str]] = watchlist.get("tw_stocks", [])

        # RSS 來源
        self.rss_feeds: List[Dict[str, str]] = raw_yaml.get("rss_feeds", [])

        # 快訊關鍵字
        alert_kw = raw_yaml.get("alert_keywords", {})
        self.alert_entities: List[str] = alert_kw.get("entities", [])
        self.alert_actions: List[str] = alert_kw.get("actions", [])

        # 管線參數
        pipeline = raw_yaml.get("pipeline", {})
        self.alert_min_score: int = pipeline.get("alert_min_score", 4)
        self.extractor_timeout: int = pipeline.get("extractor_timeout_seconds", 8)

        # 環境變數與機密
        self.discord_webhook_daily_url: str = os.getenv("DISCORD_WEBHOOK_DAILY_URL", "").strip()
        self.discord_webhook_alert_url: str = os.getenv("DISCORD_WEBHOOK_ALERT_URL", "").strip()
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "").strip()
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").strip()
        self.supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
        self.supabase_key: str = os.getenv("SUPABASE_KEY", "").strip()


def load_config(config_path: Path = CONFIG_YAML_PATH) -> AppConfig:
    """載入 YAML 設定檔並合併環境變數"""
    if not config_path.exists():
        raise FileNotFoundError(f"找不到設定檔: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return AppConfig(data)


# 全域單例設定物件
config = load_config()
