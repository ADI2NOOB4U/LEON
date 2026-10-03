import { motion } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS } from '../../theme';
import { SPRING } from '../../theme/easing';

interface MemoryItem {
  id: string;
  category: string;
  title: string;
  tags: string[];
  importance: number;
  accessCount: number;
}

const MOCK_MEMORIES: MemoryItem[] = [
  {
    id: '1',
    category: 'knowledge',
    title: 'React performance optimization patterns',
    tags: ['react', 'performance', 'memoization'],
    importance: 0.9,
    accessCount: 14,
  },
  {
    id: '2',
    category: 'preference',
    title: 'User prefers dark mode interfaces',
    tags: ['ui', 'preference', 'dark-mode'],
    importance: 0.7,
    accessCount: 8,
  },
  {
    id: '3',
    category: 'skill',
    title: 'Three.js shader programming techniques',
    tags: ['3d', 'shaders', 'webgl'],
    importance: 0.85,
    accessCount: 11,
  },
  {
    id: '4',
    category: 'conversation',
    title: 'Discussion about neural network architectures',
    tags: ['ai', 'neural-nets', 'deep-learning'],
    importance: 0.6,
    accessCount: 3,
  },
];

const CATEGORY_COLORS: Record<string, string> = {
  knowledge: '#3b82f6',
  preference: '#f59e0b',
  skill: '#10b981',
  conversation: '#8b5cf6',
};

export function MemoryView() {
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
        Memory
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
        Knowledge graph · {MOCK_MEMORIES.length} entries stored
      </motion.p>

      {/* Category Pills */}
      <div style={{ display: 'flex', gap: SPACING.sm, marginBottom: SPACING.xl, flexWrap: 'wrap' }}>
        {Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
          <motion.div
            key={cat}
            whileHover={{ scale: 1.05 }}
            transition={SPRING.snappy}
            style={{
              padding: `4px 12px`,
              borderRadius: BORDER_RADIUS.full,
              border: `1px solid ${color}40`,
              background: `${color}10`,
              fontFamily: TYPOGRAPHY.caption.family,
              fontSize: '11px',
              fontWeight: 500,
              letterSpacing: '0.06em',
              color: color,
              textTransform: 'uppercase' as const,
              cursor: 'pointer',
            }}
          >
            {cat}
          </motion.div>
        ))}
      </div>

      {/* Memory Items */}
      {MOCK_MEMORIES.map((mem, i) => (
        <motion.div
          key={mem.id}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.08 }}
          whileHover={{ scale: 1.01, backgroundColor: COLORS.background.tertiary }}
          style={{
            padding: SPACING.lg,
            borderRadius: BORDER_RADIUS.lg,
            border: `1px solid ${COLORS.border.secondary}`,
            marginBottom: SPACING.md,
            cursor: 'pointer',
            background: 'transparent',
            transition: 'background 0.2s',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: SPACING.sm, marginBottom: SPACING.sm }}>
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: CATEGORY_COLORS[mem.category] || COLORS.text.muted,
              }}
            />
            <span
              style={{
                fontFamily: TYPOGRAPHY.caption.family,
                fontSize: '10px',
                fontWeight: 600,
                letterSpacing: '0.08em',
                color: CATEGORY_COLORS[mem.category] || COLORS.text.muted,
                textTransform: 'uppercase' as const,
              }}
            >
              {mem.category}
            </span>
            <div style={{ flex: 1 }} />
            <span
              style={{
                fontFamily: TYPOGRAPHY.mono.family,
                fontSize: '10px',
                color: COLORS.text.muted,
              }}
            >
              ×{mem.accessCount}
            </span>
          </div>

          <h3
            style={{
              fontFamily: TYPOGRAPHY.body.family,
              fontSize: TYPOGRAPHY.body.size,
              fontWeight: 500,
              color: COLORS.text.primary,
              margin: `0 0 ${SPACING.sm} 0`,
            }}
          >
            {mem.title}
          </h3>

          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {mem.tags.map((tag) => (
              <span
                key={tag}
                style={{
                  fontFamily: TYPOGRAPHY.mono.family,
                  fontSize: '10px',
                  color: COLORS.text.muted,
                  padding: '2px 8px',
                  borderRadius: BORDER_RADIUS.sm,
                  background: COLORS.background.tertiary,
                }}
              >
                {tag}
              </span>
            ))}
          </div>

          {/* Importance bar */}
          <div
            style={{
              marginTop: SPACING.sm,
              width: '100%',
              height: '2px',
              borderRadius: '1px',
              background: COLORS.background.tertiary,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${mem.importance * 100}%`,
                background: CATEGORY_COLORS[mem.category] || COLORS.text.muted,
                borderRadius: '1px',
                opacity: 0.5,
              }}
            />
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
