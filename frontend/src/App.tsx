import { useEffect, useRef, useState, type FormEvent, type PointerEvent } from 'react'
import { motion } from 'motion/react'
import { InstrumentCursor } from './interactions/InstrumentCursor'
import { getMuted, playSound, setMuted as setSoundMuted, unlockSound } from './interactions/sound'
import { LeonCore, type InteractionState } from './graphics/LeonCore'
import { interactionVariants } from './graphics/motion'
import { fetchHealth, fetchTasks, sendCommand } from './api/client'
import type { HealthStatus, Task } from './types/api'

const nav = [
  { glyph: '◌', label: 'Sanctum' },
  { glyph: '⌁', label: 'Missions' },
  { glyph: '⌑', label: 'Memory' },
  { glyph: '⌘', label: 'Systems' },
]

const activeStatuses = new Set(['queued', 'planning', 'running', 'executing', 'verifying'])

function stateFromTask(status?: string): InteractionState {
  if (status === 'queued' || status === 'planning') return 'thinking'
  if (status === 'running' || status === 'executing' || status === 'verifying') return 'executing'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  return 'idle'
}

function useResettableState() {
  const [state, setState] = useState<InteractionState>('idle')
  const timer = useRef<number | undefined>(undefined)

  const showState = (next: InteractionState, duration = 0) => {
    window.clearTimeout(timer.current)
    setState(next)
    if (duration > 0) {
      timer.current = window.setTimeout(() => setState('idle'), duration)
    }
  }

  useEffect(() => () => window.clearTimeout(timer.current), [])
  return [state, showState] as const
}

