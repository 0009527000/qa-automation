# Web/App 功能测试与自动化回归平台

一个面向软件测试实习岗的个人实践项目：**给一个可运行的 Web 系统做「用例 → 执行 → 缺陷 → 回归 → 报告」的完整闭环**，并预留性能、移动端、AI 用例生成三个扩展模块。

> **重要说明（请先看）**
> 1. 仓库里 `mock_server.py` 是一个**零依赖的最小被测服务**，只用来让框架 clone 后能立刻跑通。正式练习请换成你自己的课程设计或开源业务系统，并相应改写 `cases/*.yaml`。
> 2. 仓库中的 12 条用例、Prompt 模板、评审表都是**示例/模板**，**不包含任何「发现 N 个 Bug」「性能提升 X%」之类未实测的数据**。简历里的数字必须按 `ai/review.md`、`perf/README.md` 和本 README 第八节的方法真实跑出来再填，跑不出来就删掉对应表述。
> 3. 这是测试框架，不是业务系统；写进简历时请如实说明被测对象是什么、你负责的是测试侧工作。

---

## 一、它覆盖哪些岗位要求

| 岗位要求 | 仓库里的对应实现 |
| --- | --- |
| Web/App 功能测试、执行用例、提交 Bug | `cases/*.yaml` 等价类 / 边界值 / 异常场景用例；`buglog.py` 缺陷台账 |
| 跟踪修复进度、回归验证 | 缺陷状态 `open → fixed → closed` 带时间戳；`runner.py --tag regression` 回归 |
| 建立与维护自动化脚本、提升效率 | 数据驱动（YAML 用例）+ 统一请求封装 + 一键执行 + CI 定时回归 |
| 性能测试 | `perf/` 压测指引 + 慢查询定位方法（需你真实执行） |
| 移动端专项 | 扩展位，Android 模拟器 + Appium 冒烟（需你真实执行） |
| Python / MySQL | Python 为主；默认 SQLite 零配置，设置环境变量即切 MySQL |
| AI 智能化测试工具预研 | `ai/prompt.md` 生成用例 + `ai/review.md` 人工评审与采纳率统计 |

## 二、三种运行方式（按你的环境挑一个）

### 方式 A：零依赖直接跑（推荐，什么都不用装）

```bash
python runner.py                # 跑全部 12 条用例
python runner.py --tag smoke    # 只跑冒烟
python runner.py --tag regression
```

**不需要 pip install，任何 Python 3.x 都能跑**：用例解析用自带的极简 YAML 解析器（`common/miniyaml.py`），HTTP 请求用标准库 `urllib`，结果写 SQLite。脚本会自动拉起 `mock_server.py`（已在运行就直接复用），跑完自动关掉。

Windows 也可以直接双击 `verify.bat`（= `python verify.py`）。

### 方式 B：pytest（想用成熟框架 / Allure 报告时）

```bash
pip install -r requirements.txt
python mock_server.py      # 另开一个终端，保持运行
pytest -q                  # 12 passed
pytest -m smoke -q         # 按 YAML 里的 tags 筛选
pytest --alluredir=allure-results -q && allure serve allure-results
```

### 方式 C：VS Code 里一键运行

用 VS Code 打开 `qa-automation` 目录，按 **F5**，在左上角下拉里选：

| 配置 | 作用 |
| --- | --- |
| ① 运行全部用例（推荐） | 执行 `runner.py`，终端直接看逐条结果 |
| ② 只跑冒烟用例 | `runner.py --tag smoke` |
| ③ 一键自检 | `verify.py`：跑用例 + 打印数据库历史统计 |
| ④ 查看执行统计 | `report.py --md`：历史通过率、趋势、失败清单 |

也可以 `Ctrl+Shift+B` 直接跑默认任务（`.vscode/tasks.json` 已配好 5 个任务）。

> 注意：VS Code 用的解释器可能和你装依赖的解释器不是同一个。方式 A 只依赖标准库，所以换哪个解释器都能跑；方式 B 需要在该解释器里装过 `requirements.txt`。

## 三、跑完你能看到什么

一次执行会产出四层结果，都是可直接拿去写周报或面试展示的：

**1. 终端逐条结果**

```
结果       用例             状态码    耗时       标题
[PASS]   TC_LOGIN_001   200    12ms     正确账号密码登录
[PASS]   TC_ORDER_004   401    3ms      未登录提交订单
...
用例 12 条：通过 12，失败 0，通过率 100.0%
耗时：平均 9.3ms，P95 22ms，最长 24ms
RESULT: PASS - 12/12 passed
```

**2. 数据库 `run_result` 表**（`qa_results.sqlite3`，或用 MySQL）

每条用例每次执行一行：`case_id / status / cost_ms / http_code / message / run_at / batch`。失败也记，`message` 里存完整断言信息，所以通过率不会被"只统计成功的用例"美化。`batch` 是批次号，用来精确统计「某一轮执行」。

**3. Markdown 报告**

- `reports/run_report.md`：本次执行的逐条明细（跑完自动生成）
- `reports/report.md`：历史汇总，`python report.py --md` 生成——累计执行次数、通过率、P95 耗时、按模块统计、近 7 天趋势、最近失败清单

**4. 缺陷台账**

`buglog.py` 把「发现 → 修复 → 回归关闭」写成带时间戳的记录，是"Bug 闭环"唯一的可查证据（见第五节）。

## 四、目录结构

