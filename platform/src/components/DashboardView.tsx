import { useCallback, useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts'
import type ReactECharts from 'echarts-for-react'
import {
  Alert,
  Button,
  Dropdown,
  Popconfirm,
  Progress,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  exportUrl,
  formatTimestamp,
  isRunning,
  stopTest,
  type LocustException,
  type LocustStatEntry,
  type LocustStatsError,
} from '../api/locust'
import ChartPanel from './ChartPanel'
import type { LocustDashboardData } from '../hooks/useLocustStats'
import {
  buildLinkedTimeLineOption,
  chartTheme,
  exportChartPng,
  exportHistoryCsv,
  timeSeriesData,
} from '../utils/dashboardCharts'
import { exportDomPng, fileStamp } from '../utils/exportDom'

const THEME = chartTheme
const P95_THRESHOLD = 500

function round(val: number | null | undefined, digits = 0): string {
  if (val == null || Number.isNaN(val)) return '-'
  return digits > 0 ? val.toFixed(digits) : String(Math.round(val))
}

/** 聚合行失败率：始终来自 Locust 累计统计，不受图表/KPI 清空影响 */
function aggregatedFailRatio(entry: LocustStatEntry): number {
  if (entry.num_requests <= 0) return 0
  return entry.num_failures / entry.num_requests
}

interface ApiStatRow {
  key: string
  type: string
  name: string
  requests: number
  fails: number
  median: number
  p95: number
  p99: number
  avg: number
  min: number
  max: number
  avgSize: number
  currentRps: number
  currentFails: number
}

function mapApiStats(stats: LocustStatEntry[]): ApiStatRow[] {
  return stats.map((s, i) => ({
    key: `${s.method}-${s.name}-${i}`,
    type: s.method ?? '-',
    name: s.name,
    requests: s.num_requests,
    fails: s.num_failures,
    median: s.median_response_time,
    p95: (s['response_time_percentile_0.95'] as number) ?? 0,
    p99: (s['response_time_percentile_0.99'] as number) ?? 0,
    avg: s.avg_response_time,
    min: s.min_response_time,
    max: s.max_response_time,
    avgSize: s.avg_content_length,
    currentRps: s.current_rps,
    currentFails: s.current_fail_per_sec,
  }))
}

const apiColumns: ColumnsType<ApiStatRow> = [
  { title: 'Type', dataIndex: 'type', width: 80, fixed: 'left' },
  { title: 'Name', dataIndex: 'name', width: 180, ellipsis: true },
  { title: '#Requests', dataIndex: 'requests', width: 100 },
  {
    title: '#Fails',
    dataIndex: 'fails',
    width: 80,
    render: (v: number) => (
      <span className={v > 0 ? 'fails-highlight' : undefined}>{v}</span>
    ),
  },
  { title: 'Median(ms)', dataIndex: 'median', width: 100, render: (v) => round(v) },
  {
    title: '95%ile(ms)',
    dataIndex: 'p95',
    width: 110,
    render: (v: number) => (
      <span className={v > P95_THRESHOLD ? 'p95-highlight' : undefined}>
        {round(v)}
        {v > P95_THRESHOLD ? ' 🔥' : ''}
      </span>
    ),
  },
  { title: '99%ile(ms)', dataIndex: 'p99', width: 110, render: (v) => round(v) },
  { title: 'Average(ms)', dataIndex: 'avg', width: 110, render: (v) => round(v, 1) },
  { title: 'Min(ms)', dataIndex: 'min', width: 90, render: (v) => round(v) },
  { title: 'Max(ms)', dataIndex: 'max', width: 90, render: (v) => round(v) },
  { title: 'Avg Size(bytes)', dataIndex: 'avgSize', width: 130, render: (v) => round(v) },
  { title: 'Current RPS', dataIndex: 'currentRps', width: 110, render: (v) => round(v, 1) },
  {
    title: 'Current Fails/s',
    dataIndex: 'currentFails',
    width: 120,
    render: (v) => round(v, 2),
  },
]

interface FailRow {
  key: string
  failCount: number
  method: string
  apiName: string
  errorInfo: string
  firstSeen: string
  lastSeen: string
}

const failColumns: ColumnsType<FailRow> = [
  { title: '失败数', dataIndex: 'failCount', width: 80 },
  { title: '方法', dataIndex: 'method', width: 70 },
  { title: '接口名', dataIndex: 'apiName', width: 150, ellipsis: true },
  { title: '错误信息', dataIndex: 'errorInfo', ellipsis: true },
  { title: '首次出现', dataIndex: 'firstSeen', width: 160 },
  { title: '最后出现', dataIndex: 'lastSeen', width: 160 },
]

interface ExceptionRow {
  key: string
  count: number
  exceptionInfo: string
  stackSummary: string
}

const exceptionColumns: ColumnsType<ExceptionRow> = [
  { title: '发生次数', dataIndex: 'count', width: 90 },
  { title: '异常信息', dataIndex: 'exceptionInfo', ellipsis: true },
  { title: '堆栈摘要', dataIndex: 'stackSummary', ellipsis: true },
]

interface DashboardViewProps {
  stats: LocustDashboardData
  visible?: boolean
}

export default function DashboardView({ stats, visible = true }: DashboardViewProps) {
  const {
    aggregated,
    apiStats,
    failDetails,
    exceptions,
    recentLogs,
    history,
    kpi,
    recording,
    connected,
    error,
    clearChartHistory,
  } = stats

  const rpsChartRef = useRef<ReactECharts>(null)
  const rtChartRef = useRef<ReactECharts>(null)
  const usersChartRef = useRef<ReactECharts>(null)
  const apiTableRef = useRef<HTMLDivElement>(null)
  const aggregatedRef = useRef<HTMLDivElement>(null)

  const downloadCapture = useCallback(async (el: HTMLDivElement | null, name: string) => {
    const ok = await exportDomPng(el, `${name}-${fileStamp()}.png`)
    if (!ok) message.warning('内容尚未就绪，请稍后重试')
  }, [])

  const LINKED_CHART_GROUP = 'locust-dashboard-charts'

  useEffect(() => {
    const instances = [rpsChartRef, rtChartRef, usersChartRef]
      .map((ref) => ref.current?.getEchartsInstance())
      .filter((inst): inst is NonNullable<typeof inst> => inst != null)

    for (const inst of instances) {
      inst.group = LINKED_CHART_GROUP
    }
    if (instances.length >= 2) {
      echarts.connect(LINKED_CHART_GROUP)
    }
    return () => {
      if (instances.length >= 2) {
        echarts.disconnect(LINKED_CHART_GROUP)
      }
    }
  })

  useEffect(() => {
    if (!visible) return
    const id = window.requestAnimationFrame(() => {
      for (const ref of [rpsChartRef, rtChartRef, usersChartRef]) {
        ref.current?.getEchartsInstance()?.resize()
      }
    })
    return () => window.cancelAnimationFrame(id)
  }, [visible, history.length])

  const handleClearCharts = useCallback(() => {
    clearChartHistory()
    message.success('图表与实时指标已清空')
  }, [clearChartHistory])

  const total = aggregated
  const { totalRps, failRatio, successRate, p95, userCount, peakRps, peakUsers } = kpi

  const emptyChartHint = recording
    ? '压测启动后将开始绘制折线'
    : history.length > 0
      ? '记录已暂停，显示上次压测数据'
      : '压测未运行，暂无图表数据'

  const rpsOption = useMemo(
    () =>
      buildLinkedTimeLineOption({
        legend: { data: ['RPS', 'Failures/s'] },
        yAxis: { type: 'value', name: '请求数', min: 0 },
        series: [
          {
            name: 'RPS',
            type: 'line',
            data: timeSeriesData(history, (h) => h.totalRps),
            smooth: false,
            lineStyle: { color: THEME, width: 2 },
            symbol: 'none',
          },
          {
            name: 'Failures/s',
            type: 'line',
            data: timeSeriesData(history, (h) => h.totalFailPerSec),
            smooth: false,
            lineStyle: { color: '#F56C6C', width: 2 },
            symbol: 'none',
          },
        ],
      }),
    [history],
  )

  const responseTimeOption = useMemo(
    () =>
      buildLinkedTimeLineOption({
        legend: { data: ['P50', 'P95'] },
        yAxis: { type: 'value', name: 'ms', min: 0 },
        series: [
          {
            name: 'P50',
            type: 'line',
            data: timeSeriesData(history, (h) => h.p50),
            smooth: false,
            lineStyle: { color: '#67C23A', width: 2 },
            symbol: 'none',
          },
          {
            name: 'P95',
            type: 'line',
            data: timeSeriesData(history, (h) => h.p95),
            smooth: false,
            lineStyle: { color: '#E6A23C', width: 2 },
            symbol: 'none',
          },
        ],
      }),
    [history],
  )

  const activeUsersOption = useMemo(
    () =>
      buildLinkedTimeLineOption({
        legend: { data: ['Number of Users'] },
        yAxis: { type: 'value', name: '用户数', min: 0 },
        series: [
          {
            name: 'Number of Users',
            type: 'line',
            data: timeSeriesData(history, (h) => h.userCount),
            smooth: false,
            lineStyle: { color: THEME, width: 2 },
            symbol: 'none',
          },
        ],
      }),
    [history],
  )

  const failRows: FailRow[] = failDetails.map((e: LocustStatsError, i) => ({
    key: `${e.method}-${e.name}-${i}`,
    failCount: e.occurrences,
    method: e.method,
    apiName: e.name,
    errorInfo: e.error,
    firstSeen: formatTimestamp(e.first_seen),
    lastSeen: formatTimestamp(e.last_seen),
  }))

  const exceptionRows: ExceptionRow[] = exceptions.map(
    (e: LocustException, i) => ({
      key: `exc-${i}`,
      count: e.count,
      exceptionInfo: e.msg,
      stackSummary: e.traceback.split('\n').slice(0, 2).join(' '),
    }),
  )

  const exportMenuItems = [
    { key: 'charts-csv', label: '图表时序数据 CSV' },
    { key: 'charts-png-all', label: '导出全部图表 PNG' },
    { type: 'divider' as const },
    { key: 'requests', label: '请求统计 CSV' },
    { key: 'failures', label: '失败明细 CSV' },
    { key: 'exceptions', label: '异常 CSV' },
    { key: 'report', label: 'HTML 报告' },
  ]

  const handleExport = ({ key }: { key: string }) => {
    if (key === 'charts-csv') {
      if (!exportHistoryCsv(history)) {
        message.warning('暂无图表数据可导出')
      }
      return
    }
    if (key === 'charts-png-all') {
      if (history.length === 0) {
        message.warning('暂无图表数据可导出')
        return
      }
      const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
      const ok =
        exportChartPng(rpsChartRef.current?.getEchartsInstance(), `rps-${stamp}.png`) &&
        exportChartPng(rtChartRef.current?.getEchartsInstance(), `response-time-${stamp}.png`) &&
        exportChartPng(usersChartRef.current?.getEchartsInstance(), `users-${stamp}.png`)
      if (!ok) message.warning('图表尚未就绪，请稍后重试')
      return
    }
    const paths: Record<string, string> = {
      requests: '/stats/requests/csv',
      failures: '/stats/failures/csv',
      exceptions: '/exceptions/csv',
      report: '/stats/report?download=1',
    }
    window.open(exportUrl(paths[key] ?? '/stats/requests/csv'), '_blank')
  }

  const chartRecordingTag = recording ? (
    <Tag color="processing">记录中</Tag>
  ) : history.length > 0 ? (
    <Tag>已停止记录</Tag>
  ) : null

  return (
    <div>
      {!connected && error && (
        <Alert
          className="connection-alert"
          type="warning"
          showIcon
          message="Locust 连接异常"
          description={error}
        />
      )}

      <div className="kpi-row">
        <div className="glass-card kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">当前 RPS</span>
          </div>
          <div className="kpi-value">{round(totalRps, 1)}</div>
          <div className="kpi-sub">
            峰值 <span className="highlight">{round(peakRps, 1)}</span>
          </div>
        </div>
        <div className="glass-card kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">失败率</span>
          </div>
          <div className={`kpi-value${failRatio > 0.01 ? ' error' : ''}`}>
            {(failRatio * 100).toFixed(2)}%
          </div>
          <div className="kpi-sub">
            成功率 <span className="highlight">{successRate.toFixed(2)}%</span>
          </div>
        </div>
        <div className="glass-card kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">P95 响应时间</span>
          </div>
          <div className="kpi-value">{round(p95)}ms</div>
          <div className="kpi-sub">
            阈值 <span className="highlight">{P95_THRESHOLD}ms</span>
          </div>
        </div>
        <div className="glass-card kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">活跃用户数</span>
          </div>
          <div className="kpi-value">{userCount}</div>
          <div className="kpi-sub">
            峰值 <span className="highlight">{peakUsers}</span>
          </div>
        </div>
      </div>

      <div className="glass-card chart-status-banner">
        <div className="panel-header">
          <h3 className="section-title">实时图表</h3>
          <Popconfirm
            title="确认清空全部图表数据？"
            description="仅清除上方 KPI 卡片与折线图历史；聚合报告、API 统计表仍显示 Locust 服务端累计数据。"
            onConfirm={handleClearCharts}
            okText="清空"
            cancelText="取消"
          >
            <Tooltip title="清空全部图表数据">
              <Button
                type="text"
                size="small"
                className="panel-icon-btn"
                icon={<ReloadOutlined />}
                aria-label="清空全部图表数据"
              />
            </Tooltip>
          </Popconfirm>
        </div>
        <div className="chart-status-body">
          {chartRecordingTag}
          <Typography.Text type="secondary" className="chart-status-hint">
            {emptyChartHint}
          </Typography.Text>
          <Typography.Text type="secondary" className="chart-status-tip">
            仅在压测运行期间记录；停止后保留上次数据。鼠标悬停任一图表可联动虚线纵轴。
          </Typography.Text>
        </div>
      </div>

      <ChartPanel
        title="Total Requests per Second"
        option={rpsOption}
        chartRef={rpsChartRef}
        pngFilename="rps"
        onReset={handleClearCharts}
      />

      <ChartPanel
        title="响应时间 (ms)"
        option={responseTimeOption}
        chartRef={rtChartRef}
        pngFilename="response-time"
        onReset={handleClearCharts}
      />

      <ChartPanel
        title="活跃用户数趋势"
        option={activeUsersOption}
        chartRef={usersChartRef}
        pngFilename="users"
        onReset={handleClearCharts}
      />

      <div className="glass-card table-section export-panel">
        <div className="panel-header">
          <h3 className="section-title">详细 API 统计</h3>
          <Button
            type="default"
            size="small"
            className="panel-header-action"
            icon={<DownloadOutlined />}
            onClick={() => downloadCapture(apiTableRef.current, 'api-stats')}
          >
            下载 PNG
          </Button>
        </div>
        <div ref={apiTableRef} className="export-capture-target">
          <Table<ApiStatRow>
            size="small"
            bordered
            scroll={{ x: 1400 }}
            pagination={false}
            dataSource={mapApiStats(apiStats)}
            columns={apiColumns}
          />
        </div>
      </div>

      {total && (
        <div className="glass-card table-section export-panel">
          <div className="panel-header">
            <h3 className="section-title">聚合报告</h3>
            <Button
              type="default"
              size="small"
              className="panel-header-action"
              icon={<DownloadOutlined />}
              onClick={() => downloadCapture(aggregatedRef.current, 'aggregated-report')}
            >
              下载 PNG
            </Button>
          </div>
          <div ref={aggregatedRef} className="aggregated-report-card export-capture-target">
            <div className="aggregated-report-row">
              <span className="aggregated-label">接口</span>
              <span className="aggregated-value">{total.name}</span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">总请求数</span>
              <span className="aggregated-value">{total.num_requests}</span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">失败数</span>
              <span className="aggregated-value">{total.num_failures}</span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">失败率</span>
              <span className="aggregated-value">
                {(aggregatedFailRatio(total) * 100).toFixed(2)}%
              </span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">平均响应</span>
              <span className="aggregated-value">{round(total.avg_response_time, 1)} ms</span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">中位数</span>
              <span className="aggregated-value">{round(total.median_response_time)} ms</span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">P95</span>
              <span className="aggregated-value">
                {round((total['response_time_percentile_0.95'] as number) ?? 0)} ms
              </span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">当前 RPS</span>
              <span className="aggregated-value">{round(total.current_rps, 1)}</span>
            </div>
            <div className="aggregated-report-row">
              <span className="aggregated-label">总 RPS</span>
              <span className="aggregated-value">{round(total.total_rps, 1)}</span>
            </div>
          </div>
        </div>
      )}

      <div className="table-row">
        <div className="glass-card table-half left">
          <h3 className="section-title">失败请求明细</h3>
          <Table<FailRow>
            size="small"
            bordered
            pagination={false}
            scroll={{ y: 250 }}
            dataSource={failRows}
            columns={failColumns}
            locale={{ emptyText: '暂无失败记录' }}
          />
        </div>
        <div className="glass-card table-half right">
          <h3 className="section-title">异常统计</h3>
          <Table<ExceptionRow>
            size="small"
            bordered
            pagination={false}
            scroll={{ y: 250 }}
            dataSource={exceptionRows}
            columns={exceptionColumns}
            locale={{ emptyText: '暂无异常' }}
          />
        </div>
      </div>

      <div className="glass-card toolbar-section">
        <div className="log-preview">
          {recentLogs.length > 0 ? (
            recentLogs.map((log, idx) => (
              <div key={idx} className="log-item">
                <Tag color="default" style={{ fontSize: 11 }}>
                  log
                </Tag>
                {log}
              </div>
            ))
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              暂无日志（压测运行后将显示 Locust master 日志）
            </Typography.Text>
          )}
        </div>
        <div className="success-rate">
          <span className="rate-label">成功率</span>
          <Progress
            percent={Number(successRate.toFixed(2))}
            strokeColor={THEME}
            size="small"
            style={{ flex: 1 }}
          />
        </div>
        <Dropdown menu={{ items: exportMenuItems, onClick: handleExport }}>
          <Button type="primary" style={{ background: THEME, borderColor: THEME }}>
            导出数据
          </Button>
        </Dropdown>
      </div>
    </div>
  )
}

export function DashboardHeaderActions({
  state,
  onStop,
}: {
  state: string | undefined
  onStop: () => void
}) {
  const running = state ? isRunning(state as Parameters<typeof isRunning>[0]) : false

  const handleStop = async () => {
    try {
      const res = await stopTest()
      if (res.success) {
        message.success(res.message)
        onStop()
      } else {
        message.error(res.message)
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '停止失败')
    }
  }

  return (
    <Space>
      <Button danger size="small" disabled={!running} onClick={handleStop}>
        停止运行
      </Button>
    </Space>
  )
}
