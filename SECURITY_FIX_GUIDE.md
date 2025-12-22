# 🔒 安全修復指南 - SEO LazyPack

## 📋 修復內容總覽

本次安全修復解決了三個關鍵安全問題：

1. ✅ **API Key 暴露問題** - 將 Gemini API Key 從前端移至後端
2. ✅ **第三方代理風險** - 使用自建後端爬蟲替換第三方 CORS 代理
3. ✅ **HTML 清理不完整** - 統一使用 DOMPurify 進行 XSS 防護

---

## 🏗️ 新架構說明

### 修復前（不安全）
```
前端瀏覽器
  ├─ 包含 API Key 的 JavaScript Bundle
  ├─ 直接調用 Gemini API
  └─ 使用第三方 CORS 代理爬取網頁
```

### 修復後（安全）
```
前端瀏覽器 (Port 3000)
  └─ 調用 → 後端 API Server (Port 3001)
              ├─ /api/gemini/* (Gemini API 代理)
              ├─ /api/scraper/* (安全爬蟲服務)
              └─ 🔑 API Key 僅存在後端環境
```

---

## 📦 專案結構

```
lazypack1210/
├── backend/               # 🆕 新增後端服務器
│   ├── server.js          # Express 主服務器
│   ├── package.json       # 後端依賴
│   ├── .env.example       # 後端環境變數範例
│   ├── routes/
│   │   ├── gemini.js      # Gemini API 路由
│   │   └── scraper.js     # 爬蟲 API 路由
│   ├── services/
│   │   ├── geminiService.js   # Gemini 業務邏輯
│   │   └── scraperService.js  # 爬蟲業務邏輯
│   └── middleware/
│       └── errorHandler.js    # 錯誤處理
├── services/              # 🔄 修改前端服務層
│   ├── geminiService.ts   # 改為調用後端 API
│   └── curationService.ts # 改為調用後端 API
├── components/
│   └── ResultView.tsx     # 🔄 改用 DOMPurify
├── vite.config.ts         # 🔄 移除 API Key 配置
├── .env.example           # 🆕 前端環境變數範例
└── README.md              # 🔄 更新安裝說明
```

---

## 🚀 安裝與啟動

### 1. 安裝依賴

```bash
# 前端依賴 (根目錄)
npm install

# 後端依賴
cd backend
npm install
cd ..
```

### 2. 配置環境變數

**後端配置** (`backend/.env`):
```bash
cp backend/.env.example backend/.env
nano backend/.env
```

填入您的配置：
```
GEMINI_API_KEY=your_actual_gemini_api_key_here
PORT=3001
NODE_ENV=development
FRONTEND_URL=http://localhost:3000
```

**前端配置** (`.env.local`):
```bash
cp .env.example .env.local
nano .env.local
```

填入：
```
VITE_API_URL=http://localhost:3001
```

### 3. 啟動服務

**方式 A：分別啟動（推薦開發時使用）**

終端 1 - 啟動後端：
```bash
cd backend
npm start
# 或使用 watch 模式: npm run dev
```

終端 2 - 啟動前端：
```bash
npm run dev
```

**方式 B：使用 PM2 同時管理（推薦生產環境）**

```bash
# 安裝 PM2
npm install -g pm2

# 啟動後端
pm2 start backend/server.js --name seo-backend

# 啟動前端
pm2 start "npm run dev" --name seo-frontend

# 查看狀態
pm2 status

# 查看日誌
pm2 logs
```

### 4. 訪問應用

- 前端: http://localhost:3000
- 後端 API: http://localhost:3001
- 健康檢查: http://localhost:3001/health

---

## 🧪 測試安全修復

### 測試 1：驗證 API Key 不再暴露

```bash
# 構建前端
npm run build

# 檢查構建後的文件
grep -r "AIza" dist/

# ✅ 預期結果：找不到任何 Gemini API Key
```

### 測試 2：測試後端 API

```bash
# 測試健康檢查
curl http://localhost:3001/health

# 測試爬蟲服務
curl -X POST http://localhost:3001/api/scraper/fetch \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'

# 測試 Gemini API (需要有效內容)
curl -X POST http://localhost:3001/api/gemini/analyze \
  -H "Content-Type: application/json" \
  -d '{"articleContent":"測試文章", "urlList":[]}'
```

### 測試 3：前端功能測試

1. 訪問 http://localhost:3000
2. 輸入 Sitemap XML 或網址列表
3. 輸入文章內容
4. 點擊「生成內鏈建議」
5. 確認能正常顯示結果

---

## 🌐 生產環境部署

### 後端部署建議

**選項 A：Heroku**
```bash
cd backend
heroku create your-app-name
heroku config:set GEMINI_API_KEY=your_key
heroku config:set FRONTEND_URL=https://your-frontend-url.com
git push heroku main
```

**選項 B：VPS (Ubuntu)**
```bash
# 安裝 Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 部署後端
cd backend
npm install --production
pm2 start server.js --name seo-backend
pm2 startup
pm2 save

# 配置 Nginx 反向代理 (可選)
sudo nano /etc/nginx/sites-available/seo-api
```

### 前端部署建議

**選項 A：Vercel**
```bash
# 在 Vercel Dashboard 中設置環境變數
VITE_API_URL=https://your-backend-api.herokuapp.com

vercel --prod
```

**選項 B：Netlify**
```bash
# netlify.toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

---

## 🔐 安全最佳實踐

### 1. 環境變數管理
- ✅ **切勿**將 `.env` 文件提交到 Git
- ✅ 使用 `.env.example` 作為範本
- ✅ 生產環境使用平台的環境變數管理（如 Heroku Config Vars）

### 2. API 安全
- ✅ 添加請求頻率限制（Rate Limiting）
- ✅ 實作 API 身份驗證（如 JWT）
- ✅ 啟用 HTTPS

### 3. CORS 配置
```javascript
// backend/server.js
const corsOptions = {
  origin: process.env.FRONTEND_URL, // 只允許前端域名
  credentials: true
};
```

---

## 📝 進一步改進建議

### 短期
- [ ] 添加 API 請求日誌記錄
- [ ] 實作錯誤監控 (如 Sentry)
- [ ] 添加單元測試

### 中期
- [ ] 添加用戶身份驗證
- [ ] 實作請求頻率限制
- [ ] 添加 Redis 緩存

### 長期
- [ ] 使用 Docker 容器化
- [ ] 實作 CI/CD 流程
- [ ] 添加效能監控

---

## ❓ 常見問題

### Q1: 為什麼要使用後端 API？
**A:** 前端代碼會被編譯成 JavaScript 發送到用戶瀏覽器，任何人都可以查看。將 API Key 放在後端，只有服務器能訪問，確保安全。

### Q2: 後端爬蟲會不會比第三方代理慢？
**A:** 實際上通常更快，因為：
- 減少了中間轉發環節
- 可以優化爬取邏輯
- 避免第三方服務的限流

### Q3: 如果後端服務掛了怎麼辦？
**A:** 建議：
- 使用 PM2 自動重啟
- 實作健康檢查端點
- 使用負載均衡 (如 Nginx)
- 設置監控告警

### Q4: 成本會增加嗎？
**A:** 基本成本：
- 免費方案：Heroku (後端) + Vercel (前端) = $0/月
- 進階方案：VPS $5-10/月 即可運行

---

## 📞 支持

如有問題，請：
1. 查看本文件的常見問題部分
2. 檢查後端日誌：`pm2 logs`
3. 提交 Issue 到 GitHub

---

**修復完成日期：** 2025-12-22
**版本：** v2.0 (安全加固版)
