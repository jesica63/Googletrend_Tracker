---
### English Summary
This is an automated Python script that tracks Top 10 trending keywords from Google Trends for the Taiwan region. It cross-references these keywords with real-time news from the Central News Agency (CNA) to identify the potential stories behind the trends. When a match is found, it sends an email notification and archives the results to Google Sheets.

**Key Technologies:** `Python`, `Google Trends RSS`, `Feedparser`, `GSpread`, `GitHub Actions`
---
# 🚀 Google Trends 台灣地區趨勢追蹤器 (Google Trends Tracker for Taiwan)

這是一個自動化的 Python 腳本，旨在解決一個核心問題：**「當一個關鍵字在 Google Trends 上爆紅時，它背後真正的原因是什麼？」**

此專案會定時抓取台灣地區的 Google Trends 熱門關鍵字，並自動與中央社（CNA）的即時新聞進行交叉比對，試圖找出兩者之間的關聯。當成功找到關聯時，系統會自動發送郵件通知，讓您在第一時間掌握輿情脈動。

---

## ✨ 功能亮點 (Features)

*   **自動化趨勢監控**：定時（預設為每小時）從 Google Trends 抓取最新的熱門搜尋關鍵字。
*   **智慧新聞比對**：
    *   優先採用 Google 直接提供的關聯新聞。
    *   當 Google 未提供或來源非中央社時，會自動與預先載入的**中央社多分類新聞資料庫**進行「彈性關鍵字比對」。
*   **統一郵件通知**：無論是 Google 直接提供或是二次比對成功，只要找到與中央社的關聯，就會觸發一次性的郵件通知，並將所有成功匹配的結果匯總在一封郵件中。
*   **雙工作表歸檔 (Dual-Sheet Archiving)**：
    *   **最新趨勢儀表板**：一個永遠只顯示最新一輪執行結果的乾淨儀表板。
    *   **完整歷史日誌**：一個以附加模式（Append Mode）永久保存每一次執行結果的完整日誌，供未來分析使用。
*   **為自動化而生**：腳本設計強健，能優雅處理外部 RSS Feed 可能的格式錯誤，並已針對 GitHub Actions 的無狀態執行環境進行了優化。

---

## ⚙️ 運作流程 (How It Works)

每一次的自動化執行都會遵循以下步驟：

1.  **預載新聞資料庫**：啟動時，腳本會先抓取所有指定的中央社 RSS Feeds，並在記憶體中建立一個強健、容錯的即時新聞資料庫。
2.  **抓取趨勢關鍵字**：接著，腳本會從 Google Trends 的 RSS Feed 中獲取當前的熱門關鍵字列表。
3.  **逐一交叉比對**：對於每一個熱門關鍵字，腳本會執行一個**統一比對邏輯**：
    a. **優先檢查**自建的中央社資料庫，看是否存在標題或摘要包含所有關鍵字的匹配。
    b. 如果上述未找到，則**再次檢查** Google 是否直接提供了一則來源為「中央社」或「CNA」的新聞。
4.  **觸發郵件通知**：只要在步驟 3 中有任何一個比對成功，該項目就會被加入待發送的郵件列表中。
5.  **寫入 Google Sheet**：將本次執行的所有結果，同時以「清空後寫入」的方式更新儀表板，並以「附加」的方式寫入歷史日誌。
6.  **發送郵件**：如果郵件列表不為空，則將所有成功匹配的項目格式化成一封摘要郵件，並發送出去。

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
