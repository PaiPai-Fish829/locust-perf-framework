import { locustApiBase } from '../config'

/** Locust runner 状态 */
export type LocustState =
  | 'ready'
  | 'running'
  | 'spawning'
  | 'stopped'
  | 'stopping'
  | 'cleanup'
  | 'missing'

export interface LocustStatEntry {
  method: string | null
  name: string
  num_requests: number
  num_failures: number
  min_response_time: number
  max_response_time: number
  current_rps: number
  current_fail_per_sec: number
  avg_response_time: number
  median_response_time: number
  total_rps: number
  total_fail_per_sec: number
  avg_content_length: number
  [key: `response_time_percentile_${number}`]: number | undefined
  [key: string]: string | number | null | undefined
}

export interface LocustStatsError {
  method: string
  name: string
  error: string
  occurrences: number
  first_seen: number | null
  last_seen: number | null
}

export interface LocustStatsReport {
  stats: LocustStatEntry[]
  errors: LocustStatsError[]
  total_rps: number
  total_fail_per_sec: number
  fail_ratio: number
  current_response_time_percentiles?: Record<string, number | null>
  state: LocustState
  user_count: number
  workers?: Array<{
    id: string
    state: string
    user_count: number
    cpu_usage: number
    memory_usage: number
  }>
  worker_count?: number
}

export interface LocustException {
  count: number
  msg: string
  traceback: string
  nodes: string
}

export interface SwarmParams {
  user_count?: number
  spawn_rate?: number
  host?: string
  run_time?: string
  shape_class?: string
  user_classes?: string[]
}

async function locustFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${locustApiBase}${path}`, {
    ...init,
    credentials: 'include',
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Locust API ${path} 失败 (${res.status}): ${text}`)
  }
  const contentType = res.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    return res.json() as Promise<T>
  }
  return res.text() as Promise<T>
}

export function fetchStats(): Promise<LocustStatsReport> {
  return locustFetch<LocustStatsReport>('/stats/requests')
}

/** Locust 服务端 stats.history 单条记录（与原生 WebUI 图表一致） */
export interface LocustStatsHistoryEntry {
  time: string
  current_rps?: [string, number]
  current_fail_per_sec?: [string, number]
  user_count?: [string, number]
  'response_time_percentile_0.5'?: [string, number]
  'response_time_percentile_0.95'?: [string, number]
  [key: string]: string | [string, number] | undefined
}

export function fetchStatsHistory(): Promise<{ history: LocustStatsHistoryEntry[] }> {
  return locustFetch('/platform/stats/history')
}

export function getAggregatedStat(
  report: LocustStatsReport | null,
): LocustStatEntry | undefined {
  return report?.stats?.find((s) => s.name === 'Aggregated')
}

export function fetchExceptions(): Promise<{ exceptions: LocustException[] }> {
  return locustFetch('/exceptions')
}

export function fetchLogs(): Promise<{ master: string[]; workers: Record<string, string[]> }> {
  return locustFetch('/logs')
}

export function stopTest(): Promise<{ success: boolean; message: string }> {
  return locustFetch('/stop')
}

export function resetStats(): Promise<string> {
  return locustFetch('/stats/reset')
}

export async function startSwarm(params: SwarmParams): Promise<{ success: boolean; message: string }> {
  const body = new URLSearchParams()
  if (params.shape_class) {
    body.set('shape_class', params.shape_class)
  } else {
    if (params.user_count != null) body.set('user_count', String(params.user_count))
    if (params.spawn_rate != null) body.set('spawn_rate', String(params.spawn_rate))
  }
  if (params.host) body.set('host', params.host)
  if (params.run_time) body.set('run_time', params.run_time)
  if (params.user_classes?.length) {
    for (const cls of params.user_classes) {
      body.append('user_classes', cls)
    }
  }

  const res = await fetch(`${locustApiBase}/swarm`, {
    method: 'POST',
    body,
    credentials: 'include',
  })
  return res.json()
}

export function exportUrl(path: string): string {
  return `${locustApiBase}${path}`
}

export function formatTimestamp(ts: number | null | undefined): string {
  if (ts == null) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

export function stateLabel(state: LocustState): string {
  const map: Record<LocustState, string> = {
    ready: '就绪',
    running: '运行中',
    spawning: '孵化中',
    stopped: '已停止',
    stopping: '停止中',
    cleanup: '清理中',
    missing: '未连接',
  }
  return map[state] ?? state
}

export function isRunning(state: LocustState): boolean {
  return state === 'running' || state === 'spawning'
}
