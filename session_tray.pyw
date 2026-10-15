"""세션 트레이 — 작업 표시줄(Windows) · 메뉴 막대(macOS) 아이콘에서 지금 돌아가는 것을 본다.

- 개발 서버: 포트를 열고 있는 node · python 등(어느 프로젝트 · 포트)
- 백그라운드 작업: 포트 없이 도는 사용자 폴더의 node · python
- Claude 세션: 최근 15분 안에 대화가 오간 Claude Code 세션(폴더 · 제목)
- 항목별 CPU · 메모리, PC 전체 사용량

구조: 트레이 프로세스는 아이콘 · 메뉴만 맡고, "세션 보기"를 누르면 창을 별도 프로세스(--window)로 띄운다.
macOS 는 메뉴 막대 아이콘과 창을 한 프로세스의 메인 스레드에서 같이 돌릴 수 없어서 이렇게 나눴다.

실행: Windows  pythonw session_tray.pyw   ·   macOS  python3 session_tray.pyw
"""

from __future__ import annotations

__version__ = "1.0.0"  # 바꾸면 README 의 버전 기록 · git 태그도 같이

import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

import psutil
from PIL import Image, ImageDraw

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
HOME = Path.home()
CLAUDE_PROJECTS = HOME / ".claude" / "projects"
ACTIVE_MINUTES = 15
SELF_PID = os.getpid()
FROZEN = bool(getattr(sys, "frozen", False))  # 실행 파일(.exe · .app)로 돌고 있나
SCRIPT = Path(sys.executable if FROZEN else __file__).resolve()
HERE = SCRIPT.parent
APP_ID = "Eehnodu.SessionTray"

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
WINDOW_PID = STATE / "window.pid"
RAISE_FILE = STATE / "raise"  # 트레이가 이 파일을 건드리면 떠 있는 창이 앞으로 나온다
FONT = (FONT_FAMILY, 13 if IS_MAC else 10)
DEMO = "--demo" in sys.argv

# 실행 파일 이름(확장자 뺀 것, 소문자) — 정확히 같거나 python 으로 시작할 때만 본다
WATCH_NAMES = {"node", "python", "pythonw", "uvicorn", "java", "deno", "bun", "ruby", "php", "go"}

# 프로젝트가 있을 만한 곳 — 앞에 있는 것부터 본다. 여기 없으면 사용자 폴더 기준 경로로 보인다
ROOTS = [HOME / "dev" / "project", HOME / "dev", HOME / "source" / "repos", HOME / "projects", HOME / "Documents", HOME / "Desktop", HOME]
# 앱 · 편집기 내부 도구는 뺀다(경로를 / 로 바꾸고 소문자로 비교)
SKIP = ("/appdata/", "/.vscode", "/.cursor", "/.claude/", "/program files", "/windows/", "/.local/", "/library/", "/applications/", "/.nvm/", "/.pyenv/", "/opt/homebrew/")
STOP = {"node_modules", ".venv", "venv", "scripts", "src", "frontend", "backend", "dist", ".bin", "lib", "bin"}


@dataclass
class Row:
    kind: str  # "서버" · "작업" · "Claude"
    name: str  # 프로젝트 · 세션 제목
    where: str  # 포트 · 위치
    pid: int | None = None
    since: float | None = None  # 시작(또는 마지막 활동) 시각
    detail: str = ""
    ports: list[int] = field(default_factory=list)
    folder: str | None = None
    cpu: float | None = None  # 전체 CPU 대비 %(자식 프로세스 포함)
    mem: float | None = None  # MB(자식 프로세스 포함)


def log_error() -> None:
    """창 없이 도는 프로세스라 오류가 안 보인다 — 마지막 오류를 session_tray.log 에 남긴다"""
    import traceback

    try:
        LOG.write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + traceback.format_exc(), encoding="utf-8")
    except OSError:
        pass


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
        return "CPU 12% · 메모리 9.4/16GB (59%)"
    vm = psutil.virtual_memory()
    return f"CPU {psutil.cpu_percent(None):.0f}% · 메모리 {vm.used / 1073741824:.1f}/{vm.total / 1073741824:.0f}GB ({vm.percent:.0f}%)"


# ---------------- 찾기 ----------------
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


