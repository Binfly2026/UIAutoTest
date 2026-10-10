# UIAutoTest — Playwright Web UI Automation Test Framework

## Requirements

- Python 3.12+
- Windows / macOS / Linux

---

## Quick Start

### 1. Install Dependencies

```powershell
cd UIAutoTest
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\playwright install chromium
```

> Or run `python run_tests.py` — it auto-detects and completes all steps above.

### 2. Run Tests

```powershell
# Run by priority
python run_tests.py                       # default: all (see DEFAULT_PRIORITY in run_tests.py)
python run_tests.py --priority P0         # only P0
python run_tests.py --all                 # all priorities

# Run by tag
python run_tests.py --tags smoke,login

# Direct pytest (advanced)
.\venv\Scripts\pytest test_case/ -v -m p0
.\venv\Scripts\pytest test_case/ -v -m "p0 and smoke"
```

### 3. View Results

| Output | Path |
|--------|------|
| HTML Report | `reports/YY-MM-DD/TestReport_YY-MM-DD_HH-MM-SS.html` |
| Step Screenshots | `reports/YY-MM-DD/screenshots/{test_id}/{HH-MM-SS}/` |
| Failed Screenshots | Same path, directory renamed to `{test_id} [FAILED]/` |
| Runtime Log | `reports/logs/log_YY-MM-DD.log` |

---

## Directory Structure

```
UIAutoTest/
├── record.py                      # Record browser actions → native pytest file
├── run_tests.py                   # One-click install + run (editable filter defaults)
├── pytest.ini                     # Pytest markers & discovery config
├── requirements.txt               # Dependencies
│
├── config/
│   └── settings.py                # Browser, viewport, timeout, etc.
│
├── test_case/
│   ├── conftest.py                # Browser fixtures + failure screenshots + report gen
│   └── YY-MM-DD/
│       └── REC_26-10-07_11-03-23_test.py   # Auto-generated test (native pytest)
├── utils/
│   ├── screenshot.py              # Screenshot manager
│   ├── report_generator.py        # Enhanced HTML report generator
│   ├── logger.py                  # Logger
│   └── converter.py               # Codegen .py → pytest .py converter
├── recorder/
│   └── YY-MM-DD/
│       └── REC_26-10-10_09-10-28.py    # Raw recording (replayable + regenerable)
│
└── reports/                       # Output (auto-generated)
    ├── YY-MM-DD/
    │   ├── TestReport_YY-MM-DD_HH-MM-SS.html
    │   └── screenshots/
    │       └── {test_id}/
    │           └── HH-MM-SS/   (or [FAILED] suffix)
    └── logs/
        └── log_YY-MM-DD.log
```

---

## Recording (Generate Test Cases from Browser Actions)

Record your browser actions, and the tool generates a ready-to-run native pytest file with assertions.

### Record a New Test

```powershell
python record.py                                    # record on demo page
python record.py https://example.com                # custom URL
python record.py --name "Login" https://example.com  # custom test name
python record.py --priority P1 --tags smoke,login https://example.com
python record.py --browser edge https://example.com   # record with Edge
```

| Argument | Default | Description |
|----------|---------|-------------|
| `URL` | demo page | Target website URL |
| `--name` | auto (timestamp) | Test case name |
| `--priority` | `P2` | Priority: `P0`, `P1`, `P2`, `P3` |
| `--tags` | none | Comma-separated: `smoke,login,regression` |
| `--browser` | `chromium` | `chromium`, `edge` |

Browser opens → perform actions → close browser. The tool will:

1. Save raw recording to `recorder/YY-MM-DD/REC_YY-MM-DD_HH-MM-SS.py` (with `page.pause()` for replay)
2. Auto-convert to `test_case/YY-MM-DD/REC_YY-MM-DD_HH-MM-SS_test.py` (native pytest with assertions)

### Generated Test File Structure

