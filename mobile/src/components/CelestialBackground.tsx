import { Canvas, Circle, Group, Paint, RadialGradient, vec } from '@shopify/react-native-skia';
import { StyleSheet, View } from 'react-native';

export function CelestialBackground() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <Canvas style={StyleSheet.absoluteFill}>
        <Circle cx={310} cy={110} r={310}>
          <Paint><RadialGradient c={vec(310, 110)} r={310} colors={['#2D2B5A', '#11172E', '#070914']} /></Paint>
        </Circle>
        <Group opacity={0.45}>
          <Circle cx={38} cy={220} r={1.4} color="#EAE6D8" /><Circle cx={314} cy={300} r={1} color="#EAE6D8" />
          <Circle cx={270} cy={83} r={1.2} color="#B7D4FF" /><Circle cx={67} cy={430} r={.8} color="#B7D4FF" />
          <Circle cx={337} cy={612} r={1} color="#E9C787" /><Circle cx={150} cy={95} r={.75} color="#E9C787" />
        </Group>
      </Canvas>
    </View>
  );
}