def collect_processes() -> list[Row]:
    listen = _listening_all()
    cands: dict[int, tuple[psutil.Process, str, str | None, float, int | None]] = {}
    # 이름만 먼저 훑는다 — 시작 시각 · 부모를 처음부터 같이 읽으면 시스템 프로세스 때문에 20 ~ 30초 걸린다(Windows 실측)
    for p in psutil.process_iter(["name"]):
        try:
            name = (p.info["name"] or "").lower().removesuffix(".exe")
            if p.pid == SELF_PID or not (name in WATCH_NAMES or name.startswith("python")):
                continue
            cmd = _cmd(p)
            if "session_tray" in cmd:
                continue  # 이 도구 자신(트레이 · 창)
            cwd = _cwd(p)
            ports = listen.get(p.pid, set()) if listen is not None else _listening_of(p)
            proj = _project_of(cmd) or _project_of(cwd)
            if not proj and not ports:
                continue  # 사용자 폴더 밖 · 앱 내부의 node · python
            if listen is None and ports:
                listen_local = ports
            else:
                listen_local = ports
            cands[p.pid] = (p, cmd, cwd, p.create_time(), p.ppid())
            p.info["ports"] = listen_local
        except (psutil.Error, OSError):
            continue

    rows: list[Row] = []
    for pid, (p, cmd, cwd, created, ppid) in cands.items():
        if ppid in cands:
            continue  # 자식은 부모 한 줄로 묶는다(.venv 런처 → 실제 python, npm → vite 등) — 부모가 자식의 포트까지 보인다
        kids = [c for c, v in cands.items() if c != pid and v[4] == pid]
        ports = sorted(set(p.info.get("ports", set())).union(*(cands[c][0].info.get("ports", set()) for c in kids)))
        try:
            tree = [pid] + [c.pid for c in p.children(recursive=True)]
        except psutil.Error:
            tree = [pid, *kids]
        cpu, mem = usage(tree)
        short = re.sub(r'^"?[^"\s]*[\\/](node|python[\d.]*|pythonw)(\.exe)?"?\s*', "", cmd, flags=re.I)
        short = re.sub(r"\S*node_modules[\\/]\.bin[\\/]+\.\.[\\/]", "", short)
        rows.append(
            Row(
                kind="서버" if ports else "작업",
                name=_project_of(cmd) or _project_of(cwd) or (p.info.get("name") or ""),
                where=", ".join(f":{x}" for x in ports) if ports else (p.info.get("name") or ""),
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
    for f in CLAUDE_PROJECTS.glob("*/*.jsonl"):
        try:
            mt = f.stat().st_mtime
        except OSError:
            continue
        if now - mt > ACTIVE_MINUTES * 60:
            continue
        try:
            t = _tail(f)
        except OSError:
            continue
        title = _last_json_str(t, '"customTitle":"') or _last_json_str(t, '"aiTitle":"')
        cwd = _last_json_str(t, '"cwd":"')
        rows.append(Row(kind="Claude", name=title or f.stem[:8], where=_project_of(cwd) or (cwd or f.parent.name), since=mt, detail=f"세션 {f.stem}", folder=cwd))
    rows.sort(key=lambda r: -(r.since or 0))
    return rows


def demo_rows() -> list[Row]:
    """README 캡처용 예시 — 실제 컴퓨터 정보를 쓰지 않는다(--demo)"""
    now = time.time()
    return [
        Row("서버", "shop/web", ":5173", 18420, now - 3 * 3600, "vite --port 5173", [5173], str(HOME), 1.8, 212),
        Row("서버", "shop/api", ":8000", 18533, now - 3 * 3600, "-m uvicorn app.main:app --reload --port 8000", [8000], str(HOME), 0.6, 96),
        Row("작업", "trading-bot", "python.exe", 20711, now - 21 * 3600, "-m scripts.run_scanner", [], str(HOME), 0.4, 71),
        Row("Claude", "결제 화면 리팩터링", "shop", None, now - 40, "세션 7f3c…", [], str(HOME)),
        Row("Claude", "README 정리", "session-tray", None, now - 6 * 60, "세션 a91e…", [], str(HOME)),
    ]



def collect() -> list[Row]:
    if DEMO:
        return demo_rows()
    return collect_processes() + collect_claude()


def ago(ts: float | None, claude: bool) -> str:
    if not ts:
        return "-"
    s = int(time.time() - ts)
    if s < 60:
        t = f"{s}초"
    elif s < 3600:
        t = f"{s // 60}분"
    elif s < 86400:
        t = f"{s // 3600}시간 {s % 3600 // 60}분"
    else:
        t = f"{s // 86400}일"
    return f"{t} 전 활동" if claude else f"{t}째"


# ---------------- 아이콘 ----------------
def make_icon(servers: int, jobs: int, size: int = 64) -> Image.Image:
    """남색 둥근 네모 + 겹친 창 두 장(세션들). 상태 점: 초록 = 서버 있음 · 주황 = 작업만. 크게 그려 줄여서 가장자리를 매끄럽게"""
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


def open_path(path: str) -> None:
    if IS_WIN:
        subprocess.Popen(["explorer", path])
    elif IS_MAC:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------- 창(별도 프로세스) ----------------
def run_window() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    from PIL import ImageTk

    set_app_id()
    WINDOW_PID.write_text(str(SELF_PID), encoding="utf-8")
    root = tk.Tk()
    root.title(f"실행 중인 세션 · 세션 트레이 v{__version__}" + (" (예시)" if DEMO else ""))
    if IS_WIN:
        try:
            root.iconbitmap(default=str(ensure_ico()))
        except tk.TclError:
            pass
    icon_img = ImageTk.PhotoImage(make_icon(0, 0, 64))
    root.iconphoto(True, icon_img)
    root.geometry("1220x560")
    root.minsize(720, 320)

    style = ttk.Style(root)
    style.configure("Treeview", font=FONT, rowheight=30 if IS_MAC else 28)
    style.configure("Treeview.Heading", font=(FONT[0], FONT[1], "bold"))
    style.configure("TButton", font=FONT, padding=(10, 4))

    rows: dict[str, Row] = {}
    labels: dict[str, tk.Label] = {}

    bar = ttk.Frame(root, padding=(12, 10, 12, 6))
    bar.pack(fill="x")
    status = tk.StringVar(value="")

    cols = ("where", "pid", "cpu", "mem", "since", "detail", "action")
    t = ttk.Treeview(root, columns=cols, show="tree headings", selectmode="browse")
    for c, text in (("#0", "이름"), ("where", "포트 · 위치"), ("pid", "PID"), ("cpu", "CPU"), ("mem", "메모리"), ("since", "시간"), ("detail", "명령 · 세션"), ("action", "")):
        t.heading(c, text=text)
    t.column("#0", width=240, stretch=False)
    t.column("where", width=150, stretch=False)
    t.column("pid", width=70, anchor="e", stretch=False)
    t.column("cpu", width=64, anchor="e", stretch=False)
    t.column("mem", width=84, anchor="e", stretch=False)
    t.column("since", width=120, anchor="center", stretch=False)  # 메모리 숫자와 붙지 않게 가운데
    t.column("detail", width=260, minwidth=120)  # 남는 폭을 이 칸이 가져간다 — 종료 칸이 잘리지 않게
    t.column("action", width=70, anchor="center", stretch=False)
    ACTION = f"#{len(cols)}"

    def selected() -> Row | None:
        s = t.selection()
        return rows.get(s[0]) if s else None

    def place_labels() -> None:
        """표 칸은 글자색을 따로 못 바꾼다 — 종료 칸 위에 빨간 라벨을 얹고, 칸이 움직일 때마다 다시 맞춘다"""
        sel = set(t.selection())
        bg_norm = style.lookup("Treeview", "fieldbackground") or style.lookup("Treeview", "background") or "white"
        bg_sel = style.lookup("Treeview", "background", ["selected"]) or "#0078d7"
        live = set()
        for iid, r in rows.items():
            if not r.pid:
                continue
            box = t.bbox(iid, column="action")
            if not box:
                continue  # 접힌 묶음 · 화면 밖
            live.add(iid)
            lab = labels.get(iid)
            if lab is None or not lab.winfo_exists():
                lab = tk.Label(t, text="종료", font=(FONT[0], FONT[1], "bold"), cursor="hand2", bd=0)
                lab.bind("<Button-1>", lambda _e, i=iid: (t.selection_set(i), root.after(10, kill)))
                labels[iid] = lab
            x, y, w, h = box
            lab.configure(bg=bg_sel if iid in sel else bg_norm, fg="#ffffff" if iid in sel else "#dc2626")
            lab.place(x=x + 1, y=y + 1, width=w - 2, height=h - 2)
        for iid in list(labels):
            if iid not in live:
                labels.pop(iid).destroy()

    def refresh() -> None:
        sel = selected()
        keep = (sel.kind, sel.pid, sel.detail) if sel else None
        data = collect()
        t.delete(*t.get_children())
        rows.clear()
        for lab in labels.values():
            lab.destroy()
        labels.clear()
        groups = {"서버": "개발 서버", "작업": "백그라운드 작업", "Claude": f"Claude 세션 (최근 {ACTIVE_MINUTES}분)"}
        for kind, label in groups.items():
            items = [r for r in data if r.kind == kind]
            g = t.insert("", "end", text=f"{label}  {len(items)}", open=True)
            if not items:
                t.insert(g, "end", text="없음", values=("",) * len(cols))
            for r in items:
                cpu = f"{r.cpu:.1f}%" if r.cpu is not None else "-"
                mem = f"{r.mem:,.0f} MB" if r.mem is not None else "-"
                iid = t.insert(g, "end", text=r.name, values=(r.where, r.pid or "", cpu, mem, ago(r.since, r.kind == "Claude"), r.detail, ""))
                rows[iid] = r
                if keep and (r.kind, r.pid, r.detail) == keep:
                    t.selection_set(iid)
        status.set(f"{system_usage()}   ·   갱신 {time.strftime('%H:%M:%S')}")
        root.after_idle(place_labels)

    def open_browser(silent: bool = False) -> bool:
        r = selected()
        if r and r.ports:
            webbrowser.open(f"http://localhost:{r.ports[0]}")
            return True
        if not silent:
            messagebox.showinfo("브라우저로 열기", "포트가 있는 개발 서버를 골라 주세요.", parent=root)
        return False

    def open_folder() -> None:
        r = selected()
        if r and r.folder and Path(r.folder).exists():
            open_path(r.folder)
        elif r:
            messagebox.showinfo("폴더 열기", "이 항목의 폴더를 찾지 못했습니다.", parent=root)

    def kill() -> None:
        r = selected()
        if not r or not r.pid:
            messagebox.showinfo("종료", "끌 서버 · 작업을 골라 주세요. Claude 세션은 Claude 에서 닫아 주세요.", parent=root)
            return
        if not messagebox.askyesno("종료", f"{r.name} ({r.where})\nPID {r.pid} 를 종료할까요?\n\n{r.detail}", parent=root):
            return
        if DEMO:
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
            messagebox.showerror("종료", f"종료하지 못했습니다: {e}", parent=root)
        refresh()

    for text, cmd in (("새로고침", refresh), ("브라우저로 열기", open_browser), ("폴더 열기", open_folder)):  # 종료는 줄 끝 "종료" 칸 · 우클릭에서
        ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))
    ttk.Label(bar, textvariable=status, font=FONT).pack(side="right")
    t.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    menu = tk.Menu(root, tearoff=False, font=FONT)
    menu.add_command(label="브라우저로 열기", command=open_browser)
    menu.add_command(label="폴더 열기", command=open_folder)
    menu.add_separator()
    menu.add_command(label="종료", command=kill)

    def on_click(e: tk.Event) -> None:
        if t.identify_region(e.x, e.y) != "cell":
            return
        iid = t.identify_row(e.y)
        if t.identify_column(e.x) == ACTION and iid in rows and rows[iid].pid:
            t.selection_set(iid)
            root.after(10, kill)  # 고른 표시가 먼저 그려진 뒤 묻는다

    def on_right(e: tk.Event) -> None:
        iid = t.identify_row(e.y)
        if not iid or iid not in rows:
            return
        t.selection_set(iid)
        r = rows[iid]
        menu.entryconfigure(0, state="normal" if r.ports else "disabled")
        menu.entryconfigure(1, state="normal" if r.folder else "disabled")
        menu.entryconfigure(3, state="normal" if r.pid else "disabled")
        menu.tk_popup(e.x_root, e.y_root)

    def on_motion(e: tk.Event) -> None:
        iid = t.identify_row(e.y)
        on = t.identify_column(e.x) == ACTION and iid in rows and bool(rows[iid].pid)
        t.configure(cursor="hand2" if on else "")

    t.bind("<Double-1>", lambda _e: open_browser(silent=True) or open_folder())
    t.bind("<Button-1>", on_click)
    # 우클릭: Windows 는 3번 단추, macOS 는 2번 단추와 Control+클릭
    for ev in ("<Button-2>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",):
        t.bind(ev, on_right)
    t.bind("<Motion>", on_motion)
    for ev in ("<Configure>", "<<TreeviewOpen>>", "<<TreeviewClose>>", "<<TreeviewSelect>>", "<MouseWheel>", "<ButtonRelease-1>", "<KeyRelease>"):
        t.bind(ev, lambda _e: root.after_idle(place_labels), add="+")

    last_raise = [RAISE_FILE.stat().st_mtime if RAISE_FILE.exists() else 0.0]

    def tick() -> None:
        refresh()
        root.after(5000, tick)

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
    flags = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW
    subprocess.Popen(args, cwd=str(HERE), creationflags=flags) if IS_WIN else subprocess.Popen(args, cwd=str(HERE), start_new_session=True)


