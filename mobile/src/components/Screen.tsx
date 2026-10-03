import type { PropsWithChildren } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CelestialBackground } from './CelestialBackground';

export function Screen({ children, scroll = true }: PropsWithChildren<{ scroll?: boolean }>) {
  const content = <View style={styles.content}>{children}</View>;
  return <SafeAreaView edges={['top']} style={styles.safe}><CelestialBackground />{scroll ? <ScrollView contentContainerStyle={styles.scroll}>{content}</ScrollView> : content}</SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: '#070914' }, scroll: { flexGrow: 1, paddingBottom: 105 }, content: { flex: 1, paddingHorizontal: 20, paddingTop: 12 } });
