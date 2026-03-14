import os
import sys
import threading
import time

# Mark desktop mode so app can suppress the "create a public link" message
os.environ["VOICE_CHANGER_DESKTOP"] = "1"

import webview

from app import launch_gradio, DEFAULT_SERVER_NAME, DEFAULT_PORT


def start_server():
    """
    Start the Gradio server in a background thread.
    """
    # Ensure we run from the project root
    now_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(now_dir)
    launch_gradio(DEFAULT_SERVER_NAME, DEFAULT_PORT)


def main():
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Small delay to give the server time to start
    time.sleep(3)

    url = f"http://{DEFAULT_SERVER_NAME}:{DEFAULT_PORT}"
    window_title = "George Michael Voice Converter v1.0"

    webview.create_window(window_title, url)
    webview.start()


if __name__ == "__main__":
    # When launched directly (e.g. via run-desktop.bat), start the desktop window.
    main()

