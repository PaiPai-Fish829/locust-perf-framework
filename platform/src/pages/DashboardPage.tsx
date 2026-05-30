import { useCallback, useState } from 'react'

import { Menu } from 'antd'

import type { MenuProps } from 'antd'

import { isRunning, stateLabel, type LocustState } from '../api/locust'

import DashboardView, { DashboardHeaderActions } from '../components/DashboardView'

import TestTaskPanel from '../components/TestTaskPanel'

import { useLocustStats } from '../hooks/useLocustStats'

import '../styles/dashboard.css'



type MenuKey = 'task' | 'report' | 'dashboard' | 'script' | 'strategy'



const PLACEHOLDER_TITLES: Record<string, string> = {

  report: '测试报告',

  script: '脚本库',

  strategy: '策略库',

}



const menuItems: MenuProps['items'] = [

  { key: 'task', label: '测试任务' },

  { key: 'dashboard', label: '仪表盘' },

  { key: 'report', label: '测试报告' },

  {

    key: 'resources',

    label: '测试资源',

    children: [

      { key: 'script', label: '脚本库' },

      { key: 'strategy', label: '策略库' },

    ],

  },

]



function statusDotClass(state: LocustState | undefined, connected: boolean): string {

  if (!connected) return 'error'

  if (!state || state === 'missing') return 'error'

  if (isRunning(state)) return 'running'

  if (state === 'ready') return 'ready'

  return 'stopped'

}



function tabPanelClass(active: boolean): string {

  return active ? 'tab-panel' : 'tab-panel tab-panel-hidden'

}



export default function DashboardPage() {

  const [activeMenu, setActiveMenu] = useState<MenuKey>('task')

  const stats = useLocustStats(true)



  const runnerState = stats.runnerState ?? 'missing'

  const connected = stats.connected



  const handleMenuSelect: MenuProps['onClick'] = ({ key }) => {

    setActiveMenu(key as MenuKey)

  }



  const handleStop = useCallback(() => {

    stats.refresh()

  }, [stats])



  const placeholderTitle = PLACEHOLDER_TITLES[activeMenu] ?? '未知模块'

  const showPlaceholder = !['task', 'dashboard'].includes(activeMenu)



  return (

    <div className="dashboard-app">

      <header className="glass-header glass-card">

        <div className="header-left">

          <div className="logo-area">

            <svg fill="#15803d" width="28" height="28" viewBox="0 0 24 24">

              <path d="M12 2L2 7v10l10 5 10-5V7l-10-5zM10 19.76l-6-3V8.24l6 3v8.52zm8-3l-6 3v-8.52l6-3v8.52zM12 11.24L6.24 8.5 12 5.76l5.76 2.74L12 11.24z" />

            </svg>

            <span className="logo-text">压测监控平台</span>

          </div>

          <Menu

            mode="horizontal"

            className="nav-menu"

            selectedKeys={[activeMenu]}

            items={menuItems}

            onClick={handleMenuSelect}

            style={{ border: 'none', background: 'transparent' }}

          />

        </div>

        <div className="header-right">

          <div className="status-badge">

            <span className={`status-dot ${statusDotClass(runnerState, connected)}`} />

            <span className="status-label">

              {connected ? stateLabel(runnerState) : '未连接'}

            </span>

          </div>

          <DashboardHeaderActions state={runnerState} onStop={handleStop} />

        </div>

      </header>



      <main className="main-content main-content-tabs">

        <div className={tabPanelClass(activeMenu === 'task')}>

          <TestTaskPanel />

        </div>



        <div className={tabPanelClass(activeMenu === 'dashboard')}>

          <DashboardView stats={stats} visible={activeMenu === 'dashboard'} />

        </div>



        <div className={tabPanelClass(showPlaceholder)}>

          <div className="placeholder-page">

            <div className="glass-card placeholder-card">

              <svg fill="#15803d" width="64" height="64" opacity="0.3" viewBox="0 0 24 24">

                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />

              </svg>

              <h3 className="placeholder-title">{placeholderTitle}</h3>

              <p className="placeholder-desc">该模块正在开发中，敬请期待</p>

            </div>

          </div>

        </div>

      </main>

    </div>

  )

}


