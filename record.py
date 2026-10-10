#!/usr/bin/env python
"""Record browser actions and generate executable test case.

Usage:
    python record.py                                    # record on demo page
    python record.py https://example.com                # record on custom URL
    python record.py --name "Login" https://example.com  # custom test name
    python record.py --priority P1 --tags smoke,login https://example.com
    python record.py --browser edge https://example.com  # record with Edge
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent
RECORD_DIR = ROOT / "recorder"
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"

args = sys.argv[1:]
# url = "https://seleniumbase.io/demo_page"
url = "https://www.saucedemo.com/"
test_name = ""
priority = "P2"
tags = []
browser = "chromium" # "chromium" / "edge"

i = 0
while i < len(args):
    if args[i] == "--name" and i + 1 < len(args):
        test_name = args[i + 1]
        i += 2
    elif args[i] == "--priority" and i + 1 < len(args):
        priority = args[i + 1].upper()
        if priority not in ("P0", "P1", "P2", "P3"):
            print(f"Invalid priority: {args[i + 1]}. Must be P0, P1, P2, or P3.")
            sys.exit(1)
        i += 2
    elif args[i] == "--tags" and i + 1 < len(args):
        tags = [t.strip() for t in args[i + 1].split(",") if t.strip()]
        i += 2
    elif args[i] == "--browser" and i + 1 < len(args):
        browser = args[i + 1].lower()
        if browser not in ("chromium", "edge"):
            print(f"Invalid browser: {args[i + 1]}. Must be chromium or edge.")
            sys.exit(1)
        i += 2
    else:
        url = args[i]
        i += 1

record_timestamp = datetime.now().strftime("%y-%m-%d_%H-%M-%S")
record_date = datetime.now().strftime("%y-%m-%d")
recordings_dir = RECORD_DIR / record_date
recordings_dir.mkdir(parents=True, exist_ok=True)
recording_file = recordings_dir / f"REC_{record_timestamp}.py"

if not test_name:
    test_name = f"Recorded {record_timestamp}"

print(f"Timestamp  : {record_timestamp}")
print(f"URL        : {url}")
print(f"Browser    : {browser}")
print(f"Test name  : {test_name}")
print(f"Priority   : {priority}")
print(f"Tags       : {tags or 'none'}")
print("=" * 50)
print("Browser will open. Perform your actions,")
print("then close the browser to stop recording.")
print("=" * 50)

_browser_map = {
    "chromium": ["--browser", "chromium"],
    "edge":     ["--browser", "chromium", "--channel", "msedge"],
}
_browser_args = _browser_map.get(browser, ["--browser", browser])

codegen_cmd = [
    str(VENV_PYTHON), "-m", "playwright", "codegen",
    *_browser_args,
    "--target", "python", "-o", str(recording_file),
    url,
]

result = subprocess.run(codegen_cmd, cwd=str(ROOT))

if result.returncode != 0:
    print("Recording was cancelled or failed.")
    sys.exit(0)

if not recording_file.exists() or recording_file.stat().st_size == 0:
    print("No actions recorded.")
    sys.exit(0)

# Insert page.pause() so browser stays open after replay
content = recording_file.read_text(encoding="utf-8")
content = content.replace("\n    page.close()", "\n    page.pause()\n    page.close()", 1)
recording_file.write_text(content, encoding="utf-8")

print(f"\nRaw recording saved: {recording_file}")
print("Generating test case...")

tag_args = []
if tags:
    tag_args = ["--tags", ",".join(tags)]

convert_result = subprocess.run(
    [
        str(VENV_PYTHON), "-B",
        str(ROOT / "utils" / "converter.py"),
        str(recording_file),
        test_name,
        "--priority", priority,
        "--browser", browser,
    ] + tag_args,
    cwd=str(ROOT),
    capture_output=True, text=True,
)

print(convert_result.stdout)
if convert_result.stderr:
    print(convert_result.stderr)

py_file = ROOT / "test_case" / record_date / f"REC_{record_timestamp}_test.py"
print(f"\nTest case : {py_file}")
print(f"Recording : {recording_file}")
print(f"\nRun: python run_tests.py")

# Append regeneration block to the recording file
tag_part = f', "--tags", "{",".join(tags)}"' if tags else ""
regen_block = f'''

# ═══════════════════════════════════════════════════════════════
# REGENERATE: run this file to create a new test variant.
# Each run auto-increments the sequence number.
# ═══════════════════════════════════════════════════════════════
# if __name__ == "__main__":
#     import subprocess
#     from pathlib import Path
#
#     root = Path(__file__).resolve().parent.parent.parent
#     base = Path(__file__).stem
#     existing = sorted((root / "test_case" / "{record_date}").glob(f"{{base}}_test_*.py"))
#     n = str(int(existing[-1].stem.rsplit("_", 1)[-1]) + 1).zfill(3) if existing else "001"
#
#     subprocess.run([
#         str(root / "venv" / "Scripts" / "python.exe"), "-B",
#         str(root / "utils" / "converter.py"),
#         str(Path(__file__).resolve()),
#         "{test_name}",
#         "--priority", "{priority}"{tag_part},
#         "--browser", "{browser}",
#         "--variant", n,
#     ], cwd=str(root))
#
#     print(f"Created: test_case\\{record_date}\\{{base}}_test_{{n}}.py")
'''
with open(recording_file, "a", encoding="utf-8") as f:
    f.write(regen_block)