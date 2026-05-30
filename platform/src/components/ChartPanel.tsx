import { useCallback } from 'react'
import type { ReactNode, RefObject } from 'react'
import ReactECharts from 'echarts-for-react'
import { Button, Popconfirm, Space, Tooltip, message } from 'antd'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import type { EChartsOption } from 'echarts'
import type { EChartsType } from 'echarts/core'
import { exportChartPng } from '../utils/dashboardCharts'
import { fileStamp } from '../utils/exportDom'

interface ChartPanelProps {
  title: ReactNode
  option: EChartsOption
  chartRef: RefObject<ReactECharts | null>
  pngFilename: string
  onReset?: () => void
  height?: number
}

export default function ChartPanel({
  title,
  option,
  chartRef,
  pngFilename,
  onReset,
  height = 260,
}: ChartPanelProps) {
  const handleDownload = useCallback(() => {
    const inst: EChartsType | undefined = chartRef.current?.getEchartsInstance()
    if (!exportChartPng(inst, `${pngFilename}-${fileStamp()}.png`)) {
      message.warning('图表尚未就绪，请稍后重试')
    }
  }, [chartRef, pngFilename])

  return (
    <div className="glass-card chart-section chart-section-linked chart-panel">
      <div className="panel-header">
        <h3 className="chart-title">{title}</h3>
        <Space size={4} className="panel-header-actions">
          <Tooltip title="下载 PNG">
            <Button
              type="text"
              size="small"
              className="panel-icon-btn"
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              aria-label="下载 PNG"
            />
          </Tooltip>
          {onReset && (
            <Popconfirm
              title="确认清空全部图表数据？"
              description="清空折线与实时 KPI；表格数据仍来自 Locust，除非服务端已重置。"
              onConfirm={onReset}
              okText="清空"
              cancelText="取消"
            >
              <Tooltip title="清空图表数据">
                <Button
                  type="text"
                  size="small"
                  className="panel-icon-btn"
                  icon={<ReloadOutlined />}
                  aria-label="清空图表数据"
                />
              </Tooltip>
            </Popconfirm>
          )}
        </Space>
      </div>
      <ReactECharts ref={chartRef} option={option} style={{ height }} notMerge />
    </div>
  )
}
