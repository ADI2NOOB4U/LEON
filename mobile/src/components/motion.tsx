import type { PropsWithChildren } from 'react';
import { useEffect } from 'react';
import { StyleSheet, View, type ViewStyle } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { colors } from '@/theme';
import { useReducedMotion } from '@/hooks/useReducedMotion';

/** A one-time, UI-thread reveal for screen content. */
export function Reveal({ children, delay = 0, style }: PropsWithChildren<{ delay?: number; style?: ViewStyle }>) {
  const reducedMotion = useReducedMotion();
  const progress = useSharedValue(reducedMotion ? 1 : 0);

  useEffect(() => {
    progress.value = reducedMotion ? 1 : withDelay(delay, withTiming(1, { duration: 420, easing: Easing.out(Easing.cubic) }));
  }, [delay, progress, reducedMotion]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: (1 - progress.value) * 12 }],
  }));
  return <Animated.View style={[style, animatedStyle]}>{children}</Animated.View>;
}

/** A low-frequency status light. It avoids timers and runs entirely on the UI thread. */
export function SignalDot({ active = true, color = colors.good }: { active?: boolean; color?: string }) {
  const reducedMotion = useReducedMotion();
  const pulse = useSharedValue(1);
  useEffect(() => {
    pulse.value = !active || reducedMotion
      ? 1
      : withRepeat(withTiming(0.42, { duration: 1250, easing: Easing.inOut(Easing.quad) }), -1, true);
  }, [active, pulse, reducedMotion]);
  const animatedStyle = useAnimatedStyle(() => ({ opacity: pulse.value, transform: [{ scale: 0.72 + pulse.value * 0.28 }] }));
  return <Animated.View style={[styles.signalDot, { backgroundColor: color }, animatedStyle]} />;
}

/** GPU-composited progress transition for task telemetry. */
export function ProgressTrack({ value }: { value: number }) {
  const reducedMotion = useReducedMotion();
  const width = useSharedValue(0);
  const safeValue = Math.max(0, Math.min(100, value));
  useEffect(() => {
    width.value = reducedMotion ? safeValue : withTiming(safeValue, { duration: 550, easing: Easing.out(Easing.cubic) });
  }, [reducedMotion, safeValue, width]);
  const fillStyle = useAnimatedStyle(() => ({ width: `${width.value}%` }));
  return <View style={styles.track}><Animated.View style={[styles.fill, fillStyle]} /></View>;
}

const styles = StyleSheet.create({
  signalDot: { width: 6, height: 6, borderRadius: 3, shadowColor: colors.good, shadowOpacity: 0.75, shadowRadius: 7, elevation: 3 },
  track: { height: 3, borderRadius: 3, overflow: 'hidden', backgroundColor: 'rgba(255,255,255,.1)' },
  fill: { height: '100%', borderRadius: 3, backgroundColor: colors.gold },
});
