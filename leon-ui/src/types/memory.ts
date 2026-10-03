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
