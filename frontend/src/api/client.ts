import type { CommandResponse, HealthStatus, ImportantDate, MediaStatus, Memory, NewsEvent, PersonalMemory, PersonalProfile, Relationship, SpotifyStatus, Task, VisionMode, VisionResponse, VoiceTurnResponse } from '../types/api'

export const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api'

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status = 0,
    public readonly code = 'request_failed',
    public readonly details: unknown = undefined,
    public readonly retryable = status === 0 || status >= 500,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

function createRequestId(): string {
  const randomId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `LEON-REQ-${randomId}`
}

function detailFromPayload(payload: any, fallback: string): string {
  if (typeof payload?.detail === 'string') return payload.detail
  if (typeof payload?.detail?.message === 'string') return payload.detail.message
  if (Array.isArray(payload?.detail) && typeof payload.detail[0]?.msg === 'string') return payload.detail[0].msg
  if (typeof payload?.message === 'string') return payload.message
  return fallback
}

async function fetchApiResponse(path: string, init: RequestInit = {}, timeoutMs = 30_000): Promise<Response> {
  const controller = new AbortController()
  const externalSignal = init.signal
  let timedOut = false
  let abortedByCaller = false
  const requestId = createRequestId()
  const abortFromCaller = () => controller.abort()
  const markCallerAbort = () => { abortedByCaller = true; abortFromCaller() }
  externalSignal?.addEventListener('abort', markCallerAbort, { once: true })
  const timeout = window.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  let response: Response
  try {
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    headers.set('X-Request-ID', requestId)
    // Only JSON bodies need a content type. Adding it to every GET/DELETE
    // turns otherwise simple CORS requests into avoidable preflights.
    if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers,
    })
  } catch (error) {
    if (timedOut) throw new ApiRequestError('The request timed out while contacting LEON backend.', 0, 'TIMEOUT', undefined, true)
    if (abortedByCaller) throw new ApiRequestError('The request was cancelled.', 0, 'ABORTED', undefined, true)
    throw new ApiRequestError('Unable to reach LEON backend. Check that the backend is running and the browser origin is allowed.', 0, 'NETWORK_ERROR', { request_id: requestId }, true)
  } finally {
    window.clearTimeout(timeout)
    externalSignal?.removeEventListener('abort', markCallerAbort)
  }

  if (!response.ok) {
    let payload: any
    try { payload = await response.json() } catch { payload = undefined }
    const statusCode = `HTTP_${response.status}`
    const detail = detailFromPayload(payload, `LEON rejected the request (HTTP ${response.status}).`)
    throw new ApiRequestError(detail, response.status, statusCode, { payload, request_id: response.headers.get('X-Request-ID') ?? requestId })
  }
  return response
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 30_000): Promise<T> {
  const response = await fetchApiResponse(path, init, timeoutMs)

  if (response.status === 204) {
    return undefined as T
  }

  try {
    return (await response.json()) as T
  } catch (error) {
    throw new ApiRequestError('LEON returned an invalid response.', response.status, 'INVALID_RESPONSE', error)
  }
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
export async function fetchMissions(): Promise<Task[]> {
  return request<Task[]>('/missions')
}

export async function pauseMission(id: number): Promise<Task> {
  return request<Task>(`/missions/${id}/pause`, { method: 'POST' })
}

export async function resumeMission(id: number): Promise<Task> {
  return request<Task>(`/missions/${id}/resume`, { method: 'POST' })
}

export async function cancelMission(id: number): Promise<Task> {
  return request<Task>(`/missions/${id}/cancel`, { method: 'POST' })
}

export async function retryMission(id: number): Promise<Task> {
  return request<Task>(`/missions/${id}/retry`, { method: 'POST' })
}

export async function approveMission(id: number): Promise<Task> {
  return request<Task>(`/missions/${id}/approve`, { method: 'POST' })
}

export async function recordImprovementFeedback(payload: {
  request: string
  outcome: string
  rating: number
  comment?: string
  route?: string
  verified?: boolean
}): Promise<void> {
  await request('/improvement/feedback', { method: 'POST', body: JSON.stringify(payload) })
}

export async function fetchMediaStatus(): Promise<MediaStatus> {
  return request<MediaStatus>('/media/status')
}

export async function fetchSpotifyStatus(): Promise<SpotifyStatus> {
  return request<SpotifyStatus>('/media/spotify/status')
}

export async function fetchSpotifyToken(): Promise<{ access_token: string }> {
  return request<{ access_token: string }>('/media/spotify/token')
}

export async function registerSpotifyDevice(deviceId: string, deviceName = 'LEON Player'): Promise<SpotifyStatus> {
  return request<SpotifyStatus>('/media/spotify/device', {
    method: 'POST',
    body: JSON.stringify({ device_id: deviceId, device_name: deviceName }),
  })
}

export async function clearSpotifyDevice(deviceId?: string | null): Promise<void> {
  await request('/media/spotify/device', {
    method: 'DELETE',
    ...(deviceId ? { body: JSON.stringify({ device_id: deviceId }) } : {}),
  })
}

export async function connectSpotify(): Promise<{ authorization_url: string }> {
  return request<{ authorization_url: string }>('/media/spotify/connect', { method: 'POST' })
}

export async function disconnectSpotify(): Promise<void> {
  await request('/media/spotify/disconnect', { method: 'DELETE' })
}

export async function sendCommand(message: string, confirmed = false, confirmationId?: string | null): Promise<CommandResponse> {
  return request<CommandResponse>('/command', {
    method: 'POST',
    body: JSON.stringify({ message, confirmed, ...(confirmationId ? { confirmation_id: confirmationId } : {}) }),
  })
}

export async function fetchMemory(): Promise<Memory[]> {
  return request<Memory[]>('/memory')
}

export async function fetchPersonalProfile(): Promise<{ profile: PersonalProfile; settings: Record<string, unknown>; updated_at: string }> {
  return request<{ profile: PersonalProfile; settings: Record<string, unknown>; updated_at: string }>('/memory/profile')
}

export async function updatePersonalProfile(changes: Partial<PersonalProfile>): Promise<{ profile: PersonalProfile; settings: Record<string, unknown>; updated_at: string }> {
  return request<{ profile: PersonalProfile; settings: Record<string, unknown>; updated_at: string }>('/memory/profile', { method: 'PATCH', body: JSON.stringify(changes) })
}

export async function fetchPersonalMemories(params: { q?: string; category?: string } = {}): Promise<PersonalMemory[]> {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.category && params.category !== 'all') query.set('category', params.category)
  return request<PersonalMemory[]>(`/memory/personal${query.toString() ? `?${query}` : ''}`)
}