export default function App() {
  const [activeNav, setActiveNav] = useState('Sanctum')
  const [interaction, showState] = useResettableState()
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [command, setCommand] = useState('')
  const [reply, setReply] = useState('')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [muted, setMuted] = useState(getMuted)
  const [coreHovered, setCoreHovered] = useState(false)
  const previousStatuses = useRef(new Map<number, string>())

  useEffect(() => {
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
          for (const task of nextTasks) {
            const previous = previousStatuses.current.get(task.id)
            if (previous && previous !== task.status) {
              if (task.status === 'completed') {
                playSound('complete')
                showState('success', 1500)
              } else if (task.status === 'failed') {
                playSound('error')
                showState('error', 1500)
              }
            }
            previousStatuses.current.set(task.id, task.status)
          }
          setTasks(nextTasks)
        }
      } catch {
        if (active) {
          setTasks([])
        }
      }
    }

    void load()
    const refresh = window.setInterval(() => void load(), 4000)

    return () => {
      active = false
      window.clearInterval(refresh)
    }
  }, [])

  const connected = health?.status === 'online'
  const activeTask = tasks.find((task) => activeStatuses.has(task.status)) ?? null
  const currentTask = tasks.find((task) => task.id === selectedTaskId) ?? activeTask ?? tasks[0] ?? null
  const coreState = interaction !== 'idle'
    ? interaction
    : coreHovered
      ? 'hover'
      : stateFromTask(activeTask?.status)

  const handlePointerOver = (event: PointerEvent<HTMLElement>) => {
    const target = event.target
    const related = event.relatedTarget
    if (!(target instanceof Element)) return
    const control = target.closest('button, [role="button"]')
    if (control && (!(related instanceof Node) || !control.contains(related))) {
      playSound('hover')
    }
  }

  const handleClickCapture = (event: PointerEvent<HTMLElement>) => {
    const target = event.target
    if (!(target instanceof Element)) return
    const sound = target.closest<HTMLElement>('[data-sound]')?.dataset.sound
    if (sound === 'click' || sound === 'focus') playSound(sound)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = command.trim()

    if (!text) {
      return
    }

    unlockSound()
    playSound('message')
    showState('thinking')
    setCommand('')

    try {
      const result = await sendCommand(text)
      setReply(result.message)

      if (result.task) {
        setTasks((current) => [result.task!, ...current.filter((task) => task.id !== result.task!.id)])
        setSelectedTaskId(result.task.id)
        previousStatuses.current.set(result.task.id, result.task.status)
        playSound('taskStart')
        showState('executing', 1800)
      } else {
        playSound('complete')
        showState('success', 1400)
      }
    } catch {
      playSound('error')
      showState('error', 1800)
      setReply('The request could not be completed. Check the connection and try again.')
    }
  }

  return (
    <main className="app-shell" onPointerOverCapture={handlePointerOver} onClickCapture={handleClickCapture} onPointerDownCapture={unlockSound} onKeyDownCapture={unlockSound}>
      <div className="grain" />
      <InstrumentCursor />

      <aside className="rail">
        <div className="mark" aria-label="LEON">L<span>·</span></div>

        <div className="rail-nav">
          {nav.map(({ glyph, label }) => (
            <button
              key={label}
              className={activeNav === label ? 'nav-item active' : 'nav-item'}
              onClick={() => setActiveNav(label)}
              aria-current={activeNav === label ? 'page' : undefined}
              data-sound="click"
            >
              <span className="nav-glyph" aria-hidden="true">{glyph}</span>
              <small>{label}</small>
            </button>
          ))}
        </div>

        <button
          className="sound-toggle"
          type="button"
          aria-label={muted ? 'Unmute LEON sounds' : 'Mute LEON sounds'}
          aria-pressed={muted}
          data-sound="click"
          onClick={() => {
            const nextMuted = !muted
            setMuted(nextMuted)
            setSoundMuted(nextMuted)
          }}
          title={muted ? 'Sound off' : 'Sound on'}
        >
          <span aria-hidden="true">{muted ? '◖' : '◗'}</span>
          <small>{muted ? 'sound off' : 'sound on'}</small>
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">LEON <span>/</span> PERSONAL MACHINE</p>
            <h1>{activeNav}</h1>
          </div>

          <div className="top-meta">
            <span className={connected ? 'connection live' : 'connection'} role="status">
              <i /> {connected ? 'Connected' : 'Offline'}
            </span>
          </div>
        </header>

        <div className="content-grid">
          <section className="core-stage" aria-label="LEON core">
            <div className="stage-heading">
              <div>
                <span className="section-kicker">CORE</span>
                <p className="stage-subtitle">Personal system</p>
              </div>
              <motion.span
                className={`state-readout ${coreState}`}
                variants={interactionVariants}
                animate={coreState}
                initial="idle"
                role="status"
              >
                <i />{coreState}
              </motion.span>
            </div>

            {activeNav === 'Memory' ? (
              <div className="stage-message">
                <span className="message-mark">L·</span>
                <h2>Memory is not connected.</h2>
                <p>This workspace has no memory view wired to the current service.</p>
              </div>
            ) : activeNav === 'Systems' ? (
              <div className="system-readout">
                <span className="section-kicker">CONNECTION</span>
                <strong>{connected ? 'Online' : 'Unavailable'}</strong>
                <p>{health ? `${health.service} · ${health.version}` : 'The LEON service could not be reached.'}</p>
              </div>
            ) : (
              <div
                className="core-wrap"
                onPointerEnter={() => setCoreHovered(true)}
                onPointerLeave={() => setCoreHovered(false)}
              >
                <LeonCore
                  state={coreState}
                  onActivate={() => {
                    playSound('focus')
                    showState('focus', 650)
                  }}
                />
                <span className="core-caption">{activeNav === 'Missions' ? 'Mission control' : 'At your service'}</span>
              </div>
            )}

            <div className="stage-foot">
              <span><i className={connected ? 'pulse-dot live' : 'pulse-dot'} />{connected ? 'Service available' : 'Local interface'}</span>
              <span>{currentTask ? `${activeTask ? 'Active' : selectedTaskId ? 'Selected' : 'Last task'} · ${currentTask.title}` : 'No active work'}</span>
            </div>
          </section>

          <aside className="workbench" id="missions">
            <div className="workbench-head">
              <span className="section-kicker">TASKS</span>
              <span className="task-count">{tasks.length.toString().padStart(2, '0')}</span>
            </div>

            <div className="current-work">
              <div className="current-work-top">
                <span className={`task-status ${currentTask?.status ?? 'quiet'}`}><i />{currentTask?.status ?? 'Standing by'}</span>
                {currentTask && <span className="task-id">#{currentTask.id}</span>}
              </div>
              <h2>{currentTask?.title ?? 'Nothing in motion'}</h2>
              <p>{currentTask?.current_stage || (currentTask ? 'No further update' : 'Send a request to begin.')}</p>
              {currentTask && (
                <div className="progress-track" aria-label={`Task progress ${currentTask.progress}%`}>
                  <span style={{ width: `${Math.max(0, Math.min(100, currentTask.progress))}%` }} />
                </div>
              )}
            </div>

            <div className="task-log" aria-label="Recent tasks">
              <div className="list-heading"><span>Recent tasks</span><span>SELECT TO INSPECT</span></div>
              {tasks.length === 0 ? (
                <p className="empty-state">Your task history will appear here.</p>
              ) : tasks.slice(0, 5).map((task) => (
                <button
                  className={`task-row${task.id === currentTask?.id ? ' selected' : ''}`}
                  key={task.id}
                  type="button"
                  onClick={() => setSelectedTaskId(task.id)}
                  data-sound="click"
                >
                  <span className="task-row-mark" aria-hidden="true" />
                  <span className="task-row-title">{task.title}</span>
                  <span className="task-row-state">{task.status}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="command-area" aria-label="Command interface">
            <div className="reply-line" aria-live="polite">
              <span className="reply-mark">L·</span>
              <p>{reply || 'Ready when you are.'}</p>
            </div>
            <form className="command-deck" onSubmit={handleSubmit}>
              <label className="command-glyph" htmlFor="command-input" aria-label="Command">↳</label>
              <input
                id="command-input"
                value={command}
                placeholder="Give LEON a task or ask a question"
                onFocus={() => {
                  playSound('focus')
                  if (interaction === 'idle') showState('focus')
                }}
                onBlur={() => {
                  if (interaction === 'focus') showState('idle')
                }}
                onChange={(event) => setCommand(event.target.value)}
              />
              <button type="submit" disabled={!command.trim()} data-sound="send">
                <span>Send</span><span aria-hidden="true">↗</span>
              </button>
            </form>
            <p className="command-note">Enter to send</p>
          </section>
        </div>
      </section>
    </main>
  )
}