```python
import pytest
from playwright.sync_api import Page, expect
from utils.screenshot import screenshot_manager

@pytest.mark.p2
def test_REC_26_10_10_09_10_28_test(page: Page):
    """Recorded 26-10-10_09-10-28"""
    _ss = "REC_26-10-10_09-10-28_test"
    def screenshot(name):
        screenshot_manager.take_step_screenshot(page, name, test_name=_ss)

    # Step 1: Navigate to https://example.com
    page.goto('https://example.com')
    page.wait_for_load_state("domcontentloaded")
    screenshot('navigate_1')
    # expect(page).to_have_title("...")

    # Step 2: Type 'hello' into #search
    page.locator('#search').fill('hello')
    expect(page.locator('#search')).to_have_value('hello')   # ← auto-assertion

    # Step 3: Check #agree
    page.locator('#agree').check()
    screenshot('check_3')
    expect(page.locator('#agree')).to_be_checked()           # ← auto-assertion

    # --------------------------------------------------
    # TODO: add custom verification points below
    # --------------------------------------------------
```

> Add `expect()` calls in the `TODO` section for custom checks. Replace `"..."` in `# expect(page).to_have_title("...")` / `# expect(page).to_have_url("...")` with actual expected values and uncomment.

### Regenerate Test Variants

Each recording file has a regenerator block at the bottom. Uncomment it and run:

```powershell
.\venv\Scripts\python.exe recorder\YY-MM-DD\REC_26-10-10_09-10-28.py
```

This creates `test_case/YY-MM-DD/REC_26-10-10_09-10-28_test_001.py`, `_test_002.py`, etc. Each run auto-increments the sequence number without overwriting existing files. Use this when you need multiple scenario variants from the same recording.

### Re-convert Manually

```powershell
.\venv\Scripts\python.exe -B utils\converter.py recorder\YY-MM-DD\REC_26-10-10.py "Test Name" --priority P1 --tags smoke
```

| Argument | Description |
|----------|-------------|
| `filename.py` | Path to recorded .py file |
| `"Test Name"` | Test case name |
| `--priority` | Priority: `P0` ~ `P3` |
| `--tags` | Comma-separated tags |

---

## Assertion Strategy

Auto-generated assertions are placed **inline** right after each action. The strategy:

| Action | Auto-Assertion | Type |
|--------|----------------|------|
| `page.locator(sel).fill('text')` | `expect(page.locator(sel)).to_have_value('text')` | **Executable** — verifies the text was entered |
| `page.locator(sel).check()` | `expect(page.locator(sel)).to_be_checked()` | **Executable** — verifies checkbox is checked |
| `page.locator(sel).uncheck()` | `expect(page.locator(sel)).not_to_be_checked()` | **Executable** — verifies it's unchecked |
| `page.locator(sel).select_option('v')` | `expect(page.locator(sel)).to_have_value('v')` | **Executable** — verifies selected option |
| `page.goto(url)` | `# expect(page).to_have_title("...")` | **Hint** — fill in the expected page title |
| `page.locator(sel).click()` | `# expect(page).to_have_url("...")` | **Hint** — fill in the expected URL after click |
| `page.locator(sel).dblclick()` | `# expect(page).to_have_url("...")` | **Hint** |
| `page.locator(sel).hover()` | `# TODO: verify hover result` | **Hint** |
| `drag_to(target)` | `# TODO: verify drag & drop result` | **Hint** |
| `press(key)` | `# TODO: verify result after key press` | **Hint** |

**Design philosophy**: Actions with deterministic results (fill, check, select) get executable assertions that pass immediately. Actions with uncertain results (click, hover, drag) get comment hints — fill in the actual expected value and uncomment to activate.

---

## Screenshot Policy

The shorthand `screenshot('name')` is available inside every test function. It captures automatically on:

| Action | Screenshot | Rationale |
|--------|:--:|------|
| `page.goto()` | ✅ | Page loaded |
| `.click()` | ✅ | Page state change |
| `.dblclick()` | ✅ | Post double-click |
| `.check()` / `.uncheck()` | ✅ | Checkbox state change |
| `.select_option()` | ✅ | Dropdown change |
| `.hover()` | ✅ | Hover-triggered UI |
| `.drag_to()` | ✅ | Drag result |
| `.fill()` / `.press()` | — | Text input, no visual change |

Failed test directories get a `[FAILED]` suffix automatically.

---

## Default Test Filter

