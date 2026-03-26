from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def resolve_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resolve_runtime_root() -> Path:
    configured = os.getenv('CHEMEX_RUNTIME_ROOT')
    if configured:
        runtime_root = Path(configured)
    else:
        local_appdata = os.getenv('LOCALAPPDATA')
        if local_appdata:
            runtime_root = Path(local_appdata) / 'ChemExDesktop'
        else:
            runtime_root = Path.home() / 'AppData' / 'Local' / 'ChemExDesktop'
    runtime_root.mkdir(parents=True, exist_ok=True)
    return runtime_root


APP_ROOT = resolve_app_root()
RUNTIME_ROOT = resolve_runtime_root()
PYDEPS = APP_ROOT / 'pydeps'
if PYDEPS.exists() and str(PYDEPS) not in sys.path:
    sys.path.insert(0, str(PYDEPS))
os.environ.setdefault('CHEMEX_APP_ROOT', str(APP_ROOT))
os.environ.setdefault('CHEMEX_RUNTIME_ROOT', str(RUNTIME_ROOT))
os.environ.setdefault('MPLBACKEND', 'Agg')

LOG_FILE = RUNTIME_ROOT / 'desktop-launcher.log'


def log(message: str) -> None:
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with LOG_FILE.open('a', encoding='utf-8') as handle:
            handle.write(f'[{timestamp}] {message}\n')
    except OSError:
        pass

from werkzeug.serving import make_server
from backend.app import app

app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024


class LocalServer:
    def __init__(self) -> None:
        self.port = self._find_free_port()
        self.url = f'http://127.0.0.1:{self.port}/'
        self._server = make_server('127.0.0.1', self.port, app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('127.0.0.1', 0))
            return int(sock.getsockname()[1])

    def start(self) -> None:
        log(f'Starting local ChemEx server at {self.url}')
        self._thread.start()
        self.wait_until_ready()
        log(f'Local ChemEx server is ready at {self.url}')

    def wait_until_ready(self, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(self.url + 'api/health', timeout=1) as response:
                    if response.status == 200:
                        return
            except Exception as exc:  # pragma: no cover - polling helper
                last_error = exc
                time.sleep(0.15)
        raise RuntimeError(f'ChemEx local server failed to start: {last_error}')

    def stop(self) -> None:
        log('Stopping local ChemEx server')
        self._server.shutdown()
        self._thread.join(timeout=2)


def show_error_dialog(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
        return
    except Exception:
        pass

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        pass


def run_browser_shell(server: LocalServer) -> int:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:
        log(f'Tkinter is unavailable, falling back to plain browser mode: {exc}')
        webbrowser.open(server.url)
        while True:
            time.sleep(1)

    root = tk.Tk()
    root.title('ChemEx')
    root.geometry('440x230')
    root.minsize(440, 230)
    root.maxsize(440, 230)
    root.configure(bg='#edf3fb')

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)

    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass

    style.configure('ChemEx.TFrame', background='#edf3fb')
    style.configure('ChemEx.TLabel', background='#edf3fb', foreground='#163a5a', font=('Segoe UI', 10))
    style.configure('ChemExTitle.TLabel', background='#edf3fb', foreground='#11263c', font=('Segoe UI', 16, 'bold'))
    style.configure('ChemEx.TButton', font=('Segoe UI', 10, 'bold'))
    frame.configure(style='ChemEx.TFrame')

    title = ttk.Label(frame, text='ChemEx 已在本地离线启动', style='ChemExTitle.TLabel')
    title.pack(anchor='w')

    subtitle = ttk.Label(
        frame,
        text='界面会在默认浏览器中打开，计算仍在本机执行，不需要联网。',
        style='ChemEx.TLabel',
        wraplength=380,
        justify='left',
    )
    subtitle.pack(anchor='w', pady=(8, 14))

    url_label = ttk.Label(frame, text=server.url, style='ChemEx.TLabel')
    url_label.pack(anchor='w', pady=(0, 16))

    button_row = ttk.Frame(frame, style='ChemEx.TFrame')
    button_row.pack(fill='x', pady=(0, 14))

    def open_browser() -> None:
        log(f'Opening ChemEx in browser at {server.url}')
        webbrowser.open(server.url)

    ttk.Button(button_row, text='打开 ChemEx', command=open_browser, style='ChemEx.TButton').pack(side='left')

    def copy_url() -> None:
        root.clipboard_clear()
        root.clipboard_append(server.url)
        status_var.set('本地地址已复制到剪贴板')

    ttk.Button(button_row, text='复制地址', command=copy_url, style='ChemEx.TButton').pack(side='left', padx=(10, 0))

    status_var = tk.StringVar(value='关闭此窗口会停止本地服务')
    status_label = ttk.Label(frame, textvariable=status_var, style='ChemEx.TLabel')
    status_label.pack(anchor='w')

    def shutdown() -> None:
        try:
            root.destroy()
        finally:
            server.stop()

    root.protocol('WM_DELETE_WINDOW', shutdown)
    root.after(400, open_browser)
    root.mainloop()
    return 0


def run_self_test() -> int:
    server = LocalServer()
    server.start()
    try:
        with urllib.request.urlopen(server.url + 'api/health', timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
        print(json.dumps({'url': server.url, 'health': payload}, ensure_ascii=False))
        return 0
    finally:
        server.stop()


def run_desktop() -> int:
    server = LocalServer()
    server.start()
    try:
        return run_browser_shell(server)
    finally:
        if server._thread.is_alive():
            server.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description='ChemEx desktop launcher')
    parser.add_argument('--self-test', action='store_true', help='Start local services, query /api/health, and exit.')
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    return run_desktop()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f'Fatal desktop launcher error: {exc!r}')
        show_error_dialog('ChemEx 启动失败', f'ChemEx 无法启动。\n\n{exc}')
        raise
