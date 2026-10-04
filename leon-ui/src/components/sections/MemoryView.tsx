import { useEffect, useState } from 'react';
import { COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS } from '../../theme';
import { forgetPersonalMemory, getPersonalMemories, getPersonalProfile } from '../../api/client';
import type { PersonalMemory, UserProfile } from '../../types/memory';

const emptyProfile: UserProfile = { preferred_name: null, date_of_birth: null, location: null, timezone: null, languages: [], education: {}, career: {}, skills: [], interests: [], preferences: {}, communication_style: {}, important_dates: {}, projects: [], goals: [], astrology_profile: {} };

export function MemoryView() {
  const [profile, setProfile] = useState<UserProfile>(emptyProfile);
  const [memories, setMemories] = useState<PersonalMemory[]>([]);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const load = async (search = query) => {
    try { const [profileData, memoryData] = await Promise.all([getPersonalProfile(), getPersonalMemories(search)]); setProfile(profileData.profile); setMemories(memoryData); setError(null); } catch { setError('Memory service is unavailable.'); }
  };
  useEffect(() => { void load(''); }, []);
  return <div style={{ flex: 1, padding: SPACING['2xl'], overflowY: 'auto', color: COLORS.text.primary }}>
    <h1 style={{ fontFamily: TYPOGRAPHY.heading.family, margin: 0 }}>Memory</h1>
    <p style={{ color: COLORS.text.tertiary, marginTop: SPACING.sm }}>Your profile and durable memories — controlled, searchable, and local-first.</p>
    <input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void load(); }} placeholder="Search memory" style={{ width: '100%', maxWidth: 520, padding: '12px 14px', background: COLORS.background.secondary, color: COLORS.text.primary, border: `1px solid ${COLORS.border.secondary}`, borderRadius: BORDER_RADIUS.md, outline: 'none' }} />
    {error && <p style={{ color: '#f87171' }}>{error}</p>}
    <section style={{ marginTop: SPACING.xl, padding: SPACING.lg, border: `1px solid ${COLORS.border.secondary}`, borderRadius: BORDER_RADIUS.lg }}><h2 style={{ fontSize: 14, letterSpacing: '0.08em' }}>MY PROFILE</h2><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: SPACING.md, color: COLORS.text.secondary }}><span>Name<br /><strong>{profile.preferred_name || 'Not set'}</strong></span><span>Location<br /><strong>{profile.location || 'Not set'}</strong></span><span>Timezone<br /><strong>{profile.timezone || 'Not set'}</strong></span><span>Languages<br /><strong>{profile.languages.join(', ') || 'Not set'}</strong></span></div></section>
    <section style={{ marginTop: SPACING.xl }}><h2 style={{ fontSize: 14, letterSpacing: '0.08em' }}>MEMORIES <span style={{ color: COLORS.text.muted }}>({memories.length})</span></h2>{memories.length === 0 ? <p style={{ color: COLORS.text.tertiary }}>No durable memories match this search.</p> : memories.map((memory) => <article key={memory.id} style={{ padding: SPACING.lg, marginBottom: SPACING.md, border: `1px solid ${COLORS.border.secondary}`, borderRadius: BORDER_RADIUS.lg }}><div style={{ color: COLORS.text.tertiary, fontSize: 11, letterSpacing: '0.08em' }}>{memory.memory_type} · {memory.confidence} · {memory.privacy_level}</div><h3 style={{ margin: '8px 0' }}>{memory.key}</h3><p style={{ color: COLORS.text.secondary }}>{String(memory.value)}</p><button onClick={async () => { await forgetPersonalMemory(memory.id); await load(); }} style={{ background: 'transparent', color: '#f87171', border: 'none', cursor: 'pointer', padding: 0 }}>Forget</button></article>)}</section>
  </div>;
}
