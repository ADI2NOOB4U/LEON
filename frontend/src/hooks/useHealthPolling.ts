import { useEffect, useState } from 'react'
import { fetchHealth } from '../api/client'
import { createHealthPoller, type HealthConnectionState } from '../api/healthPoller'
import type { HealthStatus } from '../types/api'

export function useHealthPolling() {
  const [connection, setConnection] = useState<HealthConnectionState>('connecting')
  const [health, setHealth] = useState<HealthStatus | null>(null)

  useEffect(() => createHealthPoller({
    check: fetchHealth,
    onChange: (nextConnection, nextHealth) => {
      setConnection(nextConnection)
      setHealth(nextHealth)
    },
  }).start(), [])

  return { connection, health }
}