"""Convert Playwright codegen recording to pytest-compatible test file.

The raw recording uses standalone sync_playwright() which cannot run under pytest.
This converter wraps the recorded actions into a pytest test function that uses
pytest-playwright's `page` fixture, keeping the original Playwright API calls intact
so users can easily add their own expect() assertions.
"""

import os
import re
import sys
from datetime import datetime

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
from pathlib import Path

_ESCAPE_MAP = str.maketrans({
    "'": "\\'",
})


def _py_str(s: str) -> str:
    return "'" + s.translate(_ESCAPE_MAP) + "'"


def convert_codegen_to_pytest(py_file: str, test_name: str = "Recorded Test",
                              test_id: str = None, priority: str = "P2",
                              tags: list = None, browser: str = "chromium") -> str:
    with open(py_file, "r", encoding="utf-8") as f:
        code = f.read()

    steps = []
    step_num = 0
    lines = code.split("\n")
    current_iframe = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("from ") or stripped.startswith("import "):
            continue

        action_data = _parse_line(stripped)
        if action_data:
            step_num += 1

            if "_iframe" in action_data:
                iframe_sel = action_data.pop("_iframe")
                if iframe_sel != current_iframe:
                    current_iframe = iframe_sel
                    step_entry_iframe = {
                        "step": step_num,
                        "action": "switch_to_frame",
                        "params": {"selector": iframe_sel},
                        "description": f"Switch to frame {iframe_sel}",
                    }
                    steps.append(step_entry_iframe)
                    step_num += 1
            elif current_iframe:
                step_entry_back = {
                    "step": step_num,
                    "action": "switch_to_default",
                    "params": {},
                    "description": "Return to main page",
                }
                steps.append(step_entry_back)
                current_iframe = None
                step_num += 1

            step_entry = {
                "step": step_num,
                "action": action_data["action"],
                "params": action_data["params"],
                "description": action_data.get("description", ""),
            }
            steps.append(step_entry)

    if not steps:
        raise ValueError(f"No valid Playwright actions found in {py_file}")

    if test_id is None:
        test_id = Path(py_file).stem

    if tags is None:
        tags = []

    return _render_pytest_file(steps, test_id, test_name, priority, tags, browser)


def _render_pytest_file(steps: list, test_id: str, test_name: str,
                        priority: str, tags: list, browser: str = "chromium") -> str:
    func_name = "test_" + test_id.replace("-", "_").replace(".", "_")
    out = []
    out.append('"""')
    out.append(f"Auto-generated test case: {test_name}")
    out.append(f"test_id: {test_id}")
    out.append(f"priority: {priority}")
    out.append(f"tags: {tags}")
    out.append('"""')
    out.append("import pytest")
    out.append("from playwright.sync_api import Page, expect")
    out.append("from utils.screenshot import screenshot_manager")
    out.append("")

    priority_lower = priority.lower()
    out.append(f'@pytest.mark.{priority_lower}')
    out.append(f'@pytest.mark.browser_{browser}')
    for tag in tags:
        out.append(f'@pytest.mark.{tag}')
    out.append('@pytest.mark.parametrize("_repeat", range(1))  # change range(N) to repeat N times')
    out.append(f'def {func_name}(page: Page, _repeat: int):')
    out.append(f'    """{test_name}"""')
    out.append(f'    _ss = "{test_id}"')
    out.append(f'    def screenshot(name):')
    out.append(f'        screenshot_manager.take_step_screenshot(page, name, test_name=_ss)')
    out.append(f'    def wait(seconds):')
    out.append(f'        """Pause for N seconds."""')
    out.append(f'        page.wait_for_timeout(seconds * 1000)')
    out.append("")

    frame_selector = None

    for step in steps:
        py_lines = _step_to_py_lines(step, frame_selector)
        if step["action"] == "switch_to_frame":
            frame_selector = step["params"]["selector"]
        elif step["action"] == "switch_to_default":
            frame_selector = None
        for pl in py_lines:
            out.append(f"    {pl}")
        out.append("    # wait(1)  # uncomment to pause 1 second between steps")
        out.append("")

    # keep only first & last screenshot active, comment out the rest
    screenshot_indices = [i for i, line in enumerate(out) if line.lstrip().startswith("screenshot(")]
    if len(screenshot_indices) > 2:
        for i in screenshot_indices[1:-1]:
            out[i] = "# " + out[i]

    out.append("    # --------------------------------------------------")
    out.append("    # TODO: add custom verification points below")
    out.append("    # --------------------------------------------------")
    return "\n".join(out) + "\n"


