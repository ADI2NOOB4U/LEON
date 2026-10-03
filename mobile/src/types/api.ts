export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | string;

export interface LeonTask {
  id: number;
  title: string;
  status: TaskStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
  result: string | null;
  error: string | null;
  progress: number;
  current_stage: string;
  retry_count: number;
  max_retries: number;
  cancel_requested: number;
}

export interface TaskLog { timestamp: string; stage: string; message: string }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; createdAt: number }
export interface HealthResponse { status: 'online' | string; service: string; version: string }