export async function forgetPersonalMemory(id: number): Promise<void> {
  await request(`/memory/personal/${id}`, { method: 'DELETE' })
}

export async function fetchRelationships(): Promise<Relationship[]> {
  return request<Relationship[]>('/memory/relationships')
}

export async function fetchImportantDates(): Promise<ImportantDate[]> {
  return request<ImportantDate[]>('/memory/important-dates')
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

export async function sendVoiceTurn(recording: Blob, timeoutMs = 180000): Promise<VoiceTurnResponse> {
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
    }, timeoutMs)
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error('The voice request timed out. Try again.')
    }
    throw error
  } finally {
    window.clearTimeout(timer)
  }
}

export async function synthesizeSpeech(text: string, timeoutMs = 60_000): Promise<Blob> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetchApiResponse('/voice/speech', {
      method: 'POST',
      body: JSON.stringify({ text }),
      signal: controller.signal,
    }, timeoutMs)
    const speech = await response.blob()
    if (speech.size === 0) throw new ApiRequestError('LEON returned an empty audio response.', response.status, 'INVALID_RESPONSE')
    return speech
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

export async function fetchComputerStatus(): Promise<import('../types/api').ComputerStatus> {
  return request<import('../types/api').ComputerStatus>('/computer/status')
}

export async function observeComputer(
  includeVision = true,
  prompt?: string,
  mode = 'screen'
): Promise<import('../types/api').ComputerObservation> {
  return request<import('../types/api').ComputerObservation>('/computer/observe', {
    method: 'POST',
    body: JSON.stringify({ include_vision: includeVision, prompt, mode }),
  })
}

export async function diagnoseComputerScreen(
  question?: string
): Promise<import('../types/api').DiagnosisResponse> {
  return request<import('../types/api').DiagnosisResponse>('/computer/diagnose', {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
}

export async function executeComputerAction(
  action: import('../types/api').ComputerAction,
  confirmed = false
): Promise<import('../types/api').ExecutionResult> {
  return request<import('../types/api').ExecutionResult>('/computer/act', {
    method: 'POST',
    body: JSON.stringify({ action, confirmed }),
  })
}

export async function cancelComputerAction(): Promise<{ status: string; state: string }> {
  return request<{ status: string; state: string }>('/computer/cancel', {
    method: 'POST',
  })
}
