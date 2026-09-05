"""
Discord Embed 訊息排版模組 (src/pipeline/formatter.py)
依照 spec.md 4.3 規範建構 Discord Webhook Embed JSON 結構。
支援依產業族群 (Industry Sectors) 分類排版呈現各族群熱門股行情。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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
        "description": description[:4000],
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

    # 1. 隔夜美股四大核心指數
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

    # 2. TSM ADR 專區
    tsm = market_data.get("tsm_adr")
    if tsm and tsm.get("status") == "ok":
        t_sign = "+" if tsm.get("change_percent", 0) >= 0 else ""
        t_icon = "🚀" if tsm.get("is_up") else "📉"
        fields.append({
            "name": f"{t_icon} 台積電 ADR (TSM) 開盤前瞻",
            "value": f"最新價格: **\${tsm['price']}** | 漲跌: **{t_sign}{tsm['change_percent']}%** ({t_sign}{tsm['change']})",
            "inline": False,
        })

def compute_sector_metrics(quotes: List[Dict[str, Any]]) -> Tuple[float, str]:
    """
    計算族群內所有個股的平均表現與多空強弱燈號。
    回傳: (平均漲跌幅, 燈號字串)
    - 🟢 (+X.XX%): 多數/平均上漲
    - 🔴 (-X.XX%): 多數/平均下跌
    - ⚪ (0.00%): 持平
    """
    valid_quotes = [q for q in quotes if q.get("status") == "ok"]
    if not valid_quotes:
        return 0.0, ""

    total_pct = sum(q.get("change_percent", 0.0) for q in valid_quotes)
    avg_pct = total_pct / len(valid_quotes)

    if avg_pct > 0:
        indicator = "🟢"
    elif avg_pct < 0:
        indicator = "🔴"
    else:
        indicator = "⚪"

    sign = "+" if avg_pct >= 0 else ""
    label = f"{indicator} ({sign}{avg_pct:.2f}%)"
    return avg_pct, label


def format_morning_embed(market_data: Dict[str, Any], ai_summary: str) -> Dict[str, Any]:
    """
    建構開盤晨報 (Morning Brief) Discord Embed。
    """
    fields = []

    # 1. 隔夜美股四大核心指數
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

    # 2. TSM ADR 專區
    tsm = market_data.get("tsm_adr")
    if tsm and tsm.get("status") == "ok":
        t_sign = "+" if tsm.get("change_percent", 0) >= 0 else ""
        t_icon = "🚀" if tsm.get("is_up") else "📉"
        fields.append({
            "name": f"{t_icon} 台積電 ADR (TSM) 開盤前瞻",
            "value": f"最新價格: **\${tsm['price']}** | 漲跌: **{t_sign}{tsm['change_percent']}%** ({t_sign}{tsm['change']})",
            "inline": False,
        })

    # 3. 美股依產業族群呈現焦點行情 (依平均強弱排序並標示 🟢/🔴 燈號)
    sector_groups = market_data.get("sector_groups", [])
    ranked_groups = []
    for group in sector_groups:
        avg_pct, strength_label = compute_sector_metrics(group.get("quotes", []))
        ranked_groups.append((avg_pct, strength_label, group))

    # 依平均漲跌幅由強至弱排序
    ranked_groups.sort(key=lambda x: x[0], reverse=True)

    for avg_pct, strength_label, group in ranked_groups:
        sector_name = group.get("sector_name", "")
        icon = group.get("icon", "📌")
        stk_items = []
        for stk in group.get("quotes", []):
            s_sign = "+" if stk.get("change_percent", 0) >= 0 else ""
            s_icon = "▲" if stk.get("is_up") else "▼"
            stk_items.append(f"{s_icon} {stk['name']}: {stk['price']} ({s_sign}{stk['change_percent']}%)")

        if stk_items:
            fields.append({
                "name": f"{strength_label} {icon} {sector_name}",
                "value": "\n".join(stk_items)[:1024],
                "inline": True,
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
    將台股個股依照「產業族群 (Sectors)」清晰分組呈現。
    """
    fields = []

    # 1. 加權指數總結
    tw_index = market_data.get("tw_index", {})
    sign = "+" if tw_index.get("change_percent", 0) >= 0 else ""
    icon = "🟢" if tw_index.get("is_up") else "🔴"
    
    fields.append({
        "name": "🇹🇼 台灣加權指數 (^TWII)",
        "value": f"{icon} 收盤點數: **{tw_index.get('price')}** | 漲跌幅: **{sign}{tw_index.get('change_percent')}%**",
        "inline": False,
    })

    # 2. 依照產業族群分類呈现 (依平均強弱排序並標示 🟢/🔴 燈號)
    sector_groups = market_data.get("sector_groups", [])
    ranked_groups = []
    for group in sector_groups:
        avg_pct, strength_label = compute_sector_metrics(group.get("quotes", []))
        ranked_groups.append((avg_pct, strength_label, group))

    # 依平均漲跌幅由強至弱排序 (主流強勢族群排在最前面)
    ranked_groups.sort(key=lambda x: x[0], reverse=True)

    for avg_pct, strength_label, group in ranked_groups:
        sector_name = group.get("sector_name", "")
        icon = group.get("icon", "📌")
        stk_items = []
        for stk in group.get("quotes", []):
            s_sign = "+" if stk.get("change_percent", 0) >= 0 else ""
            s_icon = "▲" if stk.get("is_up") else "▼"
            stk_items.append(f"{s_icon} **{stk['name']}**: {stk['price']} ({s_sign}{stk['change_percent']}%)")

        if stk_items:
            fields.append({
                "name": f"{strength_label} {icon} {sector_name}",
                "value": "\n".join(stk_items)[:1024],
                "inline": True,
            })

    embed_color = COLOR_BULLISH if tw_index.get("is_up", True) else COLOR_BEARISH

    embed = {
        "author": {
            "name": "🌆 台股盤後綜述 (Market Wrap)",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/3222/3222800.png",
        },
        "title": f"【盤後復盤】今日收盤總結與產業族群動態 — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "description": ai_summary[:4000],
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
    嚴格校驗超連結，避免無效 URL 導致 Discord 回傳 HTTP 400。
    """
    fields = []

    ref_lines = []
    for idx, art in enumerate(top_articles[:5], 1):
        title = art.get("title", "").strip() or "焦點事件"
        # 尋找合法 URL (必須為 http:// 或 https://)
        link = art.get("link") or art.get("url") or ""
        if isinstance(link, str) and (link.startswith("http://") or link.startswith("https://")):
            ref_lines.append(f"{idx}. [{title}]({link})")
        else:
            source = art.get("source", "")
            source_tag = f"【{source}】" if source else ""
            ref_lines.append(f"{idx}. {source_tag}{title}")

    if ref_lines:
        fields.append({
            "name": "📚 本週代表性焦點研報與新聞",
            "value": "\n".join(ref_lines)[:1024],
            "inline": False,
        })

    embed = {
        "author": {
            "name": "🔬 週末產業週報 (Weekly Deep-dive)",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/2910/2910795.png",
        },
        "title": f"【深度綜述】全球科技與半導體供應鏈週回顧 — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "description": ai_summary[:4000],
        "color": COLOR_NEUTRAL,
        "fields": fields,
        "footer": {
            "text": DISCLAIMER_FOOTER,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {"embeds": [embed]}
