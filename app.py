import io
import os
import tempfile
import warnings
from pathlib import Path

import gradio as gr
import pandas as pd
import requests
import urllib3
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ------------------------------------------------------------------
# 設定（皆可用 Render 的環境變數覆蓋）
# ------------------------------------------------------------------
URL = os.getenv(
    "DATA_URL",
    "https://data.tainan.gov.tw/File/ResourceCsvDownload/6c16b2c8-92b6-49d9-98b5-02966462172c",
)
VERIFY_SSL = os.getenv("VERIFY_SSL", "false").lower() == "true"
ENCODINGS = ["utf-8-sig", "utf-8", "big5", "cp950"]  # 編碼備援
TITLE = os.getenv("APP_TITLE", "臺南市開放資料瀏覽器")

BASE_DIR = Path(__file__).resolve().parent
PWA_DIR = BASE_DIR / "static"

if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

_cache = {"df": None}


# ------------------------------------------------------------------
# 資料處理
# ------------------------------------------------------------------
def read_csv_safe(content: bytes) -> pd.DataFrame:
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise ValueError(f"無法解析 CSV（已嘗試 {ENCODINGS}）：{last_err}")


def get_df(force: bool = False) -> pd.DataFrame:
    """下載並讀取資料；force=True 時重新下載。"""
    if force or _cache["df"] is None:
        response = requests.get(URL, verify=VERIFY_SSL, timeout=30)
        response.raise_for_status()
        raw = read_csv_safe(response.content)
        df = raw.dropna().reset_index(drop=True)
        if df.empty:  # 欄位多時 dropna() 可能全刪，退而求其次只刪整列皆空
            df = raw.dropna(how="all").reset_index(drop=True)
        if df.empty:
            raise ValueError("資料來源沒有任何資料")
        _cache["df"] = df
    return _cache["df"]


def _col_updates(df: pd.DataFrame):
    cols = list(df.columns)
    return gr.update(choices=cols, value=cols), gr.update(choices=cols, value=cols[0])


def init():
    try:
        return _col_updates(get_df())
    except Exception as e:  # noqa: BLE001
        raise gr.Error(f"資料載入失敗：{e}")


def reload_data():
    try:
        return _col_updates(get_df(force=True))
    except Exception as e:  # noqa: BLE001
        raise gr.Error(f"重新下載失敗：{e}")


def query(keyword, cols):
    """關鍵字搜尋 + 欄位篩選。"""
    try:
        df = get_df()
    except Exception as e:  # noqa: BLE001
        raise gr.Error(f"資料載入失敗：{e}")

    result = df
    keyword = (keyword or "").strip()
    if keyword:
        mask = (
            df.astype(str)
            .apply(lambda col: col.str.contains(keyword, case=False, regex=False))
            .any(axis=1)
        )
        result = df[mask]

    valid_cols = [c for c in (cols or []) if c in result.columns]
    note = ""
    if valid_cols:
        result = result[valid_cols]
    else:
        note = "　⚠️ 未勾選欄位，已顯示全部欄位"

    info = (
        f"### 📊 查詢結果\n"
        f"**符合筆數：** {len(result):,} ／ {len(df):,}　|　"
        f"**顯示欄位：** {result.shape[1]} ／ {df.shape[1]}{note}"
    )

    # 每次產生獨立暫存檔，避免多人使用時互相覆蓋
    fd, out_path = tempfile.mkstemp(suffix=".csv", prefix="filtered_")
    os.close(fd)
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    return info, result, out_path


def analyze(col, topn):
    """統計某欄位出現次數最多的前 N 項。"""
    df = get_df()
    if not col or col not in df.columns:
        empty = pd.DataFrame({"類別": [], "數量": []})
        return empty, empty
    vc = df[col].astype(str).value_counts().head(int(topn)).reset_index()
    vc.columns = ["類別", "數量"]
    return vc, vc


