# Web/App 功能测试与自动化回归平台

一个面向软件测试实习岗的个人实践项目：**给一个可运行的 Web 系统做「用例 → 执行 → 缺陷 → 回归 → 报告」的完整闭环**，并预留性能、移动端、AI 用例生成三个扩展模块。

> **重要说明（请先看）**
> 1. 仓库里 `mock_server.py` 是一个**零依赖的最小被测服务**，只用来让框架 clone 后能立刻跑通。正式练习请换成你自己的课程设计或开源业务系统，并相应改写 `cases/*.yaml`。
> 2. 仓库中的 12 条用例、Prompt 模板、评审表都是**示例/模板**，**不包含任何「发现 N 个 Bug」「性能提升 X%」之类未实测的数据**。简历里的数字必须按 `ai/review.md`、`perf/README.md` 和本 README 第六节的方法真实跑出来再填，跑不出来就删掉对应表述。
> 3. 这是测试框架，不是业务系统；写进简历时请如实说明被测对象是什么、你负责的是测试侧工作。

---

## 一、它覆盖哪些岗位要求

| 岗位要求 | 仓库里的对应实现 |
| --- | --- |
| Web/App 功能测试、执行用例、提交 Bug | `cases/*.yaml` 等价类 / 边界值 / 异常场景用例，`sql/init.sql` 的 `bug` 表 |
| 跟踪修复进度、回归验证 | Bug 状态 `new → fixed → retest → closed`，`pytest -m regression` 按标签回归 |
| 建立与维护自动化脚本、提升效率 | `pytest + requests` 数据驱动框架、统一请求封装、CI 定时执行 |
| 性能测试 | `perf/` 压测指引 + 慢查询定位方法（需你真实执行） |
| 移动端专项 | `ai/` 之外的扩展位，Android 模拟器 + Appium 冒烟（需你真实执行） |
| Python / MySQL | Python 为主；默认 SQLite 便于零配置运行，设置环境变量即切 MySQL |
| AI 智能化测试工具预研 | `ai/prompt.md` 生成用例 + `ai/review.md` 人工评审与采纳率统计 |

## 二、快速开始（3 步跑通）

```bash
# 1. 安装依赖（Python 3.9+）
pip install -r requirements.txt

# 2. 启动最小被测服务（另开一个终端）
python mock_server.py

# 3. 执行全部用例，结果写入 qa_results.sqlite3
pytest -q

# 只跑冒烟 / 回归标签
pytest -m smoke -q
pytest -m regression -q

# 生成 Allure 报告（需本机装 allure 命令行）
pytest --alluredir=allure-results -q
allure serve allure-results
```

`BASE_URL` 默认是 `http://127.0.0.1:8000`，可用环境变量覆盖指向你自己的被测系统。

### 一键自检（不想敲命令就用这个）

**Windows：直接双击 `verify.bat`**；也可以在 VS Code 里右键 `verify.py` → Run Python File；或命令行 `python verify.py`。

**不需要 pip、不需要安装任何第三方包，任何 Python 3.x 都能跑。** 脚本只用标准库完成：启动 `mock_server.py` → 用 `urllib` 执行 6 条核心接口场景并断言 → 把结果写进项目同一张 `run_result` 表 → 清理产物 → 打印结果。看到 **`RESULT: PASS - everything works`** 就是运行正常，不用开两个终端，也不用手动 `cd`。

如果当前解释器恰好装了 `pytest / requests / PyYAML`，脚本会额外跑完整的 12 条用例，结果显示 `core checks + full 12-case suite`；没装则显示 `SKIPPED`，**但不影响 PASS**。这就避开了「VS Code 选中的是另一个没装 pip 的 Python」这类环境问题。脚本也不调用 `sys.exit()`，调试器不会再弹 `SystemExit` 异常。

> 常见误操作：在别的目录直接执行 `python mock_server.py` 会报 `No such file or directory`；把说明文字（`#` 开头的注释）一起复制进命令行会让 pytest 报 `file or directory not found: #`。用 `verify.bat` 可以完全避开这两个问题。

## 三、目录结构

