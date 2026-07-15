import os
import atexit
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

    def get_session(self):
        def log_psm(msg):
            try:
                with open("/tmp/thread_debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [PSM] {msg}\n")
            except Exception:
                pass

        is_active = False
        try:
            if self.browser and self.browser.is_connected() and self.page and not self.page.is_closed():
                _ = self.page.url
                is_active = True
        except Exception as e:
            log_psm(f"Session check error: {e}")
            is_active = False
            
        if not is_active:
            log_psm("Starting session reset/close")
            self.close()
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                raise ImportError(
                    f"\n{Colors.FAIL}Knihovna Playwright není nainstalována. "
                    f"Spusťte: pip install playwright && playwright install chromium{Colors.ENDC}"
                )
                
            log_psm("Calling sync_playwright().start()")
            self.playwright = sync_playwright().start()
            log_psm("sync_playwright().start() completed")
            executable_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
            launch_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            try:
                if executable_path and os.path.exists(executable_path):
                    log_psm(f"Launching system Chromium at {executable_path}")
                    self.browser = self.playwright.chromium.launch(executable_path=executable_path, headless=False, args=launch_args)
                else:
                    log_psm("Launching browser (chrome channel)")
                    self.browser = self.playwright.chromium.launch(channel="chrome", headless=False, args=launch_args)
            except Exception as e:
                log_psm(f"Browser launch fallback: {e}. Launching default chromium.")
                self.browser = self.playwright.chromium.launch(headless=False, args=launch_args)
            log_psm("Browser launched successfully")
            
            if SESSION_STATE_PATH.exists():
                log_psm("Loading session state (cookies)")
                self.context = self.browser.new_context(storage_state=str(SESSION_STATE_PATH))
            else:
                log_psm("Creating new context")
                self.context = self.browser.new_context()
            
            log_psm("Setting default timeout")
            self.context.set_default_timeout(30000)
            log_psm("Creating new page")
            self.page = self.context.new_page()
            log_psm("Session initialized successfully")
            
        return self.playwright, self.browser, self.context, self.page

    def save_state(self):
        if self.context:
            try:
                self.context.storage_state(path=str(SESSION_STATE_PATH))
            except Exception as e:
                print(f"  {Colors.WARNING}Nepodařilo se uložit stav relace: {e}{Colors.ENDC}")

    def close(self):
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
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

session_manager = PlaywrightSessionManager()
atexit.register(session_manager.close)
