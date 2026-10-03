export type CoreState = 'idle' | 'thinking' | 'executing' | 'completed' | 'error'

export interface HealthStatus {
  status: string
  service: string
  version: string
}

export type TaskStatus =
  | 'queued'
  | 'running'
  | 'waiting'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface Task {
  id: number
  title: string
  status: TaskStatus | string
  progress: number
  current_stage: string
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  result?: string | null
  error?: string | null
  last_activity?: string | null
  summary?: string | null
  artifacts?: TaskArtifact[]
}

export interface TaskArtifact {
  id: number
  task_id: number
  path: string
  type: string
  size: number
  created_at: string
}

export interface CommandResponse {
  type: 'task' | 'chat'
  message: string
  task?: Task
}

export interface MediaStatus {
  success: boolean
  state: string
  provider?: string
  title?: string | null
  artist?: string | null
  message?: string
}

export interface SpotifyStatus {
  configured: boolean
  authenticated: boolean
  requires_auth: boolean
  devices_available?: number
  account_name?: string | null
  device_available?: boolean
  device_name?: string | null
}

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking' | 'error'

export interface VoiceTurnResponse {
  transcript: string
  assistant: string
  audio_base64: string
  audio_content_type: string
  audio_error: string | null
}

export interface VisionResponse {
  success: boolean
  description: string
  observations: string[]
  ocr_text: string | null
  confidence_note: string | null
  model: string
  mode: string
  width: number
  height: number
}

export type VisionMode = 'general' | 'ocr' | 'screen' | 'document' | 'object'

export interface Memory {
  id: number
  type: 'fact' | 'preference' | 'project' | 'note' | string
  content: string
  importance: number
  created_at: string
  updated_at: string
}

export interface NewsSource {
  id: number
  event_id: number
  url: string
  title?: string | null
  publisher?: string | null
  published_at?: string | null
  retrieved_at: string
  source_type: string
  verification_status: string
}

export interface NewsBriefing {
  what_happened?: string | null
  when_it_happened?: string | null
  where?: string | null
  why_it_matters?: string | null
  what_is_confirmed?: string | null
  what_is_uncertain?: string | null
  timeline?: Array<{ label?: string | null; time?: string | null }>
  important_developments?: string[]
  source_links?: Array<{ title?: string | null; url?: string | null }>
  related_coverage?: Array<{ title?: string | null; url?: string | null }>
  map_context?: string | null
}

export interface NewsEvent {
  id: number
  topic: string
  title: string
  importance: 'critical' | 'important' | 'interesting' | 'ignore' | string
  status: string
  summary?: string | null
  location?: string | null
  source_url?: string | null
  source?: string | null
  first_seen_at: string
  last_seen_at: string
  last_alerted_at?: string | null
  alerted: boolean | number
  sources: NewsSource[]
  briefing?: NewsBriefing
}
