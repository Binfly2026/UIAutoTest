from pathlib import Path

VERSION = "1.0.0"

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT_DIR / "reports"
SCREENSHOT_DIR = REPORT_DIR
LOG_DIR = REPORT_DIR / "logs"

BROWSER = "chromium"
HEADLESS = True
VIEWPORT = {"width": 1920, "height": 1080}

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"