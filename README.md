# locust-perf-framework

一个基于 **Python + Locust** 的最小可运行性能测试框架，用于 HTTP API 压测，支持本机高并发和阶梯压力测试。

## 1. 环境要求

- Python 3.9+
- Docker / Docker Compose（用于 Prometheus + Grafana）

## 2. 安装

```bash
git clone https://github.com/PaiPai-Fish829/locust-perf-framework.git
cd locust-perf-framework
python -m venv .venv
source .venv/bin/activate  # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
```

## 项目结构（当前）

```text
locust-perf-framework/
├── tasks/                         # 原子任务层：单接口请求定义（可复用）
│   ├── login_task.py              # POST 登录
│   ├── index_task.py              # GET 首页
│   ├── user_home_task.py          # GET 用户中心
│   ├── cart_task.py               # GET 购物车
│   └── __init__.py
├── scenarios/                     # 场景层：组织业务流程（登录、流程编排等）
│   ├── add_location_flow.py
│   ├── login_scenario.py
│   └── __init__.py
├── utils/                         # 框架工具：参数化、形状策略、数据加载
│   ├── parametrize.py             # 场景层 data 参数化（scenarios 专用）
│   ├── data_loader.py
│   └── configurable_shape.py
├── common/                        # 公共能力：认证、断言、日志、指标导出
│   ├── user_session.py          # 会话：auto 登录 / manual token
│   ├── auth.py                  # 兼容旧 login()，内部转 UserSession
│   ├── assertions.py
│   ├── logger.py
│   ├── metrics.py                 # 暴露 /metrics，供 Prometheus 抓取
│   └── __init__.py
├── shapes/                        # 压测形状策略（LoadTestShape）
│   ├── stage_shape.py             # 阶梯压测：每 30 秒 +10，直到 100
│   ├── stage_hold_shape.py        # 阶梯增长 + 峰值保持策略
│   └── __init__.py
├── config/                        # 配置读取与分发（从根目录 YAML 加载到运行时）
│   ├── settings.py
│   └── __init__.py
├── monitoring/                    # 监控栈配置：Prometheus + Grafana
│   ├── docker-compose.yml
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       │   └── locust-overview.json
│       └── provisioning/
│           ├── datasources/prometheus.yml
│           └── dashboards/dashboard.yml
├── reports/                       # 运行产物目录（CSV 统计、失败、异常等）
├── scripts/                       # 启动入口与运行控制脚本
│   ├── run.py                     # 统一命令入口：load / stress
│   └── __init__.py
├── data/                          # 参数化测试数据（CSV/YAML）
│   └── users.csv
├── locust-config.yaml             # 根配置文件（环境、端口、并发、运行时参数）
├── locustfile.py                  # Locust 入口（用户类与 shape 注册）
├── platform/                      # 管理平台（React + TypeScript + Vite，独立 Web 应用）
│   ├── src/
│   │   ├── components/            # LocustMonitor、GrafanaMonitor、布局
│   │   ├── pages/                 # 监控页 / 配置页
│   │   └── config.ts              # Locust / Grafana 地址配置
│   ├── .env.example
│   └── README.md
├── requirements.txt               # Python 依赖
└── README.md
```

> 说明：`__pycache__/`、`.venv/`、运行时生成的 CSV 文件不属于源码结构，文档中默认省略。

## 3. 运行示例

### 3.1 WebUI 模式（推荐调试）

```bash
python scripts/run.py load
```

- Locust WebUI: http://localhost:8089
- 在 UI 中手工设置用户数和启动压测
- WebUI 端口读取根目录 `locust-config.yaml` 中当前环境的 `locust_web_port`
- 若端口被占用会直接报错，避免同机启动多个 WebUI
- `load` 默认启用自动重载（修改 `.py` 文件后自动重启 Locust 进程）

### 3.2 无头模式（CLI）

```bash
python scripts/run.py stress
```

