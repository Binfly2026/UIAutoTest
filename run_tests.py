import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent

# ═══════════════════════════════════════════════════════════════
# EDIT BELOW to set default test filter (overridden by CLI)
#   DEFAULT_PRIORITY = "P0"  →  only run P0 tests
#   DEFAULT_PRIORITY = ""    →  run all priorities
#   DEFAULT_TAGS = "smoke"   →  only run smoke-tagged tests
#   DEFAULT_DIR = "26-10-10" →  only run tests under test_case/26-10-10/，"" →  run all directories
# ═══════════════════════════════════════════════════════════════
DEFAULT_PRIORITY = ""
DEFAULT_TAGS = ""
DEFAULT_DIR = ""


def install_dependencies():
    venv_dir = PROJECT_DIR / "venv"
    if not venv_dir.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    pip = venv_dir / "Scripts" / "pip.exe"
    requirements = PROJECT_DIR / "requirements.txt"
    offline_dir = PROJECT_DIR / "offline_pkgs"

    if offline_dir.exists() and any(offline_dir.glob("*.whl")):
        print("Checking offline packages...")
        r = subprocess.run(
            [str(pip), "install", "--dry-run", "--no-index", "--find-links", str(offline_dir),
             "-r", str(requirements)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print("WARNING: offline packages may be incomplete!")
            print(r.stderr.strip().split("\n")[-1] if r.stderr.strip() else "")
            print("Attempting install anyway...\n")
        else:
            print("All dependencies found in offline_pkgs/")
        subprocess.run(
            [str(pip), "install", "--no-index", "--find-links", str(offline_dir), "-r", str(requirements)],
            check=True,
        )
    else:
        print("Installing dependencies from PyPI...")
        subprocess.run([str(pip), "install", "-r", str(requirements)], check=True)

    browsers_dir = PROJECT_DIR / "browsers"
    if browsers_dir.exists() and any(browsers_dir.glob("chromium-*")):
        print("Using bundled Playwright browsers (offline)...")
    else:
        print("Installing Playwright browser...")
        playwright = venv_dir / "Scripts" / "playwright.exe"
        subprocess.run([str(playwright), "install", "chromium"], check=True)

    print("Dependencies installed successfully!")


def run_tests():
    venv_dir = PROJECT_DIR / "venv"
    pytest = venv_dir / "Scripts" / "pytest.exe"

    if not pytest.exists():
        install_dependencies()

    now = datetime.now()
    run_date = now.strftime("%y-%m-%d")
    run_time = now.strftime("%H-%M-%S")

    marker_exprs = []
    pytest_args = []
    test_dir = DEFAULT_DIR
    extra = sys.argv[1:]
    i = 0
    while i < len(extra):
        if extra[i] == "--priority" and i + 1 < len(extra):
            marker_exprs.append(extra[i + 1].lower())
            i += 2
        elif extra[i] == "--tags" and i + 1 < len(extra):
            for t in extra[i + 1].split(","):
                t = t.strip()
                if t:
                    marker_exprs.append(t)
            i += 2
        elif extra[i] == "--dir" and i + 1 < len(extra):
            test_dir = extra[i + 1]
            i += 2
        elif extra[i] == "--all":
            marker_exprs.clear()
            i += 1
        else:
            pytest_args.append(extra[i])
            i += 1

    if not marker_exprs:
        if DEFAULT_PRIORITY:
            marker_exprs.append(DEFAULT_PRIORITY.lower())
        if DEFAULT_TAGS:
            for t in DEFAULT_TAGS.split(","):
                t = t.strip()
                if t:
                    marker_exprs.append(t)

    args = [str(pytest), "-v", "--tb=short"]

    if test_dir:
        if test_dir.startswith("test_case") or test_dir.startswith("test_case/"):
            args.append(test_dir.rstrip("/"))
        else:
            args.append("test_case/" + test_dir.strip("/"))
    else:
        args.append("test_case/")

    args += pytest_args

    if marker_exprs:
        mark_filter = " or ".join(marker_exprs)
        args += ["-m", mark_filter]
        print(f"Marker filter: {mark_filter}")

    print(f"Running: {' '.join(args)}")

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TEST_RUN_DATE"] = run_date
    env["TEST_RUN_TIME"] = run_time

    browsers_dir = PROJECT_DIR / "browsers"
    if browsers_dir.exists():
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)

    result = subprocess.run(args, cwd=str(PROJECT_DIR), env=env)

    if result.returncode == 5:
        print("\nNo test cases found.")
    elif result.returncode == 0:
        print("\nTests completed successfully.")
        print(f"Report saved in: reports/{run_date}/")
    else:
        print(f"\nTests completed with failures (exit code: {result.returncode})")
        print(f"Report saved in: reports/{run_date}/")
    return result.returncode


if __name__ == "__main__":
    run_tests()