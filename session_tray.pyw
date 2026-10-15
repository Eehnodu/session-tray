"""세션 트레이 — 작업 표시줄(Windows) · 메뉴 막대(macOS) 아이콘에서 지금 돌아가는 것을 본다.

- 개발 서버: 포트를 열고 있는 node · python 등(어느 프로젝트 · 포트)
- 백그라운드 작업: 포트 없이 도는 사용자 폴더의 node · python
- Docker 컨테이너: 돌고 있는 컨테이너(포트 · 이미지)
- Claude 세션: 최근 대화가 오간 Claude Code 세션(폴더 · 제목) — Claude 앱에서 바로 열기
- 항목별 CPU · 메모리, PC 전체 사용량, 꺼짐 · 메모리 알림, 새 버전 알림

구조: 트레이 프로세스는 아이콘 · 메뉴 · 알림만 맡고, "세션 보기"를 누르면 창을 별도 프로세스(--window)로 띄운다.
macOS 는 메뉴 막대 아이콘과 창을 한 프로세스의 메인 스레드에서 같이 돌릴 수 없어서 이렇게 나눴다.

실행: Windows  pythonw session_tray.pyw   ·   macOS  python3 session_tray.pyw
"""

from __future__ import annotations

__version__ = "1.1.1"  # 바꾸면 README(두 언어) 의 버전 기록 · git 태그도 같이

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

import psutil
from PIL import Image, ImageDraw

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
HOME = Path.home()
CLAUDE_PROJECTS = HOME / ".claude" / "projects"
SELF_PID = os.getpid()
FROZEN = bool(getattr(sys, "frozen", False))  # 실행 파일(.exe · .app)로 돌고 있나
SCRIPT = Path(sys.executable if FROZEN else __file__).resolve()
HERE = SCRIPT.parent
APP_ID = "Eehnodu.SessionTray"
REPO = "Eehnodu/session-tray"
RELEASES = f"https://github.com/{REPO}/releases/latest"
NO_WINDOW = 0x08000000  # Windows: 콘솔 창 없이 하위 프로세스

if IS_WIN:
    STATE = Path(os.environ.get("LOCALAPPDATA", HOME)) / "session-tray"
    FONT_FAMILY = "맑은 고딕"
elif IS_MAC:
    STATE = HOME / "Library" / "Application Support" / "session-tray"
    FONT_FAMILY = "Apple SD Gothic Neo"
else:
    STATE = HOME / ".local" / "state" / "session-tray"
    FONT_FAMILY = "Noto Sans CJK KR"
STATE.mkdir(parents=True, exist_ok=True)
LOG = STATE / "session_tray.log"
SETTINGS_FILE = STATE / "settings.json"
WINDOW_PID = STATE / "window.pid"
RAISE_FILE = STATE / "raise"  # 트레이가 이 파일을 건드리면 떠 있는 창이 앞으로 나온다
KILLED_FILE = STATE / "killed.json"  # 창에서 직접 끈 것 — 트레이가 "꺼짐" 알림을 보내지 않게
FONT = (FONT_FAMILY, 13 if IS_MAC else 10)
DEMO = "--demo" in sys.argv

# 실행 파일 이름(확장자 뺀 것, 소문자) — 정확히 같거나 python 으로 시작할 때만 본다
WATCH_NAMES = {"node", "python", "pythonw", "uvicorn", "java", "deno", "bun", "ruby", "php", "go"}
# 앱 · 편집기 내부 도구는 뺀다(경로를 / 로 바꾸고 소문자로 비교)
SKIP = ("/appdata/", "/.vscode", "/.cursor", "/.claude/", "/program files", "/windows/", "/.local/", "/library/", "/applications/", "/.nvm/", "/.pyenv/", "/opt/homebrew/")
STOP = {"node_modules", ".venv", "venv", "scripts", "src", "frontend", "backend", "dist", ".bin", "lib", "bin"}


def log_error() -> None:
    """창 없이 도는 프로세스라 오류가 안 보인다 — 마지막 오류를 session_tray.log 에 남긴다"""
    import traceback

    try:
        LOG.write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + traceback.format_exc(), encoding="utf-8")
    except OSError:
        pass


# ---------------- 설정 ----------------
DEFAULTS: dict = {
    "language": "auto",  # auto · ko · en
    "extra_roots": [],  # 프로젝트를 두는 폴더를 더 적는다 — 예: ["~/work", "D:/code"]
    "active_minutes": 15,  # Claude 세션: 이 시간 안에 대화가 오간 것만
    "refresh_seconds": 5,  # 창 새로 읽기 간격
    "notify_on_stop": True,  # 서버 · 작업 · 컨테이너가 꺼지면 알림
    "memory_alert_mb": 2048,  # 한 항목이 이만큼 넘게 쓰면 알림(0 = 끔)
    "check_updates": True,  # 하루 한 번 새 버전 확인
    "window_geometry": "",  # 창 크기 · 위치(자동 저장)
}


