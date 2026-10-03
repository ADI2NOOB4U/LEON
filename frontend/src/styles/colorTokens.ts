export type LeonVisualState = 'idle' | 'listening' | 'thinking' | 'executing' | 'success' | 'error' | 'offline'

export const COLORS: Record<LeonVisualState, { primary: string; accent: string; particle: string; glow: string }> = {
  idle: { primary: '#111a2c', accent: '#5677b8', particle: '#76c8ff', glow: 'rgba(76, 135, 222, .26)' },
  listening: { primary: '#301b16', accent: '#ff9d4d', particle: '#ffd36a', glow: 'rgba(255, 137, 54, .36)' },
  thinking: { primary: '#241534', accent: '#b66cff', particle: '#ef8cff', glow: 'rgba(174, 74, 255, .34)' },
  executing: { primary: '#092b25', accent: '#37d69a', particle: '#7dffca', glow: 'rgba(27, 222, 157, .34)' },
  success: { primary: '#17311e', accent: '#9ae66b', particle: '#dcff9c', glow: 'rgba(145, 231, 91, .34)' },
  error: { primary: '#351a1a', accent: '#ff775f', particle: '#ffb06a', glow: 'rgba(255, 80, 61, .3)' },
  offline: { primary: '#202126', accent: '#89909d', particle: '#a4abb5', glow: 'rgba(130, 140, 153, .18)' },
}
