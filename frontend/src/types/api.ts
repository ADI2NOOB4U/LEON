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

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking' | 'error'

export interface VoiceTurnResponse {
  transcript: string
  assistant: string
  audio_base64: string
  audio_content_type: string
  audio_error: string | null
}

export interface Memory {
  id: number
  type: 'fact' | 'preference' | 'project' | 'note' | string
  content: string
  importance: number
  created_at: string
  updated_at: string
}
