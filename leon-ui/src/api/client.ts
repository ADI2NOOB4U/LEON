import axios from 'axios';
import type { SystemStatus, Task } from '../types';
import type { PersonalMemory, UserProfile } from '../types/memory';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

export async function getSystemStatus(): Promise<SystemStatus> {
  const { data } = await api.get('/health');
  return {
    state: data.status === 'online' ? 'idle' : 'error',
    isOnline: data.status === 'online',
    uptime: 0,
    version: data.version,
    cpu: 0,
    memory: 0,
    activeConnections: 0,
  };
}

export async function getTasks(): Promise<Task[]> {
  const { data } = await api.get('/tasks');
  return data;
}

export async function createTask(prompt: string): Promise<Task> {
  const { data } = await api.post('/tasks', { title: prompt });
  return data;
}

export async function getTask(id: string): Promise<Task> {
  const { data } = await api.get(`/tasks/${id}`);
  return data;
}

export async function cancelTask(id: string): Promise<void> {
  await api.post(`/tasks/${id}/cancel`);
}

export async function sendCommand(command: string): Promise<{ message: string; type: string; task?: Task; mission?: Task }> {
  const { data } = await api.post('/command', { message: command });
  return data;
}

export async function getPersonalProfile(): Promise<{ profile: UserProfile; settings: Record<string, boolean> }> {
  const { data } = await api.get('/api/memory/profile');
  return data;
}

export async function getPersonalMemories(q?: string): Promise<PersonalMemory[]> {
  const { data } = await api.get('/api/memory/personal', { params: q ? { q } : undefined });
  return data;
}

export async function forgetPersonalMemory(id: number): Promise<void> {
  await api.delete(`/api/memory/personal/${id}`);
}

export { api };
