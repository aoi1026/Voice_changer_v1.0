# Plataform config
from rvc.lib.platform import platform_config

platform_config()

import asyncio
import os
import sys
import time
import logging

from typing import Any

# Use project-owned temp dir for Gradio to avoid Windows permission errors on system temp
now_dir = os.getcwd()
gradio_temp = os.path.join(now_dir, "assets", "gradio_temp")
os.makedirs(gradio_temp, exist_ok=True)
# Clear old temp files on startup to avoid PermissionError when serving stale paths (e.g. on Windows)
try:
    now = time.time()
    for name in os.listdir(gradio_temp):
        path = os.path.join(gradio_temp, name)
        if os.path.isdir(path):
            for f in os.listdir(path):
                fp = os.path.join(path, f)
                if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > 3600:
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
            try:
                if not os.listdir(path):
                    os.rmdir(path)
            except OSError:
                pass
        elif os.path.isfile(path) and (now - os.path.getmtime(path)) > 3600:
            try:
                os.remove(path)
            except OSError:
                pass
except OSError:
    pass
os.environ.setdefault("GRADIO_TEMP_DIR", gradio_temp)

import gradio as gr

# On Windows, suppress ConnectionResetError when a client disconnects during long-running
# inference (e.g. browser tab closed). The conversion still completes; the error is just noise.
if sys.platform == "win32":
    import socket
    import asyncio.proactor_events as _proactor_events

    _orig_call_connection_lost = _proactor_events._ProactorBasePipeTransport._call_connection_lost

    def _patched_call_connection_lost(self, exc):
        try:
            _orig_call_connection_lost(self, exc)
        except ConnectionResetError:
            # Client closed connection; finish cleanup without shutting down the socket
            if not getattr(self, "_called_connection_lost", True):
                try:
                    if self._sock is not None and self._sock.fileno() != -1:
                        self._sock.close()
                except OSError:
                    pass
                self._sock = None
                server = getattr(self, "_server", None)
                if server is not None:
                    server._detach()
                    self._server = None
                self._called_connection_lost = True

    _proactor_events._ProactorBasePipeTransport._call_connection_lost = _patched_call_connection_lost

DEFAULT_SERVER_NAME = "127.0.0.1"
DEFAULT_PORT = 6969
MAX_PORT_ATTEMPTS = 10

# Set up logging
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add current directory to sys.path
sys.path.append(now_dir)

# Zluda hijack
import rvc.lib.zluda

# Import Tabs (Inference only)
from tabs.inference.inference import inference_tab

# Run prerequisites
from core import run_prerequisites_script

run_prerequisites_script(
    pretraineds_hifigan=True,
    models=True,
    exe=True,
)

# Initialize i18n
from assets.i18n.i18n import I18nAuto

i18n = I18nAuto()

# Check installation
import assets.installation_checker as installation_checker

installation_checker.check_installation()

# Load theme
import assets.themes.loadThemes as loadThemes

my_applio = loadThemes.load_theme() or "ParityError/Interstellar"

# Define Gradio interface
with gr.Blocks(
    title="George Michael Voice Converter v1.0",
) as Applio:
    gr.Markdown(
        "<div style='text-align: center; padding: 0.75em 0;'>"
        "<h1 style='font-size: 1.5em; margin:1.25em 0; line-height: 1.3;'>George Michael Voice Converter v1.0</h1>"
        "</div>"
    )
    inference_tab()

    


def launch_gradio(server_name: str, server_port: int) -> None:
    # When running as desktop app, suppress Gradio's "To create a public link..." message
    _desktop = os.environ.pop("VOICE_CHANGER_DESKTOP", None)
    if _desktop:
        _orig_stdout = sys.stdout
        class _FilteredStdout:
            def __init__(self):
                self._buf = ""
            def write(self, s):
                self._buf += s
                while "\n" in self._buf or "\r" in self._buf:
                    line, _, self._buf = self._buf.partition("\n")
                    if "\r" in line:
                        line, _, _ = line.partition("\r")
                    if "To create a public link" not in line and "share=True" not in line:
                        _orig_stdout.write(line + "\n")
            def flush(self):
                if self._buf and "To create a public link" not in self._buf:
                    _orig_stdout.write(self._buf)
                self._buf = ""
                _orig_stdout.flush()
            def isatty(self):
                return getattr(_orig_stdout, "isatty", lambda: False)()
        sys.stdout = _FilteredStdout()
    try:
        Applio.launch(
            favicon_path="assets/ICON.ico",
            share="--share" in sys.argv,
            inbrowser="--open" in sys.argv,
            server_name=server_name,
            server_port=server_port,
            theme=my_applio,
            css=(
                "footer{display:none !important}"
                " .gr-audio { --audio-controls-padding: 6px; }"
                " .gr-audio .gr-form, .gr-audio .gr-padded, .gr-audio > div { padding-top: 4px; padding-bottom: 6px; overflow: visible !important; }"
                " .gr-audio .gr-text-sm, .gr-audio .gr-text-small, .gr-audio span.gr-text, .gr-audio [class*='text'] { line-height: 1.5 !important; padding-top: 2px !important; overflow: visible !important; min-height: 1.4em; }"
                " .timestamps.svelte-1ffmt2w { margin-top: 20px;}"
                " .gradio-container-6-5-1 { font-family: 'Arial', monospace; }"
                " .gr-audio input[type='range'] { margin-top: 2px; }"
            ),
        )
    finally:
        if _desktop:
            sys.stdout = _orig_stdout


def get_value_from_args(key: str, default: Any = None) -> Any:
    if key in sys.argv:
        index = sys.argv.index(key) + 1
        if index < len(sys.argv):
            return sys.argv[index]
    return default


if __name__ == "__main__":
    port = int(get_value_from_args("--port", DEFAULT_PORT))
    server = get_value_from_args("--server-name", DEFAULT_SERVER_NAME)

    for _ in range(MAX_PORT_ATTEMPTS):
        try:
            launch_gradio(server, port)
            break
        except OSError:
            print(
                f"Failed to launch on port {port}, trying again on port {port - 1}..."
            )
            port -= 1
        except Exception as error:
            print(f"An error occurred launching Gradio: {error}")
            break
