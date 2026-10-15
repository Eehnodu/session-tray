<p align="center">
  <img src="assets/icon.png" width="96" alt="세션 트레이 아이콘">
</p>

<h1 align="center">세션 트레이</h1>

<p align="center">
  작업 표시줄 · 메뉴 막대 아이콘 하나로<br>
  <b>지금 내 PC 에서 돌아가는 개발 서버 · 백그라운드 작업 · Claude Code 세션</b>과 CPU · 메모리를 한눈에.
</p>

<p align="center">
  <a href="https://github.com/Eehnodu/session-tray/releases/latest"><img src="https://img.shields.io/github/v/release/Eehnodu/session-tray?label=%EB%B2%84%EC%A0%84&color=4338ca" alt="버전"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%C2%B7%2011-0078d4" alt="Windows">
  <img src="https://img.shields.io/badge/macOS-12%2B-000000" alt="macOS">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776ab" alt="Python">
  <a href="LICENSE"><img src="https://img.shields.io/badge/%EB%9D%BC%EC%9D%B4%EC%84%A0%EC%8A%A4-MIT-16a34a" alt="MIT"></a>
</p>

<p align="center">
  <img src="assets/window.png" alt="세션 보기 창(예시 데이터)">
</p>

---

## 활용 예시

- 터미널을 여러 개 띄워 두다 보니 **어느 프로젝트의 서버가 몇 번 포트에 떠 있는지** 헷갈릴 때
- 끈 줄 알았던 `node` · `python` 이 뒤에서 계속 돌며 **메모리를 먹고 있을 때**
- Claude Code 세션을 여러 개 열어 두고 **지금 어느 폴더에서 무슨 작업이 돌아가는지** 보고 싶을 때

## 주요 기능

| | |
|---|---|
| **개발 서버** | 포트를 열고 있는 node · python · java 등을 프로젝트 이름 · 포트와 함께 보여 줍니다 |
| **백그라운드 작업** | 포트 없이 도는 스크립트(봇 · 스캐너 · 워커)도 따로 모아 보여 줍니다 |
| **Claude Code 세션** | 최근 15분 안에 대화가 오간 세션을 제목 · 폴더와 함께 보여 줍니다 |
| **사용량** | 항목마다 CPU % · 메모리(자식 프로세스 포함), 위쪽에 PC 전체 사용량 |
| **바로 동작** | 브라우저로 열기 · 폴더 열기 · 줄 끝 빨간 **종료**(확인 후 그 프로세스만) |
| **아이콘 상태** | <img src="assets/states.png" height="40" align="center" alt="아이콘 상태"> 점 없음 = 아무것도 안 돎 · 초록 = 서버 있음 · 주황 = 작업만 |

## 설치

### Windows

