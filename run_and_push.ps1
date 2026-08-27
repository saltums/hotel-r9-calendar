# hotel-r9-calendar — ローカル自動実行スクリプト
# タスクスケジューラから呼び出す

$REPO = "C:\Users\sugar\Claude\hotel-r9-calendar"
$PYTHON = "C:\Users\sugar\AppData\Local\Programs\Python\Python312\python.exe"
$GIT = "C:\Program Files\Git\cmd\git.exe"
$LOG = "$REPO\scraper.log"

Set-Location $REPO

# ログ記録開始
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $LOG "===== $timestamp ====="

# スクレイパー実行
Write-Host "スクレイパー起動..."
& $PYTHON "$REPO\scraper.py" 2>&1 | Tee-Object -Append $LOG

# prices.json が更新されたか確認
$diff = & $GIT diff --stat prices.json 2>&1
if ($diff -match "prices.json") {
    Write-Host "prices.json を GitHub へ push..."
    & $GIT add prices.json
    & $GIT commit -m "chore: update prices $(Get-Date -Format 'yyyy-MM-dd HH:mm') JST"
    & $GIT push
    Add-Content $LOG "  -> push 完了"
    Write-Host "push 完了"
} else {
    Write-Host "変更なし (push スキップ)"
    Add-Content $LOG "  -> 変更なし"
}
