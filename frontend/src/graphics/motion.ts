import type { Transition, Variants } from 'motion/react'

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

export const hoverLift = { y: -2, transition: { type: 'spring', stiffness: 420, damping: 26 } }
export const pressIn = { scale: 0.96 }
