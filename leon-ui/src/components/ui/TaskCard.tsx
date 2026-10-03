import { motion } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SHADOWS, BORDER_RADIUS, type LeonState } from '../../theme';
import { SPRING } from '../../theme/easing';
import type { Task } from '../../types';

interface TaskCardProps {
  task: Task;
  state: LeonState;
  index: number;
}

export function TaskCard({ task, state, index }: TaskCardProps) {
  const stateColors = COLORS.state[state];
  const progress = task.progress / 100;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      transition={{ delay: index * 0.05, ...SPRING.gentle }}
      whileHover={{
        scale: 1.02,
        boxShadow: SHADOWS.lg,
      }}
      style={{
        padding: '20px',
        borderRadius: BORDER_RADIUS.lg,
        background: COLORS.background.tertiary,
        border: `1px solid ${COLORS.border.secondary}`,
        cursor: 'pointer',
        marginBottom: '12px',
      }}
    >
      {/* Task Name */}
      <h3
        style={{
          margin: 0,
          fontFamily: TYPOGRAPHY.subheading.family,
          fontSize: TYPOGRAPHY.subheading.size,
          fontWeight: TYPOGRAPHY.subheading.weight,
          letterSpacing: TYPOGRAPHY.subheading.letterSpacing,
          color: COLORS.text.primary,
          marginBottom: '8px',
        }}
      >
        {task.name.toUpperCase()}
      </h3>

      {/* Step Info */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '12px',
        }}
      >
        <span
          style={{
            fontFamily: TYPOGRAPHY.mono.family,
            fontSize: TYPOGRAPHY.mono.size,
            color: stateColors.accent,
            fontWeight: 600,
          }}
        >
          {String(task.currentStep).padStart(2, '0')} / {String(task.totalSteps).padStart(2, '0')}
        </span>
        <span
          style={{
            color: COLORS.text.muted,
            fontSize: '10px',
          }}
        >
          │
        </span>
        <span
          style={{
            fontFamily: TYPOGRAPHY.metadata.family,
            fontSize: TYPOGRAPHY.metadata.size,
            color: COLORS.text.secondary,
            textTransform: 'uppercase' as const,
            letterSpacing: '0.04em',
          }}
        >
          {task.stepName}
        </span>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: '100%',
          height: '3px',
          borderRadius: '2px',
          background: COLORS.background.secondary,
          overflow: 'hidden',
        }}
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${progress * 100}%` }}
          transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
          style={{
            height: '100%',
            borderRadius: '2px',
            background: `linear-gradient(90deg, ${stateColors.primary}, ${stateColors.accent})`,
            boxShadow: `0 0 8px ${stateColors.glow}60`,
          }}
        />
      </div>
    </motion.div>
  );
}
