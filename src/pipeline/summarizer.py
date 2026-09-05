"""
AI 提煉與摘要模組 (src/pipeline/summarizer.py)
整合 Google Gemini 模型 (gemini-2.5-flash / gemini-1.5-flash) 進行結構化摘要、嚴重性評分與市場解讀。
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from src.config import config

logger = logging.getLogger(__name__)


def get_gemini_client():
    """初始化 Google GenAI Client"""
    if not config.llm_api_key:
        logger.warning("未偵測到 LLM_API_KEY，將使用規則模擬摘要 (Mock)")
        return None

    try:
        from google import genai
        client = genai.Client(api_key=config.llm_api_key)
        return client
    except Exception as e:
        logger.error(f"初始化 Gemini Client 失敗: {e}")
        return None


def call_gemini(prompt: str, model_name: str = "gemini-2.5-flash") -> str:
    """呼叫 Gemini API 產生回應"""
    client = get_gemini_client()
    if not client:
        return ""

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return response.text or ""
    except Exception as e:
        # 若 2.5-flash 不支援，嘗試降級使用 1.5-flash
        if "gemini-2.5-flash" in model_name:
            try:
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt,
                )
                return response.text or ""
            except Exception as e2:
                logger.error(f"Gemini API 呼叫失敗 (fallback 也失敗): {e2}")
        else:
            logger.error(f"Gemini API 呼叫失敗: {e}")
        return ""


def clean_json_text(raw_text: str) -> str:
    """去除 Markdown ```json 區塊外框以解析純 JSON"""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def summarize_alert(article_title: str, article_content: str) -> Dict[str, Any]:
    """
    快訊模式 (Breaking Alert)：
    對單篇新聞評估市場震撼度 (1~5 分) 與萃取結構化要點。
    要求以 JSON 輸出。
    """
    prompt = f"""
你是一位專業的半導體與高科技財經分析師。請分析以下這篇突發新聞，並客觀評估其重要性與產業影響。

新聞標題: {article_title}
新聞內文:
{article_content[:2500]}

請嚴格以繁體中文與 JSON 格式回傳，欄位規範如下：
{{
  "significance_score": 1到5的整數 (5代表極高衝擊如重大制裁/全球併購/破產，4代表重要事件如聯準會重大決策/台積電重大法說/蘋果發布全新晶片，3代表一般營收或常態產品更新，1-2代表噪音公關稿),
  "core_event": "一句話總結事件核心 (不超過 50 字)",
  "key_details": ["關鍵細節與數據 1", "關鍵細節與數據 2", "關鍵細節 3 (可選)"],
  "industry_impact": "對半導體、AI、供應鏈或相關受惠/受害族群的實質影響評估 (約 60-100 字)",
  "sentiment": "bullish (偏多) / bearish (偏空) / neutral (中性客觀)"
}}
只回傳合法的 JSON 物件，不要有任何多餘的前後文字。
"""
    raw_response = call_gemini(prompt)
    if raw_response:
        try:
            cleaned = clean_json_text(raw_response)
            data = json.loads(cleaned)
            return data
        except Exception as e:
            logger.warning(f"解析 Gemini 快訊 JSON 回應失敗: {e}，原文: {raw_response[:100]}")

    # 若無 API KEY 或解析失敗，提供基線 fallback 結構
    return {
        "significance_score": 4,
        "core_event": f"掌握重大動態：{article_title[:40]}",
        "key_details": [
            "涉及核心追蹤科技標的與供應鏈實體變動",
            "相關業務與市場行情具備高度關注度",
        ],
        "industry_impact": "短期內可能牽動台美相關供應鏈族群與投資人情緒，需留意後續法人評估與法說進一步說明。",
        "sentiment": "neutral",
    }


def summarize_morning(market_data: Dict[str, Any], top_articles: List[Dict[str, Any]]) -> str:
    """
    開盤晨報模式 (Morning Brief)：
    結合美股隔夜四大指數行情、TSM ADR、科技股與精選焦點新聞，產出精闢的前瞻解讀。
    """
    market_summary_lines = []
    for item in market_data.get("indices", []):
        sign = "+" if item.get("change_percent", 0) >= 0 else ""
        market_summary_lines.append(f"- {item['name']}: {item['price']} ({sign}{item['change_percent']}%)")
    
    tsm = market_data.get("tsm_adr", {})
    tsm_line = f"台積電 ADR (TSM): {tsm.get('price')} (漲跌: {tsm.get('change_percent')}%)"

    articles_text = ""
    for idx, art in enumerate(top_articles[:3], 1):
        articles_text += f"{idx}. 【{art.get('source')}】{art.get('title')}\n"

    prompt = f"""
你是一位資深台美股市策略分析師。請為投資人撰寫「台股開盤晨報 (Morning Brief)」重點前瞻。

【隔夜市場行情】
{chr(10).join(market_summary_lines)}
{tsm_line}

【精選產業焦點新聞】
{articles_text}

請以繁體中文撰寫，包含以下三個結構化段落（精簡俐落，採用 Markdown 條列格式）：
1. 🌐 **隔夜美股動態與半導體表現**：總結美股指數漲跌主因與科技族群氣氛。
2. 🇹🇼 **台股開盤前瞻與重要指標**：以台積電 ADR 表現與國際半導體走勢，客觀前瞻今日台股加權指數與電子權值股開盤可能氣氛。
3. 🔍 **今日焦點關鍵事件**：挑選 1-2 則最關鍵焦點提點。

字數控制在 250~350 字之間，語氣專業客觀。
"""
    response = call_gemini(prompt)
    if response:
        return response.strip()

    # Fallback 預設摘要
    return f"""
🌐 **隔夜美股動態與半導體表現**
美股四大指數維持震盪整理，投資人持續消化總體經濟數據與主要科技巨頭獲利預期。半導體族群與大型科技權值股維持健康輪動。

🇹🇼 **台股開盤前瞻與重要指標**
{tsm_line}。在美股科技權值指引下，預期今日台股開盤以電子代工及先進製程族群為盤面中樞，觀察外資早盤資金流向。

🔍 **今日焦點關鍵事件**
密切追蹤半導體封測與 AI 伺服器供應鏈後續訂單動能，並留意主要央行利率會議與最新通膨預期。
""".strip()


def summarize_wrap(market_data: Dict[str, Any], top_articles: List[Dict[str, Any]]) -> str:
    """
    盤後綜述模式 (Market Wrap)：
    結合台股收盤點數、權值股表現與焦點新聞，產出盤後總結與晚間美股前瞻。
    """
    tw_index = market_data.get("tw_index", {})
    sign = "+" if tw_index.get("change_percent", 0) >= 0 else ""
    tw_index_line = f"加權指數收盤: {tw_index.get('price')} 點 ({sign}{tw_index.get('change_percent')}%)"

    tw_stocks_lines = []
    for item in market_data.get("tw_stocks", []):
        s_sign = "+" if item.get("change_percent", 0) >= 0 else ""
        tw_stocks_lines.append(f"- {item['name']}: {item['price']} ({s_sign}{item['change_percent']}%)")

    articles_text = ""
    for idx, art in enumerate(top_articles[:3], 1):
        articles_text += f"{idx}. 【{art.get('source')}】{art.get('title')}\n"

    prompt = f"""
你是一位專業盤後分析師。請為投資人撰寫「台股盤後綜述與美股開盤前瞻 (Market Wrap)」。

【今日台股行情數據】
{tw_index_line}
{chr(10).join(tw_stocks_lines)}

【今日焦點動態】
{articles_text}

請以繁體中文撰寫，包含以下三個段落（精簡條列）：
1. 📊 **台股盤後結構總結**：總結加權指數與代表權值股之強弱表現。
2. 💡 **族群脈絡與焦點新聞**：結合今日新聞歸納資金聚焦重點與供應鏈焦點。
3. 🇺🇸 **今晚美股開盤前瞻**：提醒今晚美股開盤重點關注指標（如期指、財報或經濟數據）。

字數控制在 250~350 字之間，客觀專業。
"""
    response = call_gemini(prompt)
    if response:
        return response.strip()

    return f"""
📊 **台股盤後結構總結**
{tw_index_line}。權值龍頭股表現持穩，電子權值股發揮撐盤要角，中小型題材股依個別題材展現輪動節奏。

💡 **族群脈絡與焦點新聞**
今日市場資金重點聚焦於高速運算、AI 相關零組件與先進封裝供應鏈，供應鏈訂單能見度維持良好。

🇺🇸 **今晚美股開盤前瞻**
今晚留意美股期貨電子盤與科技龍頭股開盤表現，持續觀察美國重要總經數據與美債殖利率波動對全球資金之影響。
""".strip()


def summarize_weekly(articles: List[Dict[str, Any]]) -> str:
    """
    週末產業週報 (Weekly Deep-dive)：
    針對過去 7 天記錄之歷史文章，進行跨事件宏觀歸納，提煉出「本週 3 大核心產業技術與供應鏈動向總結」。
    """
    if not articles:
        return "本週資料庫無足夠歷史記錄進行跨事件綜述。"

    news_digest = ""
    for idx, art in enumerate(articles[:15], 1):
        news_digest += f"{idx}. [{art.get('source', '')}] {art.get('title', '')}: {art.get('summary_markdown', '')[:80]}\n"

    prompt = f"""
你是一位高階科技產業投資與研究總監。以下是過去 7 天在半導體、AI 與全球科技供應鏈中記錄的重要事件清單：

{news_digest}

請進行深度的跨事件宏觀歸納，提煉出「本週 3 大核心產業技術與供應鏈動向總結」。

格式要求（繁體中文）：
### 🚀 趨勢一：[明確的趨勢主題]
- **核心脈絡**：歸納本週發生的關鍵轉折。
- **供應鏈意涵**：對台美晶圓代工、設備或算力生態系的長遠影響。

### ⚡ 趨勢二：[明確的趨勢主題]
- **核心脈絡**：...
- **供應鏈意涵**：...

### 🌐 趨勢三：[明確的趨勢主題]
- **核心脈絡**：...
- **供應鏈意涵**：...

請直接輸出歸納內容，字數約 350~500 字，具備高度洞察力，避免空泛描述。
"""
    response = call_gemini(prompt)
    if response:
        return response.strip()

    return f"""
### 🚀 趨勢一：先進製程與高階封裝產能維持高負載
- **核心脈絡**：全球雲端巨頭持續擴充算力基礎建設，CoWoS 等先進封裝供需依然緊俏。
- **供應鏈意涵**：台系設備與載板封測廠商具備長期營運動能支撐。

### ⚡ 趨勢二：端側 AI 應用與消費電子規格升級加速
- **核心脈絡**：晶片大廠紛紛推出整合 NPU 之新世代處理器架構。
- **供應鏈意涵**：驅動終端換機週期與散熱、記憶體頻寬升級需求。

### 🌐 趨勢三：地緣戰略與跨國供應鏈多元布局常態化
- **核心脈絡**：各國晶片法案與海外設廠進展持續推動半導體供應鏈重構。
- **供應鏈意涵**：具備海外建廠服務能力之供應鏈夥伴將享有更高戰略溢價。
""".strip()
