export const COLORS = {
  background: {
    primary: '#0a0a0a',
    secondary: '#121218',
    tertiary: '#1a1a22',
    elevated: 'rgba(20, 20, 30, 0.8)',
    overlay: 'rgba(0, 0, 0, 0.7)'
  },
  text: {
    primary: '#ffffff',
    secondary: '#a0a0a0',
    tertiary: '#666666',
    muted: '#444444'
  },
  state: {
    idle: {
      primary: '#3d5a80',
      accent: '#00a8ff',
      glow: '#0088cc',
      particles: 'rgba(0, 168, 255, 0.3)'
    },
    listening: {
      primary: '#ff6b35',
      accent: '#ffa500',
      glow: '#ff8c00',
      particles: 'rgba(255, 165, 0, 0.4)'
    },
    thinking: {
      primary: '#7c3aed',
      accent: '#a855f7',
      glow: '#d946ef',
      particles: 'rgba(217, 70, 239, 0.35)'
    },
    executing: {
      primary: '#059669',
      accent: '#10b981',
      glow: '#34d399',
      particles: 'rgba(16, 185, 129, 0.4)'
    },
    success: {
      primary: '#047857',
      accent: '#06b6d4',
      glow: '#22d3ee',
      particles: 'rgba(34, 211, 238, 0.35)'
    },
    error: {
      primary: '#7f1d1d',
      accent: '#ef4444',
      glow: '#ff6b6b',
      particles: 'rgba(239, 68, 68, 0.35)'
    }
  },
  semantic: {
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6'
  },
  border: {
    primary: 'rgba(255, 255, 255, 0.1)',
    secondary: 'rgba(255, 255, 255, 0.05)',
    accent: 'rgba(0, 168, 255, 0.3)'
  }
} as const;

export type LeonState = keyof typeof COLORS.state;
export type StateColors = typeof COLORS.state[LeonState];