# ------------------------------------------------------------------
# PWA：<head> 注入（manifest、iOS 設定、Service Worker、安裝按鈕）
# ------------------------------------------------------------------
HEAD = """
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#4f46e5">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="南市資料">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="apple-touch-icon" href="/pwa-assets/icons/apple-touch-icon.png">
<script>
  // Gradio 可能在 load 事件之後才注入這段 script，所以要先判斷頁面是否已載入完成
  if ("serviceWorker" in navigator) {
    var regSW = function () {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .then(function (r) { console.log("[PWA] Service Worker 註冊成功", r.scope); })
        .catch(function (err) { console.warn("[PWA] Service Worker 註冊失敗", err); });
    };
    if (document.readyState === "complete") { regSW(); }
    else { window.addEventListener("load", regSW); }
  }

  // 自訂「安裝 App」按鈕（Chrome / Edge / Android；iOS 請用「加入主畫面」）
  var deferredPrompt = null;
  function removeInstallBtn() {
    var b = document.getElementById("pwa-install-btn");
    if (b) b.remove();
  }
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    if (document.getElementById("pwa-install-btn")) return;
    var btn = document.createElement("button");
    btn.id = "pwa-install-btn";
    btn.textContent = "📲 安裝 App";
    btn.onclick = function () {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.finally(function () {
        deferredPrompt = null;
        removeInstallBtn();
      });
    };
    document.body.appendChild(btn);
  });
  window.addEventListener("appinstalled", removeInstallBtn);

  // iOS Safari 不支援 beforeinstallprompt，改顯示「加入主畫面」說明按鈕
  window.addEventListener("load", function () {
    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    var standalone = window.navigator.standalone === true;
    if (isIOS && !standalone) {
      setTimeout(function () {
        if (document.getElementById("pwa-install-btn")) return;
        var btn = document.createElement("button");
        btn.id = "pwa-install-btn";
        btn.textContent = "📲 加入主畫面";
        btn.onclick = function () {
          alert("請點 Safari 下方的「分享」按鈕，再選「加入主畫面」。");
        };
        document.body.appendChild(btn);
      }, 1500);
    }
  });
</script>
"""

# ------------------------------------------------------------------
# RWD：自訂 CSS
# ------------------------------------------------------------------
CSS = """
.gradio-container {
  max-width: 1200px !important;
  margin: 0 auto !important;
}
.app-title h1 {
  font-size: clamp(1.4rem, 4.5vw, 2.2rem);
  line-height: 1.25;
  margin-bottom: .25rem;
}
.app-title p { font-size: clamp(.9rem, 2.8vw, 1.05rem); opacity: .8; }

.toolbar-row { flex-wrap: wrap !important; gap: 8px !important; }
.toolbar-row > * { min-width: 120px; }

.table-wrap { overflow-x: auto; }

#pwa-install-btn {
  position: fixed; right: 16px; bottom: 16px; z-index: 9999;
  background: #4f46e5; color: #fff; border: 0; border-radius: 999px;
  padding: 12px 20px; font-size: 1rem; min-height: 44px;
  box-shadow: 0 6px 18px rgba(79, 70, 229, .4); cursor: pointer;
}

/* 平板以下 */
@media (max-width: 900px) {
  .gradio-container { padding-left: 10px !important; padding-right: 10px !important; }
}

/* 手機 */
@media (max-width: 640px) {
  .toolbar-row { flex-direction: column !important; }
  .toolbar-row > * { width: 100% !important; flex: 1 1 auto !important; min-width: 0 !important; }
  .gradio-container button, .gradio-container input, .gradio-container select {
    min-height: 44px;  /* 觸控友善 */
  }
  .gradio-container input, .gradio-container textarea { font-size: 16px !important; } /* 避免 iOS 自動放大 */
  .tab-nav button, button[role="tab"] { padding: 10px 12px !important; }
}

/* 以 App 形式開啟時 */
@media (display-mode: standalone) {
  footer { display: none !important; }
}
"""

# ------------------------------------------------------------------
# 介面
# ------------------------------------------------------------------
theme = gr.themes.Soft(primary_hue="indigo", secondary_hue="sky", neutral_hue="slate")

