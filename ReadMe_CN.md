# UIAutoTest — Playwright Web UI 自动化测试框架

## 环境要求

- Python 3.12+
- Windows / macOS / Linux

---

## 快速开始

### 1. 安装依赖

```powershell
cd UIAutoTest
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\playwright install chromium
```

> 或直接运行 `python run_tests.py`，脚本会自动完成以上全部步骤。

### 2. 运行测试

```powershell
# 按优先级运行
python run_tests.py                       # 默认全部（见 run_tests.py 中 DEFAULT_PRIORITY）
python run_tests.py --priority P0         # 只跑 P0
python run_tests.py --all                 # 全部优先级

# 按标签运行
python run_tests.py --tags smoke,login

# 直接使用 pytest（高级用法）
.\venv\Scripts\pytest test_case/ -v -m p0
.\venv\Scripts\pytest test_case/ -v -m "p0 and smoke"
```

### 3. 查看结果

| 产物 | 路径 |
|------|------|
| HTML 报告 | `reports/YY-MM-DD/TestReport_YY-MM-DD_HH-MM-SS.html` |
| 步骤截图 | `reports/YY-MM-DD/screenshots/{test_id}/{HH-MM-SS}/` |
| 失败截图 | 同一路径，目录名重命名为 `{test_id} [FAILED]/` |
| 运行日志 | `reports/logs/log_YY-MM-DD.log` |

---

## 目录结构

```
UIAutoTest/
├── record.py                      # 录制浏览器操作 → 原生 pytest 文件
├── run_tests.py                   # 一键安装 + 运行（可编辑默认过滤条件）
├── pytest.ini                     # Pytest 标记与发现配置
├── requirements.txt               # 依赖包列表
│
├── config/
│   └── settings.py                # 浏览器、视口、超时等全局配置
│
├── test_case/
│   ├── conftest.py                # 浏览器 Fixture + 失败截图 + 报告生成
│   └── YY-MM-DD/
│       └── REC_26-10-07_11-03-23_test.py   # 自动生成的测试（原生 pytest）
├── utils/
│   ├── screenshot.py              # 截图管理
│   ├── report_generator.py        # 增强版 HTML 报告生成器
│   ├── logger.py                  # 日志
│   └── converter.py               # Codegen .py → pytest .py 转换器
├── recorder/
│   └── YY-MM-DD/
│       └── REC_26-10-10_09-10-28.py    # 原始录制（可回放 + 可再生成）
│
└── reports/                       # 输出（运行时自动生成）
    ├── YY-MM-DD/
    │   ├── TestReport_YY-MM-DD_HH-MM-SS.html
    │   └── screenshots/
    │       └── {test_id}/
    │           └── HH-MM-SS/   （失败则目录名加 [FAILED] 后缀）
    └── logs/
        └── log_YY-MM-DD.log
```

---

## 录制生成测试用例

在浏览器中操作，自动生成带断言的原生 pytest 文件。

### 录制新用例

```powershell
python record.py                                    # 在 Demo 页面上录制
python record.py https://example.com                # 自定义 URL
python record.py --name "登录" https://example.com   # 自定义用例名
python record.py --priority P1 --tags smoke,login https://example.com
python record.py --browser edge https://example.com   # 用 Edge 录制
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `URL` | Demo 页面 | 目标网站地址 |
| `--name` | 自动（时间戳） | 测试用例名称 |
| `--priority` | `P2` | 优先级：`P0`、`P1`、`P2`、`P3` |
| `--tags` | 无 | 逗号分隔：`smoke,login,regression` |
| `--browser` | `chromium` | `chromium`、`edge` |

浏览器打开 → 执行操作 → 关闭浏览器。工具会自动：

1. 保存原始录制到 `recorder/YY-MM-DD/REC_YY-MM-DD_HH-MM-SS.py`（包含 `page.pause()` 用于回放）
2. 转换为 `test_case/YY-MM-DD/REC_YY-MM-DD_HH-MM-SS_test.py`（原生 pytest，含断言）

### 生成的测试文件结构

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

    # Step 1: 打开 https://example.com
    page.goto('https://example.com')
    page.wait_for_load_state("domcontentloaded")
    screenshot('navigate_1')
    # expect(page).to_have_title("...")

    # Step 2: 输入 'hello' 到 #search
    page.locator('#search').fill('hello')
    expect(page.locator('#search')).to_have_value('hello')   # ← 自动断言

    # Step 3: 勾选 #agree
    page.locator('#agree').check()
    screenshot('check_3')
    expect(page.locator('#agree')).to_be_checked()           # ← 自动断言

    # --------------------------------------------------
    # TODO: add custom verification points below
    # --------------------------------------------------
```