def _step_to_py_lines(step: dict, frame_selector: str = None) -> list:
    action = step["action"]
    params = step.get("params", {})
    desc = step.get("description", "")
    step_num = step["step"]
    sel = _py_str(params.get("selector", ""))

    def loc(sel_str):
        if frame_selector:
            return f"page.frame_locator({_py_str(frame_selector)}).locator({sel_str})"
        return f"page.locator({sel_str})"

    lines = []
    lines.append(f"# Step {step_num}: {desc}")

    if action == "navigate":
        lines.append(f"page.goto({_py_str(params['url'])})")
        lines.append('page.wait_for_load_state("domcontentloaded")')
        lines.append(f"screenshot({_py_str(f'navigate_{step_num}')})")
        lines.append("# TODO: verify page content below")
        lines.append('page_text = page.inner_text("body")')
        lines.append('# page text save alongside screenshots (uncomment below)')
        lines.append(f'# text_file = screenshot_manager.screenshot_dir / "page_texts" / "step_{step_num}.txt"')
        lines.append('# text_file.parent.mkdir(parents=True, exist_ok=True)')
        lines.append('# text_file.write_text(page_text, encoding="utf-8")')
        lines.append('# assert "EXPECTED_CONTENT" in page_text, f"Expected text not found: {page_text[:200]}"')

    elif action == "click":
        lines.append(f"{loc(sel)}.click()")
        lines.append(f"screenshot({_py_str(f'click_{step_num}')})")
        lines.append("# TODO: verify page content below")
        lines.append('page_text = page.inner_text("body")')
        lines.append('# page text save alongside screenshots (uncomment below)')
        lines.append(f'# text_file = screenshot_manager.screenshot_dir / "page_texts" / "step_{step_num}.txt"')
        lines.append('# text_file.parent.mkdir(parents=True, exist_ok=True)')
        lines.append('# text_file.write_text(page_text, encoding="utf-8")')
        lines.append('# assert "EXPECTED_CONTENT" in page_text, f"Expected text not found: {page_text[:200]}"')
        lines.append("")
    elif action == "dblclick":
        lines.append(f"{loc(sel)}.dblclick()")
        lines.append(f"screenshot({_py_str(f'dblclick_{step_num}')})")
        lines.append("# TODO: verify page content below")
        lines.append('page_text = page.inner_text("body")')
        lines.append('# page text save alongside screenshots (uncomment below)')
        lines.append(f'# text_file = screenshot_manager.screenshot_dir / "page_texts" / "step_{step_num}.txt"')
        lines.append('# text_file.parent.mkdir(parents=True, exist_ok=True)')
        lines.append('# text_file.write_text(page_text, encoding="utf-8")')
        lines.append('# assert "EXPECTED_CONTENT" in page_text, f"Expected text not found: {page_text[:200]}"')

    elif action == "fill":
        text = params.get("text", "")
        lines.append(f"{loc(sel)}.fill({_py_str(text)})")
        lines.append(f"expect({loc(sel)}).to_have_value({_py_str(text)})")

    elif action == "press_key":
        lines.append(f"{loc(sel)}.press({_py_str(params.get('key', ''))})")
        lines.append("# TODO: verify result after key press")

    elif action == "select_option":
        val = params.get("value", "")
        lines.append(f"{loc(sel)}.select_option({_py_str(val)})")
        lines.append(f"screenshot({_py_str(f'select_{step_num}')})")
        lines.append(f"expect({loc(sel)}).to_have_value({_py_str(val)})")

    elif action == "check":
        lines.append(f"{loc(sel)}.check()")
        lines.append(f"screenshot({_py_str(f'check_{step_num}')})")
        lines.append(f"expect({loc(sel)}).to_be_checked()")

    elif action == "uncheck":
        lines.append(f"{loc(sel)}.uncheck()")
        lines.append(f"screenshot({_py_str(f'uncheck_{step_num}')})")
        lines.append(f"expect({loc(sel)}).not_to_be_checked()")

    elif action == "hover":
        lines.append(f"{loc(sel)}.hover()")
        lines.append(f"screenshot({_py_str(f'hover_{step_num}')})")
        lines.append("# TODO: verify hover result (e.g. tooltip, dropdown)")

    elif action == "drag_and_drop":
        lines.append(
            f"page.locator({_py_str(params['source'])}).drag_to(page.locator({_py_str(params['target'])}))")
        lines.append(f"screenshot({_py_str(f'drag_{step_num}')})")
        lines.append("# TODO: verify drag & drop result")

    elif action == "wait":
        lines.append(f"page.wait_for_timeout({params.get('ms', 1000)})")

    elif action == "wait_for_element":
        lines.append(f"{loc(sel)}.wait_for(state=\"visible\")")

    elif action == "switch_to_frame":
        lines.append(f"# [iframe] Entering: {params['selector']}")

    elif action == "switch_to_default":
        lines.append(f"# [iframe] Returning to main page")

    else:
        lines.append(f"# [TODO] Unknown action: {action}")

    return lines


