import { motion } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS } from '../../theme';
import { SPRING } from '../../theme/easing';
import { useLeonStore } from '../../store/useLeonStore';
import { soundSystem } from '../../audio/soundSystem';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    id: 'sanctum',
    label: 'SANCTUM',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L3 7v10l9 5 9-5V7l-9-5z" />
        <path d="M12 22V12" />
        <path d="M3 7l9 5 9-5" />
        <circle cx="12" cy="12" r="2" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    id: 'missions',
    label: 'MISSIONS',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="6" />
        <circle cx="12" cy="12" r="2" fill="currentColor" stroke="none" />
        <line x1="12" y1="2" x2="12" y2="5" />
        <line x1="12" y1="19" x2="12" y2="22" />
        <line x1="2" y1="12" x2="5" y2="12" />
        <line x1="19" y1="12" x2="22" y2="12" />
      </svg>
    ),
  },
  {
    id: 'memory',
    label: 'MEMORY',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2C8 2 4 5 4 9c0 3 2 5 4 6v3h8v-3c2-1 4-3 4-6 0-4-4-7-8-7z" />
        <path d="M9 18h6" />
        <path d="M10 21h4" />
        <path d="M8 9c0-2 2-4 4-4" opacity="0.5" />
      </svg>
    ),
  },
  {
    id: 'systems',
    label: 'SYSTEMS',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="6" r="2" />
        <circle cx="18" cy="6" r="2" />
        <circle cx="6" cy="18" r="2" />
        <circle cx="18" cy="18" r="2" />
        <circle cx="12" cy="12" r="2" />
        <line x1="7.5" y1="7.5" x2="10.5" y2="10.5" />
        <line x1="13.5" y1="10.5" x2="16.5" y2="7.5" />
        <line x1="7.5" y1="16.5" x2="10.5" y2="13.5" />
        <line x1="13.5" y1="13.5" x2="16.5" y2="16.5" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const expanded = useLeonStore((s) => s.sidebarExpanded);
  const activeSection = useLeonStore((s) => s.activeSection);
  const setActiveSection = useLeonStore((s) => s.setActiveSection);
  const toggleSidebar = useLeonStore((s) => s.toggleSidebar);
  const state = useLeonStore((s) => s.state);
  const stateColors = COLORS.state[state];

  return (
    <motion.aside
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0, width: expanded ? 220 : 72 }}
      transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
      onMouseEnter={() => !expanded && toggleSidebar()}
      onMouseLeave={() => expanded && toggleSidebar()}
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: COLORS.background.secondary,
        borderRight: `1px solid ${COLORS.border.secondary}`,
        padding: `${SPACING.lg} ${SPACING.sm}`,
        overflow: 'hidden',
        zIndex: 10,
      }}
    >
      {/* Logo */}
      <motion.div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: SPACING.sm,
          padding: `${SPACING.sm} ${SPACING.sm}`,
          marginBottom: SPACING['2xl'],
        }}
      >
        <motion.div
          animate={{
            boxShadow: `0 0 12px ${stateColors.glow}40`,
          }}
          style={{
            width: 36,
            height: 36,
            borderRadius: BORDER_RADIUS.md,
            background: `linear-gradient(135deg, ${stateColors.primary}, ${stateColors.accent})`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontFamily: TYPOGRAPHY.heading.family,
              fontWeight: 700,
              fontSize: '14px',
              color: '#fff',
              letterSpacing: '-0.02em',
            }}
          >
            L
          </span>
        </motion.div>
        <motion.span
          initial={false}
          animate={{
            opacity: expanded ? 1 : 0,
            width: expanded ? 'auto' : 0,
          }}
          transition={{ duration: 0.2 }}
          style={{
            fontFamily: TYPOGRAPHY.heading.family,
            fontWeight: 700,
            fontSize: '16px',
            color: COLORS.text.primary,
            letterSpacing: '-0.01em',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
          LEON
        </motion.span>
      </motion.div>

      {/* Navigation */}
      <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navItems.map((item) => {
          const isActive = activeSection === item.id;
          return (
            <motion.button
              key={item.id}
              onClick={() => {
                setActiveSection(item.id);
                soundSystem.click();
              }}
              whileHover={{ scale: 1.03, backgroundColor: 'rgba(255, 255, 255, 0.06)' }}
              whileTap={{ scale: 0.97 }}
              transition={SPRING.snappy}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: SPACING.md,
                padding: `${SPACING.sm} ${SPACING.sm}`,
                border: 'none',
                borderRadius: BORDER_RADIUS.md,
                background: isActive ? 'rgba(255, 255, 255, 0.06)' : 'transparent',
                color: isActive ? stateColors.accent : COLORS.text.tertiary,
                cursor: 'pointer',
                width: '100%',
                textAlign: 'left',
                transition: 'color 0.3s',
              }}
            >
              <div style={{ flexShrink: 0, width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {item.icon}
              </div>
              <motion.span
                initial={false}
                animate={{
                  opacity: expanded ? 1 : 0,
                  width: expanded ? 'auto' : 0,
                }}
                transition={{ duration: 0.2 }}
                style={{
                  fontFamily: TYPOGRAPHY.caption.family,
                  fontSize: TYPOGRAPHY.caption.size,
                  fontWeight: TYPOGRAPHY.caption.weight,
                  letterSpacing: '0.08em',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                }}
              >
                {item.label}
              </motion.span>
              {isActive && (
                <motion.div
                  layoutId="activeIndicator"
                  style={{
                    position: 'absolute',
                    left: 0,
                    width: '3px',
                    height: '20px',
                    borderRadius: '0 2px 2px 0',
                    background: stateColors.accent,
                  }}
                  transition={SPRING.snappy}
                />
              )}
            </motion.button>
          );
        })}
      </nav>

      {/* Version */}
      <motion.div
        animate={{ opacity: expanded ? 0.5 : 0 }}
        style={{
          fontFamily: TYPOGRAPHY.mono.family,
          fontSize: '10px',
          color: COLORS.text.muted,
          padding: SPACING.sm,
          letterSpacing: '0.05em',
        }}
      >
        v4.6.0
      </motion.div>
    </motion.aside>
  );
}