with gr.Blocks(theme=theme, title=TITLE, css=CSS, head=HEAD, fill_width=True) as demo:
    gr.Markdown(
        f"""
        # 🏙️ {TITLE}
        搜尋、篩選、視覺化並下載臺南市政府開放資料
        """,
        elem_classes="app-title",
    )

    with gr.Tabs():
        with gr.TabItem("🔍 資料查詢"):
            with gr.Row(elem_classes="toolbar-row"):
                keyword = gr.Textbox(
                    label="關鍵字搜尋",
                    placeholder="輸入任意文字，會搜尋所有欄位…",
                    scale=4,
                    min_width=240,
                )
                search_btn = gr.Button("搜尋", variant="primary", scale=1, min_width=120)
                reload_btn = gr.Button("🔄 重新下載資料", scale=1, min_width=160)

            cols_box = gr.CheckboxGroup(label="顯示欄位", choices=[], value=[])
            info_md = gr.Markdown()
            table = gr.Dataframe(
                label="資料表",
                interactive=False,
                wrap=True,
                max_height=500,
                elem_classes="table-wrap",
            )
            file_out = gr.File(label="⬇️ 下載查詢結果 (CSV)")

        with gr.TabItem("📈 統計圖表"):
            with gr.Row(elem_classes="toolbar-row"):
                ana_col = gr.Dropdown(label="選擇統計欄位", choices=[], min_width=220)
                topn = gr.Slider(5, 50, value=10, step=1, label="顯示前 N 名", min_width=220)
            plot = gr.BarPlot(
                x="類別",
                y="數量",
                sort="-y",
                title="欄位次數分布",
                height=400,
                x_label_angle=-30,  # 手機上長標籤不重疊
                label="長條圖",
            )
            stat_table = gr.Dataframe(
                label="統計明細", interactive=False, elem_classes="table-wrap"
            )

    q_inputs = [keyword, cols_box]
    q_outputs = [info_md, table, file_out]
    a_inputs = [ana_col, topn]
    a_outputs = [plot, stat_table]

    # 載入：初始化選單 → 查詢 → 統計
    demo.load(init, outputs=[cols_box, ana_col]).then(
        query, q_inputs, q_outputs
    ).then(analyze, a_inputs, a_outputs)

    search_btn.click(query, q_inputs, q_outputs)
    keyword.submit(query, q_inputs, q_outputs)
    cols_box.input(query, q_inputs, q_outputs)  # 只有使用者操作才觸發

    reload_btn.click(reload_data, outputs=[cols_box, ana_col]).then(
        query, q_inputs, q_outputs
    ).then(analyze, a_inputs, a_outputs)

    ana_col.input(analyze, a_inputs, a_outputs)
    topn.release(analyze, a_inputs, a_outputs)  # 放開滑鼠才觸發


# ------------------------------------------------------------------
# FastAPI：提供 PWA 檔案（Service Worker 必須由根路徑提供才能控制整站）
# ------------------------------------------------------------------
app = FastAPI(title=TITLE)


def _pwa_file(name: str, media_type: str, headers: dict | None = None):
    path = PWA_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path, media_type=media_type, headers=headers)


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return _pwa_file("manifest.webmanifest", "application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return _pwa_file(
        "sw.js",
        "application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.get("/offline.html", include_in_schema=False)
def offline():
    return _pwa_file("offline.html", "text/html")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


# static/ 缺少時不要讓整個服務崩潰，只是停用 PWA 功能
if PWA_DIR.is_dir():
    app.mount("/pwa-assets", StaticFiles(directory=PWA_DIR), name="pwa-assets")
else:
    print(f"[警告] 找不到 {PWA_DIR}，PWA 功能停用。請確認 static/ 資料夾已上傳到 GitHub。")

_favicon = PWA_DIR / "icons" / "icon-192.png"

# Gradio 掛在根路徑；上面先註冊的路由優先比對
app = gr.mount_gradio_app(
    app,
    demo.queue(),
    path="/",
    favicon_path=str(_favicon) if _favicon.is_file() else None,
    allowed_paths=[tempfile.gettempdir()],
)


if __name__ == "__main__":
    # Render 會提供 PORT 環境變數，且必須綁定 0.0.0.0
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        proxy_headers=True,       # 讓 https 在反向代理後仍被正確識別
        forwarded_allow_ips="*",
    )
