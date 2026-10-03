import { motion } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS } from '../../theme';
import { SPRING } from '../../theme/easing';
import { useLeonStore } from '../../store/useLeonStore';

interface SystemMetric {
  label: string;
  value: string;
  unit: string;
  percentage: number;
  color: string;
}

export function SystemsView() {
  const state = useLeonStore((s) => s.state);
  const isOnline = useLeonStore((s) => s.isOnline);
  const soundEnabled = useLeonStore((s) => s.soundEnabled);
  const toggleSound = useLeonStore((s) => s.toggleSound);
  const setState = useLeonStore((s) => s.setState);
  const stateColors = COLORS.state[state];

  const metrics: SystemMetric[] = [
    { label: 'CPU', value: '23', unit: '%', percentage: 0.23, color: COLORS.semantic.info },
    { label: 'MEMORY', value: '1.2', unit: 'GB', percentage: 0.38, color: COLORS.semantic.warning },
    { label: 'NETWORK', value: isOnline ? '142' : '0', unit: 'ms', percentage: isOnline ? 0.14 : 0, color: COLORS.semantic.success },
    { label: 'STORAGE', value: '45', unit: 'GB', percentage: 0.56, color: '#8b5cf6' },
  ];

  const states: Array<{ key: string; label: string }> = [
    { key: 'idle', label: 'IDLE' },
    { key: 'listening', label: 'LISTENING' },
    { key: 'thinking', label: 'THINKING' },
    { key: 'executing', label: 'EXECUTING' },
    { key: 'success', label: 'SUCCESS' },
    { key: 'error', label: 'ERROR' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{
        flex: 1,
        padding: SPACING['2xl'],
        overflowY: 'auto',
      }}
    >
      {/* Header */}
      <motion.h1
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          fontFamily: TYPOGRAPHY.heading.family,
          fontSize: TYPOGRAPHY.heading.size,
          fontWeight: TYPOGRAPHY.heading.weight,
          letterSpacing: TYPOGRAPHY.heading.letterSpacing,
          color: COLORS.text.primary,
          marginBottom: SPACING.sm,
        }}
      >
        Systems
      </motion.h1>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.6 }}
        transition={{ delay: 0.1 }}
        style={{
          fontFamily: TYPOGRAPHY.body.family,
          fontSize: TYPOGRAPHY.metadata.size,
          color: COLORS.text.tertiary,
          marginBottom: SPACING['2xl'],
        }}
      >
        System diagnostics & configuration
      </motion.p>

      {/* Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: SPACING.md,
          marginBottom: SPACING['2xl'],
        }}
      >
        {metrics.map((metric, i) => (
          <motion.div
            key={metric.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ scale: 1.02 }}
            style={{
              padding: SPACING.lg,
              borderRadius: BORDER_RADIUS.lg,
              background: COLORS.background.tertiary,
              border: `1px solid ${COLORS.border.secondary}`,
            }}
          >
            <div
              style={{
                fontFamily: TYPOGRAPHY.caption.family,
                fontSize: '10px',
                fontWeight: 600,
                letterSpacing: '0.1em',
                color: COLORS.text.muted,
                marginBottom: SPACING.sm,
              }}
            >
              {metric.label}
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: '4px',
                marginBottom: SPACING.sm,
              }}
            >
              <span
                style={{
                  fontFamily: TYPOGRAPHY.mono.family,
                  fontSize: '1.5rem',
                  fontWeight: 700,
                  color: metric.color,
                }}
              >
                {metric.value}
              </span>
              <span
                style={{
                  fontFamily: TYPOGRAPHY.mono.family,
                  fontSize: '0.75rem',
                  color: COLORS.text.muted,
                }}
              >
                {metric.unit}
              </span>
            </div>
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
                animate={{ width: `${metric.percentage * 100}%` }}
                transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: [0.25, 0.46, 0.45, 0.94] }}
                style={{
                  height: '100%',
                  borderRadius: '2px',
                  background: metric.color,
                }}
              />
            </div>
          </motion.div>
        ))}
      </div>

      {/* State Switcher (Demo) */}
      <div style={{ marginBottom: SPACING['2xl'] }}>
        <h3
          style={{
            fontFamily: TYPOGRAPHY.caption.family,
            fontSize: TYPOGRAPHY.caption.size,
            fontWeight: 600,
            letterSpacing: '0.1em',
            color: COLORS.text.tertiary,
            marginBottom: SPACING.md,
          }}
        >
          STATE CONTROL
        </h3>
        <div style={{ display: 'flex', gap: SPACING.sm, flexWrap: 'wrap' }}>
          {states.map((s) => {
            const isActive = state === s.key;
            const sColor = COLORS.state[s.key as keyof typeof COLORS.state].accent;
            return (
              <motion.button
                key={s.key}
                onClick={() => setState(s.key as any)}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                transition={SPRING.snappy}
                style={{
                  padding: '6px 14px',
                  borderRadius: BORDER_RADIUS.md,
                  border: `1px solid ${isActive ? sColor : COLORS.border.secondary}`,
                  background: isActive ? `${sColor}20` : 'transparent',
                  color: isActive ? sColor : COLORS.text.muted,
                  fontFamily: TYPOGRAPHY.caption.family,
                  fontSize: '11px',
                  fontWeight: 600,
                  letterSpacing: '0.06em',
                  cursor: 'pointer',
                }}
              >
                {s.label}
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Settings */}
      <div>
        <h3
          style={{
            fontFamily: TYPOGRAPHY.caption.family,
            fontSize: TYPOGRAPHY.caption.size,
            fontWeight: 600,
            letterSpacing: '0.1em',
            color: COLORS.text.tertiary,
            marginBottom: SPACING.md,
          }}
        >
          CONFIGURATION
        </h3>

        {/* Sound Toggle */}
        <motion.div
          whileHover={{ backgroundColor: COLORS.background.tertiary }}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: SPACING.md,
            borderRadius: BORDER_RADIUS.lg,
            border: `1px solid ${COLORS.border.secondary}`,
            cursor: 'pointer',
            marginBottom: SPACING.sm,
          }}
          onClick={toggleSound}
        >
          <div>
            <div
              style={{
                fontFamily: TYPOGRAPHY.body.family,
                fontSize: TYPOGRAPHY.metadata.size,
                fontWeight: 500,
                color: COLORS.text.primary,
                marginBottom: '2px',
              }}
            >
              Sound Effects
            </div>
            <div
              style={{
                fontFamily: TYPOGRAPHY.caption.family,
                fontSize: '11px',
                color: COLORS.text.muted,
              }}
            >
              UI interaction sounds
            </div>
          </div>
          <motion.div
            animate={{
              background: soundEnabled ? stateColors.accent : COLORS.text.muted,
            }}
            style={{
              width: 36,
              height: 20,
              borderRadius: BORDER_RADIUS.full,
              padding: '2px',
              display: 'flex',
              alignItems: soundEnabled ? 'center' : 'center',
              justifyContent: soundEnabled ? 'flex-end' : 'flex-start',
            }}
          >
            <motion.div
              layout
              transition={SPRING.snappy}
              style={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                background: '#fff',
              }}
            />
          </motion.div>
        </motion.div>

        {/* Connection Status */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: SPACING.md,
            borderRadius: BORDER_RADIUS.lg,
            border: `1px solid ${COLORS.border.secondary}`,
          }}
        >
          <div>
            <div
              style={{
                fontFamily: TYPOGRAPHY.body.family,
                fontSize: TYPOGRAPHY.metadata.size,
                fontWeight: 500,
                color: COLORS.text.primary,
                marginBottom: '2px',
              }}
            >
              API Connection
            </div>
            <div
              style={{
                fontFamily: TYPOGRAPHY.mono.family,
                fontSize: '11px',
                color: COLORS.text.muted,
              }}
            >
              127.0.0.1:8000
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: isOnline ? COLORS.semantic.success : COLORS.semantic.error,
              }}
            />
            <span
              style={{
                fontFamily: TYPOGRAPHY.caption.family,
                fontSize: '11px',
                fontWeight: 500,
                color: isOnline ? COLORS.semantic.success : COLORS.semantic.error,
                letterSpacing: '0.04em',
              }}
            >
              {isOnline ? 'CONNECTED' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
