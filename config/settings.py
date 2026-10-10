from pathlib import Path


def _get_version() -> str:
    """Derive version from the nearest git tag, e.g. 'v1.0.0' → '1.0.0'.
    Appends '-dirty' when the working tree has uncommitted changes.
    Falls back to the hardcoded default when git is not available.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["git", "describe", "--tags", "--dirty", "--always"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            desc = result.stdout.strip().lstrip("v")
            return desc if desc else "0.0.0"
    except Exception:
        pass
    return "0.0.0"


VERSION = _get_version()

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT_DIR / "reports"
SCREENSHOT_DIR = REPORT_DIR
LOG_DIR = REPORT_DIR / "logs"

BROWSER = "chromium"
HEADLESS = True
VIEWPORT = {"width": 1920, "height": 1080}

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"