export type MemoryCategory = 'conversation' | 'knowledge' | 'preference' | 'skill';

export interface MemoryEntry {
  id: string;
  category: MemoryCategory;
  title: string;
  content: string;
  tags: string[];
  importance: number;
  createdAt: string;
  accessedAt: string;
  accessCount: number;
}

export interface MemoryStats {
  totalEntries: number;
  categories: Record<MemoryCategory, number>;
  storageUsed: number;
  storageLimit: number;
}

export interface PersonalMemory {
  id: number;
  memory_type: string;
  category: string;
  key: string;
  value: unknown;
  source: string;
  confidence: string;
  privacy_level: string;
  updated_at: string;
  active: boolean;
}

export interface UserProfile {
  preferred_name: string | null;
  date_of_birth: string | null;
  location: string | null;
  timezone: string | null;
  languages: string[];
  education: Record<string, unknown>;
  career: Record<string, unknown>;
  skills: string[];
  interests: string[];
  preferences: Record<string, unknown>;
  communication_style: Record<string, unknown>;
  important_dates: Record<string, unknown>;
  projects: Array<Record<string, unknown>>;
  goals: Array<Record<string, unknown>>;
  astrology_profile: Record<string, unknown>;
}
