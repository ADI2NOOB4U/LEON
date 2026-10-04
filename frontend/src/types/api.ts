export type CoreState = 'idle' | 'thinking' | 'executing' | 'completed' | 'error'

export interface HealthStatus {
  status: string
  service: string
  version: string
}

export type TaskStatus =
  | 'queued'
  | 'running'
  | 'waiting'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface Task {
  id: number
  title: string
  status: TaskStatus | string
  progress: number
  current_stage: string
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  result?: string | null
  error?: string | null
  last_activity?: string | null
  summary?: string | null
  artifacts?: TaskArtifact[]
  task_type?: 'standard' | 'research' | 'mission' | string
  verification_status?: string
  checkpoint?: string | null
  waiting_reason?: string | null
  approval_granted?: number
}

export interface TaskArtifact {
  id: number
  task_id: number
  path: string
  type: string
  size: number
  created_at: string
}

export type CommandResponse = {
  type: 'task' | 'mission' | 'chat' | 'action' | 'failed' | 'clarification' | 'confirmation_required'
  message: string
  task?: Task
  mission?: Task
  capability?: string
  action?: string
  result?: Record<string, unknown>
  verified?: boolean
  confirmation_id?: string
}

export interface MediaStatus {
  success: boolean
  state: string
  provider?: string
  title?: string | null
  artist?: string | null
  album?: string | null
  album_art_url?: string | null
  progress_ms?: number | null
  duration_ms?: number | null
  is_playing?: boolean
  device?: string | null
  device_id?: string | null
  message?: string
}

export interface SpotifyStatus {
  configured: boolean
  authenticated: boolean
  requires_auth: boolean
  premium_available?: boolean | null
  sdk_loaded?: boolean
  sdk_connected?: boolean
  sdk_ready?: boolean
  playback_available?: boolean
  device_id?: string | null
  device_name?: string | null
  current_device_id?: string | null
  current_device_name?: string | null
  is_playing?: boolean
  current_track?: string | null
  current_artist?: string | null
  current_album?: string | null
  album_art_url?: string | null
  progress_ms?: number | null
  remote_devices?: Array<{ id: string; name: string; type?: string; is_active?: boolean }>
  error_code?: string
  missing_scopes?: string[]
  devices_available?: number
  account_name?: string | null
  device_available?: boolean
}

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking' | 'error'

export interface VoiceTurnResponse {
  transcript: string
  assistant: string
  audio_base64: string
  audio_content_type: string
  audio_error: string | null
  tts_provider?: string | null
  tts_model?: string | null
  tts_fallback_reason?: string | null
  audio_bytes?: number
}

export interface VisionResponse {
  success: boolean
  description: string
  observations: string[]
  ocr_text: string | null
  confidence_note: string | null
  model: string
  mode: string
  width: number
  height: number
}

export type VisionMode = 'general' | 'ocr' | 'screen' | 'document' | 'object'

export interface Memory {
  id: number
  type: 'fact' | 'preference' | 'project' | 'note' | string
  content: string
  importance: number
  created_at: string
  updated_at: string
}

export interface PersonalProfile {
  preferred_name: string | null
  date_of_birth: string | null
  birth_time?: string | null
  birth_place?: string | null
  location: string | null
  timezone: string | null
  languages: string[]
  education: Record<string, unknown>
  work?: Record<string, unknown>
  career: Record<string, unknown>
  skills: string[]
  interests: string[]
  preferences: Record<string, unknown>
  communication_style: Record<string, unknown>
  projects: Array<Record<string, unknown>>
  goals: Array<Record<string, unknown>>
  astrology_profile: Record<string, unknown>
}

export interface PersonalMemory {
  id: number
  memory_type: string
  category: string
  key: string
  value: unknown
  source: string
  confidence: string
  privacy_level: string
  retention: string
  created_at: string
  updated_at: string
  active: boolean
}

