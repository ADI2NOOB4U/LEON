import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Navigation } from '@/components/Navigation';
import { ChatScreen } from '@/screens/ChatScreen';
import { HomeScreen } from '@/screens/HomeScreen';
import { StatusScreen } from '@/screens/StatusScreen';
import { TaskDetailScreen } from '@/screens/TaskDetailScreen';
import { TasksScreen } from '@/screens/TasksScreen';
import type { LeonTask } from '@/types/api';

export type RootScreen = 'home' | 'tasks' | 'chat' | 'status';
export function LeonApp() {
  const [screen, setScreen] = useState<RootScreen>('home'); const [selectedTask, setSelectedTask] = useState<LeonTask | null>(null);
  const content = selectedTask ? <TaskDetailScreen task={selectedTask} onBack={() => setSelectedTask(null)} /> : screen === 'home' ? <HomeScreen onNavigate={setScreen} /> : screen === 'tasks' ? <TasksScreen onSelect={setSelectedTask} /> : screen === 'chat' ? <ChatScreen /> : <StatusScreen />;
  return <View style={styles.app}>{content}{!selectedTask ? <Navigation current={screen} onChange={setScreen} /> : null}</View>;
}
const styles = StyleSheet.create({ app: { flex: 1, backgroundColor: '#070914' } });
