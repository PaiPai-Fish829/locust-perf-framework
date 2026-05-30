import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchExceptions,
  fetchLogs,
  fetchStats,
  getAggregatedStat,
  isRunning,
  type LocustException,
  type LocustState,
  type LocustStatsError,
  type LocustStatsReport,
  type LocustStatEntry,
} from '../api/locust'

/** 与 Locust 原生 WebUI 轮询间隔一致（e6 组件 $3 = 2000ms） */
const POLL_INTERVAL_MS = 2000

export interface StatsHistoryPoint {
  /** 展示用时间标签 */
  time: string
  /** ISO 时间戳，供 ECharts time 轴使用 */
  timeIso: string
  /**
   * 图表 RPS：与 Locust 原生一致，取 /stats/requests 的 total_rps
   * （全程平均 RPS，压测爬坡阶段会稳步上升）
   */
  totalRps: number
  /** 图表失败/秒：total_fail_per_sec */
  totalFailPerSec: number
  userCount: number
  p50: number
  p95: number
}

/** 仪表盘顶部 KPI 展示值（压测停止或手动清空后与 Locust 累计统计解耦） */
export interface DashboardKpi {
  totalRps: number
  failRatio: number
  successRate: number
  p95: number
  userCount: number
  peakRps: number
  peakUsers: number
  /** 压测未运行或已手动清空，当前类指标应为 0 */
  isLiveIdle: boolean
}

export interface LocustDashboardData {
  report: LocustStatsReport | null
  aggregated: LocustStatEntry | undefined
  apiStats: LocustStatEntry[]
  failDetails: LocustStatsError[]
  exceptions: LocustException[]
  recentLogs: string[]
  history: StatsHistoryPoint[]
  kpi: DashboardKpi
  recording: boolean
  runnerState: LocustState | null
  connected: boolean
  error: string | null
  refresh: () => void
  /** 清空图表历史、峰值与 KPI 实时展示（不请求 Locust /stats/reset） */
  clearChartHistory: () => void
}

function buildDashboardKpi(
  report: LocustStatsReport | null,
  recording: boolean,
  kpiCleared: boolean,
  peakRps: number,
  peakUsers: number,
): DashboardKpi {
  const isLiveIdle = !recording || kpiCleared
  if (isLiveIdle) {
    return {
      totalRps: 0,
      failRatio: 0,
      successRate: 100,
      p95: 0,
      userCount: 0,
      peakRps: kpiCleared ? 0 : peakRps,
      peakUsers: kpiCleared ? 0 : peakUsers,
      isLiveIdle: true,
    }
  }

  const failRatio = report?.fail_ratio ?? 0
  const percentiles = report?.current_response_time_percentiles ?? {}
  return {
    totalRps: round2(report?.total_rps ?? 0),
    failRatio,
    successRate: Math.max(0, (1 - failRatio) * 100),
    p95: percentiles['response_time_percentile_0.95'] ?? 0,
    userCount: report?.user_count ?? 0,
    peakRps,
    peakUsers,
    isLiveIdle: false,
  }
}

function round2(val: number): number {
  return Math.round(val * 100) / 100
}

function formatTimeLabel(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function useLocustStats(enabled = true): LocustDashboardData {
  const [report, setReport] = useState<LocustStatsReport | null>(null)
  const [exceptions, setExceptions] = useState<LocustException[]>([])
  const [recentLogs, setRecentLogs] = useState<string[]>([])
  const [history, setHistory] = useState<StatsHistoryPoint[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const peakRpsRef = useRef(0)
  const peakUsersRef = useRef(0)
  const prevStateRef = useRef<LocustState | null>(null)
  const [peakRps, setPeakRps] = useState(0)
  const [peakUsers, setPeakUsers] = useState(0)
  const [recording, setRecording] = useState(false)
  const [runnerState, setRunnerState] = useState<LocustState | null>(null)
  const [kpiCleared, setKpiCleared] = useState(false)

  const resetSessionMetrics = useCallback(() => {
    peakRpsRef.current = 0
    peakUsersRef.current = 0
    setPeakRps(0)
    setPeakUsers(0)
    setHistory([])
  }, [])

  const clearChartHistory = useCallback(() => {
    resetSessionMetrics()
    setKpiCleared(true)
  }, [resetSessionMetrics])

  const poll = useCallback(async () => {
    try {
      const [statsData, excData, logsData] = await Promise.all([
        fetchStats(),
        fetchExceptions(),
        fetchLogs().catch(() => ({ master: [] as string[], workers: {} })),
      ])

      setReport(statsData)
      setExceptions(excData.exceptions)
      setConnected(true)
      setError(null)
      setRunnerState(statsData.state)

      const state = statsData.state
      const prevState = prevStateRef.current
      const nowRunning = isRunning(state)
      const wasRunning = prevState != null && isRunning(prevState)

      if (nowRunning && !wasRunning) {
        resetSessionMetrics()
        setKpiCleared(false)
      }

      prevStateRef.current = state
      setRecording(nowRunning)

      if (nowRunning) {
        const totalRps = round2(statsData.total_rps)
        if (totalRps > peakRpsRef.current) {
          peakRpsRef.current = totalRps
          setPeakRps(totalRps)
        }
        if (statsData.user_count > peakUsersRef.current) {
          peakUsersRef.current = statsData.user_count
          setPeakUsers(statsData.user_count)
        }

        const nowIso = new Date().toISOString()
        const percentiles = statsData.current_response_time_percentiles ?? {}
        const point: StatsHistoryPoint = {
          time: formatTimeLabel(nowIso),
          timeIso: nowIso,
          totalRps,
          totalFailPerSec: round2(statsData.total_fail_per_sec),
          userCount: statsData.user_count,
          p50: percentiles['response_time_percentile_0.5'] ?? 0,
          p95: percentiles['response_time_percentile_0.95'] ?? 0,
        }

        setHistory((prev) => {
          const next = [...prev, point]
          return next.length > 3600 ? next.slice(-3600) : next
        })
      }

      const masterLogs = logsData.master.slice(-5).reverse()
      setRecentLogs(masterLogs)
    } catch (e) {
      setConnected(false)
      setError(e instanceof Error ? e.message : '连接 Locust 失败')
    }
  }, [resetSessionMetrics])

  useEffect(() => {
    if (!enabled) return
    poll()
    const timer = window.setInterval(poll, POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [enabled, poll])

  const aggregated = getAggregatedStat(report)
  const apiStats = (report?.stats ?? []).filter((s) => s.name !== 'Aggregated')
  const failDetails = report?.errors ?? []
  const kpi = buildDashboardKpi(report, recording, kpiCleared, peakRps, peakUsers)

  return {
    report,
    aggregated,
    apiStats: aggregated ? [...apiStats, aggregated] : apiStats,
    failDetails,
    exceptions,
    recentLogs,
    history,
    kpi,
    recording,
    runnerState,
    connected,
    error,
    refresh: poll,
    clearChartHistory,
  }
}
