import os
import time
import atexit
import queue
import threading
from datetime import datetime
from pathlib import Path
from listing_hub.core.config import SESSION_STATE_PATH

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class PlaywrightSessionManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.latest_frame = None
        self.cdp_session = None
        self.input_queue = queue.Queue()
        self.thread = None
        self.running = False
        self._lock = threading.Lock()

    def start_worker(self):
        """Start permanent background worker thread bound to Playwright."""
        with self._lock:
            if not self.running or not self.thread or not self.thread.is_alive():
                self.running = True
                self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="PlaywrightWorker")
                self.thread.start()

    def _worker_loop(self):
        """Dedicated background thread loop that owns Playwright and processes CDP events."""
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()

            headless_env = os.environ.get("HEADLESS")
            is_headless = headless_env.lower() in ("true", "1", "yes") if headless_env else ("DISPLAY" not in os.environ)
            exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
            launch_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]

            if exec_path and os.path.exists(exec_path):
                self.browser = self.playwright.chromium.launch(executable_path=exec_path, headless=is_headless, args=launch_args)
            else:
                self.browser = self.playwright.chromium.launch(headless=is_headless, args=launch_args)

            if SESSION_STATE_PATH.exists():
                self.context = self.browser.new_context(storage_state=str(SESSION_STATE_PATH), viewport={"width": 1280, "height": 800})
            else:
                self.context = self.browser.new_context(viewport={"width": 1280, "height": 800})

            self.context.set_default_timeout(30000)
            self.page = self.context.new_page()
            self.page.goto("https://www.bazos.cz/moje-inzeraty.php")

            # Setup CDP Screencast
            import base64
            cdp = self.context.new_cdp_session(self.page)
            def _on_screencast_frame(event):
                try:
                    data_str = event.get("data")
                    if data_str:
                        self.latest_frame = base64.b64decode(data_str)
                    session_id = event.get("sessionId")
                    if session_id and hasattr(cdp, "_impl_obj") and hasattr(cdp._impl_obj, "_channel"):
                        try:
                            cdp._impl_obj._channel.send_no_reply("send", {
                                "method": "Page.screencastFrameAck",
                                "params": {"sessionId": session_id}
                            })
                        except Exception:
                            pass
                except Exception:
                    pass

            cdp.on("Page.screencastFrame", _on_screencast_frame)
            cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 70, "everyNthFrame": 1})
            self.cdp_session = cdp
        except Exception as e:
            print(f"Error initializing Playwright worker thread: {e}")
            self.running = False
            return

        # Continuous Input Processing Loop on Worker Thread
        while self.running and self.browser and self.browser.is_connected():
            try:
                has_events = False
                while not self.input_queue.empty():
                    try:
                        evt = self.input_queue.get_nowait()
                        has_events = True
                        act = evt.get("action")
                        if act == "click":
                            cx, cy = evt["x"], evt["y"]
                            self.cdp_session.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
                            self.cdp_session.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "buttons": 1, "clickCount": 1})
                            self.cdp_session.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "buttons": 0, "clickCount": 1})
                        elif act == "type":
                            for char in evt.get("text", ""):
                                self.cdp_session.send("Input.dispatchKeyEvent", {"type": "keyDown", "text": char})
                                self.cdp_session.send("Input.dispatchKeyEvent", {"type": "keyUp", "text": char})
                        elif act == "key":
                            key_name = evt.get("key", "")
                            key_data = {
                                "Backspace": {"key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
                                "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"},
                                "Tab": {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9},
                                "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}
                            }
                            params = key_data.get(key_name, {"key": key_name})
                            self.cdp_session.send("Input.dispatchKeyEvent", {"type": "keyDown", **params})
                            self.cdp_session.send("Input.dispatchKeyEvent", {"type": "keyUp", **params})
                        elif act == "goto":
                            url = evt.get("url")
                            if url and self.page and not self.page.is_closed():
                                self.page.goto(url)
                        elif act == "call":
                            func = evt["func"]
                            args = evt.get("args", ())
                            kwargs = evt.get("kwargs", {})
                            try:
                                res = func(self.page, *args, **kwargs)
                                evt["result_queue"].put((res, None))
                            except Exception as ex:
                                evt["result_queue"].put((None, ex))
                    except queue.Empty:
                        break
                    except Exception as ex:
                        print(f"Error handling event in worker: {ex}")

                if has_events and self.cdp_session:
                    try:
                        self.cdp_session.send("Runtime.evaluate", {
                            "expression": "document.body.style.opacity = '0.999'; setTimeout(() => document.body.style.opacity = '1.0', 10);"
                        })
                    except Exception:
                        pass

                time.sleep(0.05)
            except Exception as loop_e:
                print(f"Worker loop error: {loop_e}")
                time.sleep(0.1)

    def run_on_worker(self, func, *args, **kwargs):
        """Dispatches `func(self.page, *args, **kwargs)` to execute on the Playwright worker thread."""
        self.start_worker()
        res_q = queue.Queue()
        self.input_queue.put({
            "action": "call",
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "result_queue": res_q
        })
        res, err = res_q.get()
        if err:
            raise err
        return res

    def get_session(self):
        self.start_worker()
        # Wait up to 10s for worker thread to initialize page
        for _ in range(100):
            if self.page and not self.page.is_closed():
                break
            time.sleep(0.1)
        return self.playwright, self.browser, self.context, self.page

    def send_cdp_click(self, x, y):
        self.start_worker()
        self.input_queue.put({"action": "click", "x": x, "y": y})
        return True

    def send_cdp_type(self, text):
        self.start_worker()
        self.input_queue.put({"action": "type", "text": text})
        return True

    def send_cdp_key(self, key_name):
        self.start_worker()
        self.input_queue.put({"action": "key", "key": key_name})
        return True

    def save_state(self):
        if self.context:
            try:
                self.context.storage_state(path=str(SESSION_STATE_PATH))
            except Exception as e:
                print(f"  {Colors.WARNING}Nepodařilo se uložit stav relace: {e}{Colors.ENDC}")

    def close(self):
        self.running = False
        if self.context:
            self.save_state()
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.cdp_session = None
        self.latest_frame = None

session_manager = PlaywrightSessionManager()
atexit.register(session_manager.close)
