import time
from contextlib import contextmanager
from functools import wraps

import pytest
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
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
                except ex:
                    # Narrow, so an AssertionError from the wrapped function
                    # fails fast instead of being retried.
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
    # Centred, not top-aligned: the default puts the element under the fixed
    # navbar and the click is intercepted by the dropdown-toggle.
    self.parent.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", self)
    return self._execute(Command.CLICK_ELEMENT)


WebElement.click = WebElement_click  # noqa: E305

orig_send_keys = WebElement.send_keys


@retry_if_exception(WebDriverException, 5, sleep_time=1)  # noqa: E302
def WebElement_send_keys(self, keys):
    """Monky patch send_keys to ensure element is in view"""
    # Centred, not top-aligned: the default puts the element under the fixed
    # navbar and the click is intercepted by the dropdown-toggle.
    self.parent.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", self)
    return orig_send_keys(self, keys)


WebElement.send_keys = WebElement_send_keys  # noqa: E305


# A LiveServerSingleThread/StaticLiveServerSingleThreadedTestCase pair used to
# sit here, forcing a single-threaded server to work around
# https://code.djangoproject.com/ticket/29062. It never ran. Its override was
# spelled `__create_server` with two leading underscores, which Python
# name-mangles to `_LiveServerSingleThread__create_server`, while Django calls
# `_create_server` - so Django's own ThreadedWSGIServer was used throughout,
# and the suite has only ever run multi-threaded.
#
# Removed rather than repaired. Repairing it would put the suite into a
# configuration it has never actually run in, which is not a restoration, and
# the signature had drifted too: Django 4.2 passes `connections_override`,
# which is how the server thread is given the test's database connections.
# Dropping it would leave the server opening its own, unable to see the test's
# data at all.
#
# If threading turns out to cause trouble, that is a change to make
# deliberately and measure, not a workaround to reinstate.
@pytest.mark.selenium
def ajax_settled(driver):
    """True once jQuery has no requests in flight, or the page has no jQuery.

    The naive form of this - `typeof jQuery !== 'undefined' ? jQuery.active
    == 0 : true` - cannot tell a page that has no jQuery from a page whose
    jQuery has not finished loading, and answers True for both. On a page
    still fetching its scripts that returns immediately, and the next line of
    the test runs `$(...)` against a document where `$` does not exist yet.
    That is the `$ is not defined` failure seen at select_unit.

    `document.readyState` breaks the tie: while it is not yet "complete" a
    missing jQuery means "not loaded yet", so keep waiting. Once the document
    is complete and jQuery is still absent, the page genuinely does not use
    it.

    Returns the whole state in one round trip and decides here rather than in
    the script, so the decision is testable without a browser.
    """
    has_jquery, active, ready_state = driver.execute_script(
        "var has = typeof jQuery !== 'undefined';"
        "return [has, has ? jQuery.active : -1, document.readyState];"
    )
    if has_jquery:
        return active == 0
    return ready_state == 'complete'


def explicit_find_element(driver, orig_find_element, timeout):
    """Wrap driver.find_element in an explicit wait, raising NoSuchElement.

    The implicit wait is switched off by the caller, so this is what replaces
    it. Every existing `driver.find_element(...)` call site keeps the same
    behaviour - block until the element turns up, up to `timeout` - but via a
    single explicit wait rather than a driver-level implicit one layered
    underneath every other wait in the suite.

    WebDriverWait ignores NoSuchElementException while polling, so this
    retries until the element appears; StaleElementReference is added because
    a page still settling can hand back an element that goes stale between
    locating and returning it.

    **The timeout is re-raised as NoSuchElementException, not TimeoutException.**
    That is deliberate and it matters for every wait in the suite. Conditions
    like `presence_of_element_located` call find_element internally, so a
    TimeoutException escaping from here propagates straight through the
    surrounding WebDriverWait - which only ignores NoSuchElementException - and
    the message the call site passed to `.until(..., "waiting for X")` is
    never used. Raising NoSuchElementException instead lets the outer wait
    treat this as "not there yet", finish its own deadline, and fail with the
    call site's message. NoSuchElementException is also what unpatched Selenium
    raises for a missing element, so a bare find_element() call behaves as
    callers expect.
    """

    def find_element(*args, **kwargs):
        try:
            return WebDriverWait(
                driver,
                timeout,
                ignored_exceptions=(NoSuchElementException, StaleElementReferenceException),
            ).until(lambda d: orig_find_element(*args, **kwargs))
        except TimeoutException as exc:
            raise NoSuchElementException(
                "no element matched find_element(%s) within %ss"
                % (", ".join(repr(a) for a in args), timeout)
            ) from exc

    return find_element


