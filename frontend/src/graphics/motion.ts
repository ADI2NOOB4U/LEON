import type { Transition, Variants } from 'motion/react'

export type InteractionState =
  | 'idle'
  | 'hover'
  | 'focus'
  | 'listening'
  | 'thinking'
  | 'executing'
  | 'success'
  | 'error'

export const cinematicEase = [0.16, 1, 0.3, 1] as const

export const cinematicTransition: Transition = {
  duration: 0.75,
  ease: cinematicEase,
}

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 14, filter: 'blur(8px)' },
  enter: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { ...cinematicTransition, when: 'beforeChildren', staggerChildren: 0.075 },
  },
  exit: { opacity: 0, y: -10, filter: 'blur(5px)', transition: { duration: 0.28 } },
}

export const panelVariants: Variants = {
  initial: { opacity: 0, y: 18, scale: 0.985 },
  enter: { opacity: 1, y: 0, scale: 1, transition: cinematicTransition },
}

export const itemVariants: Variants = {
  initial: { opacity: 0, y: 10 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.5, ease: cinematicEase } },
}

export const interactionVariants: Variants = {
  idle: { opacity: 0.78, scale: 1 },
  hover: { opacity: 1, scale: 1.04, transition: { duration: 0.2 } },
  focus: { opacity: 1, scale: 1.02, transition: { duration: 0.24 } },
  listening: { opacity: 1, scale: 1.035, transition: { duration: 0.3 } },
  thinking: { opacity: 1, scale: 1.025, transition: { duration: 0.35 } },
  executing: { opacity: 1, scale: 1.045, transition: { duration: 0.5 } },
  success: { opacity: 1, scale: 1.03, transition: { duration: 0.25 } },
  error: { opacity: 0.9, scale: 0.99, transition: { duration: 0.18 } },
}

export const hoverLift = { y: -2, transition: { type: 'spring', stiffness: 420, damping: 26 } }
export const pressIn = { scale: 0.96 }
