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
COLOR_MOURNING = 0x34495E  # 國喪避難灰黑 (#34495E)

DISCLAIMER_FOOTER = "本資訊僅供研究與學習參考，不構成任何形式之投資建議。"

# 視覺分隔線常數 (長度 38 個字元，用於 Discord Embed 區塊分隔)
DIVIDER_LINE = "─" * 38


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
    若偵測到美股主要指數重挫暴跌，自動切換為國喪避難模式：
    - 隱藏美股個股與 ETF 詳細跌幅，避免二次心靈衝擊
    - 保留核心指數、TSM ADR、AI 隔夜前瞻總結與產業概況強弱
    - 附上莊嚴且幽默的心理避難提醒
    """
    from src.config import config
    fields = []

    # 1. 隔夜美股四大核心指數
    indices_lines = []
    total_change = 0.0
    is_panic = False
    panic_reasons = []

    for idx in market_data.get("indices", []):
        pct = idx.get("change_percent", 0.0)
        sign = "+" if pct >= 0 else ""
        icon = "🟢" if idx.get("is_up") else "🔴"
        indices_lines.append(f"{icon} **{idx['name']}**: {idx['price']} ({sign}{pct}%)")
        total_change += pct

        # 判定是否達到美股暴跌標準 (例如那指或費半跌幅 >= 3.0%)
        if config.panic_enabled and pct <= -config.panic_us_pct_drop:
            is_panic = True
            panic_reasons.append(f"{idx['name']} ({sign}{pct}%)")

    # ------------------ 避難模式 (國喪日) ------------------
    if is_panic:
        fields.append({
            "name": "🕯️ 隔夜美股重災區指數",
            "value": "\n".join(indices_lines),
            "inline": False,
        })

        tsm = market_data.get("tsm_adr")
        if tsm and tsm.get("status") == "ok":
            t_sign = "+" if tsm.get("change_percent", 0) >= 0 else ""
            t_icon = "🚀" if tsm.get("is_up") else "📉"
            fields.append({
                "name": f"{t_icon} 台積電 ADR (TSM) 開盤前瞻",
                "value": f"最新價格: **\${tsm['price']}** | 漲跌: **{t_sign}{tsm['change_percent']}%** ({t_sign}{tsm['change']})",
                "inline": False,
            })

        fields.append({
            "name": "☕ 投資人心靈防護與開盤指南",
            "value": (
                "1. **少看少痛**：美股遭遇強烈亂流，個股血流成河畫面已被系統自動過濾封存。\n"
                "2. **防護措施**：預期今日台股開盤壓力沉重，切勿急躁盲目搶反彈接飛刀。\n"
                "3. **生活依舊**：未實現損益只是暫時浮動的數字，熱咖啡泡好，深呼吸迎接挑戰。"
            ),
            "inline": False,
        })

        embed = {
            "author": {
                "name": "🌑 隔夜美股市場緊急避難通報 (Morning Brief 特別版)",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/869/869869.png",
            },
            "title": f"【全體默哀】隔夜美股遭遇重大亂流重挫 — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "description": (
                f"**⚠️ 系統偵測到隔夜美股主要指數重摔（{', '.join(panic_reasons)}）。**\n"
                "**為維護各位投資人身心靈健康與血壓穩定，今日個股及 ETF 詳細跌幅已啟動保護機制暫停展開。**\n\n"
                + ai_summary[:3500]
            ),
            "color": COLOR_MOURNING,
            "fields": fields,
            "footer": {
                "text": "真正的勇士，敢於直面慘淡的對帳單。 " + DISCLAIMER_FOOTER,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return {"embeds": [embed]}

    # ------------------ 一般正常模式 ------------------
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

    # 3. 專屬獨立美股 ETF 專區 (置頂於個股族群之前，旗艦大盤與主題策略分組並列)
    etf_groups = market_data.get("etf_groups", [])
    if etf_groups:
        fields.append({
            "name": DIVIDER_LINE,
            "value": "📊 **美股重點 ETF 專屬監控專區**",
            "inline": False,
        })
        for group in etf_groups:
            avg_pct, strength_label = compute_sector_metrics(group.get("quotes", []))
            sector_name = group.get("sector_name", "")
            icon = group.get("icon", "📈")
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

    # 4. 美股依產業族群呈現焦點行情 (依平均強弱排序並標示 🟢/🔴 燈號)
    sector_groups = market_data.get("sector_groups", [])
    ranked_groups = []
    for group in sector_groups:
        avg_pct, strength_label = compute_sector_metrics(group.get("quotes", []))
        ranked_groups.append((avg_pct, strength_label, group))

    # 依平均漲跌幅由強至弱排序
    ranked_groups.sort(key=lambda x: x[0], reverse=True)

    if ranked_groups:
        fields.append({
            "name": DIVIDER_LINE,
            "value": "🏢 **美股重點產業族群與龍頭個股**",
            "inline": False,
        })

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
    若偵測到台股加權指數大跌（單日重挫 >= 900 點 或 跌幅 >= 3.5%），
    自動切換為國喪避難模式：
    - 隱藏個股與 ETF 詳細跌幅清單，避免傷口撒鹽
    - 保留大盤指數、AI 盤後分析總結與各產業族群平均強弱概況
    - 附上莊嚴認真且帶有幽默的心理防護避難指南
    """
    from src.config import config
    fields = []

    # 1. 加權指數總結
    tw_index = market_data.get("tw_index", {})
    pct = tw_index.get("change_percent", 0.0)
    change_point = tw_index.get("change", 0.0)
    sign = "+" if pct >= 0 else ""
    icon = "🟢" if tw_index.get("is_up") else "🔴"

    # 判定是否達到台股國喪日標準 (例如大跌 900 點或跌幅達 3.5%)
    is_panic = False
    panic_msg = ""
    if config.panic_enabled and tw_index.get("status") == "ok":
        if change_point <= -config.panic_tw_point_drop:
            is_panic = True
            panic_msg = f"單日重挫 {abs(change_point):.1f} 點 (達 {config.panic_tw_point_drop:.0f} 點避難門檻)"
        elif pct <= -config.panic_tw_pct_drop:
            is_panic = True
            panic_msg = f"單日重摔 {pct:.2f}% (達 {config.panic_tw_pct_drop:.1f}% 避難門檻)"

    # ------------------ 避難模式 (國喪日) ------------------
    if is_panic:
        fields.append({
            "name": "🕯️ 台灣加權指數 (^TWII) 今日災情",
            "value": f"📉 收盤點數: **{tw_index.get('price')}** | 跌點: **{change_point} 點** ({pct}%)",
            "inline": False,
        })

        # 幽默且莊嚴的避難指引
        fields.append({
            "name": "🛡️ 投資人緊急避難與心理防護指南",
            "value": (
                "1. **物理避險**：建議立即關閉券商看盤軟體，48 小時內避免非理性砍在阿呆谷。\n"
                "2. **少看少痛**：螢幕上的未實現損益只是浮雲，只要不賣就...（咳，請嚴格遵守紀律）。\n"
                "3. **出門散步**：今日各大公園長椅風大，晚間氣溫偏低，前往散心請務必注意保暖。\n"
                "4. **明天再來**：便當還是要加蛋，太陽明日依舊升起，市場永遠都在。"
            ),
            "inline": False,
        })

        embed = {
            "author": {
                "name": "🕯️ 國家級市場緊急災情通報：今日全體默哀特別版",
                "icon_url": "https://cdn-icons-png.flaticon.com/512/3222/3222800.png",
            },
            "title": f"【休市默哀】台股遭遇系統性崩跌 — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "description": (
                f"**🚨 市場通報：加權指數今日已被空頭全數接管（{panic_msg}）。**\n"
                "**為維護各位投資人身心靈健康與血壓穩定，今日個股及 ETF 詳細跌幅已全數封存隱藏。**\n\n"
                + ai_summary[:3500]
            ),
            "color": COLOR_MOURNING,
            "fields": fields,
            "footer": {
                "text": "真正的勇士，敢於直面慘淡的對帳單。 " + DISCLAIMER_FOOTER,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return {"embeds": [embed]}

    # ------------------ 一般正常模式 ------------------
    fields.append({
        "name": "🇹🇼 台灣加權指數 (^TWII)",
        "value": f"{icon} 收盤點數: **{tw_index.get('price')}** | 漲跌幅: **{sign}{tw_index.get('change_percent')}%**",
        "inline": False,
    })

    # 2. 專屬獨立 ETF 監控專區 (置頂於個股族群之前，主動與被動獨立並列)
    etf_groups = market_data.get("etf_groups", [])
    if etf_groups:
        fields.append({
            "name": DIVIDER_LINE,
            "value": "📊 **台股重點 ETF 專屬監控專區 (主被動分開)**",
            "inline": False,
        })
        for group in etf_groups:
            avg_pct, strength_label = compute_sector_metrics(group.get("quotes", []))
            sector_name = group.get("sector_name", "")
            icon = group.get("icon", "📊")
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

    # 3. 依照產業族群分類呈现 (依平均強弱排序並標示 🟢/🔴 燈號)
    sector_groups = market_data.get("sector_groups", [])
    ranked_groups = []
    for group in sector_groups:
        avg_pct, strength_label = compute_sector_metrics(group.get("quotes", []))
        ranked_groups.append((avg_pct, strength_label, group))

    # 依平均漲跌幅由強至弱排序 (主流強勢族群排在最前面)
    ranked_groups.sort(key=lambda x: x[0], reverse=True)

    if ranked_groups:
        fields.append({
            "name": DIVIDER_LINE,
            "value": "🏢 **台股關鍵產業供應鏈族群**",
            "inline": False,
        })

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
