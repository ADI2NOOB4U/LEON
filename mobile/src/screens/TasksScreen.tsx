import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Screen } from '@/components/Screen';
import { ProgressTrack, Reveal } from '@/components/motion';
import { leonApi } from '@/lib/api';
import { colors } from '@/theme';
import type { LeonTask } from '@/types/api';

export function TasksScreen({ onSelect }: { onSelect: (task: LeonTask) => void }) {
  const [tasks, setTasks] = useState<LeonTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { try { setError(null); setTasks(await leonApi.tasks()); } catch (e) { setError(e instanceof Error ? e.message : 'Could not load missions.'); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  if (loading) return <Screen><View style={styles.center}><ActivityIndicator color={colors.violet} /></View></Screen>;
  return (
    <Screen><Reveal><View>
      <Text style={styles.eyebrow}>MISSION CONTROL</Text><Text style={styles.title}>Tasks in orbit</Text>
      {error ? <Text style={styles.error}>{error}</Text> : tasks.length === 0 ? <Text style={styles.empty}>No missions have been dispatched yet.</Text> : tasks.map((task) => (
        <Pressable key={task.id} onPress={() => onSelect(task)} style={styles.card}>
          <View style={styles.row}><Text numberOfLines={1} style={styles.cardTitle}>{task.title}</Text><Text style={styles.status}>{task.status.toUpperCase()}</Text></View>
          <Text style={styles.stage}>{task.current_stage || 'Awaiting trajectory'}</Text><ProgressTrack value={task.progress} /><Text style={styles.percent}>{task.progress}% complete</Text>
        </Pressable>
      ))}
      <Pressable onPress={() => { setLoading(true); void load(); }} style={styles.refresh}><Text style={styles.refreshText}>Refresh mission data</Text></Pressable>
    </View></Reveal></Screen>
  );
}
const styles = StyleSheet.create({ center: { flex: 1, justifyContent: 'center' }, eyebrow: { color: colors.gold, letterSpacing: 2, fontSize: 10, marginTop: 8 }, title: { color: colors.text, fontSize: 30, fontWeight: '300', marginTop: 10, marginBottom: 24 }, card: { borderRadius: 18, padding: 16, backgroundColor: colors.glass, borderWidth: 1, borderColor: colors.line, marginBottom: 10 }, row: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 }, cardTitle: { color: colors.text, fontSize: 16, fontWeight: '600', flex: 1 }, status: { color: colors.violet, fontSize: 9, letterSpacing: 1.2 }, stage: { color: colors.muted, marginTop: 10, fontSize: 13, marginBottom: 15 }, percent: { color: colors.muted, fontSize: 11, marginTop: 7 }, error: { color: colors.danger, lineHeight: 20 }, empty: { color: colors.muted, fontSize: 15, lineHeight: 22 }, refresh: { alignSelf: 'center', padding: 14, marginTop: 8 }, refreshText: { color: colors.blue, fontSize: 13 } });