> 在 `TODO` 区域添加自定义 `expect()` 断言。将 `# expect(page).to_have_title("...")` / `# expect(page).to_have_url("...")` 中的 `"..."` 替换为实际期望值并取消注释即可。

### 重新生成测试用例

每个录制文件底部有一个再生代码块，取消注释后运行：

```powershell
.\venv\Scripts\python.exe recorder\YY-MM-DD\REC_26-10-10_09-10-28.py

会在 `test_case/YY-MM-DD/` 下生成 `REC_26-10-10_09-10-28_test_001.py`、`_test_002.py`……每次运行序号自动递增，不覆盖已有文件。适用于同一录制需要多个场景变体时。

### 手动重新转换

```powershell
.\venv\Scripts\python.exe -B utils\converter.py recorder\YY-MM-DD\REC_26-10-10.py "测试名" --priority P1 --tags smoke
```

| 参数 | 说明 |
|------|------|
| `文件名.py` | 录制的 .py 文件路径 |
| `"测试名"` | 测试用例名称 |
| `--priority` | 优先级：`P0` ~ `P3` |
| `--tags` | 逗号分隔的标签 |

---

## 断言策略

自动生成的断言**紧跟每个操作**，放在操作代码之后。策略如下：

| 操作 | 自动断言 | 类型 |
|------|----------|------|
| `page.locator(sel).fill('文本')` | `expect(page.locator(sel)).to_have_value('文本')` | **可执行** — 验证输入成功 |
| `page.locator(sel).check()` | `expect(page.locator(sel)).to_be_checked()` | **可执行** — 验证已勾选 |
| `page.locator(sel).uncheck()` | `expect(page.locator(sel)).not_to_be_checked()` | **可执行** — 验证已取消 |
| `page.locator(sel).select_option('v')` | `expect(page.locator(sel)).to_have_value('v')` | **可执行** — 验证选中项 |
| `page.goto(url)` | `# expect(page).to_have_title("...")` | **提示** — 填入实际页面标题 |
| `page.locator(sel).click()` | `# expect(page).to_have_url("...")` | **提示** — 填入点击后的实际 URL |
| `page.locator(sel).dblclick()` | `# expect(page).to_have_url("...")` | **提示** |
| `page.locator(sel).hover()` | `# TODO: verify hover result` | **提示** |
| `drag_to(目标)` | `# TODO: verify drag & drop result` | **提示** |
| `press(按键)` | `# TODO: verify result after key press` | **提示** |

**设计思路**：结果可确定的操作（输入、勾选、下拉）直接生成能跑的断言；结果不确定的操作（点击跳转、悬停、拖拽）生成注释提示，用户填入实际期望值后取消注释即可生效。

---

## 截图策略

测试函数内可用 `screenshot('name')` 快捷截图。自动截图覆盖以下动作：

| 操作 | 截图 | 原因 |
|------|:--:|------|
| `page.goto()` | ✅ | 页面加载完成 |
| `.click()` | ✅ | 页面状态变化 |
| `.dblclick()` | ✅ | 双击后结果 |
| `.check()` / `.uncheck()` | ✅ | 勾选状态变化 |
| `.select_option()` | ✅ | 下拉切换 |
| `.hover()` | ✅ | 悬停触发的 UI |
| `.drag_to()` | ✅ | 拖拽结果 |
| `.fill()` / `.press()` | — | 纯输入，无视觉变化 |

失败用例目录自动加 `[FAILED]` 后缀。

---

## 默认测试过滤

编辑 `run_tests.py` 顶部的配置区，设置默认过滤条件，每次运行无需重复输入参数：

