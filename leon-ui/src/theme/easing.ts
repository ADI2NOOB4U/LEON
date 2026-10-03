export const EASING = {
  smooth: [0.25, 0.46, 0.45, 0.94] as const,
  bounce: [0.68, -0.55, 0.265, 1.55] as const,
  snappy: [0.34, 1.56, 0.64, 1] as const,
  decelerate: [0.25, 0.46, 0.45, 0.94] as const,
  accelerate: [0.4, 0, 1, 1] as const,
} as const;

export const SPRING = {
  gentle: { type: 'spring' as const, stiffness: 100, damping: 15 },
  snappy: { type: 'spring' as const, stiffness: 300, damping: 20 },
  bouncy: { type: 'spring' as const, stiffness: 200, damping: 10 },
  stiff: { type: 'spring' as const, stiffness: 400, damping: 30 },
} as const;

export const DURATION = {
  micro: 0.15,
  fast: 0.25,
  normal: 0.4,
  slow: 0.6,
  state: 0.8,
  hero: 1.2,
} as const;
