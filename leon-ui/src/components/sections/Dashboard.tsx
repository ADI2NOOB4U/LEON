import { motion } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SPACING } from '../../theme';
import { EASING } from '../../theme/easing';
import { useLeonStore } from '../../store/useLeonStore';
import { NeuralLattice } from '../graphics/NeuralLattice';
import { StatusIndicator } from '../ui/StatusIndicator';

export function Dashboard() {
  const state = useLeonStore((s) => s.state);
  const isOnline = useLeonStore((s) => s.isOnline);
  const stateColors = COLORS.state[state];

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background gradient */}
      <motion.div
        animate={{
          background: `radial-gradient(ellipse at center, ${stateColors.glow}08 0%, transparent 70%)`,
        }}
        transition={{ duration: 1.2 }}
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
        }}
      />

      {/* Status */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        style={{
          position: 'absolute',
          top: SPACING.xl,
          display: 'flex',
          alignItems: 'center',
          gap: SPACING.md,
          zIndex: 2,
        }}
      >
        <StatusIndicator state={state} isOnline={isOnline} />
      </motion.div>

      {/* Neural Lattice (Visual Core) */}
      <div
        style={{
          width: '100%',
          height: '100%',
          position: 'absolute',
          inset: 0,
        }}
      >
        <NeuralLattice state={state} />
      </div>

      {/* Center text overlay */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8, duration: 1 }}
        style={{
          position: 'relative',
          zIndex: 2,
          textAlign: 'center',
          pointerEvents: 'none',
          marginTop: '12vh',
          textShadow: `0 0 34px ${stateColors.glow}25`,
        }}
      >
        <motion.h1
          style={{
            fontFamily: TYPOGRAPHY.display.family,
            fontSize: 'clamp(3rem, 8vw, 5rem)',
            fontWeight: TYPOGRAPHY.display.weight,
            letterSpacing: TYPOGRAPHY.display.letterSpacing,
            lineHeight: TYPOGRAPHY.display.lineHeight,
            color: '#f2f7fb',
            margin: 0,
          }}
        >
          {'LEON'.split('').map((char, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                delay: 0.9 + i * 0.08,
                duration: 0.5,
                ease: EASING.smooth,
              }}
              style={{ display: 'inline-block' }}
            >
              {char}
            </motion.span>
          ))}
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.5 }}
          transition={{ delay: 1.5, duration: 0.8 }}
          style={{
            fontFamily: TYPOGRAPHY.metadata.family,
            fontSize: TYPOGRAPHY.metadata.size,
            fontWeight: TYPOGRAPHY.metadata.weight,
            letterSpacing: '0.22em',
            color: COLORS.text.secondary,
            marginTop: SPACING.md,
            textTransform: 'uppercase',
          }}
        >
          Personal AI Operating System
        </motion.p>
      </motion.div>
    </div>
  );
}
