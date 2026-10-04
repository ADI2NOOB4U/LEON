import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS, SHADOWS } from '../../theme';
import { SPRING } from '../../theme/easing';
import { useLeonStore } from '../../store/useLeonStore';
import { soundSystem } from '../../audio/soundSystem';
import { sendCommand } from '../../api/client';

export function CommandBar() {
  const [input, setInput] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const state = useLeonStore((s) => s.state);
  const setState = useLeonStore((s) => s.setState);
  const stateColors = COLORS.state[state];

  const handleSubmit = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isSubmitting) return;

    soundSystem.send();
    setIsSubmitting(true);
    setState('thinking');

    setInput('');

    try {
      await sendCommand(trimmed);
      setState('success');
      soundSystem.success();
    } catch {
      setState('error');
      soundSystem.error();
    } finally {
      setIsSubmitting(false);
    }
  }, [input, isSubmitting, setState]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5, duration: 0.5 }}
      style={{
        padding: `${SPACING.md} ${SPACING.xl}`,
        borderTop: `1px solid ${COLORS.border.secondary}`,
        background: COLORS.background.secondary,
      }}
    >
      <motion.div
        animate={{
          boxShadow: isFocused
            ? `0 0 0 1px ${stateColors.accent}40, ${SHADOWS.glow}`
            : `0 0 0 1px ${COLORS.border.secondary}`,
        }}
        transition={{ duration: 0.3 }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: SPACING.md,
          padding: `${SPACING.sm} ${SPACING.lg}`,
          borderRadius: BORDER_RADIUS.lg,
          background: COLORS.background.tertiary,
        }}
      >
        {/* State indicator */}
        <motion.div
          animate={{
            background: stateColors.accent,
            boxShadow: `0 0 8px ${stateColors.glow}`,
          }}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            flexShrink: 0,
          }}
        />

        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder="Give LEON a task or ask a question"
          disabled={isSubmitting}
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontFamily: TYPOGRAPHY.body.family,
            fontSize: TYPOGRAPHY.body.size,
            color: COLORS.text.primary,
            caretColor: stateColors.accent,
          }}
        />

        {/* Submit button */}
        <AnimatePresence>
          {(input.trim() || isSubmitting) && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              transition={SPRING.snappy}
              onClick={handleSubmit}
              disabled={isSubmitting}
              style={{
                border: 'none',
                borderRadius: BORDER_RADIUS.md,
                background: isSubmitting ? COLORS.text.muted : stateColors.accent,
                color: '#000',
                padding: '6px 16px',
                fontFamily: TYPOGRAPHY.caption.family,
                fontSize: TYPOGRAPHY.caption.size,
                fontWeight: 600,
                letterSpacing: '0.05em',
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {isSubmitting ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  style={{ width: 12, height: 12, border: '2px solid #000', borderTopColor: 'transparent', borderRadius: '50%' }}
                />
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
            </motion.button>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Keyboard hint */}
      <motion.div
        animate={{ opacity: isFocused ? 0.4 : 0 }}
        style={{
          textAlign: 'center',
          marginTop: '6px',
          fontFamily: TYPOGRAPHY.mono.family,
          fontSize: '10px',
          color: COLORS.text.muted,
        }}
      >
        Press Enter to send · Esc to cancel
      </motion.div>
    </motion.div>
  );
}
