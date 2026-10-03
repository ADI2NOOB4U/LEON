import { COLORS } from '../../theme';
import { useLeonStore } from '../../store/useLeonStore';
import { Sidebar } from './Sidebar';
import { CommandBar } from './CommandBar';
import { TaskPanel } from '../ui/TaskPanel';
import { Dashboard } from '../sections/Dashboard';
import { TasksView } from '../sections/TasksView';
import { MemoryView } from '../sections/MemoryView';
import { SystemsView } from '../sections/SystemsView';

function MainContent() {
  const activeSection = useLeonStore((s) => s.activeSection);

  switch (activeSection) {
    case 'sanctum':
      return <Dashboard />;
    case 'missions':
      return <TasksView />;
    case 'memory':
      return <MemoryView />;
    case 'systems':
      return <SystemsView />;
    default:
      return <Dashboard />;
  }
}

export function Layout() {
  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        background: COLORS.background.primary,
        overflow: 'hidden',
      }}
    >
      {/* Left Sidebar */}
      <Sidebar />

      {/* Center + Bottom */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Main Content Area */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <MainContent />
        </div>

        {/* Command Bar */}
        <CommandBar />
      </div>

      {/* Right Task Panel */}
      <TaskPanel />
    </div>
  );
}
