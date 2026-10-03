import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { LeonApp } from './src/LeonApp';

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <LeonApp />
    </SafeAreaProvider>
  );
}
