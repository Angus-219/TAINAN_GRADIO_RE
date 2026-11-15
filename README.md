# 🏙️ 臺南市開放資料瀏覽器（PWA + RWD）

以 [Gradio](https://www.gradio.app/) 製作的臺南市政府開放資料瀏覽器，支援 **PWA（可安裝成 App）** 與 **RWD（手機／平板／桌機自適應）**。

## 功能

- 🔍 **資料查詢**：關鍵字搜尋所有欄位、自選顯示欄位、下載篩選後 CSV（UTF-8 BOM，Excel 不亂碼）
- 📈 **統計圖表**：任選欄位，顯示出現次數前 N 名長條圖
- 🔄 **重新下載**：一鍵更新最新資料（平常使用記憶體快取）
- 📲 **PWA**：可安裝到手機主畫面或桌面，以獨立視窗開啟；離線時顯示友善的離線頁
- 📱 **RWD**：手機上工具列自動直向堆疊、按鈕符合觸控尺寸、表格可橫向捲動
- 編碼自動備援（utf-8-sig / utf-8 / big5 / cp950）

## 專案結構

```
.
├── app.py                      # Gradio 介面 + FastAPI（提供 PWA 檔案）
├── requirements.txt
├── render.yaml                 # Render Blueprint（選用）
├── .python-version             # 指定 Python 版本（Render 會讀取）
├── make_icons.py               # 產生 PWA 圖示的工具（選用，需 pillow）
├── .gitignore
├── README.md
└── static/
    ├── manifest.webmanifest    # PWA 設定（名稱、圖示、主題色…）
    ├── sw.js                   # Service Worker（由 /sw.js 提供，作用範圍為整站）
    ├── offline.html            # 離線時顯示的頁面
    └── icons/                  # 192 / 512 / maskable / apple-touch-icon
```

> 對外網址：`static/` 資料夾的內容以 `/pwa-assets/` 提供（避免與 Gradio 內建的 `/static` 路徑衝突）。

重新產生圖示：`pip install pillow && python make_icons.py`

## 本機執行

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

開啟 http://localhost:7860（`localhost` 屬於安全環境，PWA 功能可直接測試）。

## 環境變數（皆為選用）

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DATA_URL` | 臺南市資料集網址 | 換成其他 CSV 資料來源 |
| `VERIFY_SSL` | `false` | 設為 `true` 啟用 SSL 憑證驗證 |
| `APP_TITLE` | 臺南市開放資料瀏覽器 | 頁面標題 |
| `PORT` | `7860` | 監聽埠（Render 會自動提供） |

## 安裝成 App

PWA 需要 **HTTPS**（Render 預設提供）。

| 裝置 | 方式 |
|------|------|
| Android Chrome / 桌面 Chrome、Edge | 點畫面右下角「📲 安裝 App」，或網址列的安裝圖示 |
| iPhone / iPad（Safari） | 分享按鈕 →「加入主畫面」 |

## 部署到 Render

### 1. 上傳到 GitHub

**請連同 `static/` 資料夾一起上傳**（內含圖示與 Service Worker）。

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<你的帳號>/<repo名稱>.git
git push -u origin main
```

### 2. 在 Render 建立服務

**方式 A：Blueprint（使用 render.yaml）**

1. Render Dashboard → **New** → **Blueprint**
2. 選擇你的 GitHub repo，按 **Apply**

**方式 B：手動建立 Web Service**

| 欄位 | 值 |
|------|----|
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python app.py` |
| Instance Type | Free |
| Python 版本 | 由 `.python-version` 指定（3.11.9），不需另外設定 |

## 注意事項

- **離線能力有限**：資料需要伺服器即時處理，所以離線時只會顯示離線頁，無法瀏覽資料。
- Render 免費方案閒置約 15 分鐘會休眠，再次開啟需等約 30–60 秒。
- 更新 PWA 檔案（如 `sw.js`）後，請把 `sw.js` 內的 `VERSION` 改成新值（如 `v2`），已安裝的使用者才會更新快取。
- 臺南市資料網站的 SSL 憑證可能無法通過驗證，所以預設 `VERIFY_SSL=false`；若來源憑證正常，建議設為 `true`。
- 免費方案記憶體有限（512 MB），資料集過大時可能無法載入。

## 資料來源

[臺南市政府資料開放平台](https://data.tainan.gov.tw/)
