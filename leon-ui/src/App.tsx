import { useEffect, useCallback, useRef } from 'react';
import { Layout } from './components/layout/Layout';
import { CustomCursor } from './components/ui/CustomCursor';
import { useLeonStore } from './store/useLeonStore';
import { getSystemStatus } from './api/client';
import { soundSystem } from './audio/soundSystem';

function App() {
  const setOnline = useLeonStore((s) => s.setOnline);
  const setState = useLeonStore((s) => s.setState);
  const soundEnabled = useLeonStore((s) => s.soundEnabled);
  const state = useLeonStore((s) => s.state);
  const previousState = useRef(state);

  // Sync sound system with store
  useEffect(() => {
    soundSystem.setMuted(!soundEnabled);
  }, [soundEnabled]);

  useEffect(() => {
    if (previousState.current !== state) soundSystem.stateTransition(state);
    previousState.current = state;
  }, [state]);

  // Poll system status
  const pollStatus = useCallback(async () => {
    try {
      const status = await getSystemStatus();
      setOnline(true);
      if (status.state) {
        setState(status.state);
      }
    } catch {
      setOnline(false);
    }
  }, [setOnline, setState]);

  useEffect(() => {
    pollStatus();
    const interval = setInterval(pollStatus, 5000);
    return () => clearInterval(interval);
  }, [pollStatus]);

  return (
    <>
      <CustomCursor />
      <Layout />
    </>
  );
}

export default App;
