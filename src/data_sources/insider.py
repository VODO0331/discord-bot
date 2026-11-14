"""
美股內部人交易擷取模組 (src/data_sources/insider.py)
透過 yfinance 讀取觀察清單美股個股之 SEC Form 4 內部人交易申報資料，
自動過濾 $0 股票獎勵與贈與，僅保留達標之公開市場買進或賣出紀錄。
"""

from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List
import yfinance as yf
from src.config import config

logger = logging.getLogger(__name__)


def _get_us_industry_stocks() -> List[Dict[str, str]]:
    """取得美股產業觀察清單（排除 ETF，因 ETF 無內部人申報）"""
    stocks: List[Dict[str, str]] = []
    seen = set()
    for sector in config.industry_sectors:
        sector_name = sector.get("name", "一般族群")
        for stk in sector.get("stocks", []):
            if stk.get("market", "").lower() == "us":
                sym = stk["symbol"]
                if sym not in seen:
                    seen.add(sym)
                    stocks.append({
                        "symbol": sym,
                        "name": stk.get("name", sym),
                        "sector": sector_name,
                    })
    return stocks


def _parse_price_hint(text: str) -> str:
    """從交易描述文字中擷取成交價格或區間"""
    if not text:
        return "未揭露"
    match = re.search(r"at price\s+([\d.,]+(?:\s*-\s*[\d.,]+)?)\s*per share", text, re.IGNORECASE)
    if match:
        return f"${match.group(1).strip()}"
    return "未揭露"


def fetch_insider_transactions(lookback_days: int = None) -> List[Dict[str, Any]]:
    """
    掃描觀察清單中的所有美股個股，擷取近 N 天內符合金額門檻的公開市場買賣交易。
    """
    if lookback_days is None:
        lookback_days = config.insider_lookback_days

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date()
    us_stocks = _get_us_industry_stocks()
    results: List[Dict[str, Any]] = []

    for stk in us_stocks:
        symbol = stk["symbol"]
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.insider_transactions
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                text = str(row.get("Text", "") or "")
                text_lower = text.lower()

                # 僅保留公開市場實質買進 (Purchase) 或賣出 (Sale)，排除 $0 配股/贈與/轉讓
                if "purchase" in text_lower:
                    action = "buy"
                elif "sale" in text_lower:
                    action = "sell"
                else:
                    continue

                # 解析日期
                raw_date = row.get("Start Date")
                if raw_date is None:
                    continue
                if hasattr(raw_date, "date"):
                    tx_date = raw_date.date()
                else:
                    try:
                        tx_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
                    except ValueError:
                        continue

                if tx_date < cutoff_date:
                    continue

                # 解析股數與金額
                try:
                    shares = int(float(row.get("Shares", 0) or 0))
                except (TypeError, ValueError):
                    shares = 0

                try:
                    value_usd = float(row.get("Value", 0) or 0)
                except (TypeError, ValueError):
                    value_usd = 0.0

                if shares <= 0 or value_usd <= 0:
                    continue

                # 套用金額門檻過濾
                if action == "buy" and value_usd < config.insider_min_buy_value_usd:
                    continue
                if action == "sell" and value_usd < config.insider_min_value_usd:
                    continue

                insider_name = str(row.get("Insider", "未知內部人") or "未知內部人").strip()
                position = str(row.get("Position", "內部人") or "內部人").strip()
                url = str(row.get("URL", "") or "").strip()

                results.append({
                    "symbol": symbol,
                    "company_name": stk["name"],
                    "sector": stk["sector"],
                    "date": tx_date.strftime("%Y-%m-%d"),
                    "insider": insider_name,
                    "position": position,
                    "action": action,
                    "shares": shares,
                    "value_usd": value_usd,
                    "price_hint": _parse_price_hint(text),
                    "url": url,
                    "raw_text": text,
                })
        except Exception as e:
            logger.warning(f"取得 {symbol} 內部人交易資料失敗: {e}")

    # 排序：買進優先，其次依成交金額由大到小
    results.sort(key=lambda x: (0 if x["action"] == "buy" else 1, -x["value_usd"]))
    logger.info(f"美股內部人交易掃描完成，共計 {len(us_stocks)} 檔標的，篩選出 {len(results)} 筆達標紀錄")
    return results
