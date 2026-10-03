import type { HealthResponse, LeonTask, TaskLog } from '@/types/api';

const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000').replace(/\/$/, '');

class ApiError extends Error {
  constructor(message: string, public readonly status?: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { headers: { 'Content-Type': 'application/json', ...init?.headers }, ...init });
  } catch {
    throw new ApiError('Unable to reach LEON. Check the connection address.');
  }
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(body || 'The request could not be completed.', response.status);
  }
  return response.json() as Promise<T>;
}

export const leonApi = {
  health: () => request<HealthResponse>('/health'),
  tasks: () => request<LeonTask[]>('/tasks'),
  task: (id: number) => request<LeonTask>(`/tasks/${id}`),
  taskLogs: (id: number) => request<TaskLog[]>(`/tasks/${id}/logs`),
  cancelTask: (id: number) => request<LeonTask>(`/tasks/${id}/cancel`, { method: 'POST' }),
  chat: (message: string) => request<{ assistant: string; provider: string }>('/chat', { method: 'POST', body: JSON.stringify({ message }) }),
};

export { API_URL, ApiError };
