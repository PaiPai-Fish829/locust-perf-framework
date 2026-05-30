import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Checkbox,
  Empty,
  Input,
  InputNumber,
  Select,
  Spin,
  Typography,
  message,
} from 'antd'
import {
  fetchDataFiles,
  fetchScenarios,
  fetchShapes,
  startPlatformSwarm,
  type DataFileMeta,
  type ScenarioDataOverride,
  type ScenarioMeta,
  type ShapeMeta,
} from '../api/platform'

const THEME = '#15803d'

function buildDefaultShapeParams(shape: ShapeMeta | null): Record<string, number> {
  if (!shape) return {}
  return Object.fromEntries(shape.params.map((p) => [p.name, p.default]))
}

export default function TestTaskPanel() {
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([])
  const [dataFiles, setDataFiles] = useState<DataFileMeta[]>([])
  const [shapes, setShapes] = useState<ShapeMeta[]>([])
  const [scenarioDataOverrides, setScenarioDataOverrides] = useState<
    Record<string, ScenarioDataOverride>
  >({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [taskName, setTaskName] = useState('')
  const [scenarioSearch, setScenarioSearch] = useState('')
  const [selectedClassNames, setSelectedClassNames] = useState<string[]>([])
  const [activeShapeId, setActiveShapeId] = useState<string | null>(null)
  const [shapeParamValues, setShapeParamValues] = useState<Record<string, number>>({})
  const [userCount, setUserCount] = useState(100)
  const [spawnRate, setSpawnRate] = useState(10)
  const [runUntilStop, setRunUntilStop] = useState(true)
  const [durationMinutes, setDurationMinutes] = useState(5)
  const [executing, setExecuting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)

    Promise.all([fetchScenarios(), fetchShapes(), fetchDataFiles()])
      .then(([scenarioRes, shapeRes, dataFileRes]) => {
        if (cancelled) return
        setScenarios(scenarioRes.scenarios)
        setDataFiles(dataFileRes.data_files)
        setShapes(shapeRes.shapes)
        const initialOverrides: Record<string, ScenarioDataOverride> = {}
        for (const s of scenarioRes.scenarios) {
          if (s.parametrized && s.default_data_file) {
            initialOverrides[s.class_name] = {
              data_file: s.default_data_file,
              data_strategy: s.data_strategy || 'cycle',
            }
          }
        }
        setScenarioDataOverrides(initialOverrides)
        if (scenarioRes.scenarios.length > 0) {
          setSelectedClassNames([scenarioRes.scenarios[0].class_name])
        }
        if (shapeRes.shapes.length > 0) {
          setActiveShapeId(shapeRes.shapes[0].id)
          setShapeParamValues(buildDefaultShapeParams(shapeRes.shapes[0]))
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : '加载配置失败')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const filteredScenarios = useMemo(() => {
    const q = scenarioSearch.trim().toLowerCase()
    if (!q) return scenarios
    return scenarios.filter(
      (s) =>
        s.class_name.toLowerCase().includes(q) ||
        s.filename.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q),
    )
  }, [scenarios, scenarioSearch])

  const activeShape = shapes.find((s) => s.id === activeShapeId) ?? null

  const handleShapeChange = (shapeId: string | null) => {
    setActiveShapeId(shapeId)
    const shape = shapes.find((s) => s.id === shapeId) ?? null
    setShapeParamValues(buildDefaultShapeParams(shape))
  }

  const summaryItems = useMemo(() => {
    const selected = scenarios.filter((s) => selectedClassNames.includes(s.class_name))
    const paramDesc = activeShape
      ? activeShape.params
          .map((p) => `${p.label} ${shapeParamValues[p.name] ?? p.default}${p.unit}`)
          .join(', ')
      : `用户数 ${userCount}, 孵化率 ${spawnRate}/秒`
    const dataDesc = selected
      .filter((s) => s.parametrized)
      .map((s) => {
        const file = scenarioDataOverrides[s.class_name]?.data_file || s.default_data_file
        return `${s.class_name}→${file || '默认'}`
      })
      .join('；')

    return [
      {
        label: '场景',
        value: selected.map((s) => s.class_name).join('、') || '未选择',
      },
      ...(dataDesc
        ? [
            {
              label: '数据文件',
              value: dataDesc,
            },
          ]
        : []),
      {
        label: '策略',
        value: activeShape ? `${activeShape.class_name} (${paramDesc})` : '默认（手动并发）',
      },
      {
        label: '执行',
        value: runUntilStop ? '持续运行直到手动停止' : `${durationMinutes} 分钟`,
      },
    ]
  }, [
    scenarios,
    selectedClassNames,
    scenarioDataOverrides,
    activeShape,
    shapeParamValues,
    userCount,
    spawnRate,
    runUntilStop,
    durationMinutes,
  ])

  const toggleScenario = (className: string, checked: boolean) => {
    setSelectedClassNames((prev) => {
      if (checked) return prev.includes(className) ? prev : [...prev, className]
      return prev.filter((c) => c !== className)
    })
  }

  const updateScenarioDataOverride = (
    className: string,
    patch: Partial<ScenarioDataOverride>,
  ) => {
    setScenarioDataOverrides((prev) => ({
      ...prev,
      [className]: { ...prev[className], ...patch },
    }))
  }

  const dataFileOptions = useMemo(
    () => dataFiles.map((f) => ({ value: f.name, label: f.name })),
    [dataFiles],
  )

  const strategyOptions = [
    { value: 'cycle', label: 'cycle（顺序轮询）' },
    { value: 'random', label: 'random（随机）' },
  ]

  const handleExecute = useCallback(async () => {
    if (selectedClassNames.length === 0) {
      message.warning('请至少选择一个测试场景')
      return
    }

    setExecuting(true)
    try {
      const runTimeParam = runUntilStop ? undefined : `${durationMinutes}m`
      const scenarioData: Record<string, ScenarioDataOverride> = {}
      for (const className of selectedClassNames) {
        const meta = scenarios.find((s) => s.class_name === className)
        if (!meta?.parametrized) continue
        const override = scenarioDataOverrides[className]
        if (override?.data_file) {
          scenarioData[className] = {
            data_file: override.data_file,
            data_strategy: override.data_strategy || meta.data_strategy || 'cycle',
          }
        }
      }

      const res = await startPlatformSwarm({
        shape_class: activeShape?.class_name,
        shape_params: activeShape ? shapeParamValues : undefined,
        user_count: activeShape ? undefined : userCount,
        spawn_rate: activeShape ? undefined : spawnRate,
        run_time: runTimeParam,
        user_classes: selectedClassNames,
        scenario_data: Object.keys(scenarioData).length > 0 ? scenarioData : undefined,
      })
      if (res.success) {
        message.success(res.message || '压测已启动')
      } else {
        message.error(res.message || '启动失败')
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '启动压测失败，请确认 Locust 已运行')
    } finally {
      setExecuting(false)
    }
  }, [
    selectedClassNames,
    scenarios,
    scenarioDataOverrides,
    activeShape,
    shapeParamValues,
    userCount,
    spawnRate,
    runUntilStop,
    durationMinutes,
  ])

  if (loading) {
    return (
      <div className="test-task-panel" style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
        <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
          正在从 scenarios/ 与 shapes/ 加载配置…
        </Typography.Paragraph>
      </div>
    )
  }

  return (
    <div className="test-task-panel">
      {loadError && (
        <Alert
          type="error"
          showIcon
          message="配置加载失败"
          description={loadError}
          style={{ marginBottom: 16 }}
        />
      )}

      <div className="glass-card task-toolbar">
        <div className="toolbar-left">
          <Input
            value={taskName}
            onChange={(e) => setTaskName(e.target.value)}
            placeholder="任务名称（可选）"
            style={{ width: 320 }}
          />
        </div>
        <div className="toolbar-right">
          <Button
            type="primary"
            loading={executing}
            onClick={handleExecute}
            style={{ background: THEME, borderColor: THEME }}
          >
            立即执行
          </Button>
        </div>
      </div>

      <div className="glass-card section">
        <div className="section-header">
          <h3 className="section-title">选择测试场景</h3>
          <span className="section-tip">来自项目 scenarios/ 目录</span>
        </div>
        <div className="scenario-toolbar">
          <Input
            value={scenarioSearch}
            onChange={(e) => setScenarioSearch(e.target.value)}
            placeholder="按类名或文件名搜索"
            style={{ width: 280 }}
            size="small"
            allowClear
          />
        </div>
        {filteredScenarios.length === 0 ? (
          <Empty description="scenarios/ 下暂无可用场景（需定义 HttpUser 子类）" />
        ) : (
          filteredScenarios.map((item) => {
            const selected = selectedClassNames.includes(item.class_name)
            const override = scenarioDataOverrides[item.class_name]
            return (
              <div key={item.id} className="scenario-item">
                <Checkbox
                  checked={selected}
                  onChange={(e) => toggleScenario(item.class_name, e.target.checked)}
                />
                <div className="scenario-item-main">
                  <span className="scenario-name">{item.class_name}</span>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {item.filename}
                  </Typography.Text>
                  {item.parametrized && selected && (
                    <div className="scenario-data-row">
                      <span className="scenario-data-label">参数化文件</span>
                      <Select
                        size="small"
                        style={{ width: 160 }}
                        placeholder="选择数据文件"
                        options={dataFileOptions}
                        value={override?.data_file || item.default_data_file}
                        onChange={(v) =>
                          updateScenarioDataOverride(item.class_name, { data_file: v })
                        }
                      />
                      <span className="scenario-data-label">策略</span>
                      <Select
                        size="small"
                        style={{ width: 140 }}
                        options={strategyOptions}
                        value={
                          override?.data_strategy || item.data_strategy || 'cycle'
                        }
                        onChange={(v) =>
                          updateScenarioDataOverride(item.class_name, { data_strategy: v })
                        }
                      />
                    </div>
                  )}
                  {item.parametrized && !selected && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      默认数据：{item.default_data_file || '—'}
                    </Typography.Text>
                  )}
                </div>
              </div>
            )
          })
        )}
        {filteredScenarios.some((s) => s.description) && (
          <div style={{ marginTop: 12 }}>
            {filteredScenarios
              .filter((s) => s.description && selectedClassNames.includes(s.class_name))
              .map((s) => (
                <Typography.Paragraph
                  key={s.id}
                  type="secondary"
                  style={{ fontSize: 12, marginBottom: 4 }}
                >
                  {s.class_name}：{s.description}
                </Typography.Paragraph>
              ))}
          </div>
        )}
      </div>

      <div className="glass-card section">
        <div className="section-header">
          <h3 className="section-title">测试策略</h3>
          <span className="section-tip">来自项目 shapes/ 目录，可编辑参数后启动</span>
        </div>
        {shapes.length === 0 ? (
          <Empty description="shapes/ 下暂无 LoadTestShape 策略，将使用手动并发参数" />
        ) : (
          <>
            <div className="strategy-templates">
              {shapes.map((shape) => (
                <button
                  key={shape.id}
                  type="button"
                  className={`tpl-btn${activeShapeId === shape.id ? ' active' : ''}`}
                  onClick={() => handleShapeChange(shape.id)}
                >
                  {shape.class_name}
                </button>
              ))}
              <button
                type="button"
                className={`tpl-btn${activeShapeId === null ? ' active' : ''}`}
                onClick={() => handleShapeChange(null)}
              >
                默认（无 Shape）
              </button>
            </div>
            {activeShape && (
              <>
                {activeShape.description && (
                  <Typography.Paragraph type="secondary" style={{ fontSize: 13 }}>
                    {activeShape.description}
                  </Typography.Paragraph>
                )}
                <div className="params-grid">
                  {activeShape.params.map((param) => (
                    <div key={param.name} className="param-item">
                      <span className="param-label">{param.label}:</span>
                      <InputNumber
                        size="small"
                        min={param.min}
                        max={param.max}
                        value={shapeParamValues[param.name] ?? param.default}
                        onChange={(v) =>
                          v != null &&
                          setShapeParamValues((prev) => ({ ...prev, [param.name]: v }))
                        }
                        style={{ width: 100 }}
                      />
                      {param.unit && <span className="param-unit">{param.unit}</span>}
                    </div>
                  ))}
                </div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  未填写的参数使用 {activeShape.filename} 中的 SHAPE_DEFAULTS；CLI 仍可通过
                  LOCUST_SHAPE_* 环境变量覆盖
                </Typography.Text>
              </>
            )}
            {!activeShape && (
              <div className="params-grid" style={{ marginTop: 12 }}>
                <div className="param-item">
                  <span className="param-label">用户数:</span>
                  <InputNumber
                    size="small"
                    min={1}
                    value={userCount}
                    onChange={(v) => v != null && setUserCount(v)}
                    style={{ width: 100 }}
                  />
                </div>
                <div className="param-item">
                  <span className="param-label">孵化率:</span>
                  <InputNumber
                    size="small"
                    min={1}
                    value={spawnRate}
                    onChange={(v) => v != null && setSpawnRate(v)}
                    style={{ width: 100 }}
                  />
                  <span className="param-unit">users/秒</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="glass-card section">
        <div className="section-header">
          <h3 className="section-title">执行时间</h3>
        </div>
        <div className="schedule-form">
          <div className="schedule-row">
            <span className="label">执行时长：</span>
            <InputNumber
              size="small"
              min={1}
              max={999}
              value={durationMinutes}
              disabled={runUntilStop}
              onChange={(v) => v != null && setDurationMinutes(v)}
              style={{ width: 80 }}
            />
            <span className="param-unit">分钟</span>
            <Checkbox checked={runUntilStop} onChange={(e) => setRunUntilStop(e.target.checked)}>
              持续运行直到手动停止
            </Checkbox>
          </div>
        </div>
      </div>

      <div className="glass-card bottom-summary-card">
        <div className="bottom-summary">
          {summaryItems.map((item) => (
            <span key={item.label} className="summary-item">
              <span className="summary-label">{item.label}:</span>
              <span className="summary-value">{item.value}</span>
            </span>
          ))}
        </div>
        <div className="bottom-actions">
          <Button
            type="primary"
            loading={executing}
            onClick={handleExecute}
            style={{ background: THEME, borderColor: THEME }}
          >
            立即执行
          </Button>
        </div>
      </div>
    </div>
  )
}
