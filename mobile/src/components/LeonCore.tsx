import { Canvas, Circle, Group, Paint, RadialGradient, vec } from '@shopify/react-native-skia';
import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming } from 'react-native-reanimated';
import { useReducedMotion } from '@/hooks/useReducedMotion';

export function LeonCore({ size = 222, active = false }: { size?: number; active?: boolean }) {
  const reducedMotion = useReducedMotion();
  const breath = useSharedValue(1);
  useEffect(() => {
    if (!reducedMotion) breath.value = withRepeat(withSequence(withTiming(active ? 1.06 : 1.035, { duration: active ? 1450 : 2900 }), withTiming(1, { duration: active ? 1450 : 2900 })), -1, false);
  }, [active, breath, reducedMotion]);
  const auraStyle = useAnimatedStyle(() => ({ transform: [{ scale: breath.value }], opacity: 0.55 + (breath.value - 1) * 8 }));
  const half = size / 2;
  return (
    <Animated.View accessible accessibilityLabel="LEON core" style={[styles.shell, { width: size, height: size }, auraStyle]}>
      <Canvas style={{ width: size, height: size }}>
        <Circle cx={half} cy={half} r={half * .96} color="rgba(201, 169, 107, .05)" />
        <Circle cx={half} cy={half} r={half * .78} color="rgba(174, 148, 244, .08)" />
        <Circle cx={half} cy={half} r={half * .64} color="rgba(201, 169, 107, .06)" />
        <Circle cx={half} cy={half} r={half * .54}>
          <Paint><RadialGradient c={vec(half * .76, half * .68)} r={half * .76} colors={['#F3DEAC', '#C1A36B', '#53576A', '#171A28']} /></Paint>
        </Circle>
        <Group opacity={.76}><Circle cx={half} cy={half} r={half * .27} color="#E7E2D4" /><Circle cx={half * .88} cy={half * .84} r={half * .11} color="#FFF8DD" /></Group>
      </Canvas>
    </Animated.View>
  );
}
const styles = StyleSheet.create({ shell: { alignItems: 'center', justifyContent: 'center' } });
