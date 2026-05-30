import type { EChartsOption } from 'echarts'
import type { EChartsType } from 'echarts/core'
import type { StatsHistoryPoint } from '../hooks/useLocustStats'

const THEME = '#15803d'

/** 折线图公共配置：无平滑、虚线纵轴指示器（与 Locust WebUI 类似） */
export const linkedAxisPointer = {
  type: 'line' as const,
  lineStyle: {
    type: 'dashed' as const,
    color: '#94a3b8',
    width: 1,
  },
}

function formatAxisTime(value: number): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const defaultLegend = {
  top: 4,
  left: 'center' as const,
  itemGap: 16,
  textStyle: { fontSize: 11 },
}

/** 与 Locust 原生一致：time 轴 + [ISO 时间, 数值] 数据点 */
export function buildLinkedTimeLineOption(partial: EChartsOption): EChartsOption {
  const { legend: partialLegend, ...rest } = partial
  const legend =
    partialLegend && typeof partialLegend === 'object' && !Array.isArray(partialLegend)
      ? { ...defaultLegend, ...partialLegend }
      : defaultLegend

  return {
    animation: false,
    grid: { left: 56, right: 24, top: 52, bottom: 32 },
    legend,
    tooltip: {
      trigger: 'axis',
      axisPointer: linkedAxisPointer,
    },
    xAxis: {
      type: 'time',
      minInterval: 1000,
      axisLabel: {
        fontSize: 10,
        formatter: (value: number) => formatAxisTime(value),
      },
    },
    ...rest,
  }
}

export function timeSeriesData(
  history: StatsHistoryPoint[],
  pick: (h: StatsHistoryPoint) => number,
): Array<[string, number]> {
  return history.map((h) => [h.timeIso, pick(h)])
}

export function downloadTextFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function exportHistoryCsv(history: StatsHistoryPoint[]) {
  if (history.length === 0) return false
  const header = 'time_iso,total_rps,total_fail_per_sec,user_count,p50_ms,p95_ms'
  const rows = history.map(
    (h) =>
      `${h.timeIso},${h.totalRps},${h.totalFailPerSec},${h.userCount},${h.p50},${h.p95}`,
  )
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  downloadTextFile(
    `locust-chart-history-${stamp}.csv`,
    [header, ...rows].join('\n'),
    'text/csv;charset=utf-8',
  )
  return true
}

export function exportChartPng(instance: EChartsType | undefined, filename: string) {
  if (!instance) return false
  const dataUrl = instance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff',
  })
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = filename
  a.click()
  return true
}

export const chartTheme = THEME
