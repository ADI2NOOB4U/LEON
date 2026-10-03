import { create } from 'zustand';
import type { LeonState, SystemStatus, Task } from '../types';

interface LeonStore {
  // System state
  state: LeonState;
  isOnline: boolean;
  systemStatus: SystemStatus | null;
  
  // Tasks
  tasks: Task[];
  activeTask: Task | null;
  
  // UI state
  sidebarExpanded: boolean;
  activeSection: string;
  commandFocused: boolean;
  soundEnabled: boolean;
  
  // Actions
  setState: (state: LeonState) => void;
  setOnline: (isOnline: boolean) => void;
  setSystemStatus: (status: SystemStatus) => void;
  setTasks: (tasks: Task[]) => void;
  setActiveTask: (task: Task | null) => void;
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  removeTask: (id: string) => void;
  toggleSidebar: () => void;
  setActiveSection: (section: string) => void;
  setCommandFocused: (focused: boolean) => void;
  toggleSound: () => void;
}

export const useLeonStore = create<LeonStore>((set) => ({
  // System state
  state: 'idle',
  isOnline: false,
  systemStatus: null,
  
  // Tasks
  tasks: [],
  activeTask: null,
  
  // UI state
  sidebarExpanded: false,
  activeSection: 'sanctum',
  commandFocused: false,
  soundEnabled: true,
  
  // Actions
  setState: (state) => set({ state }),
  setOnline: (isOnline) => set({ isOnline }),
  setSystemStatus: (systemStatus) => set({ systemStatus }),
  setTasks: (tasks) => set({ tasks }),
  setActiveTask: (activeTask) => set({ activeTask }),
  addTask: (task) => set((s) => ({ tasks: [...s.tasks, task] })),
  updateTask: (id, updates) => set((s) => ({
    tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    activeTask: s.activeTask?.id === id ? { ...s.activeTask, ...updates } : s.activeTask,
  })),
  removeTask: (id) => set((s) => ({
    tasks: s.tasks.filter((t) => t.id !== id),
    activeTask: s.activeTask?.id === id ? null : s.activeTask,
  })),
  toggleSidebar: () => set((s) => ({ sidebarExpanded: !s.sidebarExpanded })),
  setActiveSection: (activeSection) => set({ activeSection }),
  setCommandFocused: (commandFocused) => set({ commandFocused }),
  toggleSound: () => set((s) => ({ soundEnabled: !s.soundEnabled })),
}));