# ═══════════════════════════════════════════════════════════════════
# Parser — extracts actions from Playwright codegen output
# ═══════════════════════════════════════════════════════════════════

def _parse_line(line: str) -> dict:
    m = re.match(r"page\.goto\(['\"](.+?)['\"]\)", line)
    if m:
        return {"action": "navigate", "params": {"url": m.group(1)},
                "description": f"Navigate to {m.group(1)}"}

    m = re.match(r"page\.get_by_role\(['\"](.+?)['\"],\s*name=['\"](.*?)['\"]\)\.(\w+)\((.+)?\)", line)
    if m:
        role, name, method, args_str = m.group(1), m.group(2), m.group(3), m.group(4)
        return _handle_get_by_role(role, name, method, args_str)

    m = re.match(r"page\.get_by_text\(['\"](.+?)['\"](?:,\s*exact\s*=\s*True)?\)\.(\w+)\((.+)?\)", line)
    if m:
        text, method, args_str = m.group(1), m.group(2), m.group(3)
        return _handle_get_by_text(text, method, args_str)

    m = re.match(r"page\.locator\((['\"])", line)
    if m:
        result, end = _extract_quoted_string(line, m.end())
        if result is not None:
            rest = line[end:].strip()
            rest = re.sub(r"^\)\s*", "", rest)
            action_m = re.match(r"\.(\w+)\((.+)?\)", rest)
            if action_m:
                return _handle_locator_action(result, action_m.group(1),
                                              action_m.group(2) if action_m.group(2) else "")
            if ".content_frame" in rest:
                action_data = _handle_content_frame(result, rest)
                if action_data:
                    return action_data
                return None

    m = re.match(r"page\.click\(['\"](.+?)['\"]\)", line)
    if m:
        return {"action": "click", "params": {"selector": m.group(1)},
                "description": f"Click {m.group(1)}"}

    m = re.match(r"page\.fill\(['\"](.+?)['\"],\s*['\"](.*?)['\"]\)", line)
    if m:
        return {"action": "fill", "params": {"selector": m.group(1), "text": m.group(2)},
                "description": f"Type '{m.group(2)}' into {m.group(1)}"}

    m = re.match(r"page\.drag_and_drop\(['\"](.+?)['\"],\s*['\"](.+?)['\"]\)", line)
    if m:
        return {"action": "drag_and_drop", "params": {"source": m.group(1), "target": m.group(2)},
                "description": f"Drag {m.group(1)} -> {m.group(2)}"}

    m = re.match(r"page\.wait_for_selector\(['\"](.+?)['\"]\)", line)
    if m:
        return {"action": "wait_for_element", "params": {"selector": m.group(1)},
                "description": f"Wait for element {m.group(1)}"}

    m = re.match(r"page\.wait_for_timeout\((\d+)\)", line)
    if m:
        return {"action": "wait", "params": {"ms": int(m.group(1))},
                "description": f"Wait {m.group(1)}ms"}

    if "page.pause()" in line:
        return None

    print(f"  [WARN] Skipped: {line}")
    return None


