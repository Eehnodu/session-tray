#!/usr/bin/env bash
# 세션 트레이 설치 · 실행(macOS · 소스로) — clone 한 폴더에서:  bash install.sh
# 두 번 실행해도 안전하다(가상환경이 있으면 다시 만들지 않고, 떠 있는 트레이는 끄고 새로 띄운다).
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then uv venv .venv; else python3 -m venv .venv; fi
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -q -r requirements.txt
else
  .venv/bin/python -m pip install -q -r requirements.txt
fi

# tkinter 가 없으면 창을 못 띄운다(Homebrew python 은 python-tk 를 따로 설치)
if ! .venv/bin/python -c "import tkinter" 2>/dev/null; then
  echo "tkinter 가 없습니다. Homebrew 라면: brew install python-tk  (또는 python.org 설치본을 쓰세요)"
  exit 1
fi

# 이 폴더의 트레이가 떠 있으면 끄고 새로 띄운다(다른 프로그램은 건드리지 않는다)
pkill -f "$DIR/session_tray.pyw" 2>/dev/null || true
nohup .venv/bin/python "$DIR/session_tray.pyw" >/dev/null 2>&1 &
echo "세션 트레이를 띄웠습니다. 화면 위 메뉴 막대에서 아이콘을 찾으세요."
echo "로그인 시 자동 실행은 아이콘 메뉴 -> '로그인 시 실행' 으로 켭니다."
