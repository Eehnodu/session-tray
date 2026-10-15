# 세션 트레이 설치 · 실행 — clone 한 폴더에서:
#   powershell -ExecutionPolicy Bypass -File install.ps1
# 두 번 실행해도 안전하다(가상환경이 있으면 다시 만들지 않고, 떠 있는 트레이는 끄고 새로 띄운다).
$ErrorActionPreference = "Stop"
$d = $PSScriptRoot
$py = Join-Path $d ".venv\Scripts\python.exe"
$pyw = Join-Path $d ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $py)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv venv (Join-Path $d ".venv")
    } else {
        python -m venv (Join-Path $d ".venv")
    }
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install --python $py --link-mode=copy -q -r (Join-Path $d "requirements.txt")
} else {
    & $py -m pip install -q -r (Join-Path $d "requirements.txt")
}

# 이 폴더의 트레이가 이미 떠 있으면 끄고 새로 띄운다(다른 프로그램은 건드리지 않는다)
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*$d*session_tray.pyw*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Confirm:$false -ErrorAction SilentlyContinue }

Start-Process -FilePath $pyw -ArgumentList "`"$(Join-Path $d 'session_tray.pyw')`"" -WorkingDirectory $d
Write-Host "세션 트레이를 띄웠습니다. 작업 표시줄 오른쪽 ^ 숨김 아이콘에서 찾으세요."
Write-Host "윈도우 시작 시 자동 실행은 아이콘 우클릭 -> '윈도우 시작 시 실행' 으로 켭니다."
