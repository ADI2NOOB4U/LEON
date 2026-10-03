import axios from 'axios';
import type { SystemStatus, Task } from '../types';

const API_BASE = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

export async function getSystemStatus(): Promise<SystemStatus> {
  const { data } = await api.get('/api/status');
  return data;
}

export async function getTasks(): Promise<Task[]> {
  const { data } = await api.get('/api/tasks');
  return data;
}

export async function createTask(prompt: string): Promise<Task> {
  const { data } = await api.post('/api/tasks', { prompt });
  return data;
}

export async function getTask(id: string): Promise<Task> {
  const { data } = await api.get(`/api/tasks/${id}`);
  return data;
}

export async function cancelTask(id: string): Promise<void> {
  await api.delete(`/api/tasks/${id}`);
}

export async function sendCommand(command: string): Promise<{ response: string; state: string }> {
  const { data } = await api.post('/api/command', { command });
  return data;
}

export { api };