```
qa-automation/
├── runner.py               # 零依赖用例执行器（读 YAML → 请求 → 断言 → 落库 → 报告）
├── verify.py               # 一键自检：执行 + 数据库历史统计
├── report.py               # 历史数据统计报告（终端 / Markdown）
├── buglog.py               # 缺陷台账：登记 / 修复 / 关闭 / 列表 / 统计
├── mock_server.py          # 零依赖最小被测服务（仅用于演示）
├── cases/                  # YAML 用例：等价类 / 边界值 / 异常场景
│   ├── login.yaml
│   └── order.yaml
├── common/
│   ├── config.py           # BASE_URL / token / 数据库配置（读环境变量）
│   ├── cases.py            # 用例加载（优先 PyYAML，缺失时用 miniyaml）
│   ├── miniyaml.py         # 极简 YAML 解析器，让用例在无依赖环境也能跑
│   ├── http_client.py      # pytest 通道的 requests 封装
│   └── db.py               # 建表 / 迁移 / 结果与缺陷落库，SQLite / MySQL 双支持
├── tests/
│   ├── conftest.py         # 加载用例、初始化库、注入 client、按 tags 打标
│   └── test_api.py         # pytest 参数化执行 + 断言 + 结果（含失败）落库
├── sql/                    # 建表脚本（SQLite / MySQL）
├── ai/                     # 大模型生成用例的 Prompt 与人工评审表
├── perf/README.md          # 压测与慢 SQL 定位指引
├── .vscode/                # F5 运行配置与任务
├── .github/workflows/ci.yml# push + 每日定时回归，上传报告
├── verify.bat              # Windows 双击自检
├── pytest.ini
└── requirements.txt
```

## 五、缺陷台账怎么用

```bash
# 1. 发现 bug，登记（关联到具体用例，级别 P0-P4）
python buglog.py record TC_ORDER_002 P2 "数量为 0 时返回 500，预期 400 并提示数量非法"

# 2. 研发改完 → 待回归
python buglog.py fix BUG-0001

# 3. 回归通过 → 闭环（写入关闭时间）
python buglog.py close BUG-0001

# 4. 查看与统计
python buglog.py list
python buglog.py stats
```

`stats` 会给出缺陷总数、各状态数量、关闭率、平均修复时长（从登记到回归关闭）和按级别分布。这些数字就是简历里「N 个 Bug 全部闭环」的依据；没有台账，这句话在面试时经不起追问。

## 六、换成你自己的被测系统

1. 启动你的业务系统，确认有登录、列表查询、表单提交三类接口。
2. 修改 `cases/*.yaml` 里的 `path`、`body`、`expect`，断言要与真实响应一致。
3. `export BASE_URL=http://你的地址`（Windows `set BASE_URL=...`）；如果 token 不是 `X-Token` 头，改 `runner.py` 的 `_request()` 和 `common/http_client.py`。
4. 用例编号、模块、覆盖点保持可追溯，方便后面统计"用例数"和"回归范围"。

## 七、切换到 MySQL（简历写 MySQL 的前提）

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_USER=root
export MYSQL_PASSWORD=你的密码
export MYSQL_DB=qa_automation
# 先在 MySQL 里执行 sql/init.sql 建库建表
python runner.py
```

`common/db.py` 检测到 `MYSQL_HOST` 就会用 PyMySQL 连接，否则用 SQLite。SQL 里的参数占位符用 `{p}` 统一表示，由 `db.query()` 自动适配 `?` 与 `%s`。**只有在 MySQL 上真实跑过、且能讲清表结构与慢查询分析，简历里才写 MySQL。**

## 八、简历里每个数字怎么真实得到

| 简历可能写的数字 | 从这里取 |
| --- | --- |
| N 条功能用例 | `python runner.py --tag regression` 的用例数，或 `test_case` 表条数 |
| M 个 Bug 全部闭环 | `buglog.py stats` 的总数与关闭率，保留状态流转记录 |
| 回归耗时 A 分钟 → B 分钟 | 手工逐条计时一次；自动化取 `report.py` 里的"本次执行总耗时"，注明机器与用例范围 |
| 平均 / P95 响应时间 | `report.py` 的耗时统计（接口层，不是压测数据，别混用） |
| 压测响应时间 / TPS | `perf/README.md` 的 JMeter 记录，注明并发数、环境、跑几次取均值 |
| AI 用例采纳率 | `ai/review.md` 的生成条数 / 采纳条数，保留被拒绝样例 |
| 移动端冒烟条数 | Appium 运行日志与报告里的用例 ID |

> 数字先跑出来再写进简历，不要反过来。面试时把 `reports/report.md`、`run_result` 表和 JMeter 报告打开，比任何形容词都有说服力。

## 九、CI 与报告

`.github/workflows/ci.yml` 在 push / PR 和每日定时触发：启动 `mock_server.py` → `pytest -m "smoke or regression"` → 生成 Markdown 统计 → 上传 `allure-results` 与 `reports` 作为 artifact。接入自己的被测系统时，把启动步骤换成你的服务或指向测试环境地址。

## 十、局限与可优化点（面试可主动讲）

- 目前只覆盖接口层，UI 自动化（Selenium / Appium）只留了扩展位，未接入。
- 用例执行前后没有数据工厂，依赖测试数据预置，后续可加 setup/teardown 造数与清理。
- 没有覆盖率度量、没有 mock 外部依赖，回归范围靠标签人工维护。
- AI 生成用例存在幻觉字段与漏测，必须人工评审后才能入库。
- 结果表没有归档与清理策略，长期跑需要按 `batch` 定期归档。

完整设计说明、两周计划与面试追问清单见项目旁的 `test_project_plan.md`。

## 十一、License

尚未选择。公开发布前请自行添加 LICENSE（个人项目常用 MIT）。
