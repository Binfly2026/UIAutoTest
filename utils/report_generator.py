import base64
import json
import os
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from config.settings import REPORT_DIR
from utils.logger import logger

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

THUMBNAIL_WIDTH = 240


def _parse_error(error_info: str) -> dict:
    if not error_info:
        return {}
    result = {"line_no": "", "error_line": "", "error_type": "", "error_msg": ""}
    lines = error_info.split("\n")

    for line in lines:
        if not result["line_no"]:
            m = re.search(r'\.py:(\d+)', line)
            if m:
                result["line_no"] = m.group(1)
        stripped = line.strip()
        if stripped.startswith(">"):
            result["error_line"] = stripped.lstrip(">").strip()
        elif stripped.startswith("E ") or stripped.startswith("E\t"):
            if not result["error_msg"]:
                result["error_msg"] = stripped[1:].strip()
        if not result["error_type"]:
            m = re.search(r'(TimeoutError|Error|Exception|AssertionError)', stripped)
            if m:
                name = m.group(1)
                result["error_type"] = name

    if not result["error_line"]:
        result["error_line"] = error_info.strip().split("\n")[0][:120]
    if not result["error_type"]:
        result["error_type"] = "Error"
    return result


class ReportGenerator:

    def __init__(self):
        self.test_results = []

    def add_result(self, nodeid: str, outcome: str, duration: float,
                   source_file: str = "", priority: str = "", browser: str = "",
                   error_info: str = ""):
        raw_name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        m = re.search(r"\[(.+)\]", raw_name)
        display_name = m.group(1) if m else raw_name
        self.test_results.append({
            "nodeid": nodeid,
            "name": display_name,
            "outcome": outcome,
            "duration": round(duration, 2),
            "source_file": source_file,
            "priority": priority,
            "browser": browser,
            "error_info": error_info,
            "error_summary": _parse_error(error_info),
        })

    def generate(self, run_date: str, run_time: str, executor: str = "") -> str:
        screenshots_dir = REPORT_DIR / run_date / "screenshots"
        screenshots_by_test = self._collect_screenshots(screenshots_dir, run_time)

        stems = sorted(set(
            r.get("source_file", "") for r in self.test_results if r.get("source_file")
        ))
        if len(stems) == 1:
            stem = f"TestReport_{stems[0]}_{run_time}"
        else:
            stem = f"TestReport_{run_date}_{run_time}"
        report_path = REPORT_DIR / run_date / f"{stem}.html"
        html = self._build_html(screenshots_by_test, run_date, run_time, executor)

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(html, encoding="utf-8")
        logger.info(f"Test report generated: {report_path}")
        return str(report_path)

    def _collect_screenshots(self, screenshots_dir: Path, run_time: str = "") -> dict:
        """Returns {source_stem: {_screenshots: {display_name, screenshots, failed}}}"""
        result = {}
        if not screenshots_dir.exists():
            return result

        for test_dir in sorted(screenshots_dir.iterdir()):
            if not test_dir.is_dir():
                continue
            time_dir = test_dir / run_time if run_time else test_dir
            if not time_dir.exists():
                continue
            pngs = sorted(time_dir.glob("*.png"))
            if not pngs:
                continue
            is_failed = test_dir.name.endswith("[FAILED]")
            source_stem = test_dir.name.replace(" [FAILED]", "")
            display_name = source_stem.replace("_", " ")
            result[source_stem] = {
                "_screenshots": {
                    "display_name": display_name,
                    "screenshots": [str(p) for p in pngs],
                    "failed": is_failed,
                }
            }

        return result

    def _image_to_base64(self, path: str, thumbnail: bool = False) -> str:
        try:
            if HAS_PILLOW:
                img = Image.open(path)
                if thumbnail:
                    ratio = THUMBNAIL_WIDTH / img.width
                    height = int(img.height * ratio)
                    img = img.resize((THUMBNAIL_WIDTH, height), Image.LANCZOS)
                buf = BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()
            else:
                data = Path(path).read_bytes()
                return base64.b64encode(data).decode()
        except Exception as e:
            logger.warning(f"Failed to encode image {path}: {e}")
            return ""

    def _build_html(self, screenshots_by_test: dict, run_date: str, run_time: str, executor: str = "") -> str:
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["outcome"] == "passed")
        failed = sum(1 for r in self.test_results if r["outcome"] == "failed")
        skipped = total - passed - failed

        executor_info = f'&nbsp;|&nbsp; Executor: {executor}' if executor else ""

        groups = {}
        for r in self.test_results:
            sf = r.get("source_file", "") or "Other"
            groups.setdefault(sf, []).append(r)

        test_rows = ""
        for file_name in sorted(groups.keys()):
            entries = groups[file_name]
            file_passed = sum(1 for e in entries if e["outcome"] == "passed")
            file_failed = sum(1 for e in entries if e["outcome"] == "failed")
            file_total = len(entries)
            rows = ""
            for r in entries:
                icon = "✅" if r["outcome"] == "passed" else ("❌" if r["outcome"] == "failed" else "⏭️")
                browser_display = r.get("browser", "") or "—"
                priority_display = r.get("priority", "") or "—"
                error_row = ""
                if r["outcome"] == "failed" and r.get("error_summary"):
                    es = r["error_summary"]
                    err_line = es.get("error_line", "")
                    err_type = es.get("error_type", "")
                    line_no = es.get("line_no", "")
                    err_text = f"Line {line_no}: {err_line}" if line_no and err_line else (err_line or err_type or "Error")
                    full_trace = r.get("error_info", "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    error_row = f"""
                <tr class="error-detail">
                    <td colspan="6">
                        <div class="error-box">
                            <div class="error-summary">❌ {err_type}: {err_text}</div>
                            <details class="error-expand">
                                <summary>Show full traceback</summary>
                                <pre class="error-trace">{full_trace}</pre>
                            </details>
                        </div>
                    </td>
                </tr>"""
                rows += f"""
                <tr class="{r['outcome']}">
                    <td>{icon}</td>
                    <td>{r['name']}</td>
                    <td>{r['outcome'].upper()}</td>
                    <td>{r['duration']}s</td>
                    <td><span class="tag tag-priority">{priority_display}</span></td>
                    <td><span class="tag tag-browser">{browser_display}</span></td>
                </tr>{error_row}"""
            test_rows += f"""
            <div class="file-group">
                <h3 class="file-header">
                    📄 {file_name}
                    <span class="file-stats">
                        {file_total} case(s) &nbsp;|&nbsp;
                        <span class="stat-passed">{file_passed} passed</span>
                        {"&nbsp;|&nbsp;<span class='stat-failed'>" + str(file_failed) + " failed</span>" if file_failed else ""}
                    </span>
                </h3>
                <table>
                    <thead><tr><th></th><th>Test</th><th>Status</th><th>Duration</th><th>Priority</th><th>Browser</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>"""

        screenshot_sections = ""
        case_images = {}  # {case_key: [(base64_full, caption), ...]}

        stem_to_display = {}
        for r in self.test_results:
            sf = r.get("source_file", "")
            if sf:
                stem_to_display[sf] = sf

        all_stems = sorted(stem_to_display.keys())

        case_counter = 0
        for source_stem in all_stems:
            tests = screenshots_by_test.get(source_stem, {})
            if not tests:
                continue
            display_name = stem_to_display.get(source_stem, source_stem)

            screenshot_sections += f"""
            <div class="file-screenshots">
                <h3 class="file-header">📸 {display_name} — Screenshots</h3>"""

            for test_dir_name, data in tests.items():
                test_display = data["display_name"]
                case_key = f"case{case_counter}"
                case_counter += 1
                is_failed = data["failed"]
                failed_class = " failed-section" if is_failed else ""
                icon = "❌ " if is_failed else "📸 "
                count = len(data["screenshots"])
                thumbnails = ""
                case_imgs = []

                for img_path in data["screenshots"]:
                    b64 = self._image_to_base64(img_path, thumbnail=True)
                    full_b64 = self._image_to_base64(img_path, thumbnail=False)
                    fname = Path(img_path).name
                    local_idx = len(case_imgs)
                    case_imgs.append((full_b64, fname))
                    thumbnails += f"""
                    <div class="thumb-wrap">
                        <img class="thumb" src="data:image/png;base64,{b64}"
                             data-case="{case_key}" data-img-index="{local_idx}"
                             onclick="openLightbox('{case_key}',{local_idx})"
                             title="{fname}" loading="lazy" />
                        <div class="thumb-label">{fname[:30]}</div>
                    </div>"""

                if thumbnails:
                    case_images[case_key] = case_imgs
                    screenshot_sections += f"""
                    <div class="test-screenshots{failed_class}">
                        <h3 class="section-toggle" onclick="toggleSection(this)">
                            <span class="toggle-icon">▶</span>
                            {icon}{test_display} <span class="count">({count} screenshots)</span>
                        </h3>
                        <div class="section-content" style="display:none;">
                            <div class="thumb-gallery">{thumbnails}</div>
                        </div>
                    </div>"""

            screenshot_sections += """
            </div>"""

        images_json_parts = []
        for k, imgs in case_images.items():
            items = json.dumps([{"src": f"data:image/png;base64,{b64}", "caption": cap} for b64, cap in imgs])
            images_json_parts.append(f'"{k}":{items}')
        images_json = "{" + ",".join(images_json_parts) + "}"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Test Report {run_date} {run_time}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f6fa; color: #2d3436; }}
.header {{ background: linear-gradient(135deg, #2d3436, #636e72); color: #fff; padding: 24px 32px; }}
.header h1 {{ font-size: 22px; margin-bottom: 6px; }}
.header .meta {{ font-size: 13px; opacity: .7; }}
.summary {{ display: flex; gap: 16px; padding: 24px 32px; }}
.summary-card {{ background: #fff; border-radius: 10px; padding: 20px 28px; flex: 1; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
.summary-card .num {{ font-size: 36px; font-weight: 700; }}
.summary-card.passed .num {{ color: #00b894; }}
.summary-card.failed .num {{ color: #d63031; }}
.summary-card.total .num {{ color: #0984e3; }}
.summary-card .label {{ font-size: 13px; color: #636e72; margin-top: 4px; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 0 32px 40px; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
.file-group {{ margin-bottom: 24px; }}
.file-header {{ font-size: 15px; color: #2d3436; margin-bottom: 8px; padding: 10px 16px; background: #f0f2f5; border-radius: 8px 8px 0 0; display: flex; align-items: center; gap: 12px; }}
.file-stats {{ font-size: 12px; color: #636e72; font-weight: normal; }}
.stat-passed {{ color: #00b894; }}
.stat-failed {{ color: #d63031; }}
.file-screenshots {{ margin-bottom: 24px; }}
th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }}
th {{ background: #f8f9fa; font-weight: 600; color: #636e72; text-transform: uppercase; font-size: 12px; letter-spacing: .5px; }}
tr:hover {{ background: #f8f9ff; }}
tr.failed {{ background: #fff5f5; }}
.test-screenshots {{ background: #fff; border-radius: 10px; padding: 20px; margin-top: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
.section-toggle {{ font-size: 16px; margin-bottom: 14px; color: #2d3436; cursor: pointer; user-select: none; display: flex; align-items: center; gap: 8px; }}
.section-toggle:hover {{ opacity: .8; }}
.toggle-icon {{ font-size: 12px; display: inline-block; width: 16px; text-align: center; transition: transform .2s; }}
.count {{ font-size: 12px; color: #999; font-weight: normal; }}
.section-content {{ }}
.toolbar {{ display: flex; gap: 10px; margin-bottom: 16px; }}
.toolbar button {{ padding: 6px 16px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer; font-size: 13px; color: #555; }}
.toolbar button:hover {{ background: #f0f0f0; }}
.thumb-gallery {{ display: flex; flex-wrap: wrap; gap: 12px; }}
.thumb-wrap {{ text-align: center; }}
.thumb {{ width: {THUMBNAIL_WIDTH}px; border-radius: 6px; cursor: pointer; border: 2px solid #eee; transition: transform .15s, border-color .15s; }}
.thumb:hover {{ transform: scale(1.04); border-color: #0984e3; }}
.thumb-label {{ font-size: 10px; color: #999; margin-top: 4px; max-width: {THUMBNAIL_WIDTH}px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.failed-section {{ border-left: 4px solid #d63031; }}
.failed-section h3 {{ color: #d63031; }}
.lightbox {{ display: none; position: fixed; z-index: 999; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,.85); justify-content: center; align-items: center; flex-direction: column; }}
.lightbox.active {{ display: flex; }}
.lightbox img {{ max-width: 92%; max-height: 82%; border-radius: 6px; box-shadow: 0 8px 40px rgba(0,0,0,.4); }}
.lightbox .caption {{ color: #ccc; margin-top: 12px; font-size: 13px; }}
.lightbox .close {{ position: absolute; top: 20px; right: 30px; color: #fff; font-size: 32px; cursor: pointer; opacity: .7; }}
.lightbox .close:hover {{ opacity: 1; }}
.lightbox .nav {{ position: absolute; top: 50%; transform: translateY(-50%); color: #fff; font-size: 48px; cursor: pointer; opacity: .6; user-select: none; padding: 20px; transition: opacity .15s; }}
.lightbox .nav:hover {{ opacity: 1; }}
.lightbox .nav-prev {{ left: 10px; }}
.lightbox .nav-next {{ right: 10px; }}
.lightbox .counter {{ position: absolute; bottom: 30px; color: #aaa; font-size: 13px; }}
.no-screenshots {{ color: #999; font-style: italic; padding: 12px 0; }}
.tag {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
.tag-priority {{ background: #dfe6e9; color: #2d3436; }}
.tag-browser {{ background: #e8f4fd; color: #0984e3; }}
.error-detail td {{ padding: 4px 20px 10px; }}
.error-box {{ background: #fff3f3; border-left: 3px solid #d63031; border-radius: 4px; padding: 8px 14px; font-size: 13px; }}
.error-summary {{ color: #d63031; font-weight: 600; margin-bottom: 6px; font-family: Consolas, "Courier New", monospace; }}
.error-expand {{ margin-top: 4px; }}
.error-expand summary {{ cursor: pointer; color: #636e72; font-size: 12px; user-select: none; }}
.error-expand summary:hover {{ color: #2d3436; }}
.error-trace {{ margin: 8px 0 0 0; padding: 10px 14px; background: #1e1e1e; color: #d4d4d4;
    border-radius: 6px; font-size: 12px; line-height: 1.5; white-space: pre-wrap;
    word-break: break-all; max-height: 360px; overflow-y: auto; }}
</style>
</head>
<body>

<div class="header">
    <h1>Test Execution Report</h1>
    <div class="meta">Generated: {run_date} {datetime.now().strftime('%H:%M:%S')} {executor_info}</div>
</div>

<div class="summary">
    <div class="summary-card total"><div class="num">{total}</div><div class="label">Total</div></div>
    <div class="summary-card passed"><div class="num">{passed}</div><div class="label">Passed</div></div>
    <div class="summary-card failed"><div class="num">{failed}</div><div class="label">Failed</div></div>
</div>

<div class="container">
    <h2 style="margin: 20px 0 12px; font-size: 18px;">Test Results</h2>
    {test_rows}

    <h2 style="margin: 32px 0 12px; font-size: 18px;">Screenshots</h2>
    <div class="toolbar">
        <button onclick="expandAll()">Expand All</button>
        <button onclick="collapseAll()">Collapse All</button>
        <button onclick="expandFailed()">Failed Only</button>
    </div>
    {screenshot_sections if screenshot_sections else '<p class="no-screenshots">No screenshots captured in this run.</p>'}
</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
    <span class="close">&times;</span>
    <span class="nav nav-prev" id="nav-prev" onclick="event.stopPropagation();prevImage()">&#8249;</span>
    <span class="nav nav-next" id="nav-next" onclick="event.stopPropagation();nextImage()">&#8250;</span>
    <img id="lightbox-img" src="" alt="" loading="lazy" onclick="event.stopPropagation();nextImage()" />
    <div class="caption" id="lightbox-caption"></div>
    <div class="counter" id="lightbox-counter"></div>
</div>

<script>
var caseImages = {images_json};
var currentCase = "";
var currentIndex = 0;
function toggleSection(header) {{
    var content = header.nextElementSibling;
    var icon = header.querySelector('.toggle-icon');
    if (content.style.display === 'none') {{
        content.style.display = 'block';
        icon.textContent = '▼';
    }} else {{
        content.style.display = 'none';
        icon.textContent = '▶';
    }}
}}
function expandAll() {{
    document.querySelectorAll('.section-content').forEach(function(el) {{
        el.style.display = 'block';
        el.parentElement.querySelector('.toggle-icon').textContent = '▼';
    }});
}}
function collapseAll() {{
    document.querySelectorAll('.section-content').forEach(function(el) {{
        el.style.display = 'none';
        el.parentElement.querySelector('.toggle-icon').textContent = '▶';
    }});
}}
function expandFailed() {{
    collapseAll();
    document.querySelectorAll('.failed-section .section-content').forEach(function(el) {{
        el.style.display = 'block';
        el.parentElement.querySelector('.toggle-icon').textContent = '▼';
    }});
}}
function openLightbox(caseKey, index) {{
    currentCase = caseKey;
    currentIndex = index;
    showImage();
    document.getElementById('lightbox').classList.add('active');
}}
function showImage() {{
    var imgs = caseImages[currentCase];
    var img = imgs[currentIndex];
    document.getElementById('lightbox-img').src = img.src;
    document.getElementById('lightbox-caption').textContent = img.caption;
    document.getElementById('lightbox-counter').textContent = (currentIndex + 1) + ' / ' + imgs.length;
    document.getElementById('nav-prev').style.display = currentIndex <= 0 ? 'none' : '';
    document.getElementById('nav-next').style.display = currentIndex >= imgs.length - 1 ? 'none' : '';
}}
function nextImage() {{
    var imgs = caseImages[currentCase];
    if (!imgs || imgs.length === 0 || currentIndex >= imgs.length - 1) return;
    currentIndex++;
    showImage();
}}
function prevImage() {{
    var imgs = caseImages[currentCase];
    if (!imgs || imgs.length === 0 || currentIndex <= 0) return;
    currentIndex--;
    showImage();
}}
function closeLightbox() {{
    document.getElementById('lightbox').classList.remove('active');
}}
document.addEventListener('keydown', function(e) {{
    var lb = document.getElementById('lightbox');
    if (!lb.classList.contains('active')) return;
    if (e.key === 'Escape') closeLightbox();
    else if (e.key === 'ArrowRight') nextImage();
    else if (e.key === 'ArrowLeft') prevImage();
}});
</script>

</body>
</html>"""