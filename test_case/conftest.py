import getpass
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import BROWSER, HEADLESS, VIEWPORT
from utils.logger import logger
from utils.screenshot import screenshot_manager
from utils.report_generator import ReportGenerator

_test_results = []


def pytest_collection_modifyitems(config, items):
    if not items:
        return
    browsers = set()
    for item in items:
        for marker in item.iter_markers():
            if marker.name.startswith("browser_"):
                browsers.add(marker.name.replace("browser_", ""))
                break
    if len(browsers) == 1:
        import config.settings as settings
        detected = browsers.pop()
        settings.BROWSER = detected
        logger.info(f"Auto-detected browser from test markers: {detected}")


@pytest.fixture(scope="session")
def browser():
    _browser_map = {
        "chromium": ("chromium", None),
        "edge":     ("chromium", "msedge"),
    }
    engine, channel = _browser_map.get(BROWSER, (BROWSER, None))
    with sync_playwright() as p:
        browser_type = getattr(p, engine)
        launch_kwargs = {"headless": HEADLESS}
        if channel:
            launch_kwargs["channel"] = channel
        browser = browser_type.launch(**launch_kwargs)
        logger.info(f"Browser launched: {BROWSER}, headless={HEADLESS}")
        yield browser
        browser.close()
        logger.info("Browser closed")


@pytest.fixture(scope="function")
def context(browser: Browser):
    context = browser.new_context(
        viewport=VIEWPORT,
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext):
    page = context.new_page()
    yield page
    page.close()


def _extract_meta(item) -> tuple:
    source_file = ""
    priority = ""
    browser = ""
    test_name = ""
    module_file = getattr(item.module, "__file__", "")
    if module_file:
        source_file = Path(module_file).stem
    for marker in item.iter_markers():
        if marker.name in ("p0", "p1", "p2", "p3"):
            priority = marker.name.upper()
        elif marker.name.startswith("browser_"):
            browser = marker.name.replace("browser_", "")
    test_name = item.name
    if item.function and item.function.__doc__:
        doc = item.function.__doc__.strip()
        test_name = doc.split("\n")[0]
    return source_file, priority, browser, test_name


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        page = item.funcargs.get("page")
        if page:
            source_file, priority, browser, test_name = _extract_meta(item)
            ss_test_name = source_file if source_file else test_name
            try:
                run_time_fb = datetime.now().strftime("%H-%M-%S")
                ss_dir = screenshot_manager._get_run_dir() / ss_test_name / os.environ.get("TEST_RUN_TIME", run_time_fb)
                ss_dir_failed = screenshot_manager._get_run_dir() / f"{ss_test_name} [FAILED]" / os.environ.get("TEST_RUN_TIME", run_time_fb)
                if not ss_dir.exists() and not ss_dir_failed.exists():
                    screenshot_manager.take_error_screenshot(
                        page,
                        test_name=ss_test_name,
                        error=str(report.longrepr) if hasattr(report, "longrepr") else "Test failed",
                    )
                    logger.error(f"Test failed, error screenshot saved: {ss_test_name}")
            except Exception as e:
                logger.error(f"Failed to capture error screenshot: {e}")

    if report.when == "call":
        source_file, priority, browser, test_name = _extract_meta(item)
        error_info = ""
        if report.failed:
            error_info = report.longreprtext if report.longreprtext else str(report.longrepr or "")
        _test_results.append({
            "nodeid": item.nodeid,
            "outcome": report.outcome,
            "duration": report.duration,
            "source_file": source_file,
            "priority": priority,
            "browser": browser,
            "error_info": error_info,
        })


def pytest_sessionfinish(session):
    if not _test_results:
        logger.info("No test cases executed, skipping report generation.")
        return

    generator = ReportGenerator()
    for r in _test_results:
        generator.add_result(r["nodeid"], r["outcome"], r["duration"],
                             source_file=r.get("source_file", ""),
                             priority=r.get("priority", ""),
                             browser=r.get("browser", ""),
                             error_info=r.get("error_info", ""))

    now = datetime.now()
    run_date = os.environ.get("TEST_RUN_DATE", now.strftime("%y-%m-%d"))
    run_time = os.environ.get("TEST_RUN_TIME", now.strftime("%H-%M-%S"))
    try:
        executor = getpass.getuser()
        path = generator.generate(run_date, run_time, executor)
        logger.info(f"Test report saved: {path}")
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")