- 默认带阶梯形状（`StageShape`：每 30 秒 +10，直到 100）
- CSV 输出在 `reports/` 目录

### 3.3 常见参数示例

```bash
# 指定目标地址 + WebUI 端口
python scripts/run.py load --host http://127.0.0.1:8000 --web-port 8090

# 无头压测，覆盖并发和时长
python scripts/run.py stress --users 200 --spawn-rate 20 --run-time 15m

# 启用高级压测 shape（阶梯 + 峰值保持）
python scripts/run.py stress --shape stage_hold --peak-users 200 --peak-hold-time 120

# 透传 Locust 原生参数
python scripts/run.py stress --stop-timeout 30 --only-summary

# 关闭自动重载（单次启动）
python scripts/run.py load --no-reload
```

### 3.4 数据参数化（`utils/parametrize`，场景层负责）

**职责划分**：

| 目录 | 职责 |
|------|------|
| `utils/parametrize.py` | 读 CSV/YAML → `self.data`，在 **scenario** 绑定 |
| `tasks/*_task.py` | 接口内硬编码断言（`response.failure` / `success`） |
| `scenarios/*.py` | 类上 `default_data_file` + `@scenario_cases` + `@task` |
| `tasks/*_task.py` | 路径、统计名、请求头、负载结构、**接口内 assert 断言** |

每条用例 YAML 为 `data: { username, password }`；CSV 为 `data.username,data.password` 列。绑定到 `self.data`。

**YAML** / **CSV** 示例见 `data/` 目录。

**场景示例**（`scenarios/add_location_flow.py` / `scenarios/login_scenario.py`）：

- `AddLocationFlowScenario`：`on_start` 登录 + `@task` 添加收货地址
- `LoginScenario`：仅 `@task` 反复压测登录接口

每个可参数化场景在类上声明 `default_data_file`；管理平台启动时可经 `scenario_data` 按场景覆盖数据文件与 `cycle`/`random` 策略。全局 `locust-config.yaml` 的 `data_file` 仅作未声明场景时的兜底。

**任务**：每个 `tasks/*_task.py` 内含断言；scenario 只编排调用。

**手动 token**：CSV/YAML 的 `data.token` 或环境变量 `LOCUST_MANUAL_TOKEN`；`data.auth_mode=manual` 强制手动模式。

**接口契约**（每个接口一个 `tasks/*_task.py`，契约与任务同文件）：

```python
# tasks/foo_task.py
class FooPayload(TypedDict):
    field_a: str

DEFAULT_PAYLOAD: FooPayload = {"field_a": "default"}

def foo_task(client, data=None):
    client.post(PATH, json=build_payload(DEFAULT_PAYLOAD, data), ...)
```

合并逻辑见 `utils/api_payload.build_payload`；`strict=True` 可拒绝未在 DEFAULT 中声明的字段。

## 4. 启动监控栈

