import type { CommandResponse, HealthStatus, Memory, Task, VoiceTurnResponse } from '../types/api'

export const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init.headers ?? {}),
    },
  })

  if (!response.ok) {
    let detail = 'Request failed'
    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string') {
        detail = payload.detail
      }
    } catch {
      // Intentionally ignore malformed error payloads.
    }
    throw new Error(detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export async function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/health')
}

export async function fetchTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks')
}

export async function sendCommand(message: string): Promise<CommandResponse> {
  return request<CommandResponse>('/command', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

export async function fetchMemory(): Promise<Memory[]> {
  return request<Memory[]>('/memory')
}

export async function sendVoiceTurn(recording: Blob): Promise<VoiceTurnResponse> {
  const form = new FormData()
  form.append('audio', recording, `recording.${recording.type.includes('ogg') ? 'ogg' : 'webm'}`)
  return request<VoiceTurnResponse>('/voice/turn', {
    method: 'POST',
    body: form,
  })
}
