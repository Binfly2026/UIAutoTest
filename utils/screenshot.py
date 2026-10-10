from datetime import datetime
from pathlib import Path

from config.settings import SCREENSHOT_DIR
from utils.logger import logger


class ScreenshotManager:

    def __init__(self, screenshot_dir: Path = SCREENSHOT_DIR):
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _get_run_dir(self) -> Path:
        import os
        run_date = os.environ.get("TEST_RUN_DATE", datetime.now().strftime("%y-%m-%d"))
        run_dir = self.screenshot_dir / run_date / "screenshots"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def take_screenshot(self, page, name: str, test_name: str = "") -> str:
        import os
        timestamp = datetime.now().strftime("%H%M%S_%f")
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        run_time = os.environ.get("TEST_RUN_TIME", datetime.now().strftime("%H-%M-%S"))
        base = self._get_run_dir()
        target_dir = base / test_name / run_time if test_name else base / run_time
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{timestamp}_{safe_name}.png"
        filepath = target_dir / filename
        page.screenshot(path=str(filepath), full_page=False)
        logger.info(f"Screenshot saved: {filepath}")
        return str(filepath)

    def take_error_screenshot(self, page, test_name: str = "", error: str = "") -> str:
        import os
        timestamp = datetime.now().strftime("%H%M%S_%f")
        run_time = os.environ.get("TEST_RUN_TIME", datetime.now().strftime("%H-%M-%S"))
        base = self._get_run_dir()
        target_dir = base / test_name / run_time if test_name else base / run_time
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{timestamp}_error_{abs(hash(error)) % 10000}.png"
        filepath = target_dir / filename
        page.screenshot(path=str(filepath), full_page=False)
        logger.error(f"Error screenshot saved: {filepath}")

        if test_name:
            test_parent = base / test_name
            failed_parent = base / f"{test_name} [FAILED]"
            if not failed_parent.exists() and test_parent.exists():
                try:
                    test_parent.rename(failed_parent)
                    logger.info(f"Directory renamed to: {failed_parent}")
                except OSError:
                    pass

        return str(filepath)

    def take_step_screenshot(self, page, step_name: str, test_name: str = "") -> str:
        return self.take_screenshot(page, f"step_{step_name}", test_name)


screenshot_manager = ScreenshotManager()