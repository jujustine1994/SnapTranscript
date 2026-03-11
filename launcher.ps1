# SnapTranscript 啟動器
# 負責環境檢查、首次安裝說明、建立 venv、啟動主程式

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "SnapTranscript"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Clear-Host
Write-Host "[INFO] Starting SnapTranscript..." -ForegroundColor Green
Write-Host ""

# ======================================
# [1/3] 檢查 Python
# ======================================
Write-Host "[1/3] 檢查 Python 環境..." -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[WARNING] 找不到 Python，需要安裝才能繼續。" -ForegroundColor Yellow
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
            Write-Host "[INFO] 安裝完成，請關閉視窗後重新點兩下啟動檔。" -ForegroundColor Yellow
            pause; exit 0
        }
        Write-Host "[OK] Python 安裝完成。" -ForegroundColor Green
    } else {
        Write-Host "已取消。" -ForegroundColor Gray; pause; exit 1
    }
} else {
    $pyVer = python --version 2>&1
    Write-Host "[OK] $pyVer 已安裝。" -ForegroundColor Green
}

# ======================================
# [2/3] 檢查 uv
# ======================================
Write-Host "[2/3] 檢查 uv 套件管理工具..." -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[WARNING] 找不到 uv，正在安裝..." -ForegroundColor Yellow
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "[ERROR] uv 安裝失敗，請關閉視窗後重新點兩下啟動檔再試。" -ForegroundColor Red
        pause; exit 1
    }
    Write-Host "[OK] uv 安裝完成。" -ForegroundColor Green
} else {
    $uvVer = uv --version
    Write-Host "[OK] $uvVer 已安裝。" -ForegroundColor Green
}

# ======================================
# [3/3] 檢查虛擬環境
# ======================================
Write-Host "[3/3] 檢查虛擬環境..." -ForegroundColor Cyan
if (-not (Test-Path "venv")) {

    # 首次安裝說明
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "    SnapTranscript - 首次安裝說明" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  接下來程式會自動幫你安裝以下東西：" -ForegroundColor White
    Write-Host ""
    Write-Host "    1. Python 虛擬環境（venv）" -ForegroundColor Yellow
    Write-Host "       讓這個工具有獨立乾淨的執行空間，不影響電腦其他程式" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    2. google-genai" -ForegroundColor Yellow
    Write-Host "       用來呼叫 Gemini AI 做逐字稿的核心套件" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    3. python-dotenv" -ForegroundColor Yellow
    Write-Host "       用來儲存你的 API Key，下次不用重新輸入" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  全程只需要一直按 Enter 同意即可。" -ForegroundColor Green
    Write-Host "  如果有任何疑問，可以把這段說明貼給 AI 詢問。" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""

    $ans = Read-Host "[WARNING] 找不到虛擬環境，現在建立並安裝套件？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        Write-Host "[INFO] 建立虛擬環境中..." -ForegroundColor Gray
        uv venv venv
        Write-Host "[INFO] 安裝套件中..." -ForegroundColor Gray
        uv pip install -r requirements.txt --python venv\Scripts\python.exe
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] 套件安裝失敗，請確認網路連線後重新執行。" -ForegroundColor Red
            pause; exit 1
        }
        Write-Host "[OK] 套件安裝完成。" -ForegroundColor Green
    } else {
        Write-Host "已取消。請手動執行 uv venv venv 後再重新啟動。" -ForegroundColor Gray
        pause; exit 1
    }
} else {
    Write-Host "[OK] 虛擬環境已就緒。" -ForegroundColor Green
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
