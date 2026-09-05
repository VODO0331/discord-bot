# Discord 產業與市場資訊推播機器人規格書 (spec.md)

## 1\. 專案概述 (Overview)

### 1.1 專案目的

本專案為一款部署於 Discord 的智慧資訊推播與查詢機器人，旨在自動化追蹤、彙整並發送近期的全球總體經濟、特定產業趨勢（如半導體、AI、綠能等）以及關鍵市場動態。透過結構化的富文本（Embeds）與 AI 輔助重點摘要，協助社群成員、投資人與研究員快速掌握市場高價值情報，降低資訊焦慮與雜訊。

### 1.2 產品定位與免責聲明

- **產品定位**：資訊聚合與客觀趨勢摘要工具，非交易執行系統。  
- **免責聲明 (Disclaimer)**：所有推播資訊僅供研究與學習參考，不構成任何形式的投資建議、招攬或財務顧問服務。

### 1.3 核心原則：個人使用與零成本架構 (Zero-Cost Architecture)

全系統設計遵循「零營運成本」原則，優先採用免費開源工具、免費 API 額度（Free Tier）與個人用戶端運行方案，確保在個人使用場景下無需支付任何訂閱或基礎設施費用。

---

## 2\. 系統架構 (System Architecture)

本系統採「無伺服器 (Serverless) 管線」架構設計，運作流程如下：  
\[ GitHub Actions Cron 排程觸發 \]  
          │  
          ▼  
\[ 資料獲取與過濾 (Data Fetching & Filtering) \]  
          │  
          ▼  
\[ Gemini Flash 摘要提煉 (AI Summarization) \]  
          │  
          ▼  
\[ Supabase PostgreSQL 去重與記錄 (Persistence & Deduplication) \]  
          │  
          ▼  
\[ Discord Webhook HTTP POST 渲染推播 (Delivery via Webhook) \]

---

## 3\. 事前準備與外部依賴清單 (Prerequisites & Dependencies)

### 3.1 Discord Webhook 設定

1. **Webhook 整合流程**：  
   - 於 Discord 建立兩個獨立頻道，並分別於「頻道設定 \> 整合」建立 Webhook：  
     - **日報頻道 (Daily Channel)**：接收晨報、盤後綜述、週末產業週報。  
     - **快訊頻道 (Alert Channel)**：專門接收經 LLM 評分 \>= 4 的突發快訊。  
   - 取得對應的 `DISCORD_WEBHOOK_DAILY_URL` 與 `DISCORD_WEBHOOK_ALERT_URL`。此方式免除申請 Bot Token 等繁瑣流程。

### 3.2 資料來源與 API 準備

1. **金融市場數據 (行情與指數)**：  
   - 美股/全球市場：Yahoo Finance (透過開源 `yfinance` 套件，免 API Key)、Alpha Vantage (免費版 API)。  
   - 台股/大中華市場：FinMind 免費版會員 API、證交所 OpenAPI 或 TWSE 報價接口。  
2. **產業新聞與科技動態 (News & RSS)**：  
   - 國際科技/商業新聞 RSS：TechCrunch, Verge, Reuters, Bloomberg, Hacker News。  
   - 台灣科技/財經媒體：數位時代, 科技新報, 經濟日報, 工商時報。  
   - 研報/官方發布：SEC Filings (EDGAR)、公開資訊觀測站 (MOPS) RSS/爬蟲。  
3. **AI / LLM API (智慧摘要與分類)**：  
   - Google AI Studio (Gemini 1.5 Flash 免費額度，每日 1,500 次請求 / 15 RPM) 或 Groq 免費額度。  
   - 鎖定免費模型且不需綁定付費扣款。準備 Prompt 模板，包含「3點條列式摘要」、「產業影響評估」。

### 3.3 運算與基礎設施 (Serverless Infra)

1. **運行環境**：鎖定使用 **GitHub Actions**，透過 YAML 定義排程任務，實現無伺服器運行。  
2. **持久化儲存**：採用 **Supabase Free Tier (PostgreSQL)**。此雲端資料庫用於記錄已發送新聞之雜湊值，防止重複推播，且每日排程任務可防止專案因閒置而休眠。  
   - 儲存各 Discord 伺服器之訂閱頻道設定與自訂追蹤關鍵字。

---

## 4\. 功能規格 (Functional Specifications)

