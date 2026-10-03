import type { CommandResponse, HealthStatus, MediaStatus, Memory, NewsEvent, SpotifyStatus, Task, VisionMode, VisionResponse, VoiceTurnResponse } from '../types/api'

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
      } else if (
        payload?.detail
        && typeof payload.detail === 'object'
        && typeof payload.detail.message === 'string'
      ) {
        detail = payload.detail.message
      } else if (Array.isArray(payload?.detail) && typeof payload.detail[0]?.msg === 'string') {
        detail = payload.detail[0].msg
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

export async function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  const health = await request<unknown>('/health', { signal })
  if (
    !health
    || typeof health !== 'object'
    || !('status' in health)
    || health.status !== 'online'
    || !('service' in health)
    || typeof health.service !== 'string'
    || !('version' in health)
    || typeof health.version !== 'string'
  ) {
    throw new Error('The health response has an unexpected shape')
  }
  return health as HealthStatus
}

export async function fetchTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks')
}

export async function fetchMediaStatus(): Promise<MediaStatus> {
  return request<MediaStatus>('/media/status')
}

export async function fetchSpotifyStatus(): Promise<SpotifyStatus> {
  return request<SpotifyStatus>('/media/spotify/status')
}

export async function connectSpotify(): Promise<{ authorization_url: string }> {
  return request<{ authorization_url: string }>('/media/spotify/connect', { method: 'POST' })
}

export async function disconnectSpotify(): Promise<void> {
  await request('/media/spotify/disconnect', { method: 'DELETE' })
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

export async function fetchNewsEvents(): Promise<NewsEvent[]> {
  return request<NewsEvent[]>('/news/events')
}

export async function fetchNewsEvent(eventId: number): Promise<NewsEvent> {
  return request<NewsEvent>(`/news/events/${eventId}`)
}

export async function dismissNewsEvent(eventId: number): Promise<NewsEvent> {
  return request<NewsEvent>(`/news/events/${eventId}/dismiss`, { method: 'POST' })
}

export async function sendVoiceTurn(recording: Blob, timeoutMs = 45000): Promise<VoiceTurnResponse> {
  const form = new FormData()
  const mimeType = recording.type.split(';', 1)[0].toLowerCase()
  const extension: Record<string, string> = {
    'audio/webm': 'webm',
    'audio/ogg': 'ogg',
    'audio/wav': 'wav',
    'audio/x-wav': 'wav',
    'audio/mp4': 'mp4',
    'audio/mpeg': 'mp3',
  }
  const filename = extension[mimeType]
    ? `recording.${extension[mimeType]}`
    : 'recording'
  form.append('audio', recording, filename)
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await request<VoiceTurnResponse>('/voice/turn', {
      method: 'POST',
      body: form,
      signal: controller.signal,
    })
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error('The voice request timed out. Try again.')
    }
    throw error
  } finally {
    window.clearTimeout(timer)
  }
}

export async function analyzeVision(image: Blob, prompt: string, mode: VisionMode): Promise<VisionResponse> {
  const form = new FormData()
  const mimeType = image.type.split(';', 1)[0].toLowerCase()
  const filename: Record<string, string> = {
    'image/png': 'vision-snapshot.png',
    'image/jpeg': 'vision-snapshot.jpg',
    'image/webp': 'vision-snapshot.webp',
  }
  form.append('image', image, filename[mimeType] ?? 'vision-snapshot')
  if (prompt.trim()) form.append('prompt', prompt.trim())
  form.append('mode', mode)
  return request<VisionResponse>('/vision/analyze', { method: 'POST', body: form })
}