def _extract_quoted_string(s: str, content_start: int):
    quote = s[content_start - 1]
    pos = content_start
    result = []
    while pos < len(s):
        ch = s[pos]
        if ch == "\\" and pos + 1 < len(s):
            result.append(s[pos + 1])
            pos += 2
        elif ch == quote:
            return "".join(result), pos + 1
        else:
            result.append(ch)
            pos += 1
    return None, -1


def _handle_content_frame(iframe_selector: str, rest: str) -> dict:
    rest = re.sub(r"^\.content_frame", "", rest)
    rest = re.sub(r"^\)\s*", "", rest)

    m = re.match(r"\.locator\((['\"])", rest)
    if not m:
        return None
    inner_sel, end = _extract_quoted_string(rest, m.end())
    if inner_sel is None:
        return None
    rest = rest[end:].strip()
    rest = re.sub(r"^\)\s*", "", rest)

    action_m = re.match(r"\.(\w+)\((.+)?\)", rest)
    if not action_m:
        return None
    method = action_m.group(1)
    args_str = action_m.group(2) if action_m.group(2) else ""

    inner_action = _handle_locator_action(inner_sel, method, args_str)
    if inner_action:
        inner_action["_iframe"] = iframe_selector
    return inner_action


def _handle_locator_action(selector: str, method: str, args_str: str) -> dict:
    if method == "click":
        return {"action": "click", "params": {"selector": selector},
                "description": f"Click {selector}"}
    elif method == "dblclick":
        return {"action": "dblclick", "params": {"selector": selector},
                "description": f"Double-click {selector}"}
    elif method == "fill":
        text = ""
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                text = m.group(1)
        return {"action": "fill", "params": {"selector": selector, "text": text},
                "description": f"Type '{text}' into {selector}"}
    elif method == "press":
        key = ""
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                key = m.group(1)
        return {"action": "press_key", "params": {"selector": selector, "key": key},
                "description": f"Press '{key}' on {selector}"}
    elif method == "select_option":
        value = ""
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                value = m.group(1)
        return {"action": "select_option", "params": {"selector": selector, "value": value},
                "description": f"Select '{value}' in {selector}"}
    elif method == "check":
        return {"action": "check", "params": {"selector": selector},
                "description": f"Check {selector}"}
    elif method == "uncheck":
        return {"action": "uncheck", "params": {"selector": selector},
                "description": f"Uncheck {selector}"}
    elif method == "hover":
        return {"action": "hover", "params": {"selector": selector},
                "description": f"Hover over {selector}"}
    elif method == "drag_to":
        target = ""
        if args_str:
            m = re.match(r"page\.locator\(['\"](.+?)['\"]\)", args_str.strip())
            if m:
                target = m.group(1)
        return {"action": "drag_and_drop", "params": {"source": selector, "target": target},
                "description": f"Drag {selector} -> {target}"}
    return None


def _handle_get_by_role(role: str, name: str, method: str, args_str: str) -> dict:
    desc = f"{role.capitalize()} '{name}'" if name else role.capitalize()

    if name:
        selector = f'role={role}[name="{name}"]'
    else:
        selector = f'role={role}'

    result = {}
    if method == "click":
        result = {"action": "click", "params": {"selector": selector},
                  "description": f"Click {desc}"}
    elif method == "dblclick":
        result = {"action": "dblclick", "params": {"selector": selector},
                  "description": f"Double-click {desc}"}
    elif method == "fill":
        result = {"action": "fill", "params": {"selector": selector, "text": ""},
                  "description": f"Type text into {desc}"}
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                result["params"]["text"] = m.group(1)
                result["description"] = f"Type '{m.group(1)}' into {desc}"
    elif method == "press":
        key = ""
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                key = m.group(1)
        result = {"action": "press_key", "params": {"selector": selector, "key": key},
                  "description": f"Press '{key}' on {desc}"}
    elif method == "select_option":
        value = ""
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                value = m.group(1)
        result = {"action": "select_option", "params": {"selector": selector, "value": value},
                  "description": f"Select '{value}' in {desc}"}
    elif method == "check":
        result = {"action": "check", "params": {"selector": selector},
                  "description": f"Check {desc}"}
    elif method == "uncheck":
        result = {"action": "uncheck", "params": {"selector": selector},
                  "description": f"Uncheck {desc}"}
    elif method == "hover":
        result = {"action": "hover", "params": {"selector": selector},
                  "description": f"Hover over {desc}"}
    elif method == "drag_to":
        target = ""
        if args_str:
            m = re.match(r"page\.locator\(['\"](.+?)['\"]\)", args_str.strip())
            if m:
                target = m.group(1)
        result = {"action": "drag_and_drop", "params": {"source": selector, "target": target},
                  "description": f"Drag {desc} -> {target}"}

    return result