def load_settings() -> dict:
    s = dict(DEFAULTS)
    try:
        s.update({k: v for k, v in json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return s


def save_settings(**changes) -> None:
    s = load_settings()
    s.update(changes)
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


SETTINGS = load_settings()
if not SETTINGS_FILE.exists():
    save_settings()  # 처음에 기본값으로 만들어 둔다 — "설정 파일 열기"로 바로 고칠 수 있게


def project_roots() -> list[Path]:
    extra = [Path(os.path.expanduser(str(x))) for x in SETTINGS.get("extra_roots") or []]
    return extra + [HOME / "dev" / "project", HOME / "dev", HOME / "source" / "repos", HOME / "projects", HOME / "Documents", HOME / "Desktop", HOME]


ROOTS = project_roots()


# ---------------- 언어 ----------------
def detect_language() -> str:
    for a in sys.argv:
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    want = SETTINGS.get("language", "auto")
    if want in ("ko", "en"):
        return want
    try:
        if IS_WIN:
            import ctypes

            return "ko" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x12 else "en"
        if IS_MAC:
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3).stdout
            first = re.search(r'"?([a-zA-Z-]+)"?', out.split("(", 1)[-1])
            return "ko" if first and first.group(1).lower().startswith("ko") else "en"
    except Exception:
        pass
    return "ko" if os.environ.get("LANG", "").lower().startswith("ko") else "en"


LANG = detect_language()
TEXT: dict[str, tuple[str, str]] = {
    "app": ("세션 트레이", "Session Tray"),
    "win_title": ("실행 중인 세션", "Running sessions"),
    "demo": (" (예시)", " (demo)"),
    "refresh": ("새로고침", "Refresh"),
    "open_browser": ("브라우저로 열기", "Open in browser"),
    "open_folder": ("폴더 열기", "Open folder"),
    "search": ("검색", "Search"),
    "col_name": ("이름", "Name"),
    "col_where": ("포트 · 위치", "Port · Where"),
    "col_cpu": ("CPU", "CPU"),
    "col_mem": ("메모리", "Memory"),
    "col_since": ("시간", "Time"),
    "col_detail": ("명령 · 세션", "Command · Session"),
    "g_server": ("개발 서버", "Dev servers"),
    "g_job": ("백그라운드 작업", "Background jobs"),
    "g_docker": ("Docker 컨테이너", "Docker containers"),
    "g_claude": ("Claude 세션 (최근 {m}분)", "Claude sessions (last {m} min)"),
    "none": ("없음", "None"),
    "no_match": ("검색 결과 없음", "No matches"),
    "stop": ("종료", "Stop"),
    "stop_docker": ("중지", "Stop"),
    "open": ("열기", "Open"),
    "open_claude": ("Claude 에서 열기", "Open in Claude"),
    "updated": ("갱신", "Updated"),
    "ago_s": ("{n}초", "{n}s"),
    "ago_m": ("{n}분", "{n}m"),
    "ago_h": ("{h}시간 {m}분", "{h}h {m}m"),
    "ago_d": ("{n}일", "{n}d"),
    "ago_active": ("{t} 전 활동", "active {t} ago"),
    "ago_up": ("{t}째", "up {t}"),
    "session": ("세션", "session"),
    "pick_server": ("포트가 있는 개발 서버를 골라 주세요.", "Pick a dev server that has a port."),
    "no_folder": ("이 항목의 폴더를 찾지 못했습니다.", "Couldn't find this item's folder."),
    "pick_stop": ("끌 서버 · 작업 · 컨테이너를 골라 주세요.", "Pick a server, job or container to stop."),
    "ask_stop": ("{name} ({where})\n{what} 를 종료할까요?\n\n{detail}", "Stop {name} ({where})?\n{what}\n\n{detail}"),
    "stop_fail": ("종료하지 못했습니다: {e}", "Couldn't stop it: {e}"),
    "claude_fail": ("Claude 앱을 열지 못했습니다. Claude 데스크톱 앱이 설치돼 있는지 확인해 주세요.", "Couldn't open the Claude app. Make sure Claude Desktop is installed."),
    "m_show": ("세션 보기", "Show sessions"),
    "m_startup_win": ("윈도우 시작 시 실행", "Start with Windows"),
    "m_startup": ("로그인 시 실행", "Open at login"),
    "m_notify": ("꺼지면 알림", "Notify when something stops"),
    "m_settings": ("설정 파일 열기", "Open settings file"),
    "m_update": ("새 버전 {v} 받기", "Get new version {v}"),
    "m_quit": ("트레이 끄기", "Quit tray"),
    "tip": ("서버 {s} · 작업 {j} · 컨테이너 {d} · Claude {c}", "Servers {s} · Jobs {j} · Containers {d} · Claude {c}"),
    "n_stopped": ("꺼졌습니다: {name} ({where})", "Stopped: {name} ({where})"),
    "n_memory": ("메모리 {mb:,.0f} MB 사용 중: {name}", "Using {mb:,.0f} MB of memory: {name}"),
    "n_update": ("새 버전 {v} 이 나왔습니다. 트레이 메뉴에서 받을 수 있어요.", "Version {v} is available. Get it from the tray menu."),
    "sys": ("CPU {c:.0f}% · 메모리 {u:.1f}/{t:.0f}GB ({p:.0f}%)", "CPU {c:.0f}% · Memory {u:.1f}/{t:.0f} GB ({p:.0f}%)"),
}


def _(key: str, **kw) -> str:
    ko, en = TEXT[key]
    s = en if LANG == "en" else ko
    return s.format(**kw) if kw else s


# ---------------- 항목 ----------------
@dataclass
class Row:
    kind: str  # "서버" · "작업" · "컨테이너" · "Claude"
    name: str  # 프로젝트 · 컨테이너 · 세션 제목
    where: str  # 포트 · 위치
    pid: int | None = None
    since: float | None = None  # 시작(또는 마지막 활동) 시각
    detail: str = ""
    ports: list[int] = field(default_factory=list)
    folder: str | None = None
    cpu: float | None = None  # 전체 CPU 대비 %(자식 프로세스 포함)
    mem: float | None = None  # MB(자식 프로세스 포함)
    container: str | None = None  # Docker 컨테이너 ID
    session: str | None = None  # Claude 세션 ID

    @property
    def key(self) -> str:
        """다시 시작해 PID 가 바뀌어도 같은 것으로 보는 열쇠(꺼짐 알림 · 고른 줄 유지용)"""
        return f"{self.kind}|{self.name}|{self.container or self.session or self.detail}"


# ---------------- 사용량 ----------------
# CPU % 는 같은 Process 객체로 두 번 재야 나온다 — 갱신 사이에 객체를 들고 있는다
_PROCS: dict[int, psutil.Process] = {}
NCPU = psutil.cpu_count() or 1


def usage(pids: list[int]) -> tuple[float, float]:
    cpu = mem = 0.0
    for pid in pids:
        p = _PROCS.get(pid)
        if p is None:
            try:
                p = psutil.Process(pid)
                p.cpu_percent(None)
                _PROCS[pid] = p
            except psutil.Error:
                continue
        try:
            cpu += p.cpu_percent(None) / NCPU
            mem += p.memory_info().rss
        except psutil.Error:
            _PROCS.pop(pid, None)
    return cpu, mem / 1048576


def system_usage() -> str:
    if DEMO:
        return _("sys", c=12, u=9.4, t=16, p=59)
    vm = psutil.virtual_memory()
    return _("sys", c=psutil.cpu_percent(None), u=vm.used / 1073741824, t=vm.total / 1073741824, p=vm.percent)


# ---------------- 찾기: 프로세스 ----------------
def _norm(path: str) -> str:
    return path.strip('"').replace("\\", "/")


def _project_of(path: str | None) -> str | None:
    """사용자 폴더 아래 경로 → 짧은 프로젝트 이름. ~/dev/project/my/shop/.venv/... → my/shop"""
    if not path:
        return None
    raw = _norm(path)
    low = raw.lower()
    if any(x in low for x in SKIP):
        return None
    for root in ROOTS:
        r = _norm(str(root)).lower().rstrip("/") + "/"
        k = low.find(r)
        if k < 0:
            continue
        out = []
        for x in (x for x in raw[k + len(r):].split("/") if x):
            x = x.split(" ")[0].strip('"')  # 명령줄이면 다음 인자 앞에서 끊는다
            if not x or x.lower() in STOP or x.endswith((".js", ".py", ".pyw", ".exe", ".mjs", ".cjs", ".ts")):
                break
            out.append(x)
        return "/".join(out[:4]) or None
    return None


def _cmd(p: psutil.Process) -> str:
    try:
        return " ".join(p.cmdline())
    except (psutil.Error, OSError):
        return ""


def _cwd(p: psutil.Process) -> str | None:
    try:
        return p.cwd()
    except (psutil.Error, OSError):
        return None


def _listening_all() -> dict[int, set[int]] | None:
    """전체 열린 포트 — macOS 는 관리자 권한이 없으면 막히므로 None(그때는 프로세스마다 읽는다)"""
    out: dict[int, set[int]] = {}
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.pid and c.laddr and 1024 <= c.laddr.port < 49152:
                out.setdefault(c.pid, set()).add(c.laddr.port)
        return out
    except (psutil.AccessDenied, PermissionError):
        return None
    except (psutil.Error, OSError):
        return out


def _listening_of(p: psutil.Process) -> set[int]:
    try:
        conns = p.net_connections(kind="tcp") if hasattr(p, "net_connections") else p.connections(kind="tcp")
    except (psutil.Error, OSError):
        return set()
    return {c.laddr.port for c in conns if c.status == psutil.CONN_LISTEN and c.laddr and 1024 <= c.laddr.port < 49152}


def _short_cmd(cmd: str) -> str:
    """명령줄 앞의 node · python 실행 파일 경로를 뗀다. C:\\Py\\python.exe -m app → -m app"""
    short = re.sub(r'^("[^"]*[\\/]|[^"\s]*[\\/])(node|pythonw|python(?:\d+(?:\.\d+)*)?)(\.exe)?"?\s+', "", cmd, flags=re.I)
    return re.sub(r"\S*node_modules[\\/]\.bin[\\/]+\.\.[\\/]", "", short)


def collect_processes() -> list[Row]:
    listen = _listening_all()
    cands: dict[int, tuple[psutil.Process, str, str | None, float, int | None, set[int]]] = {}
    # 이름만 먼저 훑는다 — 시작 시각 · 부모를 처음부터 같이 읽으면 시스템 프로세스 때문에 20 ~ 30초 걸린다(Windows 실측)
    for p in psutil.process_iter(["name"]):
        try:
            name = (p.info["name"] or "").lower().removesuffix(".exe")
            if p.pid == SELF_PID or not (name in WATCH_NAMES or name.startswith("python")):
                continue
            cmd = _cmd(p)
            if "session_tray" in cmd:
                continue  # 이 도구 자신(소스로 띄운 트레이 · 창)
            cwd = _cwd(p)
            ports = listen.get(p.pid, set()) if listen is not None else _listening_of(p)
            if not (_project_of(cmd) or _project_of(cwd)) and not ports:
                continue  # 사용자 폴더 밖 · 앱 내부의 node · python
            cands[p.pid] = (p, cmd, cwd, p.create_time(), p.ppid(), ports)
        except (psutil.Error, OSError):
            continue

    rows: list[Row] = []
    for pid, (p, cmd, cwd, created, ppid, own_ports) in cands.items():
        if ppid in cands:
            continue  # 자식은 부모 한 줄로 묶는다(.venv 런처 → 실제 python, npm → vite 등) — 부모가 자식의 포트까지 보인다
        kids = [c for c, v in cands.items() if c != pid and v[4] == pid]
        ports = sorted(set(own_ports).union(*(cands[c][5] for c in kids)))
        try:
            tree = [pid] + [c.pid for c in p.children(recursive=True)]
        except psutil.Error:
            tree = [pid, *kids]
        cpu, mem = usage(tree)
        short = _short_cmd(cmd)
        pname = p.info.get("name") or ""
        rows.append(
            Row(
                kind="서버" if ports else "작업",
                name=_project_of(cmd) or _project_of(cwd) or pname,
                where=", ".join(f":{x}" for x in ports) if ports else pname,
                pid=pid,
                since=created,
                detail=short[:200],
                ports=ports,
                folder=cwd,
                cpu=cpu,
                mem=mem,
            )
        )
    rows.sort(key=lambda r: (r.kind != "서버", r.name))
    return rows


# ---------------- 찾기: Docker ----------------
_DOCKER_OFF_UNTIL = [0.0]  # Docker 가 없거나 꺼져 있으면 1분 동안 다시 묻지 않는다(매번 느려지지 않게)
# PATH 에 없을 때 찾아볼 자리 — macOS 는 Finder 로 연 앱의 PATH 에 /usr/local/bin 이 없고,
# Windows 는 Docker 를 설치하기 전에 띄운 트레이가 새 PATH 를 모른다
DOCKER_PLACES = (
    [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe"]
    if IS_WIN
    else [Path("/usr/local/bin/docker"), Path("/opt/homebrew/bin/docker"), Path("/Applications/Docker.app/Contents/Resources/bin/docker"), HOME / ".docker" / "bin" / "docker", HOME / ".orbstack" / "bin" / "docker", Path("/usr/bin/docker")]
)


def docker_bin() -> str | None:
    found = shutil.which("docker")
    if found:
        return found
    return next((str(x) for x in DOCKER_PLACES if x.exists()), None)


def _run(args: list[str], timeout: float = 4) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW if IS_WIN else 0)


def parse_docker_ps(out: str) -> list[Row]:
    """docker ps --format '{{json .}}' 의 줄들 → 항목"""
    rows: list[Row] = []
    now = time.time()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            c = json.loads(line)
        except ValueError:
            continue
        ports = sorted({int(m) for m in re.findall(r":(\d+)->", c.get("Ports", ""))})
        since = None
        m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", c.get("CreatedAt", ""))
        if m:
            try:
                since = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
                if since > now:  # 시간대가 어긋나면 비운다
                    since = None
            except ValueError:
                since = None
        rows.append(
            Row(
                kind="컨테이너",
                name=c.get("Names", "") or c.get("ID", "")[:12],
                where=", ".join(f":{x}" for x in ports) if ports else "docker",
                since=since,
                detail=f"{c.get('Image', '')} · {c.get('Status', '')}".strip(" ·"),
                ports=ports,
                container=c.get("ID", ""),
            )
        )
    rows.sort(key=lambda r: r.name)
    return rows


def collect_docker() -> list[Row]:
    exe = docker_bin()
    if time.time() < _DOCKER_OFF_UNTIL[0] or not exe:
        return []
    try:
        res = _run([exe, "ps", "--format", "{{json .}}"])
    except (OSError, subprocess.SubprocessError):
        res = None
    if res is None or res.returncode != 0:
        _DOCKER_OFF_UNTIL[0] = time.time() + 60  # Docker 데몬이 꺼져 있음
        return []
    return parse_docker_ps(res.stdout)


# ---------------- 찾기: Claude ----------------
def _tail(path: Path, size: int = 2_000_000) -> str:
    with path.open("rb") as f:
        f.seek(0, 2)
        n = f.tell()
        f.seek(max(0, n - size))
        return f.read().decode("utf-8", "ignore")


def _last_json_str(text: str, key: str) -> str | None:
    i = text.rfind(key)
    if i < 0:
        return None
    j = text.find('"', i + len(key))
    try:
        return json.loads('"' + text[i + len(key) : j] + '"')
    except ValueError:
        return None


def collect_claude() -> list[Row]:
    rows: list[Row] = []
    if not CLAUDE_PROJECTS.exists():
        return rows
    now = time.time()
    minutes = int(SETTINGS.get("active_minutes") or 15)
    for f in CLAUDE_PROJECTS.glob("*/*.jsonl"):
        try:
            mt = f.stat().st_mtime
        except OSError:
            continue
        if now - mt > minutes * 60:
            continue
        try:
            t = _tail(f)
        except OSError:
            continue
        title = _last_json_str(t, '"customTitle":"') or _last_json_str(t, '"aiTitle":"')
        cwd = _last_json_str(t, '"cwd":"')
        rows.append(Row(kind="Claude", name=title or f.stem[:8], where=_project_of(cwd) or (cwd or f.parent.name), since=mt, detail=f"{_('session')} {f.stem}", folder=cwd, session=f.stem))
    rows.sort(key=lambda r: -(r.since or 0))
    return rows


def demo_rows() -> list[Row]:
    """README 캡처용 예시 — 실제 컴퓨터 정보를 쓰지 않는다(--demo)"""
    now = time.time()
    ko = LANG != "en"
    return [
        Row("서버", "shop/web", ":5173", 18420, now - 3 * 3600, "vite --port 5173", [5173], str(HOME), 1.8, 212),
        Row("서버", "shop/api", ":8000", 18533, now - 3 * 3600, "-m uvicorn app.main:app --reload --port 8000", [8000], str(HOME), 0.6, 96),
        Row("작업", "trading-bot", "python.exe", 20711, now - 21 * 3600, "-m scripts.run_scanner", [], str(HOME), 0.4, 71),
        Row("컨테이너", "shop-db", ":5432", None, now - 26 * 3600, "postgres:16 · Up 26 hours", [5432], None, container="3f2a9c1b7d4e"),
        Row("Claude", "결제 화면 리팩터링" if ko else "Refactor checkout page", "shop", None, now - 40, f"{_('session')} 7f3c…", [], str(HOME), session="demo-1"),
        Row("Claude", "README 정리" if ko else "Tidy up README", "session-tray", None, now - 6 * 60, f"{_('session')} a91e…", [], str(HOME), session="demo-2"),
    ]


def collect() -> list[Row]:
    if DEMO:
        return demo_rows()
    return collect_processes() + collect_docker() + collect_claude()


def ago(ts: float | None, claude: bool) -> str:
    if not ts:
        return "-"
    s = int(time.time() - ts)
    if s < 60:
        t = _("ago_s", n=s)
    elif s < 3600:
        t = _("ago_m", n=s // 60)
    elif s < 86400:
        t = _("ago_h", h=s // 3600, m=s % 3600 // 60)
    else:
        t = _("ago_d", n=s // 86400)
    return _("ago_active", t=t) if claude else _("ago_up", t=t)


# ---------------- 아이콘 ----------------
def make_icon(servers: int, jobs: int, size: int = 64) -> Image.Image:
    """남색 둥근 네모 + 겹친 창 두 장(세션들). 상태 점: 초록 = 서버 · 컨테이너 있음 · 주황 = 작업만. 크게 그려 줄여서 가장자리를 매끄럽게"""
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=60, fill=(67, 56, 202, 255))
    d.rounded_rectangle((78, 44, 216, 150), radius=20, fill=(165, 180, 252, 255))  # 뒤 창
    d.rounded_rectangle((40, 84, 186, 206), radius=20, fill=(255, 255, 255, 255))  # 앞 창
    for x in (62, 84, 106):
        d.ellipse((x, 102, x + 14, 116), fill=(67, 56, 202, 255))
    d.rounded_rectangle((62, 134, 160, 148), radius=7, fill=(199, 210, 254, 255))
    d.rounded_rectangle((62, 162, 132, 176), radius=7, fill=(199, 210, 254, 255))
    if servers or jobs:
        d.ellipse((150, 150, 250, 250), fill=(255, 255, 255, 255))
        d.ellipse((166, 166, 234, 234), fill=(22, 163, 74, 255) if servers else (217, 119, 6, 255))
    return img.resize((size, size), Image.LANCZOS)


ICO = STATE / "session_tray.ico"


def ensure_ico() -> Path:
    """Windows 바로가기 · 창 아이콘용 .ico (여러 크기)"""
    if not ICO.exists():
        make_icon(0, 0, 256).save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    return ICO


def set_app_id() -> None:
    """Windows 작업 표시줄이 이 창을 "파이썬"으로 묶지 않게 앱 고유 ID 를 둔다 — 그래야 이 아이콘이 보인다"""
    if IS_WIN:
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass


def open_path(target: str) -> None:
    """폴더 · 파일 · URL(claude:// 포함)을 운영체제 기본 앱으로 연다"""
    if IS_WIN:
        os.startfile(target)  # type: ignore[attr-defined]
    elif IS_MAC:
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def open_settings() -> None:
    """설정 파일을 메모장(맥은 텍스트 편집기)으로 — .json 이 어느 앱에 묶였든 상관없이"""
    if not SETTINGS_FILE.exists():
        save_settings()
    if IS_WIN:
        subprocess.Popen(["notepad.exe", str(SETTINGS_FILE)])
    elif IS_MAC:
        subprocess.Popen(["open", "-t", str(SETTINGS_FILE)])
    else:
        open_path(str(SETTINGS_FILE))


def os_dark_mode() -> bool:
    try:
        if IS_WIN:
            import winreg

            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if IS_MAC:
            return _run(["defaults", "read", "-g", "AppleInterfaceStyle"], 3).stdout.strip() == "Dark"
    except Exception:
        pass
    return False


# ---------------- 창(별도 프로세스) ----------------
def run_window() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    from PIL import ImageTk

    set_app_id()
    WINDOW_PID.write_text(str(SELF_PID), encoding="utf-8")
    root = tk.Tk()
    root.title(f"{_('win_title')} · {_('app')} v{__version__}" + (_("demo") if DEMO else ""))
    if IS_WIN:
        try:
            root.iconbitmap(default=str(ensure_ico()))
        except tk.TclError:
            pass
    icon_img = ImageTk.PhotoImage(make_icon(0, 0, 64))
    root.iconphoto(True, icon_img)
    root.geometry(SETTINGS.get("window_geometry") or "1240x600")
    root.minsize(760, 320)

    # --dark · --light: 캡처용으로 강제
    dark = "--light" not in sys.argv and ("--dark" in sys.argv or (os_dark_mode() and not IS_MAC))  # macOS 의 aqua 테마는 시스템 어두운 모드를 스스로 따른다
    style = ttk.Style(root)
    if dark:
        style.theme_use("clam")
        bg, fg, card, line, sel = "#1f2024", "#e6e7ea", "#26282d", "#3a3d44", "#3b4a8a"
        root.configure(bg=bg)
        style.configure(".", background=bg, foreground=fg, fieldbackground=card, bordercolor=line, lightcolor=line, darkcolor=line)
        style.configure("Treeview", background=card, fieldbackground=card, foreground=fg)
        style.map("Treeview", background=[("selected", sel)], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background="#2c2e34", foreground=fg, relief="flat")
        style.map("Treeview.Heading", background=[("active", "#34363d")])
        style.configure("TButton", background="#2c2e34", foreground=fg, bordercolor=line)
        style.map("TButton", background=[("active", "#34363d")])
        style.configure("TEntry", fieldbackground=card, foreground=fg, insertcolor=fg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        if IS_WIN:  # 제목줄도 어둡게
            try:
                import ctypes

                root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
            except Exception:
                pass
    style.configure("Treeview", font=FONT, rowheight=30 if IS_MAC else 28)
    style.configure("Treeview.Heading", font=(FONT[0], FONT[1], "bold"))
    style.configure("TButton", font=FONT, padding=(10, 4))
    RED = "#f87171" if dark else "#dc2626"
    BLUE = "#93c5fd" if dark else "#2563eb"

    rows: dict[str, Row] = {}
    labels: dict[str, tk.Label] = {}
    last_data: list[Row] = []

    bar = ttk.Frame(root, padding=(12, 10, 12, 6))
    bar.pack(fill="x")
    status = tk.StringVar(value="")
    query = tk.StringVar(value="")

    cols = ("where", "pid", "cpu", "mem", "since", "detail", "action")
    t = ttk.Treeview(root, columns=cols, show="tree headings", selectmode="browse")
    for c, key in (("#0", "col_name"), ("where", "col_where"), ("cpu", "col_cpu"), ("mem", "col_mem"), ("since", "col_since"), ("detail", "col_detail")):
        t.heading(c, text=_(key))
    t.heading("pid", text="PID")
    t.heading("action", text="")
    t.column("#0", width=240, stretch=False)
    t.column("where", width=150, stretch=False)
    t.column("pid", width=70, anchor="e", stretch=False)
    t.column("cpu", width=64, anchor="e", stretch=False)
    t.column("mem", width=84, anchor="e", stretch=False)
    t.column("since", width=130, anchor="center", stretch=False)  # 메모리 숫자와 붙지 않게 가운데
    t.column("detail", width=250, minwidth=120)  # 남는 폭을 이 칸이 가져간다 — 끝 칸이 잘리지 않게
    t.column("action", width=90, anchor="center", stretch=False)
    ACTION = f"#{len(cols)}"

    def selected() -> Row | None:
        s = t.selection()
        return rows.get(s[0]) if s else None

    def action_of(r: Row) -> tuple[str, str] | None:
        """줄 끝 칸의 글자 · 색 — 프로세스 · 컨테이너는 빨간 종료 · 중지, Claude 세션은 파란 열기"""
        if r.kind == "Claude":
            return (_("open"), BLUE) if r.session else None
        if r.container:
            return _("stop_docker"), RED
        if r.pid:
            return _("stop"), RED
        return None

    def place_labels() -> None:
        """표 칸은 글자색을 따로 못 바꾼다 — 끝 칸 위에 색 라벨을 얹고, 칸이 움직일 때마다 다시 맞춘다"""
        sel = set(t.selection())
        bg_norm = style.lookup("Treeview", "fieldbackground") or style.lookup("Treeview", "background") or "white"
        bg_sel = style.lookup("Treeview", "background", ["selected"]) or "#0078d7"
        live = set()
        for iid, r in rows.items():
            act = action_of(r)
            if not act:
                continue
            box = t.bbox(iid, column="action")
            if not box:
                continue  # 접힌 묶음 · 화면 밖
            live.add(iid)
            lab = labels.get(iid)
            if lab is None or not lab.winfo_exists():
                lab = tk.Label(t, font=(FONT[0], FONT[1], "bold"), cursor="hand2", bd=0)
                lab.bind("<Button-1>", lambda _e, i=iid: (t.selection_set(i), root.after(10, do_action)))
                labels[iid] = lab
            x, y, w, h = box
            lab.configure(text=act[0], bg=bg_sel if iid in sel else bg_norm, fg="#ffffff" if iid in sel else act[1])
            lab.place(x=x + 1, y=y + 1, width=w - 2, height=h - 2)
        for iid in list(labels):
            if iid not in live:
                labels.pop(iid).destroy()

    def matches(r: Row, q: str) -> bool:
        return not q or q in f"{r.name} {r.where} {r.detail} {r.pid or ''} {r.container or ''}".lower()

    def render() -> None:
        sel = selected()
        keep = sel.key if sel else None
        q = query.get().strip().lower()
        t.delete(*t.get_children())
        rows.clear()
        for lab in labels.values():
            lab.destroy()
        labels.clear()
        groups = [("서버", _("g_server")), ("작업", _("g_job")), ("컨테이너", _("g_docker")), ("Claude", _("g_claude", m=int(SETTINGS.get("active_minutes") or 15)))]
        for kind, label in groups:
            all_items = [r for r in last_data if r.kind == kind]
            if kind == "컨테이너" and not all_items:
                continue  # Docker 를 안 쓰면 묶음 자체를 숨긴다
            items = [r for r in all_items if matches(r, q)]
            g = t.insert("", "end", text=f"{label}  {len(items)}", open=True)
            if not items:
                t.insert(g, "end", text=_("no_match") if q and all_items else _("none"), values=("",) * len(cols))
            for r in items:
                cpu = f"{r.cpu:.1f}%" if r.cpu is not None else "-"
                mem = f"{r.mem:,.0f} MB" if r.mem is not None else "-"
                iid = t.insert(g, "end", text=r.name, values=(r.where, r.pid or "", cpu, mem, ago(r.since, r.kind == "Claude"), r.detail, ""))
                rows[iid] = r
                if keep and r.key == keep:
                    t.selection_set(iid)
        status.set(f"{system_usage()}   ·   {_('updated')} {time.strftime('%H:%M:%S')}")
        root.after_idle(place_labels)

    def refresh() -> None:
        last_data[:] = collect()
        render()

    def open_browser(silent: bool = False) -> bool:
        r = selected()
        if r and r.ports:
            webbrowser.open(f"http://localhost:{r.ports[0]}")
            return True
        if not silent:
            messagebox.showinfo(_("open_browser"), _("pick_server"), parent=root)
        return False

    def open_folder() -> None:
        r = selected()
        if r and r.folder and Path(r.folder).exists():
            open_path(r.folder)
        elif r:
            messagebox.showinfo(_("open_folder"), _("no_folder"), parent=root)

    def open_claude() -> None:
        r = selected()
        if not r or not r.session or DEMO:
            return
        try:
            open_path(f"claude://resume?session={r.session}")
        except OSError:
            messagebox.showerror(_("open_claude"), _("claude_fail"), parent=root)

    def remember_killed(key: str) -> None:
        try:
            data = json.loads(KILLED_FILE.read_text(encoding="utf-8")) if KILLED_FILE.exists() else {}
        except (OSError, ValueError):
            data = {}
        data = {k: v for k, v in data.items() if time.time() - v < 600}
        data[key] = time.time()
        KILLED_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def kill() -> None:
        r = selected()
        if not r or not (r.pid or r.container):
            messagebox.showinfo(_("stop"), _("pick_stop"), parent=root)
            return
        what = f"Docker {r.container[:12]}" if r.container else f"PID {r.pid}"
        if not messagebox.askyesno(_("stop"), _("ask_stop", name=r.name, where=r.where, what=what, detail=r.detail), parent=root):
            return
        if DEMO:
            return
        remember_killed(r.key)  # 직접 끈 것은 트레이가 "꺼짐" 알림을 보내지 않는다
        if r.container:
            # docker stop 은 10초까지 걸린다 — 기다리지 않고 보낸 뒤 나중에 다시 읽는다
            subprocess.Popen([docker_bin() or "docker", "stop", r.container], creationflags=NO_WINDOW if IS_WIN else 0, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            root.after(3000, refresh)
            root.after(11000, refresh)
            return
        try:
            p = psutil.Process(r.pid)
            for c in p.children(recursive=True):
                c.terminate()
            p.terminate()
            psutil.wait_procs([p], timeout=3)
        except psutil.NoSuchProcess:
            pass
        except psutil.Error as e:
            messagebox.showerror(_("stop"), _("stop_fail", e=e), parent=root)
        refresh()

    def do_action() -> None:
        r = selected()
        if r and r.kind == "Claude":
            open_claude()
        else:
            kill()

    for key, cmd in (("refresh", refresh), ("open_browser", open_browser), ("open_folder", open_folder)):  # 종료 · 열기는 줄 끝 칸 · 우클릭에서
        ttk.Button(bar, text=_(key), command=cmd).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text=f"  {_('search')}", font=FONT).pack(side="left", padx=(8, 4))
    entry = ttk.Entry(bar, textvariable=query, width=22, font=FONT)
    entry.pack(side="left")
    entry.bind("<KeyRelease>", lambda _e: render())  # 이미 읽은 것을 거르기만 — 글자마다 다시 읽지 않는다
    entry.bind("<Escape>", lambda _e: (query.set(""), render()))
    ttk.Label(bar, textvariable=status, font=FONT).pack(side="right")
    t.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    menu = tk.Menu(root, tearoff=False, font=FONT)
    menu.add_command(label=_("open_browser"), command=open_browser)  # 0
    menu.add_command(label=_("open_folder"), command=open_folder)  # 1
    menu.add_command(label=_("open_claude"), command=open_claude)  # 2
    menu.add_separator()  # 3
    menu.add_command(label=_("stop"), command=kill)  # 4

    def on_click(e: tk.Event) -> None:
        if t.identify_region(e.x, e.y) != "cell":
            return
        iid = t.identify_row(e.y)
        if t.identify_column(e.x) == ACTION and iid in rows and action_of(rows[iid]):
            t.selection_set(iid)
            root.after(10, do_action)  # 고른 표시가 먼저 그려진 뒤

    def on_right(e: tk.Event) -> None:
        iid = t.identify_row(e.y)
        if not iid or iid not in rows:
            return
        t.selection_set(iid)
        r = rows[iid]
        menu.entryconfigure(0, state="normal" if r.ports else "disabled")
        menu.entryconfigure(1, state="normal" if r.folder else "disabled")
        menu.entryconfigure(2, state="normal" if r.session else "disabled")
        menu.entryconfigure(4, state="normal" if (r.pid or r.container) else "disabled")
        menu.tk_popup(e.x_root, e.y_root)

    def on_motion(e: tk.Event) -> None:
        iid = t.identify_row(e.y)
        on = t.identify_column(e.x) == ACTION and iid in rows and bool(action_of(rows[iid]))
        t.configure(cursor="hand2" if on else "")

    def on_double(_e) -> None:
        r = selected()
        if r and r.kind == "Claude":
            open_claude()
        elif not open_browser(silent=True):
            open_folder()

    t.bind("<Double-1>", on_double)
    t.bind("<Button-1>", on_click)
    # 우클릭: Windows 는 3번 단추, macOS 는 2번 단추와 Control+클릭
    for ev in ("<Button-2>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",):
        t.bind(ev, on_right)
    t.bind("<Motion>", on_motion)
    for ev in ("<Configure>", "<<TreeviewOpen>>", "<<TreeviewClose>>", "<<TreeviewSelect>>", "<MouseWheel>", "<ButtonRelease-1>", "<KeyRelease>"):
        t.bind(ev, lambda _e: root.after_idle(place_labels), add="+")

    last_raise = [RAISE_FILE.stat().st_mtime if RAISE_FILE.exists() else 0.0]
    every = max(2, int(SETTINGS.get("refresh_seconds") or 5)) * 1000

    def tick() -> None:
        refresh()
        root.after(every, tick)

    def watch_raise() -> None:
        # 트레이에서 "세션 보기"를 다시 누르면 이 창을 앞으로
        try:
            m = RAISE_FILE.stat().st_mtime if RAISE_FILE.exists() else 0.0
            if m > last_raise[0]:
                last_raise[0] = m
                root.deiconify()
                root.lift()
                root.attributes("-topmost", True)
                root.after(200, lambda: root.attributes("-topmost", False))
                root.focus_force()
        except OSError:
            pass
        root.after(400, watch_raise)

    def on_close() -> None:
        try:
            if root.state() == "normal" and not DEMO:
                save_settings(window_geometry=root.geometry())  # 다음에 같은 크기 · 자리로
            WINDOW_PID.unlink(missing_ok=True)
        except OSError:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    tick()
    watch_raise()
    root.lift()
    root.focus_force()
    root.mainloop()


def window_alive() -> bool:
    try:
        pid = int(WINDOW_PID.read_text(encoding="utf-8"))
        return psutil.pid_exists(pid) and "--window" in " ".join(psutil.Process(pid).cmdline())
    except (OSError, ValueError, psutil.Error):
        return False


def show_window() -> None:
    if window_alive():
        RAISE_FILE.write_text(str(time.time()), encoding="utf-8")  # 떠 있는 창을 앞으로
        return
    args = ([sys.executable] if FROZEN else [sys.executable, str(SCRIPT)]) + ["--window"] + (["--demo"] if DEMO else [])
    if IS_WIN:
        subprocess.Popen(args, cwd=str(HERE), creationflags=NO_WINDOW)
    else:
        subprocess.Popen(args, cwd=str(HERE), start_new_session=True)


# ---------------- 시작 시 실행 ----------------
if IS_WIN:
    STARTUP = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup\세션 트레이.lnk"
elif IS_MAC:
    STARTUP = HOME / "Library" / "LaunchAgents" / "com.eehnodu.session-tray.plist"
else:
    STARTUP = HOME / ".config" / "autostart" / "session-tray.desktop"


def startup_enabled() -> bool:
    return STARTUP.exists()


def toggle_startup() -> None:
    if startup_enabled():
        STARTUP.unlink(missing_ok=True)
        return
    STARTUP.parent.mkdir(parents=True, exist_ok=True)
    if IS_WIN:
        exe = Path(sys.executable) if FROZEN else Path(sys.executable).with_name("pythonw.exe")
        arg = "" if FROZEN else f'"{SCRIPT}"'
        q = lambda v: str(v).replace("'", "''")  # noqa: E731
        ps = (
            f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(STARTUP)}');"
            f"$s.TargetPath='{q(exe)}';$s.Arguments='{q(arg)}';$s.WorkingDirectory='{q(HERE)}';$s.IconLocation='{q(ensure_ico())}';$s.Save()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=NO_WINDOW)
    elif IS_MAC:
        STARTUP.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.eehnodu.session-tray</string>
  <key>ProgramArguments</key><array><string>{sys.executable}</string>{"" if FROZEN else f"<string>{SCRIPT}</string>"}</array>
  <key>WorkingDirectory</key><string>{HERE}</string>
  <key>RunAtLoad</key><true/>
</dict></plist>
""",
            encoding="utf-8",
        )
    else:
        cmd = sys.executable if FROZEN else f"{sys.executable} {SCRIPT}"
        STARTUP.write_text(f"[Desktop Entry]\nType=Application\nName=Session Tray\nExec={cmd}\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")


# ---------------- 새 버전 ----------------
def _ver(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", tag)[:3]) or (0,)


def latest_version() -> str | None:
    """GitHub 의 최신 Release 태그(v1.2.3 → 1.2.3). 네트워크가 없으면 None"""
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest", headers={"User-Agent": f"session-tray/{__version__}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=6) as res:
            tag = json.loads(res.read().decode("utf-8")).get("tag_name", "")
        return tag.lstrip("v") or None
    except Exception:
        return None


# ---------------- 알림 ----------------
def notify(icon, title: str, message: str) -> None:
    try:
        if IS_MAC:
            esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
            subprocess.Popen(["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}"'])
        else:
            icon.notify(message, title)
    except Exception:
        log_error()


def recently_killed() -> set[str]:
    try:
        data = json.loads(KILLED_FILE.read_text(encoding="utf-8"))
        return {k for k, v in data.items() if time.time() - v < 600}
    except (OSError, ValueError):
        return set()


class Watcher:
    """트레이 쪽 감시 — 꺼짐 · 메모리 알림. 사라진 것은 두 번 연속 보였던 것만 알린다(잠깐 떴다 진 것은 빼고)"""

    def __init__(self) -> None:
        self.seen: dict[str, int] = {}  # 열쇠 → 연속으로 보인 횟수
        self.rows: dict[str, Row] = {}
        self.mem_alerted: dict[str, float] = {}

    def step(self, data: list[Row]) -> list[tuple[str, str]]:
        alerts: list[tuple[str, str]] = []
        now_rows = {r.key: r for r in data if r.kind in ("서버", "작업", "컨테이너")}
        if SETTINGS.get("notify_on_stop", True):
            killed = recently_killed()
            for k, n in self.seen.items():
                if k not in now_rows and n >= 2 and k not in killed:
                    r = self.rows[k]
                    alerts.append((_("app"), _("n_stopped", name=r.name, where=r.where)))
        self.seen = {k: self.seen.get(k, 0) + 1 for k in now_rows}
        self.rows = now_rows
        limit = float(SETTINGS.get("memory_alert_mb") or 0)
        if limit > 0:
            for k, r in now_rows.items():
                if (r.mem or 0) > limit and time.time() - self.mem_alerted.get(k, 0) > 3600:
                    self.mem_alerted[k] = time.time()
                    alerts.append((_("app"), _("n_memory", mb=r.mem, name=r.name)))
        return alerts


# ---------------- 트레이 ----------------
def run_tray() -> None:
    import pystray

    set_app_id()
    newer: list[str | None] = [None]

    def quit_all(icon, _item=None) -> None:
        if window_alive():
            try:
                psutil.Process(int(WINDOW_PID.read_text(encoding="utf-8"))).terminate()
            except (OSError, ValueError, psutil.Error):
                pass
        icon.stop()

    def toggle_notify(_icon=None, _item=None) -> None:
        save_settings(notify_on_stop=not SETTINGS.get("notify_on_stop", True))
        SETTINGS.update(load_settings())

    icon = pystray.Icon(
        "session-tray",
        make_icon(0, 0),
        _("app"),
        menu=pystray.Menu(
            pystray.MenuItem(f"{_('app')} v{__version__}", lambda _i, _m: None, enabled=False),  # 버전 표시(누르지 않음)
            pystray.MenuItem(lambda _m: _("m_update", v=newer[0] or ""), lambda _i, _m: webbrowser.open(RELEASES), visible=lambda _m: bool(newer[0])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_("m_show"), lambda _i, _m: show_window(), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_("m_startup_win") if IS_WIN else _("m_startup"), lambda _i, _m: toggle_startup(), checked=lambda _m: startup_enabled()),
            pystray.MenuItem(_("m_notify"), toggle_notify, checked=lambda _m: bool(SETTINGS.get("notify_on_stop", True))),
            pystray.MenuItem(_("m_settings"), lambda _i, _m: open_settings()),
            pystray.MenuItem(_("m_quit"), quit_all),  # 이 프로그램만 끈다 — 서버 · 작업은 그대로
        ),
    )

    def watch() -> None:
        # 아이콘 점 · 툴팁을 15초마다 갱신(초록 = 서버 · 컨테이너 있음, 주황 = 작업만) + 알림
        w = Watcher()
        settings_mtime = 0.0
        while True:
            try:
                m = SETTINGS_FILE.stat().st_mtime if SETTINGS_FILE.exists() else 0.0
                if m != settings_mtime:  # 설정 파일을 고치면 바로 반영
                    settings_mtime = m
                    SETTINGS.update(load_settings())
                    ROOTS[:] = project_roots()
                data = collect()
                s = sum(r.kind == "서버" for r in data)
                j = sum(r.kind == "작업" for r in data)
                d = sum(r.kind == "컨테이너" for r in data)
                c = sum(r.kind == "Claude" for r in data)
                icon.icon = make_icon(s + d, j)
                icon.title = f"{_('tip', s=s, j=j, d=d, c=c)}\n{system_usage()}"[:127]
                for title, msg in w.step(data):
                    notify(icon, title, msg)
            except Exception:
                log_error()
            time.sleep(15)

    def check_updates() -> None:
        # 시작 30초 뒤, 그다음 하루에 한 번
        time.sleep(30)
        told = None
        while True:
            try:
                if SETTINGS.get("check_updates", True):
                    v = latest_version()
                    if v and _ver(v) > _ver(__version__):
                        newer[0] = v
                        icon.update_menu()
                        if told != v:
                            told = v
                            notify(icon, _("app"), _("n_update", v=v))
            except Exception:
                log_error()
            time.sleep(24 * 3600)

    def setup(ic) -> None:
        ic.visible = True
        threading.Thread(target=watch, daemon=True).start()
        threading.Thread(target=check_updates, daemon=True).start()

    icon.run(setup=setup)  # macOS 는 메인 스레드에서 돌아야 한다


# ---------------- 점검 · 빌드 ----------------
def selftest() -> None:
    """화면 없이 도는 점검 — 빌드 머신(CI)에서 쓴다. 문제가 있으면 예외로 끝난다"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 영문 코드 페이지 콘솔(Windows 빌드 머신)에서도 한글 출력
    except (AttributeError, ValueError):
        pass
    import tkinter  # noqa: F401  창에 필요한 tkinter 가 있는지

    import pystray  # noqa: F401

    t0 = time.time()
    data = collect_processes() + collect_docker() + collect_claude()
    make_icon(1, 0, 64)
    print(f"{_('app')} v{__version__} · {platform.system()} {platform.release()} · Python {platform.python_version()} · lang={LANG}")
    print(f"found {len(data)} ({time.time() - t0:.2f}s) · {system_usage()}")
    for r in data[:10]:
        print(f"  {r.kind} | {r.name} | {r.where}")
    # 경로 → 프로젝트 이름
    assert _project_of(str(HOME / "dev" / "shop" / ".venv" / "bin" / "python")) == "shop"
    # 명령 줄이기: 실행 파일 경로를 뗀다
    for raw, want in (
        (r"C:\Py\python.exe -m scripts.run", "-m scripts.run"),
        (r"C:\Py\pythonw.exe app.pyw", "app.pyw"),
        ("/usr/bin/python3.12 -m uvicorn x", "-m uvicorn x"),
        (r'"C:\Program Files\nodejs\node.exe" vite', "vite"),
    ):
        assert _short_cmd(raw) == want, (raw, _short_cmd(raw))
    # Docker 출력 읽기
    sample = '{"ID":"3f2a9c1b7d4e","Names":"shop-db","Image":"postgres:16","Ports":"0.0.0.0:5432->5432/tcp, :::5432->5432/tcp","Status":"Up 2 hours","CreatedAt":"2026-01-01 10:00:00 +0900 KST"}'
    d = parse_docker_ps(sample)
    assert d and d[0].ports == [5432] and d[0].container == "3f2a9c1b7d4e" and d[0].since, d
    # 버전 비교
    assert _ver("v1.10.0") > _ver("1.9.9") > _ver("1.0.1")
    # 꺼짐 알림: 두 번 보였던 것이 사라지면 한 번 알린다
    saved = SETTINGS.get("notify_on_stop")
    SETTINGS["notify_on_stop"] = True
    w = Watcher()
    a = Row("서버", "selftest-x", ":1", 1, detail="selftest")
    w.step([a])
    w.step([a])
    assert len(w.step([])) == 1
    SETTINGS["notify_on_stop"] = saved
    # 두 언어 문구가 다 있는지
    for k, (ko, en) in TEXT.items():
        assert ko and en, k
    print("OK")


def export_icons(out: Path) -> None:
    """빌드용 아이콘 파일(.png · .ico · .icns)을 만든다"""
    out.mkdir(parents=True, exist_ok=True)
    big = make_icon(0, 0, 1024)
    big.save(out / "icon.png")
    big.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    big.save(out / "icon.icns")
    print("icons:", ", ".join(sorted(x.name for x in out.iterdir())))


def main() -> None:
    if "--selftest" in sys.argv:
        selftest()
    elif "--export-icons" in sys.argv:
        export_icons(Path(sys.argv[sys.argv.index("--export-icons") + 1]))
    elif "--window" in sys.argv:
        run_window()
    else:
        run_tray()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_error()
        raise
