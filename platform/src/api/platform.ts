import { locustApiBase } from '../config'

export interface ScenarioMeta {
  id: string
  filename: string
  class_name: string
  description: string
  parametrized?: boolean
  default_data_file?: string
  data_strategy?: string
}

export interface DataFileMeta {
  name: string
  filename: string
}

export interface ScenarioDataOverride {
  data_file?: string
  data_strategy?: string
}

export interface ShapeParam {
  name: string
  label: string
  default: number
  unit: string
  min?: number
  max?: number
}

export interface ShapeMeta {
  id: string
  filename: string
  class_name: string
  description: string
  params: ShapeParam[]
}

export interface PlatformSwarmParams {
  shape_class?: string
  shape_params?: Record<string, number>
  user_count?: number
  spawn_rate?: number
  host?: string
  run_time?: string
  user_classes?: string[]
  /** 按场景类名覆盖参数化文件与分配策略 */
  scenario_data?: Record<string, ScenarioDataOverride>
}

export function fetchScenarios(): Promise<{ scenarios: ScenarioMeta[] }> {
  return fetch(`${locustApiBase}/platform/scenarios`, { credentials: 'include' }).then(
    async (res) => {
      if (!res.ok) throw new Error(`加载场景失败 (${res.status})`)
      return res.json()
    },
  )
}

export function fetchDataFiles(): Promise<{ data_files: DataFileMeta[] }> {
  return fetch(`${locustApiBase}/platform/data-files`, { credentials: 'include' }).then(
    async (res) => {
      if (!res.ok) throw new Error(`加载数据文件失败 (${res.status})`)
      return res.json()
    },
  )
}

export function fetchShapes(): Promise<{ shapes: ShapeMeta[] }> {
  return fetch(`${locustApiBase}/platform/shapes`, { credentials: 'include' }).then(
    async (res) => {
      if (!res.ok) throw new Error(`加载策略失败 (${res.status})`)
      return res.json()
    },
  )
}

async function parseJsonResponse<T>(res: Response, action: string): Promise<T> {
  const text = await res.text()
  if (!text.trim()) {
    throw new Error(`${action}：服务端返回空响应 (${res.status})`)
  }
  try {
    return JSON.parse(text) as T
  } catch {
    const preview = text.length > 120 ? `${text.slice(0, 120)}…` : text
    throw new Error(
      res.ok
        ? `${action}：响应不是合法 JSON（${preview}）`
        : `${action}失败 (${res.status})：${preview}`,
    )
  }
}

export async function startPlatformSwarm(
  params: PlatformSwarmParams,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${locustApiBase}/platform/swarm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(params),
  })
  const data = await parseJsonResponse<{ success: boolean; message: string }>(
    res,
    '启动压测',
  )
  if (!res.ok && data.message) {
    throw new Error(data.message)
  }
  if (!res.ok) {
    throw new Error(data.message || `启动压测失败 (${res.status})`)
  }
  return data
}
