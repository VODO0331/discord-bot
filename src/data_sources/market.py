"""
市場行情資料擷取模組 (src/data_sources/market.py)
使用 yfinance 抓取美股四大指數、TSM ADR 以及依產業族群分類的焦點股票。
"""

import logging
from typing import Any, Dict, List, Optional
import requests
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


def get_sector_quotes(
    market_filter: Optional[str] = None,
    sectors_list: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    按族群分類批次取得行情。
    market_filter 可指定 'tw' 或 'us' 來過濾特定市場。
    sectors_list 可指定特定族群設定清單（預設為 config.industry_sectors）。
    """
    sectors_summary = []
    target_sectors = sectors_list if sectors_list is not None else config.industry_sectors

    for sector in target_sectors:
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


def get_etf_quotes(market_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    取得專屬 ETF 監控專區的即時行情（支援依 market_filter 過濾 'tw' 或 'us'）。
    """
    return get_sector_quotes(market_filter=market_filter, sectors_list=config.etf_sectors)


def fetch_tw_institutional_investors() -> Dict[str, Any]:
    """
    從臺灣證券交易所 (TWSE) 官方 API 擷取最新交易日「三大法人買賣超金額」(單位：億元)。
    API: https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json
    """
    url = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("stat") != "OK" or not payload.get("data"):
            logger.warning(f"TWSE 三大法人回傳狀態非 OK: {payload.get('stat')}")
            return {"status": "unavailable"}

        raw_date = str(payload.get("date", ""))
        fmt_date = (
            f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            if len(raw_date) == 8
            else raw_date
        )

        def _parse_yi(val_str: str) -> float:
            cleaned = str(val_str).replace(",", "").strip()
            return round(float(cleaned) / 1e8, 2)

        foreign = 0.0
        trust = 0.0
        dealer_self = 0.0
        dealer_hedge = 0.0
        total = 0.0

        for row in payload["data"]:
            if len(row) < 4:
                continue
            label = str(row[0]).strip()
            net_yi = _parse_yi(row[3])
            if "外資" in label:
                foreign = round(foreign + net_yi, 2)
            elif "投信" in label:
                trust = round(trust + net_yi, 2)
            elif "自營商(自行買賣)" in label:
                dealer_self = net_yi
            elif "自營商(避險)" in label:
                dealer_hedge = net_yi
            elif "合計" in label:
                total = net_yi

        dealer = round(dealer_self + dealer_hedge, 2)
        return {
            "status": "ok",
            "date": fmt_date,
            "foreign": foreign,
            "trust": trust,
            "dealer": dealer,
            "dealer_self": dealer_self,
            "dealer_hedge": dealer_hedge,
            "total": total,
        }
    except Exception as e:
        logger.warning(f"抓取 TWSE 三大法人買賣超失敗: {e}")
        return {"status": "unavailable"}


def fetch_us_macro_sentiment() -> List[Dict[str, Any]]:
    """
    擷取美股每日資金流向與機構風險情緒代表指標 (Risk-On / Risk-Off)：
    - ^VIX: 恐慌指數 (機構避險情緒)
    - ^TNX: 美國 10 年期公債殖利率 (資金成本與股債流向)
    - DX-Y.NYB: 美元指數 (全球熱錢與避險流向)
    """
    macro_tickers = [
        ("^VIX", "恐慌指數 (VIX)"),
        ("^TNX", "美債10Y殖利率"),
        ("DX-Y.NYB", "美元指數 (DXY)"),
    ]
    results = []
    for sym, name in macro_tickers:
        q = fetch_ticker_quote(sym, name)
        if q.get("status") == "ok":
            results.append(q)
    return results


def get_morning_market_data() -> Dict[str, Any]:
    """
    開盤晨報市場數據組合：
    - 美股四大核心指數 (^SOX, ^IXIC, ^GSPC, ^DJI)
    - 美股資金與避險情緒指標 (^VIX, ^TNX, DX-Y.NYB)
    - 台積電 ADR (TSM) - 作為台股開盤重要領航
    - 美股 ETF 專屬專區 (旗艦大盤與主題公債 ETF)
    - 美股科技焦點股 (按族群分組)
    """
    indices_results = []
    for item in config.us_indices:
        quote = fetch_ticker_quote(item["symbol"], item.get("name"))
        indices_results.append(quote)

    macro_sentiment = fetch_us_macro_sentiment()
    tsm_quote = fetch_ticker_quote("TSM", "台積電 ADR")
    us_sectors = get_sector_quotes(market_filter="us")
    etf_groups = get_etf_quotes(market_filter="us")

    return {
        "indices": indices_results,
        "macro_sentiment": macro_sentiment,
        "tsm_adr": tsm_quote,
        "etf_groups": etf_groups,
        "sector_groups": us_sectors,
    }


def get_wrap_market_data() -> Dict[str, Any]:
    """
    盤後綜述市場數據組合：
    - 台灣加權指數 (^TWII)
    - 台股三大法人買賣超金額 (外資、投信、自營商、合計)
    - 台股 ETF 專屬獨立專區 (核心被動與主動管理 ETF)
    - 台股熱門個股 (按產業族群分組: 載板、PCB、CCL、AI代工、散熱等)
    - 美股代表指數作為晚間前瞻
    """
    tw_index = fetch_ticker_quote("^TWII", "加權指數")
    institutional = fetch_tw_institutional_investors()
    tw_sectors = get_sector_quotes(market_filter="tw")
    etf_groups = get_etf_quotes(market_filter="tw")

    us_preview = []
    for item in config.us_indices[:2]:
        us_preview.append(fetch_ticker_quote(item["symbol"], item.get("name")))

    return {
        "tw_index": tw_index,
        "institutional": institutional,
        "etf_groups": etf_groups,
        "sector_groups": tw_sectors,
        "us_preview": us_preview,
    }