### 4.1 自動推播功能 (Automated Broadcasts)

| 任務名稱 | 頻率 / 時間 (UTC+8) | 內容規格 |
| :---- | :---- | :---- |
| **開盤晨報 (Morning Brief)** | 每日 08:30 | 隔夜美股關鍵指標：四大指數（費半 SOX、那指 IXIC）、美股科技七巨頭動向；台股開盤前瞻：台積電 ADR (TSM)、台指期夜盤漲跌幅；精選 3 則關鍵產業速遞。 |
| **盤後綜述 (Market Wrap)** | 每日 17:30 | 今日台股總結：加權指數收盤點數、漲跌幅、成交量、三大法人買賣超動向（外資、投信、自營商）；今日焦點權值與熱門族群動態；今晚美股開盤前瞻與重要財報/經濟數據行事曆。 |
| **突發快訊 (Breaking Alert)** | 每 30 分鐘掃描一次 | 判定為高度相關之重大收購、重磅產品發表、監管突發政策，推播即時卡片。 |
| **週末產業週報 (Weekly Deep-dive)** | 每週六 10:00 | 系統於每週六 10:00 自動從 Supabase 資料庫撈取過去 7 天記錄之 processed\_articles，由 Gemini Flash 進行跨事件之宏觀歸納，提煉出「本週 3 大核心產業技術與供應鏈動向總結」，並在 Embed 結尾列出 2 篇當週評分最高或影響最廣的焦點文章原始超連結。完全活用資料庫已有數據，免去額外追蹤付費牆長文來源之脆弱性，確保零額外維運成本。 |

### 4.2 自動化單向推播說明

本架構聚焦於自動化單向資訊流（晨報、盤後、每 30 分鐘快訊）。由於採用輕量 Webhook 推播，無需常駐維護雙向 Slash Commands，可達到最簡維運、零營運成本與零休眠之目標。

### 4.3 訊息卡片排版規格 (Discord Embed Specification)

推播訊息必須具備清晰視覺層級，包含以下欄位：

1. **Author / Source**：資料來源媒體名稱與 Favicon。  
2. **Title**：新聞/研報原始標題（超連結連至原始來源）。  
3. **Description (AI 提煉重點)**：  
   - 📌 **核心事件**：一句話總結事件核心。  
   - 💡 **關鍵細節**：2\~3 點重要數據或商業動向。  
   - 📊 **市場與產業影響**：潛在受益/受害族群或供應鏈漣漪效應。  
4. **Fields (量化指標)**：相關股票代號（Ticker）、當前行情變動、產業標籤（Tags）。  
5. **Color Coding**：  
   - 綠色 (`#2ECC71`)：正面偏多消息 / 盤勢上漲。  
   - 紅色 (`#E74C3C`)：負面偏空消息 / 盤勢下跌。  
   - 藍色 (`#3498DB`)：客觀產業技術進展 / 總經數據。  
6. **Footer**：發布時間戳記與免責警語。

---

## 5\. 資料處理與去重邏輯 (Data Pipeline & Deduplication)

1. **去重機制 (Deduplication)**：  
   - **一級去重**：針對新聞原始 URL 進行 SHA-256 雜湊，比對近 14 天內的資料庫記錄。  
   - **二級語意去重**：多家媒體常報導同一則公關稿或突發新聞，比對標題 Levenshtein Distance 或利用 Embedding 計算餘弦相似度（Cosine Similarity \> 0.88），僅保留最完整或首發報導。  
2. **雙階段過濾決策 (Two-Stage Pipeline)**  
   - **第一階段（零 Token 規則過濾）**：比對核心追蹤標的（如台積電、輝達、聯準會、OpenAI 等）與重大事件關鍵字（收購、併購、制裁、降息/升息、重大財報變動、法規突發），未命中者直接略過。  
   - **第二階段（LLM 嚴重性評分）**：僅命中第一階段者送交 Gemini Flash，要求評估市場震撼度（1～5 分），僅達 4 分以上且有實質產業影響者才觸發突發快訊推播。  
   - **免費額度保護機制**：限制定時排程頻率（例如每 30 分鐘或每日定時抓取），嚴格控制 API 呼叫次數以避免觸發 LLM 或新聞端之 Rate Limit。

### 5.3 內文萃取與降級容錯 (Article Extraction & Fallback)

