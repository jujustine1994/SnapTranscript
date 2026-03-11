[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

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