class SeleniumTests(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        # Native headless, not a virtual display, so no display server is
        # needed anywhere. SELENIUM_HEADLESS = False to watch a run.
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
                # For installs with no plain binary on PATH, such as Flatpak.
                # settings.py documents the TMPDIR caveat that comes with it.
                chrome_options.binary_location = binary_path

            driver_path = getattr(settings, 'SELENIUM_CHROMIUM_DRIVER_PATH', '')
            if driver_path:
                cls.driver = webdriver.Chrome(service=ChromeService(executable_path=driver_path), options=chrome_options)
            else:
                # Selenium Manager resolves the driver itself.
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

            # An explicit setting or nothing, symmetric with the chromium
            # branch above. This used to fall back to
            # shutil.which('geckodriver'), which read as a convenience and was
            # not one: Selenium Manager already finds a geckodriver on PATH,
            # and additionally checks it against the installed browser and
            # warns when they do not match. Handing it the path ourselves
            # skipped that check, and geckodriver then picks the browser on its
            # own - which is how a run drove a Firefox-derived fork instead of
            # Firefox and still reported a pass. Set SELENIUM_FIREFOX_DRIVER_PATH
            # to pin a specific driver.
            driver_path = getattr(settings, 'SELENIUM_FIREFOX_DRIVER_PATH', '')
            if driver_path:
                cls.driver = webdriver.Firefox(service=FirefoxService(executable_path=driver_path), options=ff_options)
            else:
                # No explicit path and no system geckodriver on PATH -
                # Selenium Manager auto-resolves one for the installed
                # Firefox, same as the chromium branch above.
                cls.driver = webdriver.Firefox(options=ff_options)

        # Chromium gets longer because it renders these JS-heavy pages less
        # predictably, not because it is slower overall - it finishes the
        # suite faster than Firefox. A few waits per run land just over 5s,
        # a different few each time. One value feeds all three waits below,
        # including the cls.wait that nearly every self.wait.until() uses.
        # Set before the find_element patch, which needs it.
        cls.timeout = 10 if browser_setting == 'chromium' else 5

        cls.driver.find_element = explicit_find_element(
            cls.driver, cls.driver.find_element, cls.timeout
        )

        cls.driver.set_page_load_timeout(cls.timeout)

        # Off deliberately: Selenium warns against mixing implicit and
        # explicit waits, because the implicit one applies inside *each poll*
        # of a WebDriverWait, so a nominal cls.timeout can take far longer to
        # fail. find_element is patched above to resolve through an explicit
        # wait instead, and find_elements() - used to assert absence - returns
        # immediately rather than blocking for the full timeout.
        cls.driver.implicitly_wait(0)

        cls.driver.set_window_position(0, 0)
        cls.driver.set_window_size(1920, 1080)

        if not headless:
            # A tiling WM can ignore set_window_size silently, leaving a
            # viewport far smaller than asked for (~760x900 seen on 4K) and
            # elements genuinely unclickable. Maximize is usually honoured
            # within the window's tile, and keyboard focus follows the real
            # rendered area rather than the override below.
            try:
                cls.driver.maximize_window()
            except WebDriverException:
                pass

        cls.set_viewport_size(1920, 1080)

        cls.wait = WebDriverWait(cls.driver, cls.timeout)

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
        # Captured here, written out by conftest.py only if the test failed.
        # It cannot capture this itself: for a unittest TestCase pytest's
        # report hook runs after tearDown, once about:blank has replaced the
        # page.
        try:
            self._failure_screenshot_png = self.driver.get_screenshot_as_png()
        except WebDriverException:
            # Best effort only - the test result is what matters, not this.
            self._failure_screenshot_png = None

        self.driver.get("about:blank")
        super().tearDown()

    @contextmanager
    def wait_for_page_load(self, timeout=None):
        # cls.timeout, so this honours the per-browser value like every other
        # wait.
        old_page = self.driver.find_element(By.TAG_NAME, 'html')
        yield
        WebDriverWait(self.driver, timeout or self.timeout).until(
            staleness_of(old_page),
            "the page to be replaced - navigation did not complete",
        )

    @retry_if_exception(Exception, 2, sleep_time=1)
    def open(self, url):
        with self.wait_for_page_load():
            self.driver.execute_script("window.location.href='%s%s'" % (self.live_server_url, url))

    def wait_for_success(self):
        self.wait.until(
            e_c.presence_of_element_located((By.XPATH, '//ul[@class = "messagelist"]/li[@class = "success"]'))
        )

    def wait_for_elements(self, by, value, minimum=1):
        """Wait until at least `minimum` matching elements exist, then return them.

        driver.find_elements() is not a safe thing to index into. The
        implicit wait makes it return as soon as *one* element matches, so
        a page still rendering can hand back a shorter list than the test
        expects - or, if nothing has rendered yet, an empty one. Indexing
        that then raises IndexError from a line that looks nothing like a
        timeout, which is exactly how the Chromium CI failures presented
        (`inputs[0]` on an empty qa-input list).

        Waiting on the count instead fails as a TimeoutException naming the
        selector, which is both honest about what went wrong and bounded by
        the same browser-aware timeout as every other wait in this suite.
        """
        self.wait.until(
            lambda d: len(d.find_elements(by, value)) >= minimum,
            "expected at least %d element(s) matching %s=%r" % (minimum, by, value),
        )
        return self.driver.find_elements(by, value)

    def wait_until(self, predicate, message="condition", timeout=None):
        """Poll a plain Python predicate until it is true.

        For waiting on *server-side* state - a row appearing in the
        database after a form submit, say - where there is nothing in the
        DOM to wait on. Replaces `time.sleep(n); assert Model.objects...`,
        which has to guess n: too small and the test is flaky, too large
        and every run pays the full cost even when the row landed
        immediately. The autosave test was sleeping a flat 4.2s this way.

        Raises TimeoutException naming the condition, rather than failing
        on the assertion afterwards with no indication that timing was
        involved.
        """
        return WebDriverWait(self.driver, timeout or self.timeout).until(
            lambda d: predicate(), message="timed out waiting for %s" % message
        )

    def wait_for_ajax(self):
        """Wait until jQuery reports no requests in flight.

        These pages fire AJAX on nearly every interaction, and the suite has
        historically waited for that with a fixed sleep. This returns as soon
        as the requests finish instead. A page that genuinely has no jQuery
        settles once the document is complete - see ajax_settled for why that
        second condition is load-bearing.
        """
        return self.wait.until(
            ajax_settled,
            "jQuery.active to reach 0, or the page to finish loading without "
            "jQuery - a request on this page is still in flight",
        )

    def scroll_into_view(self, el_id):
        self.wait.until(
            e_c.presence_of_element_located((By.ID, el_id)),
            "#%s to exist before scrolling to it" % el_id,
        )
        actions = ActionChains(self.driver)
        element = self.driver.find_element(By.ID, el_id)
        actions.move_to_element(element)
        # Not decorative, despite sitting between a queued action and its
        # perform(): the admin's type-dependent widgets need settle time with
        # no in-flight request to wait on. Removing it breaks
        # LiveQATests::test_admin_tests. Replacing it means finding the DOM
        # condition the admin JS settles into.
        time.sleep(1)
        try:
            actions.perform()
            self.driver.find_element(By.CSS_SELECTOR, "body").click()
            self.driver.execute_script("window.scrollTo(0, -200);")
        except WebDriverException:
            # Best-effort: the element may already be in view, or the body
            # click may be intercepted. Neither is worth failing the test for.
            pass

    def scroll_into_view_css(self, css_sel):
        self.wait.until(
            e_c.presence_of_element_located((By.CSS_SELECTOR, css_sel)),
            "%r to exist before scrolling to it" % css_sel,
        )
        actions = ActionChains(self.driver)
        element = self.driver.find_element(By.CSS_SELECTOR, css_sel)
        actions.move_to_element(element)
        # Not decorative, despite sitting between a queued action and its
        # perform(): the admin's type-dependent widgets need settle time with
        # no in-flight request to wait on. Removing it breaks
        # LiveQATests::test_admin_tests. Replacing it means finding the DOM
        # condition the admin JS settles into.
        time.sleep(1)
        try:
            actions.perform()
            self.driver.execute_script("window.scrollTo(0, -200);")
        except WebDriverException:
            # Best-effort, as above.
            pass

    def _dismiss_open_datepicker(self):
        """Close an open flatpickr calendar if one is covering the page.

        flatpickr renders its calendar as an overlay, and it stays open
        until something dismisses it. Any click that lands underneath it
        fails with "element click intercepted", naming a .flatpickr-day as
        the overlaying element.

        This used to go unnoticed: the select2 option lookup fetched a
        possibly-empty list and looped over it, so a dropdown that never
        opened silently selected nothing and the test carried on. Waiting
        on the options properly turned that into a visible failure, which
        is how this surfaced.

        Retrying does not help - WebElement.click already retries for 5s
        and the calendar outlives that - so dismiss it explicitly.
        """
        if self.driver.find_elements(By.CSS_SELECTOR, ".flatpickr-calendar.open"):
            # An outside click, not ESCAPE: flatpickr keeps the selection on
            # the former and discards it on the latter.
            self.driver.execute_script("document.body.click();")
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: not d.find_elements(By.CSS_SELECTOR, ".flatpickr-calendar.open")
            )

    def _select2_container(self, el_id):
        """Return the select2 container for el_id, or None if it isn't one.

        Uses find_elements rather than find_element-inside-a-try: with the
        implicit wait off, find_elements returns immediately, so probing a
        plain <select> costs nothing. The old form paid a full cls.timeout
        on every non-select2 element before the exception let it fall
        through to the plain-select path.
        """
        found = self.driver.find_elements(By.ID, "select2-%s-container" % el_id)
        return found[0] if found else None

    def _select2_options(self):
        """Wait for the select2 dropdown options to render, then return them."""
        return self.wait_for_elements(By.CLASS_NAME, "select2-results__option")

    def select_by_index(self, el_id, index):
        """Select the option at `index`, whichever widget the field uses.

        Three paths, and all of them fire a `change` event, so a handler
        bound to the field runs either way:

        - a select2 container: open it and click the option
        - a plain <select>: Selenium's own Select.select_by_index
        - a <select> Selenium declines to click, because a widget covers it:
          assign the value and dispatch `change` directly

        The event matters as much as the value. Several forms pair a visible
        decoy select with a hidden field that a change handler fills in, and
        it is the hidden one that submits - so a caller that set the value
        without firing `change` would leave the form looking correct on
        screen and failing validation on save.
        """

        self.scroll_into_view(el_id)
        sel2 = self._select2_container(el_id)
        if sel2 is not None:
            self._dismiss_open_datepicker()
            sel2.click()
            # Waits for the options to render; an IndexError here is a real
            # failure and propagates.
            self._select2_options()[index].click()
        else:
            select_el = self.driver.find_element(By.ID, el_id)
            select = Select(select_el)
            try:
                select.select_by_index(index)
            except WebDriverException:
                val = select.options[index].get_attribute("value")
                self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", select_el, val)

    def select_by_text(self, el_id, text):
        """Select the option whose visible label is `text`.

        The select_by_index notes on widget paths and the `change` event
        apply here too; this differs only in how the option is identified.
        Prefer it where the label is the thing the test means, so a reordered
        choice list does not silently change what is selected.
        """
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

            self._dismiss_open_datepicker()
            sel2 = self.driver.find_element(By.ID, "select2-%s-container" % el_id)
            sel2.click()

            els = self._select2_options()
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

            self._dismiss_open_datepicker()
            sel2 = self.driver.find_element(By.ID, "select2-%s-container" % el_id)
            sel2.click()

            els = self._select2_options()
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
            except WebDriverException:
                # Retried: these are the interactions prone to a transient
                # "element not interactable". Other errors propagate.
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
        except WebDriverException:
            # Falls back to a JS click, which ignores overlays and viewport
            # position. Scoped to WebDriverException so a genuine error in the
            # test is not silently turned into a different kind of click.
            self.driver.execute_script("arguments[0].click();", element)

    def click_by_css_selector(self, css_sel):
        """Click the first match, re-finding it if it goes stale.

        Two different failures arrive as the same exception type and need
        opposite answers. An element that is present but covered wants the JS
        click, which ignores overlays and viewport position. An element that
        has been replaced since it was located wants to be found again -
        JS-clicking the dead reference raises the same staleness error one
        line further down, which reads as though the fallback itself failed.

        The date pickers are where this bites. `.open .today` matches against
        a calendar the previous interaction may still be closing, so the
        element can be located and gone before the click lands.
        """
        for attempt in range(3):
            self.scroll_into_view_css(css_sel)
            element = self.driver.find_element(By.CSS_SELECTOR, css_sel)
            try:
                element.click()
                return
            except StaleElementReferenceException:
                # Replaced mid-flight. Re-find rather than click a dead
                # reference; only give up once the page stops swapping it.
                if attempt == 2:
                    raise
            except WebDriverException:
                # Present but not directly clickable - covered by an overlay,
                # or out of position. Scoped so a genuine error is not
                # silently turned into a different kind of click.
                self.driver.execute_script("arguments[0].click();", element)
                return

    def click_by_link_text(self, link_text):
        for i in range(3):
            try:
                self.wait.until(
                    e_c.presence_of_element_located((By.LINK_TEXT, link_text)),
                    "a link reading %r" % link_text,
                )
                self.driver.find_element(By.LINK_TEXT, link_text).click()
                break
            except WebDriverException:
                # Retried: these are the interactions prone to a transient
                # "element not interactable". Other errors propagate.
                if i == 2:
                    raise
                else:
                    time.sleep(1)
