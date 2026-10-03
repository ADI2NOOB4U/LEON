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
}

export function LeonCoreHero({
  state,
  connectionState,
  connected,
  voiceState,
  activeNav,
  onActivate,
}: LeonCoreHeroProps) {
  const statusLabel = useMemo(() => {
    if (connectionState === 'connecting') return 'CONNECTING'
    if (connectionState === 'offline') return 'OFFLINE'
    if (voiceState === 'listening') return 'LISTENING'
    if (voiceState === 'processing') return 'PROCESSING VOICE'
    if (voiceState === 'speaking') return 'SPEAKING'
    if (state === 'thinking') return 'PROCESSING'
    if (state === 'executing') return 'WORKING'
    if (state === 'success') return 'COMPLETED'
    if (state === 'error') return 'ATTENTION REQUIRED'
    return 'STANDBY'
  }, [state, connectionState, voiceState])

  return (
    <div
      className={`leon-core-hero state-${state}`}
      onClick={onActivate}
      role="region"
      aria-label="LEON Core hero surface"
    >
      <div className="hero-surface-glow" aria-hidden="true" />
      <div className="hero-ambient-frame" aria-hidden="true">
        <span className="frame-corner top-left" />
        <span className="frame-corner top-right" />
        <span className="frame-corner bottom-left" />
        <span className="frame-corner bottom-right" />
        <span className="frame-line horizontal" />
      </div>

      <div className="hero-centerpiece">
        <div className="hero-mark-badge" aria-hidden="true">
          <span className="mark-ring outer" />
          <span className="mark-ring inner" />
          <span className="mark-text">L</span>
          <span className="mark-dot" />
        </div>

        <div className="hero-status-pill">
          <span className={`status-indicator-dot ${state}`} />
          <span className="status-indicator-text">{statusLabel}</span>
        </div>
      </div>

      <div className="hero-telemetry-bar">
        <div className="telemetry-item">
          <span className="telemetry-label">BACKEND</span>
          <span className={`telemetry-val ${connected ? 'ready' : 'off'}`}>
            {connected ? 'ONLINE' : connectionState.toUpperCase()}
          </span>
        </div>
        <div className="telemetry-divider" />
        <div className="telemetry-item">
          <span className="telemetry-label">VISION</span>
          <span className={`telemetry-val ${connected ? 'ready' : 'off'}`}>
            NOT CHECKED
          </span>
        </div>
        <div className="telemetry-divider" />
        <div className="telemetry-item">
          <span className="telemetry-label">VOICE</span>
          <span className={`telemetry-val ${voiceState !== 'idle' ? 'active' : connected ? 'ready' : 'off'}`}>
            {voiceState !== 'idle' ? voiceState.toUpperCase() : 'STANDBY'}
          </span>
        </div>
      </div>

      <div className="hero-footnote">
        <span className="footnote-text">
          {activeNav === 'Missions'
            ? 'MISSION CONTROL ACTIVE'
            : connectionState === 'offline'
              ? 'CONNECTION INTERRUPTED — STANDBY MODE'
              : connectionState === 'connecting'
                ? 'CONNECTING TO LEON'
                : 'LEON PERSONAL SYSTEM'}
        </span>
      </div>
    </div>
  )
}