Edit the top of `run_tests.py` to set default filters — no command-line arguments needed for repeated runs:

```python
DEFAULT_PRIORITY = ""           # run all priorities by default
DEFAULT_TAGS = ""              # no tag filter by default
# DEFAULT_TAGS = "smoke"        # only smoke tests
DEFAULT_DIR = ""               # "26-10-10", "" → run all folders
```

Priority system:

| Mark | Purpose |
|------|---------|
| `@pytest.mark.p0` | Critical — must pass before release |
| `@pytest.mark.p1` | High — blocking issues |
| `@pytest.mark.p2` | Medium — regular regression (default for recordings) |
| `@pytest.mark.p3` | Low — non-blocking |

---

## Adding Test Cases Manually

Create a `.py` file in `test_case/` with standard pytest markers:

```python
import pytest
from playwright.sync_api import Page, expect
from utils.screenshot import screenshot_manager

@pytest.mark.p0
@pytest.mark.smoke
def test_my_login(page: Page):
    """Verify login with valid credentials"""
    _ss = "my_login"
    def screenshot(name):
        screenshot_manager.take_step_screenshot(page, name, test_name=_ss)

    page.goto('https://example.com/login')
    page.wait_for_load_state("domcontentloaded")
    screenshot('navigate_to_login')

    page.locator('#username').fill('admin')
    expect(page.locator('#username')).to_have_value('admin')

    page.locator('#password').fill('123456')

    page.locator('#submit').click()
    screenshot('click_submit')

    expect(page.locator('.welcome')).to_be_visible()
    expect(page.locator('.welcome')).to_contain_text('Welcome, admin')
```

> Follow the pattern from auto-generated files: define `_ss` path for screenshots, `screenshot(name)` shorthand, inline `expect()` assertions after each action.

---

## Reading & Verifying Element Text

Use Playwright's built-in methods — no custom wrappers needed:

```python
# Get visible text (what the user sees on screen)
text = page.locator("#result").inner_text()

# Get raw text content (includes hidden text)
text = page.locator("#result").text_content()

# Get input field value
value = page.locator("#username").input_value()
```

### Common Assertion Patterns

```python
# Verify element contains substring
expect(page.locator("#result")).to_contain_text("Success")

# Verify exact text match
expect(page.locator("#result")).to_have_text("Login successful")

# Get value and use in logic
count = page.locator(".item").count()
assert count >= 3, f"Expected ≥ 3 items, got {count}"

# Print captured text for debugging
text = page.locator("#price").inner_text()
print(f"Captured text: {text}")
```

> Add these in the `TODO` section of any auto-generated test file. No JSON `get_text` / `expected` wrappers — just plain Python + Playwright.

---

## Configuration

Edit `config/settings.py`:

```python
BROWSER = "chromium"          # chromium / edge
HEADLESS = True               # True = headless / False = visible
VIEWPORT = {"width": 1920, "height": 1080}
LOG_LEVEL = "INFO"            # DEBUG / INFO / WARNING / ERROR
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

## HTML Report Features

- **Grouped by file** — each test file displayed under its own header
- **Collapsible sections** — click to expand/collapse test cases
- **Inline screenshots** — each step screenshot displayed as thumbnail, click for full size
- **Screenshots collapsed by default** — keeps the report compact
- **Executor & timestamp** — shows who ran the tests and when

---

## Quick Command Reference

```powershell
cd d:\Code\UIAutoTest

# Install & run
python run_tests.py

# Run by priority
python run_tests.py --priority P0
python run_tests.py --priority P1 --tags smoke

# Run all
python run_tests.py --all

# Record a test case
python record.py
python record.py --name "Login" --priority P1 https://example.com

# Replay a recording (browser stays open)
.\venv\Scripts\python.exe recorder\YY-MM-DD\REC_26-10-10.py

# Re-convert manually
.\venv\Scripts\python.exe -B utils\converter.py recorder\YY-MM-DD\REC_26-10-10.py "Name" --priority P2

# Direct pytest (advanced)
.\venv\Scripts\pytest test_case/ -v -m p0
.\venv\Scripts\pytest test_case/ -v -k "login"
```