1. **[SessionTray-windows.exe 내려받기](https://github.com/Eehnodu/session-tray/releases/latest/download/SessionTray-windows.exe)**
2. 내려받은 파일을 원하는 폴더(예: `문서\세션트레이`)에 두고 더블클릭
   - "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행** (개인 개발 프로그램이라 서명이 없어서 뜹니다)
3. 작업 표시줄 오른쪽 **`^`(숨김 아이콘)** 에서 남색 아이콘을 찾습니다
4. 아이콘 **우클릭 → 세션 보기**
5. 컴퓨터를 켤 때마다 띄우려면 우클릭 → **윈도우 시작 시 실행**

### macOS

맥은 설치 프로그램을 돌리지 않고, 앱 파일 하나를 폴더에 넣으면 설치가 끝납니다.

1. **내려받기** — **[SessionTray-macos.zip 내려받기](https://github.com/Eehnodu/session-tray/releases/latest/download/SessionTray-macos.zip)** 를 누르면 **다운로드** 폴더에 저장됩니다(Dock 의 다운로드 폴더 · Finder 왼쪽 "다운로드")
2. **압축 풀기** — 받은 zip 파일을 더블클릭하면 바로 옆에 `Session Tray` 앱이 생깁니다. 사파리로 받았다면 이미 풀려 있을 수 있습니다
3. **응용 프로그램 폴더로 옮기기**(권장) — Finder 창 왼쪽의 **응용 프로그램** 으로 `Session Tray` 를 끌어다 놓습니다. 윈도우에서 프로그램을 설치하는 것과 같고, 이렇게 두면 Launchpad 에서도 찾을 수 있습니다. 옮기지 않고 다운로드 폴더에서 바로 실행해도 됩니다
4. **처음 열기** — `Session Tray` 를 더블클릭합니다. 처음 한 번은 맥이 막습니다(애플 정식 인증을 받지 않은 앱이라서 — 인터넷에서 받은 작은 앱들이 대부분 그렇습니다)
   - **"악성 코드가 없음을 확인할 수 없습니다"** 창이 뜨면 **완료**(또는 확인)를 누르고
   - **시스템 설정 → 개인정보 보호 및 보안** 으로 가서 아래쪽 **"Session Tray" 이(가) 차단되었습니다** 옆의 **그래도 열기** → 맥 암호 → **열기**
   - macOS 14(소노마) 이하라면 `Session Tray` 를 **우클릭 → 열기 → 열기** 로도 됩니다
   - 한 번 열고 나면 다음부터는 그냥 더블클릭으로 열립니다
5. **쓰기** — 화면 맨 위 **메뉴 막대**(시계 왼쪽)에 생긴 아이콘을 눌러 **세션 보기**
6. 로그인할 때마다 저절로 띄우려면 아이콘 메뉴 → **로그인 시 실행**


## 소스 코드로 실행

필요한 것: Python 3.10 이상, git. `uv` 가 있으면 더 빠릅니다.

```powershell
# Windows
git clone https://github.com/Eehnodu/session-tray.git
cd session-tray
powershell -ExecutionPolicy Bypass -File install.ps1
```

```bash
# macOS
git clone https://github.com/Eehnodu/session-tray.git
cd session-tray
bash install.sh
```

두 스크립트 모두 가상환경 · 의존성(`pystray` · `psutil` · `Pillow`)을 설치하고 트레이를 띄웁니다. 다시 실행하면 떠 있는 트레이를 끄고 새로 띄우므로, 업데이트는 `git pull` 뒤 한 번 더 실행하면 됩니다.

| 명령 | 하는 일 |
|---|---|
| `python session_tray.pyw` | 트레이 띄우기(Windows 는 `pythonw` 로 띄우면 콘솔 창이 없습니다) |
| `python session_tray.pyw --window --demo` | 예시 데이터로 창만 띄우기 |
| `python session_tray.pyw --selftest` | 화면 없이 점검(목록 읽기 · 아이콘 · tkinter) |

## 사용 방법

- 아이콘 **우클릭 → 세션 보기**(Windows 는 아이콘 더블클릭도 같다). 창은 5초마다 새로 읽습니다
- 서버 · 작업 줄 끝의 빨간 **종료** → 확인하면 그 프로세스와 자식만 끕니다. Claude 세션은 Claude 에서 닫으세요
- 줄 **우클릭**(macOS 는 Control+클릭): 브라우저로 열기 · 폴더 열기 · 종료
- 줄 **더블클릭**: 서버면 브라우저로, 아니면 폴더를 엽니다
- 아이콘에 마우스를 올리면 개수와 PC 전체 사용량이 보입니다
- 아이콘 메뉴 **트레이 끄기**: 이 프로그램만 끕니다(돌던 서버 · 작업은 그대로)

## 감지 기준

| 구분 | 기준 |
|---|---|
| 개발 서버 | node · python · java · deno · bun · ruby · php · go 가 1024 ~ 49151 포트를 열고 있음 |
| 백그라운드 작업 | 사용자 폴더 아래(`~/dev` · `~/source/repos` · `~/projects` · `~/Documents` · `~/Desktop` 등)에서 도는데 포트가 없음 |
| Claude Code 세션 | `~/.claude/projects` 의 대화 기록이 최근 15분 안에 바뀜 — 이름은 바꾼 제목, 없으면 자동 제목 |

- 같은 일을 하는 자식 프로세스(`.venv` 런처 → 실제 python, `npm` → `vite` 등)는 한 줄로 묶고, 포트 · 사용량은 합쳐서 보입니다
- 편집기 · 앱 내부 도구(AppData · `~/Library` · `/Applications` · `.vscode` 등)는 뺍니다
- 모든 정보는 내 PC 안에서만 읽고, 어디로도 보내지 않습니다

## 문제 해결

| 증상 | 확인 |
|---|---|
| 아이콘이 안 보임 | Windows: `^` 숨김 아이콘 안을 보세요(끌어서 작업 표시줄로 꺼낼 수 있습니다) |
| 창이 안 뜸 · 갑자기 꺼짐 | 마지막 오류가 남습니다 — Windows `%LOCALAPPDATA%\session-tray\session_tray.log`, macOS `~/Library/Application Support/session-tray/session_tray.log` |
| 서버가 목록에 없음 | 사용자 폴더 밖에서 띄웠고 포트도 없으면 안 보입니다 |
| macOS 에서 "손상되었기 때문에 열 수 없습니다" | 1.0.0 판의 문제입니다 — [최신 판](https://github.com/Eehnodu/session-tray/releases/latest)을 다시 받으세요. 그래도 같으면 터미널에서 `xattr -cr "/Applications/Session Tray.app"` 뒤 다시 열기 |
| macOS 에서 tkinter 오류 | Homebrew python 이면 `brew install python-tk`, 또는 python.org 설치본 사용 |

## 버전 기록

| 버전 | 날짜 | 바뀐 것 |
|---|---|---|
| 1.0.1 | 2026-10-15 | macOS: 앱이 "손상되었기 때문에 열 수 없습니다"로 막히던 것 — 빌드 때 깨진 서명을 다시 붙이고 검사 |
| 1.0.0 | 2026-10-15 | 첫 공개 — 개발 서버 · 백그라운드 작업 · Claude Code 세션, 항목별 CPU · 메모리와 PC 전체 사용량, 줄마다 종료 · 우클릭 메뉴, 시작 시 자동 실행, Windows 실행 파일 · macOS 앱 |

## 라이선스

[MIT](LICENSE) — 자유롭게 받아 쓰고 고쳐 써도 됩니다.
