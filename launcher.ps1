# SnapTranscript 啟動器
# 負責環境檢查、首次安裝說明、建立 venv、啟動主程式

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "SnapTranscript"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Clear-Host
Write-Host "[INFO] Starting SnapTranscript..." -ForegroundColor Green
Write-Host ""

# 偵測系統架構
$isArm64 = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq 'Arm64'

# ======================================
# [1/4] 檢查 Python
# ======================================
Write-Host "[1/4] 檢查 Python 環境..." -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  !! 缺少元件：Python" -ForegroundColor Red
    Write-Host "     Python 是執行 SnapTranscript 的基礎，沒有它程式無法啟動。" -ForegroundColor Gray
    Write-Host ""
    if ($isArm64) {
        Write-Host "  [!] 偵測到您的電腦是 ARM 架構（例如 Snapdragon X 系列筆電）。" -ForegroundColor Yellow
        Write-Host "  [!] 如果您之前已安裝過 Python 但還是看到這個訊息，" -ForegroundColor Yellow
        Write-Host "      請先到「設定 → 應用程式」搜尋 Python 並移除，" -ForegroundColor Yellow
        Write-Host "      移除後重新點兩下啟動檔，我們會自動幫您安裝正確版本。" -ForegroundColor Yellow
        Write-Host ""
    }
    $ans = Read-Host "現在自動安裝 Python？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "[INFO] 透過 winget 安裝 Python，請稍候..." -ForegroundColor Gray
            winget install --id Python.Python.3 -e --silent --accept-source-agreements --accept-package-agreements
        } else {
            Write-Host "[ERROR] 找不到 winget，請手動至 https://www.python.org/ 下載安裝後重新執行。" -ForegroundColor Red
            pause; exit 1
        }
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
            Write-Host ""
            Write-Host "[OK] Python 安裝完成。" -ForegroundColor Green
            Write-Host ""
            Write-Host "  Windows 在安裝新程式後，需要重新開啟視窗才能認到剛裝好的程式。" -ForegroundColor Gray
            Write-Host "  這是 Windows 的正常行為，不是出錯了。" -ForegroundColor Gray
            Write-Host ""
            Write-Host "[INFO] 請關閉此視窗，再重新點兩下啟動檔，安裝流程會從下一步繼續。" -ForegroundColor Yellow
            pause; exit 0
        }
        Write-Host ""
        Write-Host "[OK] Python 安裝完成，按任意鍵繼續..." -ForegroundColor Green
        pause
    } else {
        Write-Host "已取消。" -ForegroundColor Gray; pause; exit 1
    }
} else {
    $pyVer = python --version 2>&1
    Write-Host "[OK] $pyVer 已安裝。" -ForegroundColor Green
}

# ======================================
# [2/4] 檢查 uv
# ======================================
Write-Host "[2/4] 檢查 uv 套件管理工具..." -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  !! 缺少元件：uv" -ForegroundColor Red
    Write-Host "     uv 是用來安裝與管理 Python 套件的工具。" -ForegroundColor Gray
    Write-Host ""
    Write-Host "[INFO] 正在安裝 uv..." -ForegroundColor Yellow
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "[ERROR] uv 安裝失敗，請關閉視窗後重新點兩下啟動檔再試。" -ForegroundColor Red
        pause; exit 1
    }
    Write-Host ""
    Write-Host "[OK] uv 安裝完成，按任意鍵繼續..." -ForegroundColor Green
    pause
} else {
    $uvVer = uv --version
    Write-Host "[OK] $uvVer 已安裝。" -ForegroundColor Green
}

