# Locust 压测监控平台

基于 **React + TypeScript + Vite + Ant Design + ECharts** 的独立 Web 应用，通过 Locust Web UI 同源 API 展示压测仪表盘，并提供测试任务配置（场景 / 策略 / 启动压测）。

> 更完整的待办与接入状态见同目录 [`pending-apis.txt`](./pending-apis.txt)。

## 快速开始

### 1. 启动 Locust（必须先运行）

在项目根目录：

```bash
python scripts/run.py load
```

默认 Locust Web UI：`http://localhost:8089`

### 2. 启动前端

```bash
cd platform
npm install
npm run dev
```

默认开发地址：http://localhost:5173

开发模式下，前端将 `/locust-api/*` 代理到 `VITE_LOCUST_URL`（见 `vite.config.ts`），避免跨域。

## 环境变量

复制并按需修改：

```bash
cp .env.example .env
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_LOCUST_URL` | Locust 服务地址；开发时代理目标 | `http://localhost:8089` |
| `VITE_LOCUST_API_BASE` | 前端请求 API 的基址前缀 | 开发：`/locust-api`；生产：同 `VITE_LOCUST_URL` |
| `VITE_GRAFANA_URL` | Grafana 地址（预留） | `http://localhost:3000` |

配置读取逻辑见 `src/config.ts`。修改 `.env` 后需重启 `npm run dev`。

## API 架构说明

```text
浏览器 (platform)
    │
    ├─ fetch(`${locustApiBase}/stats/requests`)     … Locust 原生路由
    ├─ fetch(`${locustApiBase}/platform/scenarios`) … 本项目扩展（common/platform_api.py）
    │
    ▼
开发: Vite proxy  /locust-api  →  http://localhost:8089
生产: 直连         VITE_LOCUST_URL（需与 Locust 同域或配置 CORS）
```

- **前端封装**：`src/api/locust.ts`（Locust 原生）、`src/api/platform.ts`（平台扩展）
- **后端实现**：Locust 内置 `locust/web.py` + 本仓库 `common/platform_api.py`（挂到 Locust Flask app）

---

## 一、Locust 原生接口（后端）

以下路由由 Locust 2.x Web UI 提供，压测进程启动后可用。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stats/requests` | 实时统计（各接口行 + Aggregated、errors、state、user_count、total_rps 等） |
| GET | `/exceptions` | 异常列表 |
| GET | `/logs` | Master / Worker 日志 |
| POST | `/swarm` | 启动压测（`application/x-www-form-urlencoded`） |
| GET | `/stop` | 停止压测 |
| GET | `/stats/reset` | 重置 Locust 服务端统计（前端已封装，UI 暂未使用） |
| GET | `/stats/requests/csv` | 导出请求统计 CSV |
| GET | `/stats/failures/csv` | 导出失败明细 CSV |
| GET | `/exceptions/csv` | 导出异常 CSV |
| GET | `/stats/report` | HTML 报告（`?download=1` 为下载） |
| GET | `/stats/requests_full_history/csv` | 完整历史 CSV（需启动时启用 `stats_history_enabled`） |
| GET | `/tasks` | 任务执行比例（未接入 UI） |
| GET | `/worker-count` | Worker 数量（未接入 UI） |

### POST `/swarm`（Locust 原生，表单）

常用字段：`user_count`、`spawn_rate`、`host`、`run_time`、`shape_class`、`user_classes[]`。

本平台**测试任务页默认使用** `POST /platform/swarm`（JSON），功能更完整；`startSwarm()` 仍保留于 `locust.ts` 供兼容。

---

## 二、平台扩展接口（后端）

由 `common/platform_api.py` 注册到 Locust Web UI 的 Flask 应用（`locustfile` 导入 `common.platform_api` 后生效）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/platform/scenarios` | 扫描 `scenarios/` 下 HttpUser 子类 |
| GET | `/platform/shapes` | 扫描 `shapes/` 下 LoadTestShape（含 `param_schema`） |
| GET | `/platform/stats/history` | 返回 `runner.stats.history`（服务端 5s 采样历史） |
| POST | `/platform/swarm` | 启动压测（`application/json` 或 form） |

### GET `/platform/scenarios`

响应示例：

```json
{
  "scenarios": [
    {
      "id": "login_scenario",
      "filename": "login_scenario.py",
      "class_name": "LoginScenario",
      "description": "..."
    }
  ]
}
```

### GET `/platform/shapes`

响应示例：

```json
{
  "shapes": [
    {
      "id": "stage_shape",
      "filename": "stage_shape.py",
      "class_name": "StageShape",
      "description": "...",
      "params": [
        { "name": "start_users", "label": "起始用户数", "default": 10, "unit": "", "min": 1 }
      ]
    }
  ]
}
```

### POST `/platform/swarm`

请求体（JSON）示例：

```json
{
  "shape_class": "StageShape",
  "shape_params": { "start_users": 10, "step_users": 10 },
  "user_classes": ["LoginScenario"],
  "host": "http://192.168.1.1:80",
  "run_time": "5m",
  "user_count": 100,
  "spawn_rate": 10
}
```

说明：

- 指定 `shape_class` 时由 Shape 控制并发，通常不传 `user_count` / `spawn_rate`。
- 未指定 Shape 时需传 `user_count`、`spawn_rate`。
- `shape_params` 在启动前应用到 `ConfigurableShape.apply_params()`。

响应：`{ "success": boolean, "message": string, "host"?: string }`

### GET `/platform/stats/history`

