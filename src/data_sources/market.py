"""
市場行情資料擷取模組 (src/data_sources/market.py)
使用 yfinance 抓取美股四大指數、焦點科技股、TSM ADR 與台股代表權值標的行情。
"""

import logging
from typing import Any, Dict, List, Optional
import yfinance as yf
from src.config import config

logger = logging.getLogger(__name__)


def fetch_ticker_quote(symbol: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """
    擷取單一標的之最新行情資訊（最新價、前日收盤價、漲跌金額、漲跌幅 %）。
    """
    name = display_name or symbol
    try:
        ticker = yf.Ticker(symbol)
        # fast_info 通常比 info 快且不易被 rate limit 阻擋
        fast_info = getattr(ticker, "fast_info", None)
        
        current_price = None
        previous_close = None
        
        if fast_info:
            current_price = getattr(fast_info, "last_price", None)
            previous_close = getattr(fast_info, "previous_close", None)
            
        # 若 fast_info 未能取得，嘗試讀取最近 2 個交易日的歷史資料
        if current_price is None or previous_close is None:
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                current_price = float(hist["Close"].iloc[-1])
                previous_close = float(hist["Close"].iloc[-2])
            elif len(hist) == 1:
                current_price = float(hist["Close"].iloc[-1])
                previous_close = float(hist["Open"].iloc[-1])

        if current_price is not None and previous_close:
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100.0
            return {
                "symbol": symbol,
                "name": name,
                "price": round(current_price, 2),
                "previous_close": round(previous_close, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "is_up": change >= 0,
                "status": "ok",
            }
        else:
            logger.warning(f"標的 {symbol} 未能取得有效價格數據")
            return {
                "symbol": symbol,
                "name": name,
                "price": 0.0,
                "change": 0.0,
                "change_percent": 0.0,
                "is_up": True,
                "status": "unavailable",
            }
    except Exception as e:
        logger.warning(f"擷取 {symbol} 行情異常: {e}")
        return {
            "symbol": symbol,
            "name": name,
            "price": 0.0,
            "change": 0.0,
            "change_percent": 0.0,
            "is_up": True,
            "status": "error",
        }


def get_morning_market_data() -> Dict[str, Any]:
    """
    開盤晨報市場數據組合：
    - 美股四大核心指數 (^SOX, ^IXIC, ^GSPC, ^DJI)
    - 台積電 ADR (TSM) - 作為台股開盤重要領航
    - 美股科技七巨頭 / 核心關注標的
    """
    indices_results = []
    for item in config.us_indices:
        quote = fetch_ticker_quote(item["symbol"], item.get("name"))
        indices_results.append(quote)

    stocks_results = []
    tsm_quote = None
    for item in config.us_stocks:
        quote = fetch_ticker_quote(item["symbol"], item.get("name"))
        stocks_results.append(quote)
        if item["symbol"].upper() == "TSM":
            tsm_quote = quote

    return {
        "indices": indices_results,
        "stocks": stocks_results,
        "tsm_adr": tsm_quote,
    }


def get_wrap_market_data() -> Dict[str, Any]:
    """
    盤後綜述市場數據組合：
    - 台灣加權指數 (^TWII)
    - 台股代表權值標的 (2330.TW, 2454.TW, 2317.TW)
    - 美股期貨或美股焦點個股盤前狀態
    """
    # 擷取台灣加權指數
    tw_index = fetch_ticker_quote("^TWII", "加權指數")

    # 擷取台股權值股
    tw_stocks_results = []
    for item in config.tw_stocks:
        quote = fetch_ticker_quote(item["symbol"], item.get("name"))
        tw_stocks_results.append(quote)

    # 美股代表標的作為晚間前瞻參考
    us_preview = []
    for item in config.us_indices[:2]:
        us_preview.append(fetch_ticker_quote(item["symbol"], item.get("name")))

    return {
        "tw_index": tw_index,
        "tw_stocks": tw_stocks_results,
        "us_preview": us_preview,
    }
