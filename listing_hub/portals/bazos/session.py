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

    def inspect_dom(self) -> dict:
        """
        Inspect the live DOM of the currently active Playwright page.
        Returns url, title, visible error messages, form inputs, and buttons.
        """
        if not self.running or not self.page or self.page.is_closed():
            return {
                "active": False,
                "message": "Browser page is not open or worker is not running."
            }

        def _do_inspect(page, *args):
            try:
                info = {
                    "active": True,
                    "url": page.url or "",
                    "title": page.title() or "",
                    "errors": [],
                    "warnings": [],
                    "has_sms_input": False,
                    "inputs": [],
                    "buttons": [],
                    "body_snippet": ""
                }

                # 1. Look for obvious error / warning elements on Bazos
                error_locators = page.locator(".chyba, .error, .upozorneni, .hlaska, font[color='red'], span[style*='red'], div[style*='red']")
                count = min(error_locators.count(), 10)
                for i in range(count):
                    try:
                        el = error_locators.nth(i)
                        if el.is_visible():
                            txt = el.inner_text().strip()
                            if txt and txt not in info["errors"]:
                                info["errors"].append(txt)
                    except Exception:
                        pass

                # 2. Check for SMS code input presence
                sms_inputs = page.locator("input[name='klic'], input[id='klic'], input[name='kodd'], input[id='kodd'], input[name='cr'], input[name='kod'], input[name='overkod']")
                if sms_inputs.count() > 0:
                    for i in range(sms_inputs.count()):
                        if sms_inputs.nth(i).is_visible():
                            info["has_sms_input"] = True
                            break

                # 3. Check text on page for typical alerts
                try:
                    content_text = page.locator("body").inner_text() or ""
                    lower = content_text.lower()
                    if "chybné heslo" in lower:
                        info["errors"].append("Detekován text: 'chybné heslo'")
                    if "vyplňte kód" in lower or "zadejte kód" in lower or "ověřovací kód" in lower:
                        info["warnings"].append("Detekována výzva k zadání SMS/ověřovacího kódu")
                    if "příliš mnoho požadavků" in lower or "blokován" in lower:
                        info["errors"].append("Detekována možná blokace / rate limit")
                    if "inzerát byl vymazán" in lower or "inzerát vymazán" in lower:
                        info["warnings"].append("Detekováno potvrzení o smazání inzerátu")
                    if "inzerát byl vložen" in lower:
                        info["warnings"].append("Detekováno potvrzení o vložení nového inzerátu")

                    # Snippet textu pro rychlou orientaci (prvních 600 znaků)
                    info["body_snippet"] = " ".join(content_text.split()[:80])
                except Exception:
                    pass

                # 4. Form inputs summary
                try:
                    inputs = page.locator("input:not([type='hidden']), select, textarea")
                    for i in range(min(inputs.count(), 15)):
                        inp = inputs.nth(i)
                        if inp.is_visible():
                            name = inp.get_attribute("name") or inp.get_attribute("id") or ""
                            tag = inp.evaluate("el => el.tagName.toLowerCase()")
                            val = inp.input_value() if tag in ("input", "textarea") else ""
                            info["inputs"].append({
                                "tag": tag,
                                "name": name,
                                "value": val[:40] if val else ""
                            })
                except Exception:
                    pass

                # 5. Buttons summary
                try:
                    btns = page.locator("input[type='submit'], button[type='submit'], input[type='button']")
                    for i in range(min(btns.count(), 8)):
                        btn = btns.nth(i)
                        if btn.is_visible():
                            val = btn.get_attribute("value") or btn.inner_text() or ""
                            info["buttons"].append(val.strip())
                except Exception:
                    pass

                return info
            except Exception as e:
                return {"active": True, "error": str(e)}

        try:
            return self.run_on_worker(_do_inspect, timeout=10.0)
        except Exception as e:
            return {"active": False, "error": f"Failed to inspect DOM: {e}"}

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
