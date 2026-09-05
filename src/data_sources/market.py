"""
市場行情資料擷取模組 (src/data_sources/market.py)
使用 yfinance 抓取美股四大指數、TSM ADR 以及依產業族群分類的焦點股票。
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

        # 若台股代號仍未取得，嘗試上市與上櫃互換 (.TW <-> .TWO)
        if (current_price is None or previous_close is None) and (".TW" in symbol.upper()):
            alt_symbol = symbol.replace(".TW", ".TWO") if ".TWO" not in symbol.upper() else symbol.replace(".TWO", ".TW")
            try:
                alt_ticker = yf.Ticker(alt_symbol)
                alt_hist = alt_ticker.history(period="5d")
                if len(alt_hist) >= 2:
                    current_price = float(alt_hist["Close"].iloc[-1])
                    previous_close = float(alt_hist["Close"].iloc[-2])
            except Exception:
                pass

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


def get_sector_quotes(market_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    按產業分類批次取得個股行情。
    market_filter 可指定 'tw' 或 'us' 來過濾特定市場。
    """
    sectors_summary = []

    for sector in config.industry_sectors:
        sector_name = sector.get("name", "一般族群")
        icon = sector.get("icon", "📌")
        matched_quotes = []

        for stk in sector.get("stocks", []):
            stk_market = stk.get("market", "").lower()
            if market_filter and stk_market != market_filter:
                continue

            quote = fetch_ticker_quote(stk["symbol"], stk.get("name"))
            matched_quotes.append(quote)

        if matched_quotes:
            sectors_summary.append({
                "sector_name": sector_name,
                "icon": icon,
                "quotes": matched_quotes,
            })

    return sectors_summary


def get_morning_market_data() -> Dict[str, Any]:
    """
    開盤晨報市場數據組合：
    - 美股四大核心指數 (^SOX, ^IXIC, ^GSPC, ^DJI)
    - 台積電 ADR (TSM) - 作為台股開盤重要領航
    - 美股科技焦點股 (按族群分組)
    """
    indices_results = []
    for item in config.us_indices:
        quote = fetch_ticker_quote(item["symbol"], item.get("name"))
        indices_results.append(quote)

    tsm_quote = fetch_ticker_quote("TSM", "台積電 ADR")
    us_sectors = get_sector_quotes(market_filter="us")

    return {
        "indices": indices_results,
        "tsm_adr": tsm_quote,
        "sector_groups": us_sectors,
    }


def get_wrap_market_data() -> Dict[str, Any]:
    """
    盤後綜述市場數據組合：
    - 台灣加權指數 (^TWII)
    - 台股熱門個股 (按產業族群分組: 載板、被動元件、AI代工、散熱等)
    - 美股代表指數作為晚間前瞻
    """
    tw_index = fetch_ticker_quote("^TWII", "加權指數")
    tw_sectors = get_sector_quotes(market_filter="tw")

    us_preview = []
    for item in config.us_indices[:2]:
        us_preview.append(fetch_ticker_quote(item["symbol"], item.get("name")))

    return {
        "tw_index": tw_index,
        "sector_groups": tw_sectors,
        "us_preview": us_preview,
    }
