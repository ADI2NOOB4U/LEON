import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { COLORS } from '../../theme';
import { useLeonStore } from '../../store/useLeonStore';

export function CustomCursor() {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isPressed, setIsPressed] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [visible, setVisible] = useState(true);
  const state = useLeonStore((s) => s.state);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    setPosition({ x: e.clientX, y: e.clientY });
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mousedown', () => setIsPressed(true));
    window.addEventListener('mouseup', () => setIsPressed(false));
    window.addEventListener('mouseleave', () => setVisible(false));
    window.addEventListener('mouseenter', () => setVisible(true));

    // Detect hoverable elements
    const observer = new MutationObserver(() => {
      document.querySelectorAll('button, a, input, [data-hoverable]').forEach((el) => {
        el.addEventListener('mouseenter', () => setIsHovering(true));
        el.addEventListener('mouseleave', () => setIsHovering(false));
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      observer.disconnect();
    };
  }, [handleMouseMove]);

  if (!visible) return null;

  const accent = COLORS.state[state]?.accent || COLORS.state.idle.accent;

  return (
    <>
      {/* Main dot */}
      <motion.div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          pointerEvents: 'none',
          zIndex: 99999,
          mixBlendMode: 'screen',
        }}
        animate={{
          x: position.x - 10,
          y: position.y - 10,
          scale: isPressed ? 0.7 : isHovering ? 1.3 : 1,
        }}
        transition={{ type: 'spring', stiffness: 500, damping: 28, mass: 0.5 }}
      >
        <svg width="20" height="20" viewBox="0 0 20 20">
          <circle cx="10" cy="10" r="2" fill={accent} />
          <circle
            cx="10"
            cy="10"
            r="6"
            fill="none"
            stroke={accent}
            strokeWidth="0.5"
            opacity={isHovering ? 0.8 : 0.3}
          />
        </svg>
      </motion.div>
      {/* Trail ring */}
      <motion.div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          pointerEvents: 'none',
          zIndex: 99998,
        }}
        animate={{
          x: position.x - 20,
          y: position.y - 20,
          scale: isHovering ? 1.5 : 1,
          opacity: isPressed ? 0.2 : 0.15,
        }}
        transition={{ type: 'spring', stiffness: 150, damping: 15, mass: 1 }}
      >
        <svg width="40" height="40" viewBox="0 0 40 40">
          <circle
            cx="20"
            cy="20"
            r="12"
            fill="none"
            stroke={accent}
            strokeWidth="0.5"
          />
        </svg>
      </motion.div>
    </>
  );
}
