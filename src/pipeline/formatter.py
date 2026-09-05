"""
Discord Embed 訊息排版模組 (src/pipeline/formatter.py)
依照 spec.md 4.3 規範建構 Discord Webhook Embed JSON 結構。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# 色碼常數定義
COLOR_BULLISH = 0x2ECC71   # 偏多/上漲綠 (#2ECC71)
COLOR_BEARISH = 0xE74C3C   # 偏空/下跌紅 (#E74C3C)
COLOR_NEUTRAL = 0x3498DB   # 中性/總經藍 (#3498DB)

DISCLAIMER_FOOTER = "本資訊僅供研究與學習參考，不構成任何形式之投資建議。"


def format_alert_embed(
    article: Dict[str, Any],
    summary_data: Dict[str, Any],
    matched_tags: List[str],
) -> Dict[str, Any]:
    """
    建構突發快訊 (Breaking Alert) Discord Embed。
    """
    sentiment = summary_data.get("sentiment", "neutral")
    if sentiment == "bullish":
        color = COLOR_BULLISH
    elif sentiment == "bearish":
        color = COLOR_BEARISH
    else:
        color = COLOR_NEUTRAL

    score = summary_data.get("significance_score", 4)
    core_event = summary_data.get("core_event", "")
    key_details = summary_data.get("key_details", [])
    industry_impact = summary_data.get("industry_impact", "")

    # 組裝細節條列
    details_str = "\n".join([f"• {item}" for item in key_details])

    description = f"""
📌 **核心事件**
{core_event}

💡 **關鍵細節**
{details_str}

📊 **市場與產業影響**
{industry_impact}
""".strip()

    tags_str = " ".join([f"`#{tag}`" for tag in matched_tags[:6]]) or "`#即時快訊`"

    embed = {
        "author": {
            "name": f"🚨 重大突發快訊 (震撼度: {'⭐' * min(score, 5)})",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/1041/1041883.png",
        },
        "title": article.get("title", "重大財經快訊"),
        "url": article.get("link", ""),
        "description": description,
        "color": color,
        "fields": [
            {
                "name": "🏷️ 追蹤實體與動態標籤",
                "value": tags_str,
                "inline": True,
            },
            {
                "name": "📰 資料來源",
                "value": article.get("source", "科技/財經媒體"),
                "inline": True,
            },
        ],
        "footer": {
            "text": DISCLAIMER_FOOTER,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {"embeds": [embed]}


def format_morning_embed(market_data: Dict[str, Any], ai_summary: str) -> Dict[str, Any]:
    """
    建構開盤晨報 (Morning Brief) Discord Embed。
    """
    fields = []

    # 指數欄位
    indices_lines = []
    total_change = 0.0
    for idx in market_data.get("indices", []):
        sign = "+" if idx.get("change_percent", 0) >= 0 else ""
        icon = "🟢" if idx.get("is_up") else "🔴"
        indices_lines.append(f"{icon} **{idx['name']}**: {idx['price']} ({sign}{idx['change_percent']}%)")
        total_change += idx.get("change_percent", 0)

    if indices_lines:
        fields.append({
            "name": "📈 隔夜美股核心指數",
            "value": "\n".join(indices_lines),
            "inline": False,
        })

    # TSM ADR 專區
    tsm = market_data.get("tsm_adr")
    if tsm and tsm.get("status") == "ok":
        t_sign = "+" if tsm.get("change_percent", 0) >= 0 else ""
        t_icon = "🚀" if tsm.get("is_up") else "📉"
        fields.append({
            "name": f"{t_icon} 台積電 ADR (TSM) 前瞻",
            "value": f"最新價格: **\${tsm['price']}** | 漲跌: **{t_sign}{tsm['change_percent']}%** ({t_sign}{tsm['change']})",
            "inline": False,
        })

    # 科技焦點股
    stock_lines = []
    for stk in market_data.get("stocks", [])[:6]:
        if stk.get("symbol") != "TSM":
            s_sign = "+" if stk.get("change_percent", 0) >= 0 else ""
            s_icon = "▲" if stk.get("is_up") else "▼"
            stock_lines.append(f"{s_icon} {stk['name']}: {stk['price']} ({s_sign}{stk['change_percent']}%)")

    if stock_lines:
        fields.append({
            "name": "💻 美股核心科技權值",
            "value": "\n".join(stock_lines),
            "inline": False,
        })

    embed_color = COLOR_BULLISH if total_change >= 0 else COLOR_BEARISH

    embed = {
        "author": {
            "name": "🌅 台股開盤晨報 (Morning Brief)",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/869/869869.png",
        },
        "title": f"【開盤前瞻】美股收盤與產業焦點 — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "description": ai_summary[:4000],
        "color": embed_color,
        "fields": fields,
        "footer": {
            "text": DISCLAIMER_FOOTER,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {"embeds": [embed]}


def format_wrap_embed(market_data: Dict[str, Any], ai_summary: str) -> Dict[str, Any]:
    """
    建構盤後綜述 (Market Wrap) Discord Embed。
    """
    fields = []

    tw_index = market_data.get("tw_index", {})
    sign = "+" if tw_index.get("change_percent", 0) >= 0 else ""
    icon = "🟢" if tw_index.get("is_up") else "🔴"
    
    fields.append({
        "name": "🇹🇼 台灣加權指數 (^TWII)",
        "value": f"{icon} 收盤點數: **{tw_index.get('price')}** | 漲跌幅: **{sign}{tw_index.get('change_percent')}%**",
        "inline": False,
    })

    stock_lines = []
    for stk in market_data.get("tw_stocks", []):
        s_sign = "+" if stk.get("change_percent", 0) >= 0 else ""
        s_icon = "▲" if stk.get("is_up") else "▼"
        stock_lines.append(f"{s_icon} **{stk['name']}**: {stk['price']} ({s_sign}{stk['change_percent']}%)")

    if stock_lines:
        fields.append({
            "name": "🏢 焦點代表權值股",
            "value": "\n".join(stock_lines),
            "inline": False,
        })

    embed_color = COLOR_BULLISH if tw_index.get("is_up", True) else COLOR_BEARISH

    embed = {
        "author": {
            "name": "🌆 台股盤後綜述 (Market Wrap)",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/3222/3222800.png",
        },
        "title": f"【盤後復盤】今日收盤總結與美股夜盤前瞻 — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "description": ai_summary,
        "color": embed_color,
        "fields": fields,
        "footer": {
            "text": DISCLAIMER_FOOTER,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {"embeds": [embed]}


def format_weekly_embed(ai_summary: str, top_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    建構週末產業週報 (Weekly Deep-dive) Discord Embed。
    """
    fields = []

    ref_lines = []
    for idx, art in enumerate(top_articles[:4], 1):
        ref_lines.append(f"{idx}. [{art.get('title', '參考文章')}]({art.get('link', art.get('url', '#'))})")

    if ref_lines:
        fields.append({
            "name": "📚 本週代表性焦點研報與新聞",
            "value": "\n".join(ref_lines),
            "inline": False,
        })

    embed = {
        "author": {
            "name": "🔬 週末產業週報 (Weekly Deep-dive)",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/2910/2910795.png",
        },
        "title": f"【深度綜述】全球科技與半導體供應鏈週回顧 — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "description": ai_summary,
        "color": COLOR_NEUTRAL,
        "fields": fields,
        "footer": {
            "text": DISCLAIMER_FOOTER,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {"embeds": [embed]}
