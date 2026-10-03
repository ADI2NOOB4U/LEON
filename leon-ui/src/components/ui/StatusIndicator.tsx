import { motion } from 'framer-motion';
import { COLORS, TYPOGRAPHY, type LeonState } from '../../theme';

interface StatusIndicatorProps {
  state: LeonState;
  isOnline: boolean;
}

const STATE_LABELS: Record<LeonState, string> = {
  idle: 'IDLE',
  listening: 'LISTENING',
  thinking: 'THINKING',
  executing: 'EXECUTING',
  success: 'SUCCESS',
  error: 'ERROR',
};

export function StatusIndicator({ state, isOnline }: StatusIndicatorProps) {
  const stateColors = COLORS.state[state];

  return (
    <motion.div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '6px 16px',
        borderRadius: '999px',
        background: 'rgba(255, 255, 255, 0.03)',
        border: `1px solid ${COLORS.border.secondary}`,
      }}
      animate={{
        borderColor: stateColors.accent + '40',
        boxShadow: `0 0 12px ${stateColors.glow}20`,
      }}
      transition={{ duration: 0.6 }}
    >
      {/* Pulse dot */}
      <motion.div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: isOnline ? stateColors.accent : COLORS.text.muted,
        }}
        animate={{
          boxShadow: isOnline
            ? [
                `0 0 0px ${stateColors.accent}`,
                `0 0 8px ${stateColors.glow}`,
                `0 0 0px ${stateColors.accent}`,
              ]
            : 'none',
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      <span
        style={{
          fontFamily: TYPOGRAPHY.caption.family,
          fontSize: TYPOGRAPHY.caption.size,
          fontWeight: TYPOGRAPHY.caption.weight,
          letterSpacing: '0.08em',
          color: isOnline ? stateColors.accent : COLORS.text.muted,
          textTransform: 'uppercase' as const,
        }}
      >
        {isOnline ? STATE_LABELS[state] : 'OFFLINE'}
      </span>
    </motion.div>
  );
}
