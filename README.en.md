<p align="center"><img src="assets/icon.png" width="96" alt=""></p>
<h1 align="center">Session Tray</h1>
<p align="center">See dev servers, background jobs, Docker containers and Claude Code sessions, with CPU and memory, from the taskbar or menu bar (Windows · macOS)</p>

<p align="center"><a href="README.md">한국어</a> · English</p>

One tray icon shows the dev processes running on your computer, and lets you stop the ones you don't need.

## Features

- Dev servers: node, python, java and others that listen on a port, with project name and port
- Background jobs: scripts without a port (bots, workers and so on), listed separately
- Docker containers: running containers with ports and image (only if Docker is installed)
- Claude Code sessions: sessions active in the last 15 minutes, with title and folder; open one in the Claude app
- Usage: CPU and memory per item (children included), plus whole-computer usage
- Quick actions: search, open in browser, open folder, stop (containers are stopped with Docker)
- Alerts: when a server, job or container stops, or uses a lot of memory (off at first)
- Update check: once a day; a new version shows up in the icon menu
- Korean and English, Windows dark mode, remembers window size and position

## Screenshots

<p align="center"><img src="assets/window.en.png" alt="Session window (demo data)"></p>

Icon status: <img src="assets/states.png" height="40" align="center" alt="Icon states"> no dot = nothing running · green = servers or containers · orange = jobs only

## Download

Get it from [Releases](https://github.com/Eehnodu/session-tray/releases/latest).

| Computer | File |
|---|---|
| Windows 10 · 11 | [SessionTray-windows.exe](https://github.com/Eehnodu/session-tray/releases/latest/download/SessionTray-windows.exe) (runs without installing) |
| macOS | [SessionTray-macos.zip](https://github.com/Eehnodu/session-tray/releases/latest/download/SessionTray-macos.zip) |

- Windows: put the file in any folder and double-click it. If "Windows protected your PC" appears, click More info → Run anyway. It appears because the app is not code-signed. The icon is under the `^` (hidden icons) arrow on the taskbar.
- macOS: unzip, move `Session Tray` to Applications and open it. If it is blocked the first time, go to System Settings → Privacy & Security → Open Anyway. The icon appears in the menu bar at the top of the screen.

## How to use

- Right-click the icon → Show sessions (on Windows, double-clicking the icon also works). The window refreshes every 5 seconds.
- Stop at the end of a row: after you confirm, stops only that process and its children. Containers are stopped.
- Open at the end of a Claude session row: opens that conversation in the Claude desktop app.
- Right-click a row (Control+click on macOS): Open in browser · Open folder · Open in Claude · Stop
- Double-click a row: a server opens in the browser, a Claude session in the Claude app, anything else opens its folder.
- Search box at the top: filters by project name, port or command (Esc clears it).
- Icon menu: Show notifications · Start with Windows (Open at login on macOS) · Open settings file · Quit tray

Quitting the tray leaves your servers and jobs running.

### What it shows

- Dev servers: node, python, java, deno, bun, ruby, php or go listening on a port from 1024 to 49151
- Background jobs: running from your user folders (`~/dev`, `~/projects`, `~/Documents`, `~/Desktop` and so on) without a port
- Docker containers: whatever `docker ps` lists
- Claude Code sessions: conversation logs in `~/.claude/projects` changed in the last 15 minutes
- Child processes doing the same job (`npm` → `vite` and so on) are folded into one row. Internal tools of editors and apps are left out.
- Everything is read on your computer. Only the update check contacts GitHub, to ask for the latest version number.

### Settings

Icon menu → Open settings file. Save it and the change applies right away (the window picks it up the next time it opens).

| Key | Default | Meaning |
|---|---|---|
| `language` | `"auto"` | Set `"ko"` or `"en"` to fix the language |
| `extra_roots` | `[]` | More folders where you keep projects (for example `["D:/code", "~/work"]`) |
| `active_minutes` | `15` | Show Claude sessions active within this many minutes |
| `refresh_seconds` | `5` | How often the window refreshes |
| `notifications` | `false` | All notifications (same as Show notifications in the menu) |
| `notify_on_stop` | `true` | Also report stops |
| `memory_alert_mb` | `2048` | Alert when one item uses more than this many MB (`0` turns it off) |
| `check_updates` | `true` | Check for a new version once a day |

### Troubleshooting

| Problem | What to check |
|---|---|
| No icon | Windows: look inside the `^` hidden icons |
| Window doesn't open or closes suddenly | Error log: Windows `%LOCALAPPDATA%\session-tray\session_tray.log`, macOS `~/Library/Application Support/session-tray/session_tray.log` |
| A server isn't listed | Started outside your user folders and without a port, it isn't shown. Add that folder to `extra_roots` in the settings |
| No alerts | Check that Show notifications is on in the menu, and that notifications are allowed in Windows Settings → System → Notifications |
| macOS says the app "is damaged and can't be opened" | Download the latest version again. If it still happens, run `xattr -cr "/Applications/Session Tray.app"` and open it again |

## Run from source

You need Python 3.10 or later and git. If `uv` is installed, the scripts use it.

```bash
git clone https://github.com/Eehnodu/session-tray.git
cd session-tray
powershell -ExecutionPolicy Bypass -File install.ps1   # Windows
bash install.sh                                        # macOS
```

The install scripts create a virtual environment, install the dependencies and start the tray. To update, `git pull` and run the script again.

```bash
python session_tray.pyw                     # start the tray (on Windows, pythonw starts it without a console)
python session_tray.pyw --window --demo     # window only, with demo data (--lang=en · --light · --dark)
python session_tray.pyw --selftest          # check without a screen
```

## Tech stack

Python · pystray · psutil · Pillow · tkinter, executables built with PyInstaller

## License

[MIT](LICENSE)