# ======================================
# [3/4] 檢查 ffmpeg
# ======================================
Write-Host "[3/4] 檢查 ffmpeg（音訊處理工具）..." -ForegroundColor Cyan
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  !! 缺少元件：ffmpeg" -ForegroundColor Red
    Write-Host "     ffmpeg 是用來切割音訊檔案的工具，SnapTranscript 的核心功能依賴它。" -ForegroundColor Gray
    Write-Host ""
    $ans = Read-Host "現在自動安裝 ffmpeg？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "[INFO] 透過 winget 安裝 ffmpeg，請稍候（檔案較大，約需 1-2 分鐘）..." -ForegroundColor Gray
            winget install --id Gyan.FFmpeg -e --silent --accept-source-agreements --accept-package-agreements
        } else {
            Write-Host "[ERROR] 找不到 winget，請手動至 https://ffmpeg.org/ 下載安裝後重新執行。" -ForegroundColor Red
            pause; exit 1
        }
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
        if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            Write-Host ""
            Write-Host "[OK] ffmpeg 安裝完成。" -ForegroundColor Green
            Write-Host ""
            Write-Host "  Windows 在安裝新程式後，需要重新開啟視窗才能認到剛裝好的程式。" -ForegroundColor Gray
            Write-Host "  這是 Windows 的正常行為，不是出錯了。" -ForegroundColor Gray
            Write-Host ""
            Write-Host "[INFO] 請關閉此視窗，再重新點兩下啟動檔，安裝流程會從下一步繼續。" -ForegroundColor Yellow
            pause; exit 0
        }
        Write-Host ""
        Write-Host "[OK] ffmpeg 安裝完成，按任意鍵繼續..." -ForegroundColor Green
        if ($isArm64) {
            Write-Host "  [!] 注意：ffmpeg 目前沒有 Windows ARM 原生版本，" -ForegroundColor Yellow
            Write-Host "      安裝的是 x64 版本，會透過模擬執行，功能正常但速度略慢。" -ForegroundColor Yellow
        }
        pause
    } else {
        Write-Host "已取消。" -ForegroundColor Gray; pause; exit 1
    }
} else {
    Write-Host "[OK] ffmpeg 已安裝。" -ForegroundColor Green
}

# ======================================
# [4/4] 檢查虛擬環境
# ======================================
Write-Host "[4/4] 檢查虛擬環境..." -ForegroundColor Cyan
if (-not (Test-Path "venv")) {

    # 首次安裝說明
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "    SnapTranscript - 首次安裝說明" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  接下來程式會自動幫你安裝以下東西：" -ForegroundColor White
    Write-Host ""
    Write-Host "  !! 缺少元件：Python 虛擬環境（venv）" -ForegroundColor Red
    Write-Host "     讓這個工具有獨立乾淨的執行空間，不影響電腦其他程式。" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    + google-genai" -ForegroundColor Yellow
    Write-Host "      用來呼叫 Gemini AI 做逐字稿的核心套件" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    + python-dotenv" -ForegroundColor Yellow
    Write-Host "      用來儲存你的 API Key，下次不用重新輸入" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    + yt-dlp" -ForegroundColor Yellow
    Write-Host "      用來下載 YouTube 音訊" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""

    $ans = Read-Host "現在建立虛擬環境並安裝套件？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        Write-Host "[INFO] 建立虛擬環境中..." -ForegroundColor Gray
        uv venv venv
        Write-Host "[INFO] 安裝套件中..." -ForegroundColor Gray
        uv pip install -r requirements.txt --python venv\Scripts\python.exe
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] 套件安裝失敗，請確認網路連線後重新執行。" -ForegroundColor Red
            pause; exit 1
        }
        Write-Host ""
        Write-Host "[OK] 套件安裝完成，按任意鍵繼續..." -ForegroundColor Green
        pause
    } else {
        Write-Host "已取消。請手動執行 uv venv venv 後再重新啟動。" -ForegroundColor Gray
        pause; exit 1
    }
} else {
    Write-Host "[OK] 虛擬環境已就緒，檢查套件更新..." -ForegroundColor Green
    # 清理損壞的 dist-info（METADATA 檔遺失的條目）
    $broken = Get-ChildItem "venv\Lib\site-packages" -Directory -Filter "*dist-info" -ErrorAction SilentlyContinue | Where-Object {
        -not (Test-Path (Join-Path $_.FullName "METADATA"))
    }
    foreach ($dir in $broken) {
        Write-Host "[INFO] 清理損壞的套件資訊：$($dir.Name)" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $dir.FullName
    }
    uv pip install -r requirements.txt --python venv\Scripts\python.exe -q
}

# 啟動虛擬環境
. ".\venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "[START] 啟動中，請保持此視窗開啟..." -ForegroundColor Green
Write-Host ""

# ======================================
# 執行主程式
# ======================================
python main.py
$exitCode = $LASTEXITCODE

if (Test-Path "__pycache__") { Remove-Item -Recurse -Force "__pycache__" }

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] 程式意外停止，請回報上方錯誤訊息。" -ForegroundColor Red
    pause
} else {
    Write-Host ""
    Write-Host "5 秒後自動關閉..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}
