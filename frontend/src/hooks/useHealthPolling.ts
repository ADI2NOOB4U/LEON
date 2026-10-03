import { useEffect, useState } from 'react'
import { fetchHealth } from '../api/client'
import { createHealthPoller, type HealthConnectionState } from '../api/healthPoller'
import type { HealthStatus } from '../types/api'

type HealthListener = (state: HealthConnectionState, health: HealthStatus | null) => void

const listeners = new Set<HealthListener>()
let sharedStop: (() => void) | null = null
let lastConnection: HealthConnectionState = 'connecting'
let lastHealth: HealthStatus | null = null

export function useHealthPolling() {
  const [connection, setConnection] = useState<HealthConnectionState>(lastConnection)
  const [health, setHealth] = useState<HealthStatus | null>(lastHealth)

  useEffect(() => {
    const listener: HealthListener = (nextConnection, nextHealth) => {
      setConnection(nextConnection)
      setHealth(nextHealth)
    }
    listeners.add(listener)
    listener(lastConnection, lastHealth)

    if (!sharedStop) {
      sharedStop = createHealthPoller({
        check: fetchHealth,
        onChange: (nextConnection, nextHealth) => {
          lastConnection = nextConnection
          lastHealth = nextHealth
          for (const item of listeners) item(nextConnection, nextHealth)
        },
      }).start()
    }

    return () => {
      listeners.delete(listener)
      if (listeners.size === 0 && sharedStop) {
        sharedStop()
        sharedStop = null
        lastConnection = 'connecting'
        lastHealth = null
      }
    }
  }, [])

  return { connection, health }
}
