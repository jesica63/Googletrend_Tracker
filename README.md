---
### English Summary
This is an automated Python script that tracks Top 10 trending keywords from Google Trends for the Taiwan region. It cross-references these keywords with real-time news from ETtoday News to identify the potential stories behind the trends. When a match is found, it sends an email notification and archives the results to Google Sheets.

**Key Technologies:** `Python`, `Google Trends RSS`, `Feedparser`, `GSpread`, `GitHub Actions`, `Gemini AI`
---
# 🚀 Google Trends 台灣地區趨勢追蹤器 (Google Trends Tracker for Taiwan)

這是一個自動化的 Python 腳本，旨在解決一個核心問題：**「當一個關鍵字在 Google Trends 上爆紅時，它背後真正的原因是什麼？」**

此專案會定時抓取台灣地區的 Google Trends 熱門關鍵字，並自動與 ETtoday 新聞雲的即時新聞進行交叉比對，試圖找出兩者之間的關聯。當成功找到關聯時，系統會自動發送郵件通知，讓您在第一時間掌握輿情脈動。

---

## ✨ 功能亮點 (Features)

*   **自動化趨勢監控**：定時（預設為每小時）從 Google Trends 抓取最新的熱門搜尋關鍵字。
*   **智慧新聞比對 (V2.0 優化版)**：
    *   採用五級評分系統 (120/100/80/60/20 分)，提供更精確的匹配結果
    *   優先匹配完整詞組，準確度提升至 75-85%
    *   自動與預先載入的 **ETtoday 多分類新聞資料庫**進行智慧關鍵字比對
    *   支援調試信息，顯示每次匹配的分數
*   **AI 生成讀者好奇問題**：使用 Gemini AI 自動生成讀者可能好奇的三個問題
*   **統一郵件通知**：只要找到與 ETtoday 的關聯，就會觸發郵件通知，並將所有成功匹配的結果匯總在一封郵件中。
*   **雙工作表歸檔 (Dual-Sheet Archiving)**：
    *   **最新趨勢儀表板**：一個永遠只顯示最新一輪執行結果的乾淨儀表板。
    *   **完整歷史日誌**：一個以附加模式（Append Mode）永久保存每一次執行結果的完整日誌，供未來分析使用。
*   **為自動化而生**：腳本設計強健，能優雅處理外部 RSS Feed 可能的格式錯誤，並已針對 GitHub Actions 的無狀態執行環境進行了優化。

---

## ⚙️ 運作流程 (How It Works)

每一次的自動化執行都會遵循以下步驟：

1.  **預載新聞資料庫**：啟動時，腳本會先抓取所有指定的 ETtoday RSS Feeds（包含即時、政治、財經、國際、社會、生活、影劇、運動、旅遊、3C、AI 等分類），並在記憶體中建立一個強健、容錯的即時新聞資料庫。
2.  **抓取趨勢關鍵字**：接著，腳本會從 Google Trends 的 RSS Feed 中獲取當前的熱門關鍵字列表。
3.  **逐一交叉比對 (V2.0 優化演算法)**：對於每一個熱門關鍵字，腳本會執行智慧比對邏輯：
    a. **優先檢查**自建的 ETtoday 資料庫，使用五級評分系統進行匹配
    b. **等級 1 (120分)**：完整詞組在標題中
    c. **等級 2 (100分)**：拆分詞全在標題中
    d. **等級 3 (80分)**：所有關鍵字在標題中
    e. **等級 4 (60分)**：完整詞組在摘要中
    f. **等級 5 (20分)**：拆分詞在標題+摘要中
    g. 如果自建資料庫未找到，則檢查 Google 是否直接提供了來源為「ETtoday」的新聞
4.  **AI 生成好奇問題**：對於成功匹配的新聞，使用 Gemini AI 生成三個讀者可能好奇的問題
5.  **觸發郵件通知**：只要在步驟 3 中有任何一個比對成功，該項目就會被加入待發送的郵件列表中。
6.  **寫入 Google Sheet**：將本次執行的所有結果，同時以「清空後寫入」的方式更新儀表板，並以「附加」的方式寫入歷史日誌。
7.  **發送郵件**：如果郵件列表不為空，則將所有成功匹配的項目格式化成一封摘要郵件，並發送出去。

---

## 🛠️ 設定與安裝 (Setup & Installation)

要讓這個專案運行起來，您需要完成以下設定。

### 1. 準備專案檔案

*   **`trend_tracker.py`**: 本專案的核心 Python 腳本。
*   **`requirements.txt`**: 一個純文字檔，內容如下，用於告訴 GitHub 需要安裝哪些函式庫：
    ```
    pandas
    gspread
    gspread-dataframe
    google-auth-oauthlib
    openpyxl
    feedparser
    ```

### 2. 設定 GitHub Actions Workflow

在您的專案中，建立一個路徑為 `.github/workflows/main.yml` 的檔案，這個檔案負責定義自動化排程。您可以參考我們討論中的版本，設定好排程時間（例如 `cron: '0 * * * *'` 代表每小時執行一次）。

### 3. 設定 GitHub Secrets

這是最關鍵的一步。請到您專案的 **Settings > Secrets and variables > Actions** 頁面，新增以下五個 Repository Secrets。

| Secret Name                 | Description                                    | Example Value                               |
| --------------------------- | ---------------------------------------------- | ------------------------------------------- |
| `GCP_SA_KEY`                | 您從 Google Cloud Platform 下載的服務帳戶 JSON 金鑰的**完整內容**。 | `{"type": "service_account", "project_id": ...}` |
| `G_SHEET_ID`                | 您要寫入的 Google Sheet 的 ID (網址中那串亂碼)。      | `1Ze1Jv2_uoY_r7jphcQv_GXEJK51t6qq53g4qpKQ3pBo` |
| `EMAIL_SENDER`              | 您用來寄送通知的 Gmail 信箱。                     | `youremail@gmail.com`                         |
| `EMAIL_RECEIVER`            | 您用來接收通知的信箱。                           | `yourpersonal.email@example.com`              |
| `EMAIL_SENDER_APP_PASSWORD` | 您為此腳本產生的 16 位 Gmail **應用程式密碼**。     | `abcd efgh ijkl mnop`                       |
| `GEMINI_API_KEY`            | Google Gemini API 金鑰（用於生成好奇問題）。        | `AIzaSy...`                                  |
| `GEMINI_PROMPT`             | Gemini AI 的提示詞模板（用於生成問題）。           | 您的自訂提示詞                                 |

> ⚠️ **重要安全警告**
>
> **切勿**將您的任何密鑰或憑證直接寫在程式碼中！`trend_tracker.py` 腳本被設計為從安全的環境變數中讀取這些密鑰。請務必使用 GitHub Secrets 來管理它們。在公開您的專案之前，請務必再次檢查您的 Git 歷史紀錄，確保從未有任何敏感資訊被意外提交過。

---

## 🚀 使用方式 (Usage)

一旦您設定好 GitHub Actions 和所有必要的 Secrets，這個腳本將會根據您在 `.yml` 檔案中設定的 `schedule` 自動執行。

您也可以隨時到專案的 **Actions** 頁面，手動觸發 `workflow_dispatch` 來立即執行一次測試。

---

## 📄 授權 (License)

本專案採用 MIT 授權。詳情請見 `LICENSE` 檔案。
