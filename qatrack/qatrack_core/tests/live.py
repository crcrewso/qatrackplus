import shutil
import time
from contextlib import contextmanager
from functools import wraps

import pytest
from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.servers.basehttp import WSGIServer
from django.test.testcases import LiveServerThread, QuietWSGIRequestHandler
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.command import Command
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as e_c
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait


# From http://stackoverflow.com/a/20559494
def retry_if_exception(ex, max_retries, sleep_time=None, reraise=True):

    def outer(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            assert max_retries > 0
            x = max_retries
            while x:
                try:
                    return func(*args, **kwargs)
                except:  # noqa: E722
                    x -= 1
                    if x == 0 and reraise:
                        raise
                if sleep_time is not None:
                    time.sleep(sleep_time)

        return wrapper

    return outer


@retry_if_exception(WebDriverException, 5, sleep_time=1)
def WebElement_click(self):
    """
    Monkey patches the element click command to work around issue with
    later versions of webdrivers that won't click on an element if it
    is not in view
    """
    self.parent.execute_script("arguments[0].scrollIntoView();", self)
    return self._execute(Command.CLICK_ELEMENT)


WebElement.click = WebElement_click  # noqa: E305

orig_send_keys = WebElement.send_keys


@retry_if_exception(WebDriverException, 5, sleep_time=1)  # noqa: E302
def WebElement_send_keys(self, keys):
    """Monky patch send_keys to ensure element is in view"""
    self.parent.execute_script("arguments[0].scrollIntoView();", self)
    return orig_send_keys(self, keys)


WebElement.send_keys = WebElement_send_keys  # noqa: E305


# Following two classes are trying to work around this issue:
# https://code.djangoproject.com/ticket/29062#no2
class LiveServerSingleThread(LiveServerThread):
    """Runs a single threaded server rather than multi threaded. Reverts https://github.com/django/django/pull/7832"""

    def __create_server(self):
        return WSGIServer((self.host, self.port), QuietWSGIRequestHandler, allow_reuse_address=False)


class StaticLiveServerSingleThreadedTestCase(StaticLiveServerTestCase):
    "A thin sub-class which only sets the single-threaded server as a class"
    server_thread_class = LiveServerSingleThread

    static_handler = StaticFilesHandler


@pytest.mark.selenium
class SeleniumTests(StaticLiveServerSingleThreadedTestCase):

    @classmethod
    def setUpClass(cls):
        # Headless is independent of which browser is selected, and uses
        # each browser's own native headless mode rather than a virtual
        # display (Xvfb/pyvirtualdisplay) - no display server of any kind
        # is needed, so this works the same on a workstation, a bare CI
        # runner, or an agent sandbox. Set SELENIUM_HEADLESS = False (and
        # run somewhere with a real display) to watch a test run.
        headless = getattr(settings, 'SELENIUM_HEADLESS', True)
        browser_setting = getattr(settings, 'SELENIUM_BROWSER', 'firefox')

        cls.browser_setting = browser_setting

        if browser_setting == 'chromium':
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService

            chrome_options = ChromeOptions()
            if headless:
                # The "new" headless mode (Chrome 109+) - the old
                # `--headless` renders differently enough from a real
                # window that it's been superseded for testing purposes.
                chrome_options.add_argument('--headless=new')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')

            binary_path = getattr(settings, 'SELENIUM_CHROMIUM_BINARY_PATH', '')
            if binary_path:
                # Only needed when Chrome isn't discoverable the normal
                # way - e.g. a Flatpak install, which has no plain
                # `google-chrome`/`chromium` binary on PATH for Selenium
                # Manager to find. See the setting's own comment in
                # settings.py for the TMPDIR caveat that goes with it.
                chrome_options.binary_location = binary_path

            driver_path = getattr(settings, 'SELENIUM_CHROMIUM_DRIVER_PATH', '')
            if driver_path:
                cls.driver = webdriver.Chrome(service=ChromeService(executable_path=driver_path), options=chrome_options)
            else:
                # No explicit path - Selenium Manager (built into Selenium
                # 4.6+) auto-detects the installed Chrome/Chromium and
                # downloads a matching chromedriver on its own. Only set
                # SELENIUM_CHROMIUM_DRIVER_PATH if you need to pin a
                # specific driver binary instead.
                cls.driver = webdriver.Chrome(options=chrome_options)
        else:
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.firefox.service import Service as FirefoxService

            ff_options = FirefoxOptions()
            if headless:
                ff_options.add_argument('-headless')
            # Enables the WebDriver BiDi session needed for
            # set_viewport_size() below, in both headless and visible
            # mode - a no-op cost-wise if a given run never calls it.
            ff_options.web_socket_url = True

            driver_path = getattr(settings, 'SELENIUM_FIREFOX_DRIVER_PATH', '') or shutil.which('geckodriver')
            if driver_path:
                cls.driver = webdriver.Firefox(service=FirefoxService(executable_path=driver_path), options=ff_options)
            else:
                # No explicit path and no system geckodriver on PATH -
                # Selenium Manager auto-resolves one for the installed
                # Firefox, same as the chromium branch above.
                cls.driver = webdriver.Firefox(options=ff_options)

        orig_find_element = cls.driver.find_element

        @retry_if_exception(WebDriverException, 2, sleep_time=1)
        def WebElement_find_element(*args, **kwargs):
            """Monky patch find element to allow retries"""
            return orig_find_element(*args, **kwargs)

        cls.driver.find_element = WebElement_find_element

        # 2s was too tight to be reliable across hosts/browsers: fine for
        # Firefox, but Chrome's heavier per-instance startup made it
        # marginal under sustained load (a full run launches and tears
        # down a fresh browser per test class) - confirmed by isolating a
        # timing-only failure that passed reliably alone but not as part
        # of a long run. 5s matches what this suite used before it was
        # tightened, and gives enough headroom on slower/busier hosts
        # without making a genuinely broken wait noticeably slower to fail.
        cls.driver.set_page_load_timeout(5)
        cls.driver.implicitly_wait(5)

        cls.driver.set_window_position(0, 0)
        cls.driver.set_window_size(1920, 1080)

        if not headless:
            # set_window_size above asks the window manager for a real,
            # on-screen 1920x1080 window - under a tiling WM sharing
            # screen space with other visible windows, that request can
            # be silently ignored, leaving the actual rendered viewport
            # far smaller (confirmed: as small as ~760x900 on a 4K
            # display with other windows also tiled), which then makes
            # elements genuinely off-screen and unclickable. Maximizing
            # first closes most of that gap: some interactions (keyboard
            # focus in particular) fall back to the real rendered area
            # rather than the overridden viewport below, and most tiling
            # WMs honour a maximize request within the window's current
            # tile even though they ignore arbitrary set_window_size
            # calls.
            try:
                cls.driver.maximize_window()
            except WebDriverException:
                pass

        cls.set_viewport_size(1920, 1080)

        cls.wait = WebDriverWait(cls.driver, 5)

        super().setUpClass()

    @classmethod
    def set_viewport_size(cls, width, height):
        """Override the browser's logical (CSS-pixel) content viewport -
        via Chrome DevTools Protocol for Chromium, WebDriver BiDi for
        Firefox - independent of whatever size the window manager
        actually gave the real window. Works the same in headless mode
        (there the "real window" is just whatever set_window_size was
        given, with no window manager involved) and callable per-test to
        check layout at a range of sizes, not just at class setup.

        Never requests a viewport *larger* than the real window's
        current size: under a tiling WM sharing screen space with other
        windows, that real area can be well under a requested size
        (confirmed as small as ~760x900 on a 4K/tiled display), and
        asking the browser to lay out at a size regardless of that makes
        it paint content assuming screen space that doesn't exist - the
        right-hand (and/or bottom) portion of the page ends up genuinely
        past the real window's edge, not just visually cropped, but
        truly offscreen and unclickable/unfocusable there. Capping to
        whatever's really available keeps every pixel the layout thinks
        it has actually reachable, at the cost of a narrower layout on a
        cramped tile - a real, visible constraint rather than a hidden
        one.
        """
        real_size = cls.driver.get_window_size()
        width = min(width, real_size['width'])
        height = min(height, real_size['height'])
        if cls.browser_setting == 'chromium':
            cls.driver.execute_cdp_cmd(
                'Emulation.setDeviceMetricsOverride',
                {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False},
            )
        else:
            from selenium.webdriver.common.bidi.browsing_context import BrowsingContext
            BrowsingContext(cls.driver).set_viewport(
                context=cls.driver.current_window_handle,
                viewport={'width': width, 'height': height},
            )

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def tearDown(self):
        self.driver.get("about:blank")
        super().tearDown()

    @contextmanager
    def wait_for_page_load(self, timeout=5):
        old_page = self.driver.find_element(By.TAG_NAME, 'html')
        yield
        WebDriverWait(self.driver, timeout).until(staleness_of(old_page))

    @retry_if_exception(Exception, 2, sleep_time=1)
    def open(self, url):
        with self.wait_for_page_load():
            self.driver.execute_script("window.location.href='%s%s'" % (self.live_server_url, url))

    def wait_for_success(self):
        self.wait.until(
            e_c.presence_of_element_located((By.XPATH, '//ul[@class = "messagelist"]/li[@class = "success"]'))
        )

    def scroll_into_view(self, el_id):
        self.wait.until(e_c.presence_of_element_located((By.ID, el_id)))
        actions = ActionChains(self.driver)
        element = self.driver.find_element(By.ID, el_id)
        actions.move_to_element(element)
        time.sleep(1)
        try:
            actions.perform()
            self.driver.find_element(By.CSS_SELECTOR, "body").click()
            self.driver.execute_script("window.scrollTo(0, -200);")
        except:  # noqa: E722
            pass

    def scroll_into_view_css(self, css_sel):
        self.wait.until(e_c.presence_of_element_located((By.CSS_SELECTOR, css_sel)))
        actions = ActionChains(self.driver)
        element = self.driver.find_element(By.CSS_SELECTOR, css_sel)
        actions.move_to_element(element)
        time.sleep(1)
        try:
            actions.perform()
            self.driver.execute_script("window.scrollTo(0, -200);")
        except:  # noqa: E722
            pass

    def select_by_index(self, el_id, index):
        """Set force_select2= True when selecting a 0 index for a select2 element"""

        self.scroll_into_view(el_id)
        try:
            # select2?
            sel2 = self.driver.find_element(By.ID, "select2-%s-container" % el_id)
            sel2.click()
            time.sleep(0.1)
            els = self.driver.find_elements(By.CLASS_NAME, "select2-results__option")
            els[index].click()
        except:  # noqa: E722
            select_el = self.driver.find_element(By.ID, el_id)
            select = Select(select_el)
            try:
                select.select_by_index(index)
            except WebDriverException:
                val = select.options[index].get_attribute("value")
                self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", select_el, val)

    def select_by_text(self, el_id, text):

        self.scroll_into_view(el_id)
        try:
            select_el = self.driver.find_element(By.ID, el_id)
            select = Select(select_el)
            try:
                select.select_by_visible_text(text)
            except WebDriverException:
                found = False
                for opt in select.options:
                    if opt.text == text:
                        self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", select_el, opt.get_attribute("value"))
                        found = True
                        break
                if not found:
                    raise Exception("Option with text '%s' not found" % text)
        except WebDriverException:

            sel2 = self.driver.find_element(By.ID, "select2-%s-container" % el_id)
            sel2.click()

            els = self.driver.find_elements(By.CLASS_NAME, "select2-results__option")
            for el in els:
                if el.text == text:
                    el.click()
                    break

    def select_by_value(self, el_id, val):

        self.scroll_into_view(el_id)
        try:
            select_el = self.driver.find_element(By.ID, el_id)
            select = Select(select_el)
            try:
                select.select_by_value(val)
            except WebDriverException:
                found = False
                for opt in select.options:
                    if opt.get_attribute("value") == val:
                        self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", select_el, val)
                        found = True
                        break
                if not found:
                    raise Exception("Option with value '%s' not found" % val)
        except WebDriverException:

            sel2 = self.driver.find_element(By.ID, "select2-%s-container" % el_id)
            sel2.click()

            els = self.driver.find_elements(By.CLASS_NAME, "select2-results__option")
            for el in els:
                if el.get_attribute('id').endswith(val):
                    el.click()
                    break

    def send_keys(self, el_id, text):
        for i in range(3):
            try:
                self.scroll_into_view(el_id)
                self.driver.find_element(By.ID, el_id).send_keys(text)
                break
            except:  # noqa: E722
                if i == 2:
                    raise
                else:
                    time.sleep(1)

    def click(self, el_id, scroll=True):
        if scroll:
            self.scroll_into_view(el_id)
        element = self.driver.find_element(By.ID, el_id)
        try:
            element.click()
        except:  # noqa: E722
            self.driver.execute_script("arguments[0].click();", element)

    def click_by_css_selector(self, css_sel):
        self.scroll_into_view_css(css_sel)
        element = self.driver.find_element(By.CSS_SELECTOR, css_sel)
        try:
            element.click()
        except:  # noqa: E722
            self.driver.execute_script("arguments[0].click();", element)

    def click_by_link_text(self, link_text):
        for i in range(3):
            try:
                self.wait.until(e_c.presence_of_element_located((By.LINK_TEXT, link_text)))
                self.driver.find_element(By.LINK_TEXT, link_text).click()
                break
            except:  # noqa: E722
                if i == 2:
                    raise
                else:
                    time.sleep(1)
