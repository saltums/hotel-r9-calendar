# hotel-r9-calendar - local runner for Task Scheduler

$REPO   = "C:\Users\sugar\Claude\hotel-r9-calendar"
$PYTHON = "C:\Users\sugar\AppData\Local\Programs\Python\Python312\python.exe"
$GIT    = "C:\Program Files\Git\cmd\git.exe"
$LOG    = "$REPO\scraper.log"

Set-Location $REPO

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $LOG "===== $timestamp ====="

# UTF-8出力を強制 (Task Schedulerはcp932で起動するためUnicodeエラーになる)
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# スクレイパー実行前に現在の prices.json を prices_prev.json として保存
if (Test-Path "$REPO\prices.json") {
    Copy-Item "$REPO\prices.json" "$REPO\prices_prev.json" -Force
}

Write-Host "scraper start..."
& $PYTHON "$REPO\scraper.py" 2>&1 | Tee-Object -Append $LOG

$diff = & $GIT diff --stat prices.json 2>&1
if ($diff -match "prices.json") {
    Write-Host "pushing to GitHub..."
    & $GIT add prices.json prices_prev.json
    & $GIT commit -m "chore: update prices $(Get-Date -Format 'yyyy-MM-dd HH:mm') JST"
    & $GIT push
    Add-Content $LOG "  -> push done"
    Write-Host "push done"
} else {
    Write-Host "no changes"
    Add-Content $LOG "  -> no changes"
}
