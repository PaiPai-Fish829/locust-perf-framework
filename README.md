# locust-perf-framework

一个基于 **Python + Locust** 的最小可运行性能测试框架，用于 HTTP API 压测，支持本机高并发和阶梯压力测试。

## 1. 环境要求

- Python 3.9+
- Docker / Docker Compose（用于 Prometheus + Grafana）

## 2. 安装

```bash
git clone <your-repo-url>
cd locust-perf-framework
python -m venv .venv
source .venv/bin/activate  # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. 运行示例

### 3.1 WebUI 模式（推荐调试）

```bash
python scripts/run.py load
```

- Locust WebUI: http://localhost:8089
- 在 UI 中手工设置用户数和启动压测
- WebUI 端口固定读取 `config/settings.py` 中的 `LOCUST_WEB_PORT`（默认 `8089`）
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

# 透传 Locust 原生参数
python scripts/run.py stress --stop-timeout 30 --only-summary

# 关闭自动重载（单次启动）
python scripts/run.py load --no-reload
```

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

## 6. 配置外置（环境变量）

可通过环境变量覆盖默认配置（见 `config/settings.py`）：

- `LOCUST_HOST`（默认 `http://192.168.47.129:80`）
- `LOCUST_USERS`
- `LOCUST_SPAWN_RATE`
- `LOCUST_RUN_TIME`
- `LOCUST_WEB_PORT`（WebUI 端口，默认 `8089`）
- `LOCUST_WEB_RELOAD`（WebUI 自动重载，默认 `true`）
- `LOCUST_ENABLE_SHAPE`（`0/1`，默认 `load` 子命令 `0`，`stress` 子命令 `1`）
- `LOGIN_PATH`
- `LOGIN_USERNAME`
- `LOGIN_PASSWORD`
- `DATA_FILE`（参数化数据文件，支持 `.csv/.json`）

示例：

Linux / Mac:

```bash
export LOCUST_HOST="http://192.168.47.129:80"
export DATA_FILE="./testdata/login_users.csv"
python scripts/run.py load
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

## 8. JMeter 痛点对应方案

- **跨线程传递 Token/Cookie**  
  在 `scenarios/login_scenario.py` 的 `on_start` 中登录，并把 token 存到 `self.token`。  
  每个虚拟用户实例天然隔离，避免跨线程变量传递复杂度。

- **参数化（CSV/JSON）**  
  通过 `common/data_loader.py` 加载 CSV/JSON，在 `tasks/login_task.py` 按用户循环取参。

- **请求语法直观**  
  Locust 基于 requests 风格，直接支持 `headers`、`params`、`json`、`data`。
