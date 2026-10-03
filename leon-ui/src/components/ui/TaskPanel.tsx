import { motion, AnimatePresence } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SPACING } from '../../theme';
import { useLeonStore } from '../../store/useLeonStore';
import { TaskCard } from './TaskCard';

export function TaskPanel() {
  const tasks = useLeonStore((s) => s.tasks);
  const state = useLeonStore((s) => s.state);

  return (
    <motion.aside
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
      style={{
        width: '320px',
        minWidth: '320px',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        padding: SPACING.lg,
        borderLeft: `1px solid ${COLORS.border.secondary}`,
        background: 'rgba(10, 13, 19, 0.82)',
        backdropFilter: 'blur(18px)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          marginBottom: SPACING.xl,
          paddingBottom: SPACING.md,
          borderBottom: `1px solid ${COLORS.border.secondary}`,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontFamily: TYPOGRAPHY.caption.family,
            fontSize: TYPOGRAPHY.caption.size,
            fontWeight: TYPOGRAPHY.caption.weight,
            letterSpacing: '0.12em',
            color: COLORS.text.tertiary,
            textTransform: 'uppercase' as const,
          }}
        >
          MISSIONS
        </h2>
      </div>

      {/* Task List */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        <AnimatePresence mode="popLayout">
          {tasks.length === 0 ? (
            <EmptyState />
          ) : (
            tasks.map((task, i) => (
              <TaskCard key={task.id} task={task} state={state} index={i} />
            ))
          )}
        </AnimatePresence>
      </div>
    </motion.aside>
  );
}

function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.5 }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        textAlign: 'center',
        padding: SPACING.xl,
      }}
    >
      <motion.div
        animate={{ opacity: [0.3, 0.6, 0.3] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          border: `1px solid ${COLORS.border.primary}`,
          marginBottom: SPACING.lg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: COLORS.text.muted,
          }}
        />
      </motion.div>
      <h3
        style={{
          fontFamily: TYPOGRAPHY.subheading.family,
          fontSize: TYPOGRAPHY.metadata.size,
          fontWeight: 600,
          letterSpacing: '0.1em',
          color: COLORS.text.tertiary,
          margin: '0 0 8px 0',
          textTransform: 'uppercase' as const,
        }}
      >
        STANDING BY
      </h3>
      <p
        style={{
          fontFamily: TYPOGRAPHY.body.family,
          fontSize: TYPOGRAPHY.caption.size,
          color: COLORS.text.muted,
          margin: 0,
          lineHeight: 1.6,
        }}
      >
        Nothing in motion.
        <br />
        Send a request to begin.
      </p>
    </motion.div>
  );
}