```bash
cd monitoring
docker-compose up -d
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 （admin/admin）

Grafana 预置了 `Locust Overview` 面板：
- Throughput（RPS）
- Error%
- Received KB/sec
- Sent KB/sec

## 5. 指标查看说明

以下指标在 Locust WebUI 和 CSV 中可直接查看：

- Samples
- Average
- Median
- 90% Line / 95% Line / 99% Line
- Min / Max
- Error%
- Throughput（RPS）

带宽相关指标通过 Prometheus + Grafana 查看：

- Received KB/sec
- Sent KB/sec

## 6. 配置外置（根目录配置文件 + 环境管理）

项目配置统一存放在根目录 `locust-config.yaml`，`config/settings.py` 只负责读取与分发。
登录场景的接口路径与默认负载定义在 `tasks/login_task.py`（`DEFAULT_PAYLOAD`），不再放入全局环境配置。
高级压测策略参数统一放在环境配置下的 `test_shape` 段。

支持环境切换：

- 配置优先级：环境变量 > 命令行参数 > YAML 默认值
- 通过配置文件 `active_env` 指定默认环境（如 `dev/staging/prod`）
- 通过环境变量 `LOCUST_ENV` 临时覆盖当前环境
- `LOCUST_SHAPE` 覆盖 shape（`none/stage/stage_hold`）
- `LOCUST_SHAPE_START_USERS / LOCUST_SHAPE_STEP_USERS / LOCUST_SHAPE_STEP_DURATION`
- `LOCUST_SHAPE_PEAK_USERS / LOCUST_SHAPE_PEAK_HOLD_TIME / LOCUST_SHAPE_TOTAL_TIME_LIMIT`

PowerShell 示例：

```powershell
$env:LOCUST_ENV="staging"
python scripts/run.py stress --shape stage_hold --peak-users 200
```

## 7. WebUI 输入框说明

如果在 WebUI 点击 `New` 后，`Number of users`、`Ramp up`、`Run time` 不能输入，通常是因为启用了 `LoadTestShape`。

- 已启用 `LoadTestShape`：这些输入框会被 Locust 禁用（由 shape 控制并发曲线）
- 未启用 `LoadTestShape`：可在 WebUI 手工输入

本项目默认行为：
- `load`（WebUI 调试）默认 `LOCUST_ENABLE_SHAPE=0`，输入框可编辑
- `stress`（无头压测）默认 `LOCUST_ENABLE_SHAPE=1`，走阶梯压测

如需手工切换：

```powershell
$env:LOCUST_ENABLE_SHAPE="1"   # 启用 shape
python scripts/run.py load
```

## 8. 高级压测策略（Stage + Hold）

新增 `shapes/stage_hold_shape.py`，支持：

1. 从 `start_users` 起步；
2. 每 `step_duration` 秒增加 `step_users`，直到 `peak_users`；
3. 峰值保持 `peak_hold_time` 秒；
4. 达到 `total_time_limit`（若 >0）或峰值保持结束后自动停止。

推荐命令：

```bash
python scripts/run.py stress --shape stage_hold
```

## 9. JMeter 痛点对应方案

- **跨线程传递 Token/Cookie**  
  在 `scenarios/add_location_flow.py` 的 `on_start` 经 `UserSession` 登录一次，业务 `@task` 复用 `self.session`。  
  每个虚拟用户实例天然隔离，避免跨线程变量传递复杂度。

- **参数化（CSV/YAML）**  
  通过 `utils/parametrize` 在 scenario 的 `on_start` 从 `data/` 加载并绑定 `self.data`。

- **请求语法直观**  
  Locust 基于 requests 风格，直接支持 `headers`、`params`、`json`、`data`。

## 10. 管理平台（platform/）

`platform/` 是与 Locust 压测脚本**完全独立**的前端 Web 应用，用于统一查看压测监控与（后续）服务器性能面板。

### 10.1 与 lite 分支的区别

| 维度 | main 分支（含 platform/） | lite 分支 |
|------|---------------------------|-----------|
| 定位 | 压测框架 + 可视化管理平台 | 纯 Locust 轻量压测基线 |
| 前端 | React 管理平台，iframe 嵌入 Locust / Grafana | 无独立前端，直接使用 Locust 原生 WebUI |
| 启动 | Python 压测与前端分别启动 | 仅需 `python scripts/run.py` |
| 适用场景 | 需要统一监控入口、后续配置编排 | 本地快速压测、CI 无头执行 |

### 10.2 启动管理平台

```bash
cd platform
npm install
cp .env.example .env   # 按需修改 Locust / Grafana 地址
npm run dev
```

- 管理平台：http://localhost:5173
- 默认首页 `/monitor`，iframe 嵌入 Locust WebUI（需先启动压测）

同时启动 Locust（项目根目录）：

```bash
python scripts/run.py load
```

在 `.env` 中设置 `VITE_LOCUST_URL=http://localhost:8089`（与 Locust WebUI 端口一致）。

### 10.3 生产构建

```bash
cd platform
npm run build
```

详细说明见 [platform/README.md](platform/README.md)。