3. 針對通過一級過濾之候選文章，優先調用 trafilatura 套件抓取新聞網頁之完整純文字內文，去除廣告與導航雜訊後傳入 Gemini Flash，以確保具備具體財報數字與深入細節。  
4. 降級容錯機制：若目標新聞站點發生 HTTP 403 (防爬蟲)、逾時或內文為空，系統自動優雅降級使用 RSS 原有的 Description / Summary 欄位進行摘要，確保排程流程永不中斷。

---

## 6\. 資料庫結構 (Database Schema)

採用關聯式資料庫（如 Supabase PostgreSQL）記錄已發送新聞，以確保「去重機制」之運作。由於本系統採個人 Webhook 固定頻道架構，無需維護動態頻道訂閱表（channel\_subscriptions），僅需單一表格儲存文章雜湊值與處理狀態。

### 6.1 持久化數據表：`processed_articles`

- `id` (INTEGER / UUID, PK)  
- `url_hash` (VARCHAR(64), UNIQUE, INDEX)  
- `title` (TEXT)  
- `source` (VARCHAR(64))  
- `published_at` (TIMESTAMP)  
- `category` (VARCHAR(32))  
- `summary_markdown` (TEXT)  
- `created_at` (TIMESTAMP, DEFAULT NOW)

**資料清理政策 (Retention Policy)**：系統將保留最近 30 天內的紀錄，超出此範圍之雜湊值將自動清除，以節省資料庫儲存空間並維持比對效能。

### 6.2 靜態宣告式設定 (config.yaml)

系統的核心邏輯與追蹤清單採靜態設定檔管理，定義於 `config.yaml` 中，包含以下關鍵欄位：

- **watchlist**：定義核心監控標的（如 Ticker、公司名稱）。  
- **rss\_feeds**：條列須抓取的國際與台灣媒體 RSS 來源網址。  
- **alert\_keywords**：設定觸發「突發快訊」的一級過濾關鍵字規則（如併購、降息、法規突發等）。

---

## 7\. 環境變數與機密設定 (GitHub Secrets)

請於 GitHub Repository Secrets 中設定以下變數：  
`DISCORD_WEBHOOK_DAILY_URL`、`DISCORD_WEBHOOK_ALERT_URL`、`LLM_API_KEY`、`LLM_PROVIDER` (gemini)、`SUPABASE_URL`、`SUPABASE_KEY`。  
**獨立專責工作流 (Dedicated Workflows)**

系統於 `.github/workflows/` 下將依任務拆分為四個專門檔案，分別以 CLI 參數 `--mode` 驅動 `main.py`，且均設定 `workflow_dispatch` 以支援手動觸發：

- `alert.yml`：`cron: '*/30 * * * *'` \-\> `python main.py --mode alert`  
- `morning_brief.yml`：`cron: '30 0 * * 1-5'` \-\> `python main.py --mode morning`  
- `market_wrap.yml`：`cron: '30 9 * * 1-5'` \-\> `python main.py --mode wrap`  
- `weekly_deepdive.yml`：`cron: '0 2 * * 6'` \-\> `python main.py --mode weekly`

## 8\. 驗收標準與測試計畫 (Acceptance Criteria & Testing)

1. **GitHub Actions 執行成功率**：自動化管線需能依排程穩定啟動並完成資料處理流程。  
2. **Webhook 推播狀態**：發送訊息後需接收到 Discord Webhook 回傳之 HTTP 204 成功代碼。  
3. **Supabase 去重有效性**：系統需準確比對資料庫記錄，確保 24 小時內同一新聞事件不重複推播。  
4. **排版格式合規**：Embed 卡片在 PC 與手機端 Discord UI 均能正常換行與縮放，無破損欄位。  
5. **例外隔離**：單一新聞來源 API 逾時或抓取失敗時，不得阻斷整體排程管線，需記錄 Log 並優雅降級（Graceful Degradation）略過該來源。

### 8.2 本機除錯與 Dry-Run 測試規範

6. **CLI 旗標**：支援 `--dry-run`（例如：`python main.py --mode morning --dry-run`）。  
7. **行為定義**：完整執行資料抓取、雙階段過濾與 Gemini 摘要生成，但跳過 HTTP POST 推播至 Discord Webhook，改將組裝後的 Embed JSON 格式化印出於終端機；同時跳過寫入 Supabase，確保本機測試與 CI 驗證時不污染資料庫與 Discord 頻道。

