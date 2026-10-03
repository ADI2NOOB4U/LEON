export type LeonState = 'idle' | 'listening' | 'thinking' | 'executing' | 'success' | 'error';

export interface SystemStatus {
  state: LeonState;
  isOnline: boolean;
  uptime: number;
  version: string;
  cpu: number;
  memory: number;
  activeConnections: number;
}

export interface LeonConfig {
  apiUrl: string;
  pollingInterval: number;
  soundEnabled: boolean;
  particleCount: number;
}
