import { useMemo } from 'react'
import type { HealthConnectionState } from '../api/healthPoller'
import type { InteractionState } from '../graphics/motion'

interface LeonCoreHeroProps {
  state: InteractionState | 'offline'
  connectionState: HealthConnectionState
  connected: boolean
  voiceState: string
  activeNav: string
  onActivate?: () => void
  onQuickPrompt?: (prompt: string) => void
}

const quickPrompts = [
  { label: 'Summarize news', prompt: 'Summarize the latest important news' },
  { label: 'Play music', prompt: 'Play music on Spotify' },
  { label: 'Play on YouTube Music', prompt: 'Play music on YouTube Music' },
  { label: 'System status', prompt: 'Check all system statuses and health' },
  { label: 'Show memory', prompt: 'What memories and context do you have stored?' },
]

export function LeonCoreHero({
  state,
  connectionState,
  connected,
  voiceState,
  activeNav,
  onActivate,
  onQuickPrompt,
}: LeonCoreHeroProps) {
  const statusInfo = useMemo(() => {
    if (connectionState === 'connecting') {
      return { label: 'Connecting...', color: 'amber', badge: 'CONNECTING' }
    }
    if (connectionState === 'offline') {
      return { label: 'Service Offline', color: 'rose', badge: 'OFFLINE' }
    }
    if (voiceState === 'listening') {
      return { label: 'Listening to your voice...', color: 'emerald', badge: 'LISTENING' }
    }
    if (voiceState === 'processing') {
      return { label: 'Processing speech...', color: 'indigo', badge: 'PROCESSING' }
    }
    if (voiceState === 'speaking') {
      return { label: 'Speaking...', color: 'emerald', badge: 'SPEAKING' }
    }
    if (state === 'thinking') {
      return { label: 'Thinking & Planning...', color: 'indigo', badge: 'THINKING' }
    }
    if (state === 'executing') {
      return { label: 'Executing Task...', color: 'cyan', badge: 'WORKING' }
    }
    if (state === 'success') {
      return { label: 'Task Complete', color: 'emerald', badge: 'READY' }
    }
    if (state === 'error') {
      return { label: 'Attention Required', color: 'rose', badge: 'ERROR' }
    }
    return { label: 'Ready for instructions', color: 'indigo', badge: 'ACTIVE' }
  }, [state, connectionState, voiceState])

  return (
    <div
      className={`hero-container state-${state} color-${statusInfo.color}`}
      onClick={onActivate}
      role="region"
      aria-label="LEON Core Assistant"
    >
      {/* Dynamic Background Glow */}
      <div className="hero-glow-backdrop" aria-hidden="true" />

      {/* Main Core Orb / Visualizer */}
      <div className="hero-core-wrapper">
        <div className="core-orb-outer">
          <div className="core-orb-pulse" />
          <div className="core-orb-inner">
            <div className="core-logo-mark">
              <span className="core-letter">L</span>
              <span className="core-dot" />
            </div>
          </div>
        </div>

        {/* Live Status Badge */}
        <div className={`hero-badge badge-${statusInfo.color}`}>
          <span className="badge-pulse-dot" />
          <span className="badge-text">{statusInfo.badge}</span>
        </div>
      </div>

      {/* Hero Content */}
      <div className="hero-content-block">
        <h2 className="hero-title">
          {voiceState === 'listening'
            ? 'Listening to you...'
            : voiceState === 'speaking'
            ? 'Speaking reply...'
            : state === 'executing'
            ? 'Processing current task...'
            : 'How can I assist you today?'}
        </h2>
        <p className="hero-subtitle">
          {connected
            ? 'Voice recognition, task automation, media control, and multimodal vision are online.'
            : 'Connecting to local LEON server... Ensure the backend service is running.'}
        </p>

        {/* Quick Suggestion Prompts */}
        {connected && onQuickPrompt && (
          <div className="hero-quick-prompts">
            <span className="prompts-label">Suggested actions:</span>
            <div className="prompts-grid">
              {quickPrompts.map(({ label, prompt }) => (
                <button
                  key={label}
                  type="button"
                  className="quick-prompt-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    onQuickPrompt(prompt)
                  }}
                  data-sound="click"
                >
                  <span className="prompt-icon">✦</span>
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Telemetry Metric Cards */}
      <div className="hero-metrics-row">
        <div className="metric-card">
          <span className="metric-label">SERVICE STATUS</span>
          <strong className={`metric-value ${connected ? 'status-online' : 'status-offline'}`}>
            {connected ? 'ONLINE' : connectionState.toUpperCase()}
          </strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">VOICE ENGINE</span>
          <strong className={`metric-value ${voiceState !== 'idle' ? 'status-active' : connected ? 'status-online' : 'status-offline'}`}>
            {voiceState !== 'idle' ? voiceState.toUpperCase() : 'STANDBY'}
          </strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">WORKSPACE</span>
          <strong className="metric-value status-neutral">
            {activeNav.toUpperCase()}
          </strong>
        </div>
      </div>
    </div>
  )
}