```python
DEFAULT_PRIORITY = ""         # 默认跑全部优先级
DEFAULT_TAGS = ""              # 默认不过滤标签
# DEFAULT_TAGS = "smoke"        # 默认只跑冒烟测试
DEFAULT_DIR = ""              # "26-10-10"，"" →  run all folders
```

优先级体系：

| 标记 | 含义 |
|------|------|
| `@pytest.mark.p0` | 关键 — 发版前必须通过 |
| `@pytest.mark.p1` | 高 — 阻塞性问题 |
| `@pytest.mark.p2` | 中 — 常规回归（录制默认） |
| `@pytest.mark.p3` | 低 — 非阻塞 |

---

## 手动编写测试用例

在 `test_case/` 下创建 `.py` 文件，使用标准 pytest 标记：

```python
import pytest
from playwright.sync_api import Page, expect
from utils.screenshot import screenshot_manager

@pytest.mark.p0
@pytest.mark.smoke
def test_my_login(page: Page):
    """验证登录功能"""
    _ss = "my_login"
    def screenshot(name):
        screenshot_manager.take_step_screenshot(page, name, test_name=_ss)

    page.goto('https://example.com/login')
    page.wait_for_load_state("domcontentloaded")
    screenshot('打开登录页')

    page.locator('#username').fill('admin')
    expect(page.locator('#username')).to_have_value('admin')

    page.locator('#password').fill('123456')

    page.locator('#submit').click()
    screenshot('点击提交')

    expect(page.locator('.welcome')).to_be_visible()
    expect(page.locator('.welcome')).to_contain_text('Welcome, admin')
```

> 遵循自动生成文件的模式：定义 `_ss` 截图路径、`screenshot(name)` 快捷方法、操作后紧跟 `expect()` 断言。

---

## 读取控件文本

用 Playwright 原生方法即可，无需封装：

```python
# 获取可见文本（人在页面上看到的文字）
text = page.locator("#result").inner_text()

# 获取完整文本内容（含隐藏文本，更底层）
text = page.locator("#result").text_content()

# 获取输入框里的值
value = page.locator("#username").input_value()
```

### 常用断言模式

```python
# 校验包含某段文字
expect(page.locator("#result")).to_contain_text("成功")

# 校验完全相等
expect(page.locator("#result")).to_have_text("登录成功")

# 先取值再判断数量
count = page.locator(".item").count()
assert count >= 3, f"期望 ≥ 3 个，实际 {count} 个"

# 打印捕获到的文本，方便调试
text = page.locator("#price").inner_text()
print(f"捕获文本: {text}")
```

> 在自动生成文件的 `TODO` 区域添加即可。不需要 JSON 里的 `get_text` / `expected` 封装，直接 Python + Playwright 原生写法。

---

## 配置修改

编辑 `config/settings.py`：

```python
BROWSER = "chromium"          # 浏览器：chromium / edge
HEADLESS = True               # True = 无头模式 / False = 可见
VIEWPORT = {"width": 1920, "height": 1080}
LOG_LEVEL = "INFO"            # DEBUG / INFO / WARNING / ERROR
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

## HTML 报告功能

- **按文件分组** — 每个测试文件独立区域展示
- **折叠展开** — 点击测试用例可折叠/展开
- **截图内嵌** — 步骤截图以缩略图显示，点击查看原图
- **默认折叠截图** — 保持报告紧凑
- **执行人与时间戳** — 显示执行者和生成时间

---

## 常用命令速查

```powershell
cd d:\Code\UIAutoTest

# 安装 + 运行
python run_tests.py

# 按优先级运行
python run_tests.py --priority P0
python run_tests.py --priority P1 --tags smoke

# 全量运行
python run_tests.py --all

# 录制测试用例
python record.py
python record.py --name "登录" --priority P1 https://example.com

# 回放录制（浏览器保持打开）
.\venv\Scripts\python.exe recorder\YY-MM-DD\REC_26-10-10.py

# 手动重新转换
.\venv\Scripts\python.exe -B utils\converter.py recorder\YY-MM-DD\REC_26-10-10.py "名称" --priority P2

# 直接使用 pytest（高级）
.\venv\Scripts\pytest test_case/ -v -m p0
.\venv\Scripts\pytest test_case/ -v -k "login"
```