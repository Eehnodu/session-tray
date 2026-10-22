<p align="center"><img src="assets/icon.png" width="96" alt=""></p>
<h1 align="center">세션 트레이</h1>
<p align="center">작업 표시줄 · 메뉴 막대에서 개발 서버 · 백그라운드 작업 · Docker 컨테이너 · Claude Code 세션과 CPU · 메모리를 한눈에 (Windows · macOS)</p>

<p align="center">한국어 · <a href="README.en.md">English</a></p>

트레이 아이콘 하나로 지금 내 PC 에서 돌고 있는 개발용 프로세스를 모아 보고, 필요 없는 것은 바로 끕니다.

## 주요 기능

- 개발 서버: 포트를 연 node · python · java 등을 프로젝트 이름 · 포트와 함께 표시
- 백그라운드 작업: 포트 없이 도는 스크립트(봇 · 워커 등)도 따로 표시
- Docker 컨테이너: 돌고 있는 컨테이너를 포트 · 이미지와 함께 표시 (Docker 가 있을 때만)
- Claude Code 세션: 최근 15분 안에 대화가 오간 세션을 제목 · 폴더와 함께 표시, Claude 앱에서 바로 열기
- 사용량: 항목마다 CPU · 메모리(자식 프로세스 포함), PC 전체 사용량
- 바로 동작: 검색, 브라우저로 열기, 폴더 열기, 종료(컨테이너는 중지)
- 알림: 서버 · 작업 · 컨테이너가 꺼지거나 메모리를 많이 쓸 때 (처음엔 꺼짐)
- 새 버전 확인: 하루 한 번, 새 버전이 있으면 아이콘 메뉴에 표시
- 한국어 · 영어, Windows 어두운 모드, 창 크기 · 위치 기억

## 화면

<p align="center"><img src="assets/window.png" alt="세션 보기 창(예시 데이터)"></p>

아이콘 상태: <img src="assets/states.png" height="40" align="center" alt="아이콘 상태"> 점 없음 = 아무것도 안 돎 · 초록 = 서버 · 컨테이너 있음 · 주황 = 작업만

## 내려받기

