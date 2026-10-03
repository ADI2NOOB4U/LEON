import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/theme';
import type { RootScreen } from '@/LeonApp';

const items: Array<{ key: RootScreen; label: string; glyph: string }> = [
  { key: 'home', label: 'Orbit', glyph: '◉' }, { key: 'tasks', label: 'Missions', glyph: '◇' }, { key: 'chat', label: 'Signal', glyph: '◌' }, { key: 'status', label: 'System', glyph: '⌁' },
];
export function Navigation({ current, onChange }: { current: RootScreen; onChange: (screen: RootScreen) => void }) {
  return <View style={styles.bar}>{items.map((item) => <Pressable key={item.key} accessibilityRole="tab" accessibilityState={{ selected: current === item.key }} onPress={() => onChange(item.key)} style={styles.item}><Text style={[styles.glyph, current === item.key && styles.active]}>{item.glyph}</Text><Text style={[styles.label, current === item.key && styles.active]}>{item.label}</Text></Pressable>)}</View>;
}
const styles = StyleSheet.create({ bar: { position: 'absolute', left: 16, right: 16, bottom: 18, height: 66, borderRadius: 22, backgroundColor: colors.glass, borderWidth: 1, borderColor: colors.line, flexDirection: 'row', justifyContent: 'space-around', alignItems: 'center' }, item: { width: 66, alignItems: 'center', gap: 3 }, glyph: { color: colors.muted, fontSize: 20 }, label: { color: colors.muted, fontSize: 10, letterSpacing: .3 }, active: { color: colors.text } });
