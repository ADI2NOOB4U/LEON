import type { HealthStatus } from '../types/api'

export type HealthConnectionState = 'connecting' | 'online' | 'offline' | 'error'

interface HealthPollerOptions {
  check: (signal: AbortSignal) => Promise<HealthStatus>
  onChange: (state: HealthConnectionState, health: HealthStatus | null) => void
  intervalMs?: number
  timeoutMs?: number
  failureThreshold?: number
}

export function createHealthPoller({
  check,
  onChange,
  intervalMs = 7000,
  timeoutMs = 4000,
  failureThreshold = 3,
}: HealthPollerOptions) {
  let active = false
  let inFlight = false
  let failures = 0
  let state: HealthConnectionState = 'connecting'
  let health: HealthStatus | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let timeout: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined

  const schedule = (delay: number) => {
    timer = setTimeout(() => void poll(), delay)
  }

  const poll = async () => {
    if (!active || inFlight) return
    inFlight = true
    const requestController = new AbortController()
    controller = requestController
    let timedOut = false
    timeout = setTimeout(() => {
      timedOut = true
      requestController.abort()
    }, timeoutMs)

    try {
      const nextHealth = await check(requestController.signal)
      if (!active) return
      if (nextHealth.status !== 'online') throw new Error('LEON health check failed')
      failures = 0
      state = 'online'
      health = nextHealth
      onChange(state, health)
    } catch (error) {
      if (!active || (requestController.signal.aborted && !timedOut)) return
      const message = error instanceof Error ? error.message : ''
      if (message.includes('unexpected shape')) {
        state = 'error'
        onChange(state, health)
      } else {
        failures += 1
        if (failures >= failureThreshold) {
          state = 'offline'
          health = null
        }
        onChange(state, health)
      }
    } finally {
      if (timeout !== undefined) clearTimeout(timeout)
      timeout = undefined
      if (controller === requestController) controller = undefined
      inFlight = false
      if (active) schedule(intervalMs)
    }
  }

  const stop = () => {
    active = false
    if (timer !== undefined) clearTimeout(timer)
    if (timeout !== undefined) clearTimeout(timeout)
    timer = undefined
    timeout = undefined
    controller?.abort()
    controller = undefined
  }

  return {
    start() {
      if (active) return stop
      active = true
      // Let StrictMode's setup/cleanup probe settle before starting the request.
      schedule(0)
      return stop
    },
  }
}