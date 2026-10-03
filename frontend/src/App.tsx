import { useEffect, useState, type FormEvent } from 'react'
import { motion } from 'motion/react'
import { LeonCore, type CoreState } from './graphics/LeonCore'
import { fetchHealth, fetchTasks, sendCommand } from './api/client'
import type { HealthStatus, Task } from './types/api'

type SystemState = CoreState

const nav = [
  ['◌', 'Sanctum'],
  ['⌁', 'Missions'],
  ['⌑', 'Memory'],
  ['⌘', 'Systems'],
]

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <motion.div
      className="metric"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.45 }}
    >
      <span>{label}</span>
      <strong>
        {value}
        <small>{unit}</small>
      </strong>
    </motion.div>
  )
}

function CoreScene({ state }: { state: SystemState }) {
  return <LeonCore state={state} />
}

export default function App() {
  const [activeNav, setActiveNav] = useState('Sanctum')
  const [state, setState] = useState<SystemState>('idle')
  const [tasks, setTasks] = useState<Task[]>([])
  const [command, setCommand] = useState('')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setTime(new Date()), 1000)
    let active = true

    const load = async () => {
      try {
        const nextHealth = await fetchHealth()
        if (active) {
          setHealth(nextHealth)
        }
      } catch {
        if (active) {
          setHealth(null)
        }
      }

      try {
        const nextTasks = await fetchTasks()
        if (active) {
          setTasks(nextTasks)
        }
      } catch {
        if (active) {
          setTasks([])
        }
      }
    }

    void load()

    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  const connected = health?.status === 'online'
  const currentTask =
    tasks.find(
      (task) =>
        task.status === 'running' ||
        task.status === 'planning' ||
        task.status === 'executing' ||
        task.status === 'queued'
    ) ?? tasks[0] ?? null

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = command.trim()

    if (!text) {
      return
    }

    setState('thinking')
    setCommand('')

    try {
      const result = await sendCommand(text)

      if (result.task) {
        setTasks((current) => [result.task!, ...current.filter((task) => task.id !== result.task!.id)])
      }

      setState(result.type === 'task' ? 'executing' : 'completed')
      window.setTimeout(() => setState('idle'), result.type === 'task' ? 1700 : 1200)
    } catch {
      setState('error')
      window.setTimeout(() => setState('idle'), 2000)
    }
  }

  return (
    <main className="app-shell">
      <div className="grain" />

      <aside className="rail">
        <div className="mark">
          L<span>·</span>
        </div>

        <div className="rail-nav">
          {nav.map(([icon, label]) => (
            <button
              key={label}
              className={activeNav === label ? 'nav-item active' : 'nav-item'}
              onClick={() => setActiveNav(label)}
              title={label}
            >
              <span>{icon}</span>
              <small>{label}</small>
            </button>
          ))}
        </div>

        <button className="profile" title="Profile">
          AD
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">PRIVATE OPERATING SANCTUARY</p>
            <h1>{activeNav}</h1>
          </div>

          <div className="top-meta">
            <span className={connected ? 'connection live' : 'connection'}>
              <i /> {connected ? 'LINKED' : 'LOCAL MODE'}
            </span>

            <time>
              {time.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </time>

            <span className="date">{time.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase()}</span>
          </div>
        </header>

        <div className="content-grid">
          <section className="hero">
            <div className="hero-copy">
              <span className="section-kicker">
                THE LEON FIELD <em>01</em>
              </span>

              <h2>
                Make room
                <br />
                for the <i>signal.</i>
              </h2>

              <p>
                A calm place for complex things. LEON keeps watch across your work,
                remembers what matters, and moves only when invited.
              </p>
            </div>

            <div className="core-wrap">
              <div className={`state-orb ${state}`}>
                <CoreScene state={state} />
                <span className="core-label">{state === 'idle' ? 'quiet orbit' : state}</span>
              </div>

              <div className="core-radial one" />
              <div className="core-radial two" />
            </div>

            <div className="hero-footer">
              <span>
                <b className="pulse-dot" /> SYSTEM {state === 'idle' ? 'AT REST' : state.toUpperCase()}
              </span>
              <span className="coordinates">34° 03′ 12″ N · 118° 14′ 37″ W</span>
            </div>
          </section>

          <aside className="intel-panel">
            <div className="panel-head">
              <span className="section-kicker">
                IN THE FIELD <em>02</em>
              </span>
              <span className="quiet-label">LIVE VIEW</span>
            </div>

            <div className="mission-card">
              <div className="card-top">
                <span className="status-chip">
                  <i /> {currentTask?.status ?? 'standby'}
                </span>
                <span className="mission-id">#{currentTask?.id ?? 'n/a'}</span>
              </div>

              <h3>{currentTask?.title ?? 'No active mission'}</h3>
              <p>
                {currentTask
                  ? currentTask.current_stage || 'Awaiting progress update'
                  : 'No tasks are active. Submit a command to start a mission.'}
              </p>

              <div className="progress-wrap">
                <span>{currentTask?.progress ?? 0}%</span>
                <div className="progress-bar">
                  <span style={{ width: `${currentTask?.progress ?? 0}%` }} />
                </div>
              </div>
            </div>

            <div className="metrics-grid">
              <Metric label="tasks" value={String(tasks.length)} unit="" />
              <Metric label="link" value={connected ? 'live' : 'offline'} unit="" />
              <Metric label="focus" value={connected ? 'stable' : 'local'} unit="" />
            </div>
          </aside>
        </div>

        <section className="command-panel">
          <form onSubmit={handleSubmit}>
            <label htmlFor="command-input">Signal intake</label>
            <div className="command-row">
              <input
                id="command-input"
                value={command}
                placeholder="Ask LEON to prepare a task, research, or summary..."
                onChange={(event) => setCommand(event.target.value)}
              />
              <button type="submit" disabled={!command.trim()}>
                Dispatch
              </button>
            </div>
          </form>

          <div className="task-list">
            <div className="panel-head compact">
              <span className="section-kicker">
                ACTIVE TASKS <em>03</em>
              </span>
            </div>

            {tasks.length === 0 ? (
              <p className="empty-state">No tasks are queued yet.</p>
            ) : (
              tasks.slice(0, 4).map((task) => (
                <div key={task.id} className="task-item">
                  <div>
                    <strong>#{task.id}</strong>
                    <span>{task.title}</span>
                  </div>
                  <small>{task.status}</small>
                </div>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  )
}
