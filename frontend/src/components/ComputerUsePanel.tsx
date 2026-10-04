import { useState, useEffect, useRef } from 'react'
import {
  fetchComputerStatus,
  observeComputer,
  diagnoseComputerScreen,
  executeComputerAction,
  cancelComputerAction,
} from '../api/client'
import type {
  ComputerObservation,
  ComputerStatus,
  DiagnosisResponse,
  ExecutionResult,
} from '../types/api'

export function ComputerUsePanel() {
  const [status, setStatus] = useState<ComputerStatus | null>(null)
  const [observation, setObservation] = useState<ComputerObservation | null>(null)
  const [diagnosis, setDiagnosis] = useState<DiagnosisResponse | null>(null)
  const [lastResult, setLastResult] = useState<ExecutionResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionState, setActionState] = useState<string>('IDLE')
  const [error, setError] = useState<string | null>(null)
  const statusRequestInFlight = useRef(false)
  const mounted = useRef(true)

  const refreshStatus = async () => {
    if (statusRequestInFlight.current) return
    statusRequestInFlight.current = true
    try {
      const data = await fetchComputerStatus()
      if (!mounted.current) return
      setError(null)
      setStatus(data)
      setActionState(data.state)
    } catch {
      if (mounted.current) setError('Computer status is unavailable.')
    } finally {
      statusRequestInFlight.current = false
    }
  }

  useEffect(() => {
    mounted.current = true
    void refreshStatus()
    const interval = setInterval(refreshStatus, 3000)
    return () => {
      mounted.current = false
      clearInterval(interval)
    }
  }, [])

  const handleObserve = async () => {
    setLoading(true)
    setError(null)
    try {
      const obs = await observeComputer(true)
      setObservation(obs)
      setActionState('COMPLETED')
      await refreshStatus()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Observation failed')
      setActionState('FAILED')
    } finally {
      setLoading(false)
    }
  }

  const handleDiagnose = async () => {
    setLoading(true)
    setError(null)
    try {
      const diag = await diagnoseComputerScreen('Analyze screen for active errors, tracebacks, or failing states')
      setDiagnosis(diag)
      setActionState('COMPLETED')
      await refreshStatus()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Diagnosis failed')
      setActionState('FAILED')
    } finally {
      setLoading(false)
    }
  }

  const handleInspectWorkspace = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await executeComputerAction({
        action_type: 'inspect_workspace',
        path: '.',
      }, true)
      setLastResult(res)
      setActionState(res.state)
      await refreshStatus()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Workspace inspection failed')
      setActionState('FAILED')
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    try {
      await cancelComputerAction()
      setActionState('CANCELLED')
      await refreshStatus()
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-6">
      {/* Header & Status Card */}
      <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 backdrop-blur-md">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
            </div>
            <div>
              <h3 className="text-base font-semibold text-zinc-100 tracking-wide">Computer Use &amp; Screen Intelligence</h3>
              <p className="text-xs text-zinc-400">Observe, diagnose, and safely operate local host environment</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 text-xs font-mono rounded-full border ${
                actionState === 'ACTING' || actionState === 'OBSERVING'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse'
                  : actionState === 'COMPLETED'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : actionState === 'FAILED'
                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                  : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
              }`}
            >
              ● {actionState}
            </span>
            {loading && (
              <button
                onClick={handleCancel}
                className="px-2.5 py-1 text-xs text-rose-400 hover:bg-rose-500/10 border border-rose-500/30 rounded-lg transition-colors"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        {/* State Pipeline Visualization */}
        <div className="grid grid-cols-5 gap-2 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 text-xs">
          <div className="flex items-center justify-center gap-1.5 text-zinc-300 font-mono">
            <span className="text-emerald-400">✓</span> UNDERSTAND
          </div>
          <div className="flex items-center justify-center gap-1.5 text-zinc-300 font-mono">
            <span className="text-emerald-400">✓</span> PLAN
          </div>
          <div className="flex items-center justify-center gap-1.5 text-zinc-300 font-mono">
            <span className={actionState === 'OBSERVING' ? 'text-amber-400 animate-pulse' : 'text-emerald-400'}>
              {actionState === 'OBSERVING' ? '●' : '✓'}
            </span>{' '}
            OBSERVE
          </div>
          <div className="flex items-center justify-center gap-1.5 text-zinc-300 font-mono">
            <span className={actionState === 'ACTING' ? 'text-amber-400 animate-pulse' : 'text-zinc-500'}>
              {actionState === 'ACTING' ? '●' : '○'}
            </span>{' '}
            ACT
          </div>
          <div className="flex items-center justify-center gap-1.5 text-zinc-300 font-mono">
            <span className={actionState === 'VERIFYING' ? 'text-amber-400 animate-pulse' : actionState === 'COMPLETED' ? 'text-emerald-400' : 'text-zinc-500'}>
              {actionState === 'COMPLETED' ? '✓' : actionState === 'VERIFYING' ? '●' : '○'}
            </span>{' '}
            VERIFY
          </div>
        </div>

        {/* Active Application Context */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 pt-4 border-t border-zinc-800/80 text-xs">
          <div>
            <span className="text-zinc-500 font-mono uppercase tracking-wider block mb-1">Active Foreground App</span>
            <span className="text-zinc-200 font-medium text-sm">
              {status?.active_application || 'Desktop'}
            </span>
            {status?.active_window && status.active_window !== status.active_application && (
              <p className="text-zinc-400 text-xs truncate mt-0.5" title={status.active_window}>
                {status.active_window}
              </p>
            )}
          </div>
          <div>
            <span className="text-zinc-500 font-mono uppercase tracking-wider block mb-1">Running Allowlisted Apps</span>
            <div className="flex flex-wrap gap-1.5">
              {status?.running_applications && status.running_applications.length > 0 ? (
                status.running_applications.map((app) => (
                  <span
                    key={app}
                    className="px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 border border-zinc-700 font-mono text-[11px]"
                  >
                    {app}
                  </span>
                ))
              ) : (
                <span className="text-zinc-500 italic">None detected</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Control Actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={handleObserve}
          disabled={loading}
          className="px-4 py-2 text-xs font-medium rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700 transition-all flex items-center gap-2 disabled:opacity-50"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          Observe Screen &amp; UI
        </button>

        <button
          onClick={handleDiagnose}
          disabled={loading}
          className="px-4 py-2 text-xs font-medium rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 transition-all flex items-center gap-2 disabled:opacity-50"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          Diagnose Screen Errors
        </button>

        <button
          onClick={handleInspectWorkspace}
          disabled={loading}
          className="px-4 py-2 text-xs font-medium rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700 transition-all flex items-center gap-2 disabled:opacity-50"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 8 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
          </svg>
          Inspect Workspace
        </button>
      </div>

      {/* Error Callout */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
          ⚠ {error}
        </div>
      )}

      {/* Screen Diagnosis Details */}
      {diagnosis && (
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-cyan-500/20 backdrop-blur-md space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-cyan-400 uppercase tracking-wider font-mono">
              Screen Diagnosis Result
            </h4>
            <span className="text-[11px] font-mono text-zinc-500">
              {Math.round(diagnosis.latency_ms)}ms
            </span>
          </div>
          <p className="text-sm text-zinc-200 leading-relaxed">
            {diagnosis.visible_summary || 'Screen analysis compiled without unhandled visual errors.'}
          </p>
          {diagnosis.error_summary && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-mono">
              Detected Error: {diagnosis.error_summary}
            </div>
          )}
          <div className="text-[11px] text-zinc-400 flex flex-wrap gap-4 pt-2 border-t border-zinc-800">
            <span>Targets found: <strong className="text-zinc-200">{diagnosis.targets_count}</strong></span>
            <span>App context: <strong className="text-zinc-200">{diagnosis.active_application || 'Desktop'}</strong></span>
          </div>
        </div>
      )}

      {/* Screen Observation & Visual Targets */}
      {observation && (
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 backdrop-blur-md space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider font-mono">
              Screen Observation &amp; Targets ({observation.screen.width}x{observation.screen.height})
            </h4>
            <span className="text-[11px] font-mono text-zinc-500">{observation.id}</span>
          </div>

          {observation.visible_text && (
            <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-300 leading-relaxed font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
              {observation.visible_text}
            </div>
          )}

          {observation.detected_targets.length > 0 && (
            <div>
              <span className="text-xs font-mono text-zinc-400 block mb-2">Detected Visual Elements:</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-56 overflow-y-auto">
                {observation.detected_targets.map((tgt) => (
                  <div
                    key={tgt.id}
                    className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs flex flex-col justify-between"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-zinc-200 truncate">{tgt.label}</span>
                      <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-mono text-cyan-400">
                        {tgt.type}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500">
                      <span>({tgt.location.x}, {tgt.location.y})</span>
                      <span>{Math.round(tgt.confidence * 100)}% conf</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action Execution Result */}
      {lastResult && (
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 backdrop-blur-md space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider font-mono">
              Action Verification Outcome
            </h4>
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-mono ${
                lastResult.success
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
              }`}
            >
              {lastResult.verification?.code || (lastResult.success ? 'VERIFIED' : 'FAILED')}
            </span>
          </div>
          <p className="text-xs text-zinc-200 leading-relaxed font-mono">
            {lastResult.message}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-zinc-800 text-[11px] font-mono text-zinc-400">
            <div>Obs: {Math.round(lastResult.metrics.observation_ms)}ms</div>
            <div>Act: {Math.round(lastResult.metrics.action_ms)}ms</div>
            <div>Verify: {Math.round(lastResult.metrics.verification_ms)}ms</div>
            <div>Total: {Math.round(lastResult.metrics.total_ms)}ms</div>
          </div>
        </div>
      )}
    </div>
  )
}
