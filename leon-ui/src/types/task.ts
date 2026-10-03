export type TaskStatus = 'pending' | 'active' | 'paused' | 'completed' | 'failed';
export type TaskPriority = 'low' | 'medium' | 'high' | 'critical';

export interface TaskStep {
  id: string;
  name: string;
  status: TaskStatus;
  description?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface Task {
  id: string;
  name: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  progress: number;
  currentStep: number;
  totalSteps: number;
  stepName: string;
  steps: TaskStep[];
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  error?: string;
}