```
qa-automation/
├── mock_server.py          # 零依赖最小被测服务（仅用于演示）
├── cases/                  # YAML 用例：等价类 / 边界值 / 异常场景
│   ├── login.yaml
│   └── order.yaml
├── common/
│   ├── config.py           # BASE_URL / token / 数据库配置（读环境变量）
│   ├── http_client.py      # requests 封装：统一 header、token、超时
│   └── db.py               # 执行结果落库，SQLite / MySQL 双支持
├── tests/
│   ├── conftest.py         # 加载用例、初始化库、注入 client、按 tags 打标
│   └── test_api.py         # 参数化执行 + 断言 + 结果（含失败）落库
├── sql/
│   ├── init.sql            # MySQL 建表（test_case / bug / run_result）
│   └── init_sqlite.sql     # SQLite 建表
├── ai/
│   ├── prompt.md           # 大模型生成用例的 Prompt 模板
│   └── review.md           # 人工评审记录表（模板，数据待填）
├── perf/README.md          # 压测与慢 SQL 定位的操作指引（模板，数据待填）
├── .github/workflows/ci.yml# push + 每日定时回归，上传报告
├── verify.py               # 一键自检脚本
├── verify.bat              # Windows 双击运行（调用 verify.py）
├── pytest.ini
└── requirements.txt
```

## 四、换成你自己的被测系统

1. 启动你的业务系统，确认有登录、列表查询、表单提交三类接口。
2. 修改 `cases/*.yaml` 里的 `path`、`body`、`expect`，断言要与真实响应一致。
3. `export BASE_URL=http://你的地址`；如果 token 不是 `X-Token` 头，改 `common/http_client.py` 的 header 名。
4. 用例编号、模块、覆盖点保持可追溯，方便后面统计"用例数"和"回归范围"。

## 五、切换到 MySQL（简历写 MySQL 的前提）

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_USER=root
export MYSQL_PASSWORD=你的密码
export MYSQL_DB=qa_automation
# 先在 MySQL 里执行 sql/init.sql 建库建表
pytest -q
```

`common/db.py` 检测到 `MYSQL_HOST` 就会用 PyMySQL 连接，否则用 SQLite。**只有在 MySQL 上真实跑过、且能讲清表结构与慢查询分析，简历里才写 MySQL。**

## 六、简历里每个数字怎么真实得到

| 简历可能写的数字 | 从这里取 |
| --- | --- |
| N 条功能用例 | `cases/*.yaml` 的实际条数（当前示例为 12 条） |
| M 个 Bug 全部闭环 | `bug` 表里 `status='closed'` 的记录，保留状态流转截图 |
| 人工回归 A 分钟 → 自动化 B 分钟 | 手工逐条计时一次；`run_result` 表或 CI 日志里的运行时长一次，注明机器与用例范围 |
| 压测响应时间 / TPS | `perf/README.md` 的 JMeter 记录，必须注明并发数、环境、跑几次取均值 |
| AI 用例采纳率 | `ai/review.md` 的生成条数 / 采纳条数，保留被拒绝样例 |
| 移动端冒烟条数 | Appium 运行日志与报告里的用例 ID |

> 数字先跑出来再写进简历，不要反过来。面试时把 `run_result` 表和 JMeter 报告打开，比任何形容词都有说服力。

## 七、CI 与报告

`.github/workflows/ci.yml` 在 push / PR 和每日定时触发：启动 `mock_server.py` → `pytest -m "smoke or regression"` → 上传 Allure 结果作为 artifact。接入自己的被测系统时，把启动步骤换成你的服务或指向测试环境地址。

## 八、局限与可优化点（面试可主动讲）

- 目前只覆盖接口层，UI 自动化（Selenium / Appium）只留了扩展位，未接入。
- 用例执行前后没有数据工厂，依赖测试数据预置，后续可加 setup/teardown 造数与清理。
- 没有覆盖率度量、没有 mock 外部依赖，回归范围靠标签人工维护。
- AI 生成用例存在幻觉字段与漏测，必须人工评审后才能入库。

完整设计说明、两周计划与面试追问清单见项目旁的 `test_project_plan.md`。

## 九、License

尚未选择。公开发布前请自行添加 LICENSE（个人项目常用 MIT）。
