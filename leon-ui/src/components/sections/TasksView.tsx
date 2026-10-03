import { motion, AnimatePresence } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS } from '../../theme';
import { SPRING } from '../../theme/easing';
import { useLeonStore } from '../../store/useLeonStore';
import { TaskCard } from '../ui/TaskCard';

export function TasksView() {
  const tasks = useLeonStore((s) => s.tasks);
  const state = useLeonStore((s) => s.state);
  const stateColors = COLORS.state[state];

  const activeTasks = tasks.filter((t) => t.status === 'active');
  const completedTasks = tasks.filter((t) => t.status === 'completed');
  const failedTasks = tasks.filter((t) => t.status === 'failed');

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
          marginBottom: SPACING.xl,
        }}
      >
        Missions
      </motion.h1>

      {/* Stats */}
      <div
        style={{
          display: 'flex',
          gap: SPACING.md,
          marginBottom: SPACING['2xl'],
        }}
      >
        {[
          { label: 'ACTIVE', count: activeTasks.length, color: stateColors.accent },
          { label: 'COMPLETED', count: completedTasks.length, color: COLORS.semantic.success },
          { label: 'FAILED', count: failedTasks.length, color: COLORS.semantic.error },
        ].map((stat) => (
          <motion.div
            key={stat.label}
            whileHover={{ scale: 1.02 }}
            transition={SPRING.snappy}
            style={{
              padding: `${SPACING.md} ${SPACING.lg}`,
              borderRadius: BORDER_RADIUS.lg,
              background: COLORS.background.tertiary,
              border: `1px solid ${COLORS.border.secondary}`,
              flex: 1,
            }}
          >
            <div
              style={{
                fontFamily: TYPOGRAPHY.mono.family,
                fontSize: '1.5rem',
                fontWeight: 700,
                color: stat.color,
                marginBottom: '4px',
              }}
            >
              {String(stat.count).padStart(2, '0')}
            </div>
            <div
              style={{
                fontFamily: TYPOGRAPHY.caption.family,
                fontSize: TYPOGRAPHY.caption.size,
                letterSpacing: '0.08em',
                color: COLORS.text.muted,
              }}
            >
              {stat.label}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Task List */}
      <AnimatePresence mode="popLayout">
        {tasks.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{
              textAlign: 'center',
              padding: SPACING['3xl'],
              color: COLORS.text.muted,
              fontFamily: TYPOGRAPHY.body.family,
            }}
          >
            No missions yet. Use the command bar to create one.
          </motion.div>
        ) : (
          tasks.map((task, i) => (
            <TaskCard key={task.id} task={task} state={state} index={i} />
          ))
        )}
      </AnimatePresence>
    </motion.div>
  );
}
