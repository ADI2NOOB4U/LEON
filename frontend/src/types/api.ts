export type CoreState = 'idle' | 'thinking' | 'executing' | 'completed' | 'error'

export interface HealthStatus {
  status: string
  service: string
  version: string
}

export type TaskStatus =
  | 'queued'
  | 'planning'
  | 'executing'
  | 'verifying'
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
}

export interface CommandResponse {
  type: 'task' | 'chat'
  message: string
  task?: Task
}
