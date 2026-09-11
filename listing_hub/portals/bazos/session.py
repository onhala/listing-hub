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
            if headless_env is not None:
                is_headless = headless_env.lower() in ("true", "1", "yes")
            else:
                display = os.environ.get("DISPLAY")
                is_headless = not (display and os.path.exists(f"/tmp/.X11-unix/X{display.replace(':', '')}"))

            exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
            launch_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]

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
                self.process_events()
                time.sleep(0.05)
            except Exception as loop_e:
                print(f"Worker loop error: {loop_e}")
                time.sleep(0.1)

    def _dispatch_event(self, evt):
        """Dispatches a single input or call event on the Playwright worker thread."""
        act = evt.get("action")
        if act == "click":
            cx, cy = evt["x"], evt["y"]
            if self.page and not self.page.is_closed():
                try:
                    self.page.mouse.click(cx, cy)
                except Exception as ex:
                    print(f"page.mouse.click error: {ex}")
            if self.cdp_session:
                try:
                    self.cdp_session.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
                    self.cdp_session.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "buttons": 1, "clickCount": 1})
                    self.cdp_session.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "buttons": 0, "clickCount": 1})
                except Exception:
                    pass
        elif act == "type":
            text_val = evt.get("text", "")
            if self.page and not self.page.is_closed():
                try:
                    # Automaticky zaměříme pole pro SMS kód – klic (nový inzerát) nebo kodd/kod/cr (přihlášení)
                    code_input = self.page.locator(
                        "input[name='klic'], input[id='klic'], "
                        "input[name='kodd'], input[id='kodd'], "
                        "input[name='cr'], input[name='kod'], input[name='overkod']"
                    )
                    if code_input.count() > 0 and code_input.first.is_visible():
                        curr_val = code_input.first.input_value() or ""
                        new_val = curr_val + text_val if len(text_val) == 1 else text_val
                        code_input.first.fill(new_val)
                    else:
                        self.page.evaluate('''() => {
                            let el = document.activeElement;
                            if (!el || el.tagName === "BODY" || (el.tagName !== "INPUT" && el.tagName !== "TEXTAREA")) {
                                let input = document.querySelector("input[name='klic']") ||
                                            document.querySelector("input[id='klic']") ||
                                            document.querySelector("input[name='kodd']") ||
                                            document.querySelector("input[id='kodd']") ||
                                            document.querySelector("input[name='cr']") ||
                                            document.querySelector("input[name='kod']") ||
                                            document.querySelector("input[type='text']") || 
                                            document.querySelector("input[type='number']") ||
                                            document.querySelector("input:not([type='hidden'])");
                                if (input) input.focus();
                            }
                        }''')
                        self.page.keyboard.type(text_val)
                except Exception as ex:
                    print(f"Type error: {ex}")
                    if self.cdp_session:
                        try:
                            self.cdp_session.send("Input.insertText", {"text": text_val})
                        except Exception:
                            pass
        elif act == "key":
            key_name = evt.get("key", "")
            if self.page and not self.page.is_closed():
                try:
                    code_input = self.page.locator(
                        "input[name='klic'], input[id='klic'], "
                        "input[name='kodd'], input[id='kodd'], "
                        "input[name='cr'], input[name='kod'], input[name='overkod']"
                    )
                    if key_name == "Backspace" and code_input.count() > 0 and code_input.first.is_visible():
                        curr_val = code_input.first.input_value() or ""
                        code_input.first.fill(curr_val[:-1])
                    elif key_name == "Enter" and code_input.count() > 0 and code_input.first.is_visible():
                        submit_btn = self.page.locator(
                            "form:has(input[name='klic']) input[type='submit'], "
                            "form:has(input[name='kodd']) input[type='submit'], "
                            "input[type='submit'][value*='Vypsat'], "
                            "input[type='submit'][value*='Ověř'], "
                            "input[type='submit'][value*='Potvrd'], "
                            "input[type='submit'][value*='Odeslat'], "
                            "button[type='submit']"
                        )
                        if submit_btn.count() > 0 and submit_btn.first.is_visible():
                            submit_btn.first.click()
                        else:
                            self.page.keyboard.press("Enter")
                    else:
                        self.page.keyboard.press(key_name)
                except Exception as ex:
                    print(f"Key error: {ex}")
        elif act == "scroll":
            cx, cy = evt["x"], evt["y"]
            dx, dy = evt.get("deltaX", 0), evt.get("deltaY", 0)
            if self.cdp_session:
                try:
                    self.cdp_session.send("Input.dispatchMouseEvent", {
                        "type": "mouseWheel",
                        "x": cx,
                        "y": cy,
                        "deltaX": dx,
                        "deltaY": dy
                    })
                except Exception as ex:
                    print(f"Scroll CDP error: {ex}")
            elif self.page and not self.page.is_closed():
                try:
                    self.page.mouse.wheel(dx, dy)
                except Exception:
                    pass
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

    def process_events(self):
        """Processes all pending events from the input queue on the worker thread."""
        has_events = False
        while not self.input_queue.empty():
            try:
                evt = self.input_queue.get_nowait()
                has_events = True
                self._dispatch_event(evt)
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
        return has_events

    def wait_while(self, condition_func, timeout=90, step=0.1):
        """
        Wait while condition_func() evaluates to True, continuously processing pending 
        user input events (clicks, typing, SMS submission) on the worker thread.
        Returns True if condition became False, False if timed out.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if getattr(self, "cancel_requested", False):
                break
            self.process_events()
            try:
                if not condition_func():
                    return True
            except Exception:
                return True
            time.sleep(step)
        return False

    def run_on_worker(self, func, *args, timeout=30.0, **kwargs):
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
        try:
            res, err = res_q.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"Vypršel limit ({timeout}s) pro zpracování požadavku v prohlížeči.")
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

    def send_cdp_scroll(self, x, y, delta_x, delta_y):
        self.start_worker()
        self.input_queue.put({"action": "scroll", "x": x, "y": y, "deltaX": delta_x, "deltaY": delta_y})
        return True

    def save_state(self):
        if self.context and self.page and not self.page.is_closed():
            def _do_save(page, *args):
                try:
                    st = page.context.storage_state()
                    import json
                    with open(SESSION_STATE_PATH, "w", encoding="utf-8") as f:
                        json.dump(st, f, indent=2)
                except Exception as e:
                    print(f"  {Colors.WARNING}Nepodařilo se uložit stav relace: {e}{Colors.ENDC}")
            try:
                self.run_on_worker(_do_save)
            except Exception:
                pass

    def cancel_current_action(self):
        self.cancel_requested = True
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass
        self.page = None

    def close(self):
        self.running = False
        if self.context and self.page and not self.page.is_closed():
            try:
                st = self.page.context.storage_state()
                import json
                with open(SESSION_STATE_PATH, "w", encoding="utf-8") as f:
                    json.dump(st, f, indent=2)
            except Exception:
                pass
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