# ---------------- 시작 시 실행 ----------------
if IS_WIN:
    STARTUP = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup\세션 트레이.lnk"
    STARTUP_LABEL = "윈도우 시작 시 실행"
elif IS_MAC:
    STARTUP = HOME / "Library" / "LaunchAgents" / "com.eehnodu.session-tray.plist"
    STARTUP_LABEL = "로그인 시 실행"
else:
    STARTUP = HOME / ".config" / "autostart" / "session-tray.desktop"
    STARTUP_LABEL = "로그인 시 실행"


def startup_enabled() -> bool:
    return STARTUP.exists()


def toggle_startup() -> None:
    if startup_enabled():
        STARTUP.unlink(missing_ok=True)
        return
    STARTUP.parent.mkdir(parents=True, exist_ok=True)
    if IS_WIN:
        exe = Path(sys.executable) if FROZEN else Path(sys.executable).with_name("pythonw.exe")
        arg = "" if FROZEN else f'\"{SCRIPT}\"'
        q = lambda v: str(v).replace("'", "''")  # noqa: E731
        ps = (
            f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(STARTUP)}');"
            f"$s.TargetPath='{q(exe)}';$s.Arguments='{q(arg)}';$s.WorkingDirectory='{q(HERE)}';$s.IconLocation='{q(ensure_ico())}';$s.Save()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000)
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
        STARTUP.write_text(f"[Desktop Entry]\nType=Application\nName=세션 트레이\nExec={cmd}\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")