[Releases](https://github.com/Eehnodu/session-tray/releases/latest) 에서 받습니다.

| 컴퓨터 | 파일 |
|---|---|
| Windows 10 · 11 | [SessionTray-windows.exe](https://github.com/Eehnodu/session-tray/releases/latest/download/SessionTray-windows.exe) (설치 없이 바로 실행) |
| macOS | [SessionTray-macos.zip](https://github.com/Eehnodu/session-tray/releases/latest/download/SessionTray-macos.zip) |

- Windows: 원하는 폴더에 두고 더블클릭합니다. "Windows의 PC 보호" 창이 뜨면 추가 정보 → 실행. 서명하지 않은 개인 앱이라 뜹니다. 아이콘은 작업 표시줄 오른쪽 `^`(숨김 아이콘) 안에 있습니다.
- macOS: zip 을 풀어 `Session Tray` 를 응용 프로그램 폴더로 옮기고 엽니다. 처음에 막히면 시스템 설정 → 개인정보 보호 및 보안 → 그래도 열기. 아이콘은 화면 맨 위 메뉴 막대에 생깁니다.

## 쓰는 법

- 아이콘 우클릭 → 세션 보기 (Windows 는 아이콘 더블클릭도 됨). 창은 5초마다 새로 읽습니다.
- 줄 끝 종료: 확인하면 그 프로세스와 자식만 끕니다. 컨테이너는 중지.
- Claude 세션 줄 끝 열기: Claude 데스크톱 앱에서 그 대화를 엽니다.
- 줄 우클릭(macOS 는 Control+클릭): 브라우저로 열기 · 폴더 열기 · Claude 에서 열기 · 종료
- 줄 더블클릭: 서버면 브라우저, Claude 세션이면 Claude 앱, 그 밖에는 폴더를 엽니다.
- 위쪽 검색 칸: 프로젝트 이름 · 포트 · 명령으로 거릅니다 (Esc 로 지움).
- 아이콘 메뉴: 알림 받기 · 윈도우 시작 시 실행(macOS 는 로그인 시 실행) · 설정 파일 열기 · 트레이 끄기

트레이를 꺼도 돌던 서버 · 작업은 그대로 남습니다.

### 무엇을 보여 주나

- 개발 서버: node · python · java · deno · bun · ruby · php · go 가 1024 ~ 49151 포트를 열고 있음
- 백그라운드 작업: 사용자 폴더 아래(`~/dev` · `~/projects` · `~/Documents` · `~/Desktop` 등)에서 도는데 포트가 없음
- Docker 컨테이너: `docker ps` 에 나오는 것
- Claude Code 세션: `~/.claude/projects` 의 대화 기록이 최근 15분 안에 바뀜
- 같은 일을 하는 자식 프로세스(`npm` → `vite` 등)는 한 줄로 묶고, 편집기 · 앱 내부 도구는 뺍니다.
- 모든 정보는 내 PC 안에서만 읽습니다. 새 버전 확인만 GitHub 에 최신 버전 번호를 묻습니다.

### 설정

아이콘 메뉴 → 설정 파일 열기. 고치고 저장하면 바로 반영됩니다(창은 다시 열 때).

| 항목 | 기본값 | 뜻 |
|---|---|---|
| `language` | `"auto"` | `"ko"` · `"en"` 으로 고정 |
| `extra_roots` | `[]` | 프로젝트를 두는 폴더 추가 (예: `["D:/code", "~/work"]`) |
| `active_minutes` | `15` | Claude 세션을 몇 분 안의 것까지 보일지 |
| `refresh_seconds` | `5` | 창을 몇 초마다 새로 읽을지 |
| `notifications` | `false` | 알림 전체 (메뉴의 알림 받기와 같음) |
| `notify_on_stop` | `true` | 꺼짐 알림도 받을지 |
| `memory_alert_mb` | `2048` | 한 항목이 이 MB 를 넘으면 알림 (`0` 이면 끔) |
| `check_updates` | `true` | 하루 한 번 새 버전 확인 |

### 문제 해결

| 증상 | 확인 |
|---|---|
| 아이콘이 안 보임 | Windows: `^` 숨김 아이콘 안을 봅니다 |
| 창이 안 뜸 · 갑자기 꺼짐 | 오류 기록: Windows `%LOCALAPPDATA%\session-tray\session_tray.log`, macOS `~/Library/Application Support/session-tray/session_tray.log` |
| 서버가 목록에 없음 | 사용자 폴더 밖에서 띄웠고 포트도 없으면 안 보입니다. 설정의 `extra_roots` 에 그 폴더를 적습니다 |
| 알림이 안 뜸 | 메뉴의 알림 받기가 켜져 있는지, Windows 설정 → 시스템 → 알림에서 허용돼 있는지 봅니다 |
| macOS 에서 "손상되었기 때문에 열 수 없습니다" | 최신 판을 다시 받습니다. 그래도 같으면 `xattr -cr "/Applications/Session Tray.app"` 뒤 다시 엽니다 |

## 소스 코드로 실행

Python 3.10 이상과 git 이 필요합니다. `uv` 가 있으면 그걸 씁니다.

```bash
git clone https://github.com/Eehnodu/session-tray.git
cd session-tray
powershell -ExecutionPolicy Bypass -File install.ps1   # Windows
bash install.sh                                        # macOS
```

설치 스크립트는 가상환경과 의존성을 설치하고 트레이를 띄웁니다. 업데이트는 `git pull` 뒤 한 번 더 실행합니다.

```bash
python session_tray.pyw                     # 트레이 띄우기 (Windows 는 pythonw 면 콘솔 창 없음)
python session_tray.pyw --window --demo     # 예시 데이터로 창만 (--lang=en · --light · --dark)
python session_tray.pyw --selftest          # 화면 없이 점검
```

## 기술 스택

Python · pystray · psutil · Pillow · tkinter, 실행 파일은 PyInstaller

## 라이선스

[MIT](LICENSE)