响应：`{ "history": [ ... ] }`，结构与 Locust 内部 `stats.history` 一致（含 `current_rps`、`time` 等）。

> **说明**：仪表盘折线图主路径为前端轮询 `GET /stats/requests` 并累积 `total_rps`（与 Locust 原生 WebUI 实时图表一致）；本接口可作为备用数据源。

---

## 三、前端 API 封装

### `src/api/locust.ts`

| 函数 | 方法 | 后端路径 | 使用位置 |
|------|------|----------|----------|
| `fetchStats()` | GET | `/stats/requests` | `useLocustStats`（2s 轮询）、仪表盘 KPI / 表格 |
| `fetchExceptions()` | GET | `/exceptions` | `useLocustStats` |
| `fetchLogs()` | GET | `/logs` | `useLocustStats`（底部日志预览） |
| `stopTest()` | GET | `/stop` | 顶栏「停止运行」 |
| `resetStats()` | GET | `/stats/reset` | 已封装，UI 未使用 |
| `startSwarm()` | POST | `/swarm` | 兼容保留，任务页用 platform 版 |
| `fetchStatsHistory()` | GET | `/platform/stats/history` | 已封装，当前图表未依赖 |
| `exportUrl(path)` | — | 拼完整 URL | 导出 CSV / HTML（新窗口打开） |
| `getAggregatedStat()` | — | — | 从 `fetchStats` 结果取 Aggregated 行 |
| `isRunning()` / `stateLabel()` | — | — | 状态展示与采样控制 |

### `src/api/platform.ts`

| 函数 | 方法 | 后端路径 | 使用位置 |
|------|------|----------|----------|
| `fetchScenarios()` | GET | `/platform/scenarios` | `TestTaskPanel` 场景列表 |
| `fetchShapes()` | GET | `/platform/shapes` | `TestTaskPanel` 策略列表 |
| `startPlatformSwarm()` | POST | `/platform/swarm` | `TestTaskPanel`「立即执行」 |

---

## 四、页面与数据流

| 菜单 | 组件 | 主要数据来源 |
|------|------|----------------|
| 测试任务 | `TestTaskPanel` | `/platform/scenarios`、`/platform/shapes`、`POST /platform/swarm` |
| 仪表盘 | `DashboardView` | `useLocustStats` → `/stats/requests` 等 |
| 测试报告 / 脚本库 / 策略库 | 占位页 | — |

### 仪表盘 `useLocustStats`（`src/hooks/useLocustStats.ts`）

- 在 `DashboardPage` 级挂载，**切换导航不卸载**，图表历史保留。
- `spawning` / `running` 时每 2s 追加采样点；停止后暂停追加，保留上次曲线。
- 图表字段：`total_rps`、`total_fail_per_sec`、`user_count`、P50/P95（与 Locust 原生实时图一致）。
- `clearChartHistory()`：仅清空前端会话曲线，不调用 `/stats/reset`。

### 仅前端实现（无独立后端路由）

| 能力 | 实现 |
|------|------|
| 折线图 PNG | ECharts `getDataURL`（`ChartPanel`） |
| 表格 / 聚合报告 PNG | `html2canvas`（`exportDom.ts`） |
| 图表时序 CSV | 客户端 `history` 导出 |
| 多图联动 | `echarts.connect` + 虚线纵轴 |

---

## 五、导出能力汇总

| 入口 | 格式 | 来源 |
|------|------|------|
| 底部「导出数据」→ 图表时序 CSV | CSV | 前端累积 |
| 底部「导出数据」→ 全部图表 PNG | PNG | ECharts |
| 各图表右上角下载图标 | PNG | ECharts |
| 详细 API 统计 → 下载 PNG | PNG | html2canvas |
| 聚合报告 → 下载 PNG | PNG | html2canvas |
| 导出数据 → 请求/失败/异常 CSV、HTML 报告 | CSV / HTML | Locust 原生路径 |

---

## 生产构建

```bash
npm run build
npm run preview
```

产物目录：`platform/dist/`。

生产环境若前端与 Locust **不同域**，需：

- 设置 `VITE_LOCUST_API_BASE` 为 Locust 可访问的完整 origin，且 Locust 开启 CORS；或
- 由 Nginx 等将前端与 `/stats`、`/platform` 反代到同一 Locust 服务。

---

## 目录结构

```text
platform/
├── src/
│   ├── api/
│   │   ├── locust.ts           # Locust 原生 API 封装
│   │   └── platform.ts         # /platform/* 扩展 API
│   ├── components/
│   │   ├── ChartPanel.tsx      # 单图（下载/重置图标）
│   │   ├── DashboardView.tsx   # 仪表盘
│   │   └── TestTaskPanel.tsx   # 测试任务
│   ├── hooks/
│   │   └── useLocustStats.ts   # 轮询与图表历史（页面级）
│   ├── pages/
│   │   └── DashboardPage.tsx   # 主导航 + Tab 保活
│   ├── utils/
│   │   ├── dashboardCharts.ts  # ECharts 配置
│   │   └── exportDom.ts        # DOM 截图导出
│   ├── config.ts               # locustApiBase / 环境变量
│   ├── App.tsx
│   └── main.tsx
├── pending-apis.txt            # 接口接入清单（勾选状态）
├── .env.example
├── vite.config.ts              # /locust-api 开发代理
└── package.json
```

---

## 相关文档

- 项目根目录 `README.md`：Locust 框架整体说明
- [`pending-apis.txt`](./pending-apis.txt)：待接入接口与优先级
- Locust 官方 Web API：以当前安装的 Locust 版本为准（本仓库参考 2.44.x）