# ---------------- 트레이 ----------------
def run_tray() -> None:
    import pystray

    set_app_id()

    def quit_all(icon, _item=None) -> None:
        if window_alive():
            try:
                psutil.Process(int(WINDOW_PID.read_text(encoding="utf-8"))).terminate()
            except (OSError, ValueError, psutil.Error):
                pass
        icon.stop()

    icon = pystray.Icon(
        "session-tray",
        make_icon(0, 0),
        "세션 트레이",
        menu=pystray.Menu(
            pystray.MenuItem(f"세션 트레이 v{__version__}", lambda _i, _m: None, enabled=False),  # 버전 표시(누르지 않음)
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("세션 보기", lambda _i, _m: show_window(), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(STARTUP_LABEL, lambda _i, _m: toggle_startup(), checked=lambda _m: startup_enabled()),
            pystray.MenuItem("트레이 끄기", quit_all),  # 이 프로그램만 끈다 — 서버 · 작업은 그대로
        ),
    )

    def watch() -> None:
        # 아이콘 점 · 툴팁을 15초마다 갱신(초록 = 서버 있음, 주황 = 작업만)
        while True:
            try:
                data = collect()
                s = sum(r.kind == "서버" for r in data)
                j = sum(r.kind == "작업" for r in data)
                c = sum(r.kind == "Claude" for r in data)
                icon.icon = make_icon(s, j)
                icon.title = f"서버 {s} · 작업 {j} · Claude {c}\n{system_usage()}"
            except Exception:
                log_error()
            time.sleep(15)

    def setup(ic) -> None:
        ic.visible = True
        threading.Thread(target=watch, daemon=True).start()

    icon.run(setup=setup)  # macOS 는 메인 스레드에서 돌아야 한다


def selftest() -> None:
    """화면 없이 도는 점검 — 빌드 머신(CI)에서 쓴다. 문제가 있으면 예외로 끝난다"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 영문 코드 페이지 콘솔(Windows 빌드 머신)에서도 한글 출력
    except (AttributeError, ValueError):
        pass
    import tkinter  # noqa: F401  창에 필요한 tkinter 가 있는지

    import pystray  # noqa: F401

    t0 = time.time()
    data = collect_processes() + collect_claude()
    make_icon(1, 0, 64)
    print(f"세션 트레이 v{__version__} · {platform.system()} {platform.release()} · Python {platform.python_version()}")
    print(f"찾은 항목 {len(data)}개 ({time.time() - t0:.2f}초) · {system_usage()}")
    for r in data[:10]:
        print(f"  {r.kind} | {r.name} | {r.where}")
    print(f"프로젝트 경로 예: {_project_of(str(HOME / 'dev' / 'shop' / '.venv' / 'bin' / 'python'))}")
    print("OK")


def export_icons(out: Path) -> None:
    """빌드용 아이콘 파일(.png · .ico · .icns)을 만든다"""
    out.mkdir(parents=True, exist_ok=True)
    big = make_icon(0, 0, 1024)
    big.save(out / "icon.png")
    big.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    big.save(out / "icon.icns")
    print("아이콘:", ", ".join(sorted(x.name for x in out.iterdir())))


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