export interface Relationship {
  id: number
  person_id: string
  name: string
  relationship_type: string
  important_dates: Record<string, unknown>
  notes?: string | null
  confidence: string
  privacy_level: string
  active: boolean
}

export interface ImportantDate {
  id: number
  name: string
  date_value: string
  time_value?: string | null
  date_type: string
  person_id?: string | null
  notes?: string | null
  confidence: string
  privacy_level: string
  active: boolean
}

export interface NewsSource {
  id: number
  event_id: number
  url: string
  title?: string | null
  publisher?: string | null
  published_at?: string | null
  retrieved_at: string
  source_type: string
  verification_status: string
}

export interface NewsBriefing {
  what_happened?: string | null
  when_it_happened?: string | null
  where?: string | null
  why_it_matters?: string | null
  what_is_confirmed?: string | null
  what_is_uncertain?: string | null
  timeline?: Array<{ label?: string | null; time?: string | null }>
  important_developments?: string[]
  source_links?: Array<{ title?: string | null; url?: string | null }>
  related_coverage?: Array<{ title?: string | null; url?: string | null }>
  map_context?: string | null
}

export interface NewsEvent {
  id: number
  topic: string
  title: string
  importance: 'critical' | 'important' | 'interesting' | 'ignore' | string
  status: string
  summary?: string | null
  location?: string | null
  source_url?: string | null
  source?: string | null
  first_seen_at: string
  last_seen_at: string
  last_alerted_at?: string | null
  alerted: boolean | number
  sources: NewsSource[]
  briefing?: NewsBriefing
}

export type ComputerState =
  | 'IDLE'
  | 'OBSERVING'
  | 'PLANNING'
  | 'AWAITING_CONFIRMATION'
  | 'ACTING'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'

export interface TargetLocation {
  x: number
  y: number
}

export interface TargetBounds {
  left: number
  top: number
  width: number
  height: number
}

export interface VisualTarget {
  id: string
  label: string
  type: string
  location: TargetLocation
  bounds?: TargetBounds | null
  confidence: number
  freshness_timestamp: string
  app_context?: string | null
  raw_text?: string | null
}

export interface ScreenInfo {
  width: number
  height: number
  scale_factor: number
  is_captured: boolean
}

export interface ComputerObservation {
  id: string
  timestamp: string
  screen: ScreenInfo
  active_application?: string | null
  active_window?: string | null
  visible_text?: string | null
  screenshot_available: boolean
  running_applications: string[]
  detected_targets: VisualTarget[]
  diagnostics: string[]
  error_summary?: string | null
}

export interface ComputerStatus {
  state: ComputerState
  active_application?: string | null
  active_window?: string | null
  running_applications: string[]
}

export interface ComputerAction {
  action_type: string
  app_name?: string | null
  target_id?: string | null
  target_label?: string | null
  coordinates?: TargetLocation | null
  text?: string | null
  hotkeys?: string[] | null
  scroll_direction?: string | null
  url?: string | null
  path?: string | null
  observation_id?: string | null
  confirmed?: boolean
  risk?: string
}

export interface ExecutionMetrics {
  observation_ms: number
  vision_ms: number
  action_ms: number
  verification_ms: number
  total_ms: number
}

export interface VerificationResult {
  verified: boolean
  code: string
  reason: string
  state_changes: Record<string, unknown>
}

export interface ExecutionResult {
  success: boolean
  state: ComputerState
  action?: ComputerAction | null
  observation_before?: ComputerObservation | null
  observation_after?: ComputerObservation | null
  verification?: VerificationResult | null
  message: string
  error?: string | null
  metrics: ExecutionMetrics
}

export interface DiagnosisResponse {
  observation_id: string
  timestamp: string
  active_application?: string | null
  active_window?: string | null
  screenshot_available: boolean
  visible_summary?: string | null
  error_detected: boolean
  error_summary?: string | null
  targets_count: number
  diagnostics: string[]
  latency_ms: number
}