def _handle_get_by_text(text: str, method: str, args_str: str) -> dict:
    result = {}
    if method == "click":
        result = {"action": "click", "params": {"selector": f"text={text}"},
                  "description": f"Click text '{text}'"}
    elif method == "fill":
        fill_text = ""
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                fill_text = m.group(1)
        result = {"action": "fill", "params": {"selector": f"text={text}", "text": fill_text},
                  "description": f"Type '{fill_text}' into text element '{text}'"}
    elif method == "press":
        key = ""
        if args_str:
            m = re.match(r"['\"](.*)['\"]", args_str.strip())
            if m:
                key = m.group(1)
        result = {"action": "press_key", "params": {"selector": f"text={text}", "key": key},
                  "description": f"Press '{key}' on text '{text}'"}
    elif method == "hover":
        result = {"action": "hover", "params": {"selector": f"text={text}"},
                  "description": f"Hover over text '{text}'"}
    elif method == "drag_to":
        target = ""
        if args_str:
            m = re.match(r"page\.locator\(['\"](.+?)['\"]\)", args_str.strip())
            if m:
                target = m.group(1)
        result = {"action": "drag_and_drop", "params": {"source": f"text={text}", "target": target},
                  "description": f"Drag text '{text}' -> {target}"}
    return result


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python utils/converter.py <recording.py> [test_name] [--priority P2] [--tags tag1,tag2] [--variant 001]")
        sys.exit(1)

    input_file = sys.argv[1]

    if not Path(input_file).exists():
        name = Path(input_file).name
        found = None
        recordings_root = Path(__file__).resolve().parent.parent / "recorder"
        if recordings_root.exists():
            for date_dir in sorted(recordings_root.iterdir(), reverse=True):
                if date_dir.is_dir():
                    alt = date_dir / name
                    if alt.exists():
                        found = str(alt)
                        break
        if found:
            input_file = found

    name = "Recorded Test"
    priority = "P2"
    tags = []
    browser = "chromium"
    variant = None
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--priority" and i + 1 < len(sys.argv):
            priority = sys.argv[i + 1].upper()
            if priority not in ("P0", "P1", "P2", "P3"):
                print(f"Invalid priority: {sys.argv[i + 1]}. Must be P0, P1, P2, or P3.")
                sys.exit(1)
            i += 2
        elif sys.argv[i] == "--tags" and i + 1 < len(sys.argv):
            tags = [t.strip() for t in sys.argv[i + 1].split(",") if t.strip()]
            i += 2
        elif sys.argv[i] == "--browser" and i + 1 < len(sys.argv):
            browser = sys.argv[i + 1].lower()
            if browser not in ("chromium", "edge"):
                print(f"Invalid browser: {sys.argv[i + 1]}. Must be chromium or edge.")
                sys.exit(1)
            i += 2
        elif sys.argv[i] == "--variant" and i + 1 < len(sys.argv):
            variant = sys.argv[i + 1]
            i += 2
        else:
            name = sys.argv[i]
            i += 1

    test_id = Path(input_file).stem
    if variant:
        test_id = f"{test_id}_test_{str(variant).zfill(3)}"
    else:
        test_id = f"{test_id}_test"

    py_code = convert_codegen_to_pytest(input_file, name, test_id=test_id,
                                        priority=priority, tags=tags, browser=browser)

    stem = Path(input_file).stem
    date_dir = stem[4:12] if stem.startswith("REC_") and len(stem) >= 12 else datetime.now().strftime("%y-%m-%d")

    out_dir = Path(__file__).resolve().parent.parent / "test_case" / date_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{test_id}.py"
    out_path.write_text(py_code, encoding="utf-8")

    action_count = sum(1 for line in py_code.split("\n") if line.strip().startswith("page."))
    print(f"Test case generated: {out_path}")
    print(f"  Priority: {priority}  |  Tags: {tags or 'none'}")
    print(f"  Actions: {action_count}")
    print(f"\nNow run: python run_tests.py")