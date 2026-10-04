import { Fragment, useEffect, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { InstrumentCursor } from './interactions/InstrumentCursor'
import { getMuted, getVolume, playSound, setMuted as setSoundMuted, setVolume as persistSoundVolume, unlockSound } from './interactions/sound'
import type { InteractionState } from './graphics/motion'
import { LeonCoreHero } from './components/LeonCoreHero'
import { VisionPanel } from './components/VisionPanel'
import { ComputerUsePanel } from './components/ComputerUsePanel'
import { connectSpotify, dismissNewsEvent, disconnectSpotify, fetchImportantDates, fetchMediaStatus, fetchMemory, fetchNewsEvents, fetchPersonalMemories, fetchPersonalProfile, fetchRelationships, fetchSpotifyStatus, fetchTasks, forgetPersonalMemory, recordImprovementFeedback, retryMission, sendCommand, sendVoiceTurn, synthesizeSpeech, updatePersonalProfile } from './api/client'
import { useHealthPolling } from './hooks/useHealthPolling'
import { useSpotifyPlayer } from './hooks/useSpotifyPlayer'
import type { ImportantDate, MediaStatus, Memory, NewsEvent, PersonalMemory, PersonalProfile, Relationship, SpotifyStatus, Task, VoiceState } from './types/api'

// Navigation items with clean icons and labels
const navItems = [
  {
    id: 'Overview',
    label: 'Overview',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    id: 'Tasks',
    label: 'Tasks',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    id: 'Memory',
    label: 'Memory',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
        <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
      </svg>
    ),
  },
  {
    id: 'Media',
    label: 'Media',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="3" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10" />
      </svg>
    ),
  },
  {
    id: 'System',
    label: 'System',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
        <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
        <line x1="6" y1="6" x2="6.01" y2="6" />
        <line x1="6" y1="18" x2="6.01" y2="18" />
      </svg>
    ),
  },
  {
    id: 'Vision',
    label: 'Vision',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
  {
    id: 'Computer',
    label: 'Computer',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    ),
  },
]

const mediaLinkGroups = [
  {
    title: 'Watch & listen',
    links: [
      { name: 'YouTube', description: 'Videos, live streams and music', url: 'https://www.youtube.com/' },
      { name: 'YouTube Music', description: 'Music, playlists and podcasts', url: 'https://music.youtube.com/' },
    ],
  },
  {
    title: 'Social',
    links: [
      { name: 'X / Twitter', description: 'Posts and live updates', url: 'https://x.com/' },
      { name: 'Reddit', description: 'Communities and discussions', url: 'https://www.reddit.com/' },
    ],
  },
  {
    title: 'News & current affairs',
    links: [
      { name: 'Google News', description: 'Coverage from multiple publishers', url: 'https://news.google.com/' },
      { name: 'Reuters', description: 'International news', url: 'https://www.reuters.com/' },
      { name: 'Associated Press', description: 'Global reporting', url: 'https://apnews.com/' },
      { name: 'BBC News', description: 'World news and analysis', url: 'https://www.bbc.com/news' },
      { name: 'The Hindu', description: 'India and world current affairs', url: 'https://www.thehindu.com/' },
    ],
  },
]

const activeStatuses = new Set([
  'queued', 'understanding', 'planning', 'ready', 'running', 'executing',
  'waiting', 'paused', 'verifying', 'repairing', 'retrying',
  'awaiting_confirmation', 'awaiting_user', 'waiting_for_user',
])

function formatTaskStatus(status?: string) {
  return (status ?? 'idle').replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase())
}

function taskLifecycle(task: Task | null) {
  if (!task) return []
  const status = task.status.toLowerCase()
  if (status === 'failed') return ['running', 'failed']
  if (status === 'cancelled') return ['running', 'cancelled']
  if (status === 'completed') return ['queued', 'running', 'verifying', 'completed']
  if (status === 'repairing' || status === 'retrying') return ['running', 'repairing', 'retrying', 'verifying']
  if (status === 'waiting' || status === 'paused' || status === 'waiting_for_user' || status === 'awaiting_user') {
    return ['running', status]
  }
  return [status]
}

function stateFromTask(status?: string): InteractionState {
  if (status === 'queued' || status === 'planning') return 'thinking'
  if (status === 'running' || status === 'executing' || status === 'verifying' || status === 'repairing' || status === 'retrying' || status === 'awaiting_confirmation' || status === 'awaiting_user') return 'executing'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  return 'idle'
}

function useResettableState() {
  const [state, setState] = useState<InteractionState>('idle')
  const timer = useRef<number | undefined>(undefined)

  const showState = (next: InteractionState, duration = 0) => {
    window.clearTimeout(timer.current)
    setState(next)
    if (duration > 0) {
      timer.current = window.setTimeout(() => setState('idle'), duration)
    }
  }

  useEffect(() => () => window.clearTimeout(timer.current), [])
  return [state, showState] as const
}

export default function App() {
  const [activeNav, setActiveNav] = useState('Overview')
  const [interaction, showState] = useResettableState()
  const [tasks, setTasks] = useState<Task[]>([])
  const [hiddenRecentTaskIds, setHiddenRecentTaskIds] = useState<Set<number>>(() => new Set())
  const [showHiddenRecentTasks, setShowHiddenRecentTasks] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [command, setCommand] = useState('')
  const [reply, setReply] = useState('')
  const [lastSubmittedRequest, setLastSubmittedRequest] = useState('')
  const [pendingConfirmation, setPendingConfirmation] = useState<string | null>(null)
  const [pendingConfirmationId, setPendingConfirmationId] = useState<string | null>(null)
  const [replyActionNotice, setReplyActionNotice] = useState('')
  const [readAloudState, setReadAloudState] = useState<'idle' | 'loading' | 'playing' | 'error'>('idle')
  const [memories, setMemories] = useState<Memory[]>([])
  const [personalProfile, setPersonalProfile] = useState<PersonalProfile | null>(null)
  const [profileNameDraft, setProfileNameDraft] = useState('')
  const [profileNotice, setProfileNotice] = useState('')
  const [personalMemories, setPersonalMemories] = useState<PersonalMemory[]>([])
  const [memorySearch, setMemorySearch] = useState('')
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [importantDates, setImportantDates] = useState<ImportantDate[]>([])
  const [memoryFilter, setMemoryFilter] = useState('all')
  const [newsEvents, setNewsEvents] = useState<NewsEvent[]>([])
  const [activeAlert, setActiveAlert] = useState<NewsEvent | null>(null)
  const [selectedBriefing, setSelectedBriefing] = useState<NewsEvent | null>(null)
  const { connection, health } = useHealthPolling()
  const [syncIssues, setSyncIssues] = useState<string[]>([])
  const [media, setMedia] = useState<MediaStatus | null>(null)
  const [spotify, setSpotify] = useState<SpotifyStatus | null>(null)
  const [spotifyBusy, setSpotifyBusy] = useState(false)
  const [spotifyNotice, setSpotifyNotice] = useState('')
  const { snapshot: spotifyPlayer, enablePlayer, retryPlayer } = useSpotifyPlayer(
    spotify?.authenticated ?? false,
    spotify?.configured ?? false,
  )
  const [muted, setMuted] = useState(getMuted)
  const [soundVolume, setSoundVolumePercent] = useState(getVolume)
  const [soundControlsOpen, setSoundControlsOpen] = useState(false)
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [voiceError, setVoiceError] = useState('')
  const [voiceAudio, setVoiceAudio] = useState('')
  const voiceRequest = useRef(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const microphone = useRef<MediaStream | null>(null)
  const replyAudio = useRef<HTMLAudioElement | null>(null)
  const replyTextAudio = useRef<HTMLAudioElement | null>(null)
  const replyTextAudioUrl = useRef<string | null>(null)
  const speechRequestId = useRef(0)
  const previousStatuses = useRef(new Map<number, string>())
  const lastAlertId = useRef<number | null>(null)

  const updateSyncIssue = (source: string, failed: boolean) => {
    setSyncIssues((current) => {
      if (failed) return current.includes(source) ? current : [...current, source]
      return current.filter((item) => item !== source)
    })
  }

  const stopReplySpeech = () => {
    speechRequestId.current += 1
    replyTextAudio.current?.pause()
    replyTextAudio.current = null
    if (replyTextAudioUrl.current) {
      URL.revokeObjectURL(replyTextAudioUrl.current)
      replyTextAudioUrl.current = null
    }
    setReadAloudState('idle')
  }

  const resetVoiceActivityState = () => {
    setVoiceState((current) => (current === 'listening' || current === 'processing' || current === 'speaking' ? 'idle' : current))
  }

  const updateReply = (text: string) => {
    stopReplySpeech()
    replyAudio.current?.pause()
    resetVoiceActivityState()
    setReply(text)
    setReplyActionNotice('')
  }

  const hideRecentTask = (taskId: number) => {
    setHiddenRecentTaskIds((current) => new Set(current).add(taskId))
    setSelectedTaskId((current) => current === taskId ? null : current)
  }

  const readReplyAloud = async () => {
    const text = reply.trim()
    if (!text) return

    stopReplySpeech()
    const requestId = speechRequestId.current
    setReplyActionNotice('')
    setReadAloudState('loading')
    replyAudio.current?.pause()
    setVoiceState((current) => current === 'speaking' ? 'idle' : current)

    try {
      const audioBlob = await synthesizeSpeech(text)
      if (speechRequestId.current !== requestId) return

      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)
      audio.volume = getVolume()
      audio.muted = getMuted()
      replyTextAudioUrl.current = audioUrl
      replyTextAudio.current = audio
      const releaseAudio = () => {
        if (replyTextAudioUrl.current === audioUrl) {
          URL.revokeObjectURL(audioUrl)
          replyTextAudioUrl.current = null
          replyTextAudio.current = null
        }
      }
      audio.onended = () => {
        releaseAudio()
        if (speechRequestId.current === requestId) setReadAloudState('idle')
      }
      audio.onerror = () => {
        releaseAudio()
        if (speechRequestId.current === requestId) {
          setReadAloudState('error')
          setReplyActionNotice('LEON returned audio that could not be played.')
        }
      }
      await audio.play()
      if (speechRequestId.current === requestId) setReadAloudState('playing')
    } catch (error) {
      if (speechRequestId.current === requestId) {
        stopReplySpeech()
        setReadAloudState('error')
        setReplyActionNotice(error instanceof Error ? error.message : 'Could not read the reply aloud.')
      }
    }
  }

  const copyReply = async () => {
    try {
      await navigator.clipboard.writeText(reply)
      setReplyActionNotice('Reply copied.')
    } catch {
      setReplyActionNotice('Could not copy the reply. Check clipboard permissions.')
    }
  }

  const downloadReply = () => {
    const url = URL.createObjectURL(new Blob([reply], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'leon-reply.txt'
    document.body.append(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
    setReplyActionNotice('Reply download started.')
  }

  const rateReply = async (rating: number) => {
    if (!lastSubmittedRequest || !reply) return
    try {
      await recordImprovementFeedback({ request: lastSubmittedRequest, outcome: reply, rating, verified: true })
      setReplyActionNotice('Feedback recorded for safe future improvement.')
    } catch {
      setReplyActionNotice('Feedback could not be recorded.')
    }
  }

  const retryTask = async (task: Task) => {
    if (task.task_type !== 'mission') return
    try {
      const updated = await retryMission(task.id)
      setTasks((current) => [updated, ...current.filter((item) => item.id !== updated.id)])
      setSelectedTaskId(updated.id)
      setReplyActionNotice('Mission retry requested.')
    } catch (error) {
      setReplyActionNotice(error instanceof Error ? error.message : 'Mission retry could not be requested.')
    }
  }

  const startSpotifyConnect = async () => {
    setSpotifyBusy(true)
    setSpotifyNotice('')
    try {
      const result = await connectSpotify()
      window.location.assign(result.authorization_url)
    } catch (error) {
      setSpotifyNotice(error instanceof Error ? error.message : 'Spotify connection failed.')
      setSpotifyBusy(false)
    }
  }

  const refreshSpotifyStatus = async () => {
    try {
      const nextSpotify = await fetchSpotifyStatus()
      setSpotify(nextSpotify)
      return nextSpotify
    } catch {
      setSpotify({ configured: false, authenticated: false, requires_auth: true })
      return null
    }
  }

  const removeSpotifyConnection = async () => {
    setSpotifyBusy(true)
    try {
      await disconnectSpotify()
      await refreshSpotifyStatus()
      await fetchMediaStatus().then(setMedia).catch(() => setMedia(null))
    } finally {
      setSpotifyBusy(false)
    }
  }

  const handleSpotifyControl = async (action: 'previous' | 'pause' | 'resume' | 'next') => {
    if (!spotify?.authenticated || !spotifyPlayer.deviceId) return
    setSpotifyBusy(true)
    try {
      const commandText =
        action === 'previous'
          ? 'Previous song'
          : action === 'pause'
          ? 'Pause Spotify'
          : action === 'resume'
          ? 'Resume Spotify'
          : 'Next song'
      const result = await sendCommand(commandText)
      updateReply(result.message)
      await refreshSpotifyStatus()
      await fetchMediaStatus().then(setMedia).catch(() => setMedia(null))
    } catch (error) {
      updateReply(error instanceof Error ? error.message : 'Spotify control action failed.')
    } finally {
      setSpotifyBusy(false)
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const spotifyState = params.get('spotify')
    if (spotifyState) {
      setActiveNav('Media')
      setSpotifyNotice(
        spotifyState === 'connected'
          ? 'Spotify connected successfully.'
          : 'Spotify authorization failed. Verify that SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are valid, and that Spotify has the exact SPOTIFY_REDIRECT_URI registered in its app settings.',
      )
      void refreshSpotifyStatus()
      const nextUrl = `${window.location.pathname}${window.location.hash}`
      window.history.replaceState({}, '', nextUrl)
    }
  }, [])

  useEffect(() => {
    if (!spotifyPlayer.track) return
    setMedia((current) => ({
      ...(current ?? { success: true, state: 'PAUSED', provider: 'spotify' }),
      success: true,
      state: spotifyPlayer.track?.isPlaying ? 'PLAYING' : 'PAUSED',
      title: spotifyPlayer.track?.name,
      artist: spotifyPlayer.track?.artist,
      album: spotifyPlayer.track?.album,
      album_art_url: spotifyPlayer.track?.albumArtUrl,
      progress_ms: spotifyPlayer.track?.positionMs,
      duration_ms: spotifyPlayer.track?.durationMs,
      is_playing: spotifyPlayer.track?.isPlaying,
      device: spotifyPlayer.deviceName,
      device_id: spotifyPlayer.deviceId,
    }))
  }, [spotifyPlayer.deviceId, spotifyPlayer.deviceName, spotifyPlayer.track])

  useEffect(() => () => {
    recorder.current?.stop()
    microphone.current?.getTracks().forEach((track) => track.stop())
    replyAudio.current?.pause()
    replyTextAudio.current?.pause()
    if (replyTextAudioUrl.current) URL.revokeObjectURL(replyTextAudioUrl.current)
  }, [])

  useEffect(() => {
    let active = true
    let refreshTimer: number | undefined

    const load = async () => {
      if (!active) return

      const [nextMedia, nextSpotify] = await Promise.allSettled([fetchMediaStatus(), fetchSpotifyStatus()])
      if (active) {
        if (nextMedia.status === 'fulfilled') {
          setMedia(nextMedia.value)
          updateSyncIssue('Media status', false)
        } else {
          updateSyncIssue('Media status', true)
        }
        if (nextSpotify.status === 'fulfilled') {
          setSpotify(nextSpotify.value)
          updateSyncIssue('Spotify status', false)
        } else {
          updateSyncIssue('Spotify status', true)
        }
      }

      if (!active) return
      try {
        const nextTasks = await fetchTasks()
        if (active) {
          for (const task of nextTasks) {
            const previous = previousStatuses.current.get(task.id)
            if (previous && previous !== task.status) {
              if (task.status === 'completed') {
                playSound('complete')
                showState('success', 2000)
              } else if (task.status === 'failed') {
                playSound('error')
                showState('error', 2000)
              }
            }
            previousStatuses.current.set(task.id, task.status)
          }
          setTasks(nextTasks)
          updateSyncIssue('Tasks', false)
        }
      } catch {
        if (active) updateSyncIssue('Tasks', true)
      }

      if (!active) return
      try {
        const nextMemory = await fetchMemory()
        if (active) {
          setMemories(nextMemory)
          updateSyncIssue('Memory', false)
        }
      } catch {
        if (active) updateSyncIssue('Memory', true)
      }

      if (!active) return
      const [profileResult, personalResult, relationshipResult, dateResult] = await Promise.allSettled([
        fetchPersonalProfile(), fetchPersonalMemories(), fetchRelationships(), fetchImportantDates(),
      ])
      if (!active) return
      if (profileResult.status === 'fulfilled') {
        setPersonalProfile(profileResult.value.profile)
        setProfileNameDraft(profileResult.value.profile.preferred_name ?? '')
        updateSyncIssue('Personal profile', false)
      } else {
        updateSyncIssue('Personal profile', true)
      }
      if (personalResult.status === 'fulfilled') {
        setPersonalMemories(personalResult.value)
        updateSyncIssue('Personal memories', false)
      } else {
        updateSyncIssue('Personal memories', true)
      }
      if (relationshipResult.status === 'fulfilled') {
        setRelationships(relationshipResult.value)
        updateSyncIssue('Relationships', false)
      } else {
        updateSyncIssue('Relationships', true)
      }
      if (dateResult.status === 'fulfilled') {
        setImportantDates(dateResult.value)
        updateSyncIssue('Important dates', false)
      } else {
        updateSyncIssue('Important dates', true)
      }

      if (!active) return
      try {
        const nextEvents = await fetchNewsEvents()
        if (active) {
          setNewsEvents(nextEvents)
          updateSyncIssue('News', false)
          const activeEvent = [...nextEvents]
            .filter((event) => Number(event.alerted) === 1)
            .sort(
              (a, b) =>
                new Date(b.last_alerted_at ?? b.last_seen_at).getTime() -
                new Date(a.last_alerted_at ?? a.last_seen_at).getTime(),
            )[0]
          if (activeEvent && activeEvent.id !== lastAlertId.current) {
            lastAlertId.current = activeEvent.id
            setActiveAlert(activeEvent)
          }
        }
      } catch {
        if (active) updateSyncIssue('News', true)
      }

      if (active) refreshTimer = window.setTimeout(() => void load(), 6000)
    }

    const initialLoad = window.setTimeout(() => void load(), 0)

    return () => {
      active = false
      window.clearTimeout(initialLoad)
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer)
    }
  }, [])

  const connected = connection === 'online'
  const spotifyConfigured = spotify?.configured ?? false
  const recentTasks = tasks.filter((task) => (
    showHiddenRecentTasks || !hiddenRecentTaskIds.has(task.id)
  ))
  const activeTask = tasks.find((task) => activeStatuses.has(task.status)) ?? null
  const selectedTask = tasks.find((task) => task.id === selectedTaskId) ?? null
  const currentTask = selectedTask ?? activeTask
  const detailTask = currentTask ?? recentTasks[0] ?? null
  const coreState = interaction !== 'idle' ? interaction : stateFromTask(activeTask?.status)
  const visualState = connection === 'offline' ? 'offline' : coreState

  const handlePointerOver = (event: ReactPointerEvent<HTMLElement>) => {
    const target = event.target
    const related = event.relatedTarget
    if (!(target instanceof Element)) return
    const control = target.closest('button, [role="button"]')
    if (control && (!(related instanceof Node) || !control.contains(related))) {
      playSound('hover')
    }
  }

  const handleClickCapture = (event: ReactPointerEvent<HTMLElement>) => {
    const target = event.target
    if (!(target instanceof Element)) return
    const sound = target.closest<HTMLElement>('[data-sound]')?.dataset.sound
    if (sound === 'click' || sound === 'focus' || sound === 'send') playSound(sound === 'send' ? 'message' : (sound as any))
  }

  const handleExecutePrompt = async (promptText: string) => {
    const text = promptText.trim()
    if (!text) return
    unlockSound()
    playSound('message')
    showState('thinking')
    setCommand('')
    setLastSubmittedRequest(text)
    stopReplySpeech()

    try {
      const result = await sendCommand(text)
      updateReply(result.message)
      if (result.type === 'confirmation_required') {
        setPendingConfirmation(text)
        setPendingConfirmationId(result.confirmation_id ?? null)
        showState('focus')
        return
      }
      setPendingConfirmation(null)
      setPendingConfirmationId(null)
      if (result.type === 'failed') {
        playSound('error')
        showState('error', 2000)
        return
      }
      if (result.type === 'clarification') {
        showState('focus')
        return
      }
      const createdTask = result.task ?? result.mission
      if (createdTask) {
        setTasks((current) => [createdTask, ...current.filter((task) => task.id !== createdTask.id)])
        setSelectedTaskId(createdTask.id)
        previousStatuses.current.set(createdTask.id, createdTask.status)
        playSound('taskStart')
        showState('executing', 2000)
      } else {
        playSound('complete')
        showState('success', 1500)
      }
    } catch (error) {
      playSound('error')
      showState('error', 2000)
      updateReply(error instanceof Error ? error.message : 'The request could not be completed.')
    }
  }

  const confirmPendingCommand = async () => {
    if (!pendingConfirmation) return
    const text = pendingConfirmation
    setPendingConfirmation(null)
    showState('thinking')
    try {
      const result = await sendCommand(text, true, pendingConfirmationId)
      updateReply(result.message)
      setPendingConfirmationId(null)
      if (result.type === 'action' || result.type === 'task' || result.type === 'mission') {
        playSound('complete')
        showState('success', 1500)
      } else {
        playSound('error')
        showState('error', 2000)
      }
    } catch (error) {
      playSound('error')
      showState('error', 2000)
      updateReply(error instanceof Error ? error.message : 'The confirmed action could not be completed.')
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!command.trim()) return
    await handleExecutePrompt(command)
  }

  const playVoiceReply = async (audioSource = voiceAudio) => {
    if (!audioSource) return
    stopReplySpeech()
    const audio = new Audio(audioSource)
    audio.volume = getVolume()
    audio.muted = getMuted()
    replyAudio.current?.pause()
    replyAudio.current = audio
    audio.onended = () => {
      setVoiceState('idle')
      showState('idle')
    }
    audio.onerror = () => {
      setVoiceError('Could not playback assistant speech audio.')
      setVoiceState('error')
      showState('error')
    }
    try {
      await audio.play()
      setVoiceState('speaking')
      showState('success')
    } catch {
      setVoiceState('idle')
      setVoiceError('Playback blocked. Press play button to listen.')
    }
  }

  const sendRecording = async (recording: Blob) => {
    if (voiceRequest.current) return
    if (!recording.size) {
      setVoiceState('error')
      setVoiceError('No audio was captured. Please try speaking again.')
      showState('error', 2000)
      return
    }

    voiceRequest.current = true
    setVoiceState('processing')
    showState('thinking')
    try {
      const result = await sendVoiceTurn(recording)
      setVoiceTranscript(result.transcript)
      updateReply(result.assistant)
      const audioSource = `data:${result.audio_content_type};base64,${result.audio_base64}`
      setVoiceAudio(audioSource)
      if (result.audio_error) {
        setVoiceState('error')
        setVoiceError(result.audio_error)
        showState('error', 2000)
        return
      }
      await playVoiceReply(audioSource)
    } catch (error) {
      resetVoiceActivityState()
      setVoiceError(error instanceof Error ? error.message : 'Voice request processing failed.')
      setVoiceState('error')
      showState('error', 2000)
    } finally {
      voiceRequest.current = false
    }
  }

  const startListening = async () => {
    if (voiceRequest.current || voiceState === 'processing' || voiceState === 'speaking') return
    setVoiceError('')
    setVoiceTranscript('')
    setVoiceAudio('')
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setVoiceState('error')
      setVoiceError('Microphone recording is not supported in this browser.')
      return
    }

    if (recorder.current && recorder.current.state === 'recording') {
      recorder.current.stop()
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
      })
      microphone.current = stream
      const candidates = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
        'audio/mp4',
      ]
      let activeRecorder: MediaRecorder | undefined
      for (const mimeType of candidates) {
        if (!MediaRecorder.isTypeSupported(mimeType)) continue
        try {
          activeRecorder = new MediaRecorder(stream, { mimeType })
          break
        } catch {
          // Fallback to next
        }
      }
      activeRecorder ??= new MediaRecorder(stream)
      const chunks: BlobPart[] = []
      let recorderFailed = false
      activeRecorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data)
      }
      activeRecorder.onerror = () => {
        recorderFailed = true
        stream.getTracks().forEach((track) => track.stop())
        microphone.current = null
        recorder.current = null
        setVoiceState('error')
        setVoiceError('Microphone capture encountered an error.')
        showState('error', 2000)
      }
      activeRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        microphone.current = null
        recorder.current = null
        if (recorderFailed) return
        const chunkWithType = chunks.find(
          (chunk): chunk is Blob => chunk instanceof Blob && Boolean(chunk.type),
        )
        const recordingType = activeRecorder.mimeType || chunkWithType?.type || ''
        const recording = new Blob(chunks, { type: recordingType })
        void sendRecording(recording)
      }
      activeRecorder.start()
      recorder.current = activeRecorder
      setVoiceState('listening')
      showState('listening')
    } catch (error) {
      microphone.current?.getTracks().forEach((track) => track.stop())
      microphone.current = null
      const name = error instanceof DOMException ? error.name : ''
      setVoiceState('error')
      setVoiceError(
        name === 'NotAllowedError'
          ? 'Microphone permission was denied. Please allow microphone access.'
          : name === 'NotFoundError'
          ? 'No microphone hardware found.'
          : 'Could not access the microphone.',
      )
      showState('error', 2000)
    }
  }

  const stopListening = () => {
    if (recorder.current?.state === 'recording') {
      recorder.current.stop()
      setVoiceState('processing')
      showState('thinking')
      return
    }
    resetVoiceActivityState()
    showState('idle')
  }

  const dismissAlert = async (event: NewsEvent | null = activeAlert) => {
    if (!event) return
    try {
      await dismissNewsEvent(event.id)
    } catch {
      // Dismiss locally
    }
    setActiveAlert(null)
    setSelectedBriefing(null)
  }

  const filteredMemories = personalMemories.filter((m) => {
    const matchesCategory = memoryFilter === 'all' || m.category.toLowerCase() === memoryFilter.toLowerCase()
    const haystack = `${m.category} ${m.key} ${typeof m.value === 'string' ? m.value : JSON.stringify(m.value)}`.toLowerCase()
    return matchesCategory && (!memorySearch.trim() || haystack.includes(memorySearch.trim().toLowerCase()))
  })

  const saveProfileName = async () => {
    try {
      const result = await updatePersonalProfile({ preferred_name: profileNameDraft.trim() || null })
      setPersonalProfile(result.profile)
      setProfileNotice('Profile updated.')
    } catch (error) {
      setProfileNotice(error instanceof Error ? error.message : 'Profile update failed.')
    }
  }

  const forgetMemory = async (memoryId: number) => {
    if (!window.confirm('Forget this personal memory?')) return
    try {
      await forgetPersonalMemory(memoryId)
      setPersonalMemories((current) => current.filter((item) => item.id !== memoryId))
    } catch (error) {
      setProfileNotice(error instanceof Error ? error.message : 'Memory could not be forgotten.')
    }
  }

  return (
    <main
      className={`app-container state-${visualState}`}
      onPointerOverCapture={handlePointerOver}
      onClickCapture={handleClickCapture}
      onPointerDownCapture={unlockSound}
      onKeyDownCapture={unlockSound}
    >
      <InstrumentCursor />

      {/* Breaking News / Alert Toast */}
      {activeAlert && !selectedBriefing && (
        <div className="alert-card" role="dialog" aria-live="assertive" aria-label="Development alert">
          <div className="alert-top">
            <span className="badge-alert">{String(activeAlert.importance).toUpperCase()} UPDATE</span>
            <span className="alert-timestamp">
              {new Date(activeAlert.last_alerted_at ?? activeAlert.last_seen_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <h3 className="alert-headline">{activeAlert.title}</h3>
          <p className="alert-body">{activeAlert.summary || 'Click to view the verified briefing and sources.'}</p>
          <div className="alert-btn-row">
            <button
              type="button"
              className="btn-alert-read"
              onClick={() => setSelectedBriefing(activeAlert)}
              data-sound="click"
            >
              View Full Briefing
            </button>
            <button
              type="button"
              className="btn-alert-dismiss"
              onClick={() => void dismissAlert(activeAlert)}
              data-sound="click"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Intelligence Briefing Modal */}
      {selectedBriefing && (
        <div className="modal-backdrop" aria-label="News Briefing Modal">
          <div className="briefing-dialog">
            <div className="briefing-modal-head">
              <div>
                <div className="briefing-tags">
                  <span className="badge-solid">{selectedBriefing.importance.toUpperCase()} PRIORITY</span>
                  <span className="badge-outline">{selectedBriefing.source || 'Verified Reports'}</span>
                </div>
                <h2>{selectedBriefing.title}</h2>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => {
                  setSelectedBriefing(null)
                  if (activeAlert && activeAlert.id === selectedBriefing.id) {
                    void dismissAlert(activeAlert)
                  }
                }}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            <div className="briefing-modal-body">
              <div className="briefing-card-grid">
                <div className="briefing-card">
                  <h4>Summary & Facts</h4>
                  <p>{selectedBriefing.briefing?.what_happened || selectedBriefing.summary || selectedBriefing.title}</p>
                </div>
                <div className="briefing-card">
                  <h4>Context & Impact</h4>
                  <p>{selectedBriefing.briefing?.why_it_matters || 'Material development affecting security, technology, or current operations.'}</p>
                </div>
                <div className="briefing-card">
                  <h4>Confirmed Points</h4>
                  <p>{selectedBriefing.briefing?.what_is_confirmed || 'Reporting is being continuously monitored and verified.'}</p>
                </div>
                <div className="briefing-card">
                  <h4>Uncertain / Developing</h4>
                  <p>{selectedBriefing.briefing?.what_is_uncertain || 'Details on timeline and scope remain evolving.'}</p>
                </div>
              </div>

              {selectedBriefing.briefing?.timeline && selectedBriefing.briefing.timeline.length > 0 && (
                <div className="briefing-timeline-card">
                  <h4>Chronology of Events</h4>
                  <ul className="timeline-items">
                    {selectedBriefing.briefing.timeline.map((item, index) => (
                      <li key={index}>
                        <span className="timeline-dot" />
                        <span className="timeline-time">
                          {item.time ? new Date(item.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recent'}
                        </span>
                        <span className="timeline-text">{item.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedBriefing.briefing?.source_links && selectedBriefing.briefing.source_links.length > 0 && (
                <div className="briefing-sources-card">
                  <h4>Source Citations</h4>
                  <div className="sources-list">
                    {selectedBriefing.briefing.source_links.map((link, index) => (
                      <a
                        key={index}
                        href={link.url ?? '#'}
                        target="_blank"
                        rel="noreferrer"
                        className="source-link-pill"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                        {link.title || link.url}
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Left Sidebar Rail */}
      <aside className="sidebar-rail">
        <div className="brand-logo" title="LEON Assistant">
          <div className="logo-box">
            <span>L</span>
            <i className="brand-pulse" />
          </div>
        </div>

        <nav className="nav-menu" aria-label="Main Navigation">
          {navItems.map(({ id, label, icon }) => (
            <button
              key={id}
              className={`nav-button ${activeNav === id ? 'active' : ''}`}
              onClick={() => setActiveNav(id)}
              aria-current={activeNav === id ? 'page' : undefined}
              data-sound="click"
              title={label}
            >
              <div className="nav-icon">{icon}</div>
              <span className="nav-label">{label}</span>
            </button>
          ))}
        </nav>

        <div className="rail-bottom-actions">
          <div className="sound-control-wrap">
          <button
            className={`sound-btn ${muted ? 'muted' : 'active'}`}
            type="button"
            aria-label={muted ? 'Unmute sounds' : 'Mute sounds'}
            onClick={() => {
              const next = !muted
              setMuted(next)
              setSoundMuted(next)
              if (replyAudio.current) replyAudio.current.muted = next
              if (replyTextAudio.current) replyTextAudio.current.muted = next
            }}
            data-sound="click"
            title={muted ? 'Audio Muted' : 'Audio Active'}
          >
            {muted ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/></svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
            )}
          </button>
            <button
              className="sound-settings-btn"
              type="button"
              aria-label="Adjust LEON audio volume"
              aria-expanded={soundControlsOpen}
              aria-controls="sound-controls-panel"
              onClick={() => setSoundControlsOpen((open) => !open)}
              title="Adjust audio volume"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="4" y1="21" x2="4" y2="14" />
                <line x1="4" y1="10" x2="4" y2="3" />
                <line x1="12" y1="21" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12" y2="3" />
                <line x1="20" y1="21" x2="20" y2="16" />
                <line x1="20" y1="12" x2="20" y2="3" />
                <line x1="2" y1="14" x2="6" y2="14" />
                <line x1="10" y1="8" x2="14" y2="8" />
                <line x1="18" y1="16" x2="22" y2="16" />
              </svg>
            </button>
            {soundControlsOpen && (
              <div className="sound-controls-panel" id="sound-controls-panel">
                <label htmlFor="leon-sound-volume">LEON audio volume</label>
                <div className="sound-volume-row">
                  <input
                    id="leon-sound-volume"
                    type="range"
                    min="0"
                    max="100"
                    value={Math.round(soundVolume * 100)}
                    onChange={(event) => {
                      const nextVolume = Number(event.currentTarget.value) / 100
                      setSoundVolumePercent(nextVolume)
                      persistSoundVolume(nextVolume)
                      if (replyAudio.current) replyAudio.current.volume = nextVolume
                      if (replyTextAudio.current) replyTextAudio.current.volume = nextVolume
                    }}
                  />
                  <output htmlFor="leon-sound-volume">{Math.round(soundVolume * 100)}%</output>
                </div>
              </div>
            )}
          </div>

          <div className={`status-pill-small ${connected ? 'online' : 'offline'}`} title={`Backend: ${connection.toUpperCase()}`}>
            <span className="status-dot" />
          </div>
        </div>
      </aside>

      {/* Main Workspace Area */}
      <div className="workspace-main">
        {/* Top Header Bar */}
        <header className="workspace-topbar">
          <div className="breadcrumb-box">
            <span className="breadcrumb-root">LEON</span>
            <span className="breadcrumb-sep">/</span>
            <span className="breadcrumb-current">{activeNav}</span>
          </div>

          <div className="topbar-status-group">
            {/* Spotify Status */}
            <div className="status-pill spotify-pill">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.48.66.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
              </svg>
              <span>{spotify?.authenticated ? (media?.state === 'PLAYING' ? `Playing: ${media.title ?? 'Track'}` : 'Spotify Connected') : 'Spotify Inactive'}</span>
              {spotify?.authenticated ? (
                <button
                  type="button"
                  className="btn-status-action"
                  onClick={() => void removeSpotifyConnection()}
                  disabled={spotifyBusy}
                >
                  Disconnect
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-status-action primary"
                  onClick={() => void startSpotifyConnect()}
                  disabled={spotifyBusy || !spotifyConfigured}
                >
                  Connect
                </button>
              )}
            </div>

            {/* Backend Connection */}
            <div className={`status-pill ${connected ? 'online' : 'offline'}`}>
              <span className="status-dot" />
              <span>{connection === 'online' ? 'BACKEND ONLINE' : connection === 'offline' ? 'OFFLINE' : 'CONNECTING'}</span>
            </div>
          </div>
        </header>

        {syncIssues.length > 0 && (
          <div className="workspace-sync-notice" role="status" aria-live="polite">
            <strong>{connection === 'offline' ? 'Backend unavailable' : 'Some workspace data is out of date'}</strong>
            <span>
              {connection === 'offline'
                ? 'LEON will reconnect automatically. Last available data is being kept on screen.'
                : `Could not refresh: ${syncIssues.join(', ')}. Last available data is being kept on screen.`}
            </span>
          </div>
        )}

        {/* Content Body Grid */}
        <div className="workspace-grid">
          {/* Main Stage Panel */}
          <section className="main-stage-card" aria-label="Main View">
            {activeNav === 'Overview' && (
              <LeonCoreHero
                state={visualState === 'offline' ? 'offline' : coreState}
                connectionState={connection}
                connected={connected}
                voiceState={voiceState}
                activeNav={activeNav}
                onQuickPrompt={(p) => void handleExecutePrompt(p)}
              />
            )}

            {activeNav === 'Tasks' && (
              <div className="tasks-view-container">
                <div className="view-header">
                  <div>
                    <span className="section-badge">TASKS + MISSIONS</span>
                    <h2 className="view-title">Mission Workflow Engine</h2>
                  </div>
                  <div className="badge-count">{recentTasks.length} Recent</div>
                </div>

                <div className="tasks-layout-grid">
                  {/* Active / Selected Task Card */}
                  <div className="task-detail-card">
                    <div className="task-detail-header">
                      <span className={`task-badge-status status-${detailTask?.status ?? 'idle'}`}>
                        {detailTask ? formatTaskStatus(detailTask.status) : 'NO TASK SELECTED'}
                      </span>
                        {detailTask && <span className="task-id-tag">{detailTask.task_type === 'mission' ? 'Mission' : 'Task'} #{detailTask.id}</span>}
                    </div>

                    <h3 className="task-detail-title">{detailTask?.title ?? 'No task selected'}</h3>
                    <p className="task-detail-stage">{detailTask?.current_stage || (detailTask ? 'Awaiting execution details.' : 'Send a command below to start a new task.')}</p>

                    {detailTask && (
                      <div className="task-progress-box">
                        <div className="progress-labels">
                          <span>Execution Progress</span>
                          <strong>{Math.round(detailTask.progress)}%</strong>
                        </div>
                        <div className="progress-bar-track">
                          <div className="progress-bar-fill" style={{ width: `${Math.max(0, Math.min(100, detailTask.progress))}%` }} />
                        </div>
                        {detailTask.status === 'failed' && (
                          <div className="task-failure-summary" role="alert">
                            <strong>Failed step</strong>
                            <span>{detailTask.current_stage || 'Execution'}</span>
                            {detailTask.error && <span>{detailTask.error}</span>}
                            {detailTask.completed_at && <span>{new Date(detailTask.completed_at).toLocaleString()}</span>}
                            {detailTask.task_type === 'mission' && (
                              <button type="button" className="task-retry-button" onClick={() => void retryTask(detailTask)}>
                                Retry mission
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {detailTask && (
                      <div className="task-stepper-row" aria-label="Task lifecycle">
                        {taskLifecycle(detailTask).map((stage, index, stages) => (
                          <Fragment key={`${detailTask.id}-${stage}-${index}`}>
                            <div className={`step-item active ${stage === detailTask.status ? 'current' : ''}`}>
                              <span className="step-circle">{index + 1}</span>
                              <span>{formatTaskStatus(stage)}</span>
                            </div>
                            {index < stages.length - 1 && <div className="step-line" />}
                          </Fragment>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Tasks List */}
                  <div className="tasks-history-card">
                    <div className="tasks-history-heading">
                      <h4>Recent tasks</h4>
                      {hiddenRecentTaskIds.size > 0 && (
                        <button
                          type="button"
                          className="show-hidden-tasks"
                          onClick={() => setShowHiddenRecentTasks((current) => !current)}
                        >
                          {showHiddenRecentTasks ? 'Hide removed' : `Show removed (${hiddenRecentTaskIds.size})`}
                        </button>
                      )}
                    </div>
                    <div className="tasks-list">
                      {recentTasks.length === 0 ? (
                        <div className="empty-list-placeholder">
                          {hiddenRecentTaskIds.size
                            ? 'No recent tasks are visible. Show removed tasks to restore one.'
                            : 'No tasks recorded yet. Issue a request below to get started.'}
                        </div>
                      ) : (
                        recentTasks.map((task) => (
                          <div
                            className={`task-list-entry${hiddenRecentTaskIds.has(task.id) ? ' removed' : ''}`}
                            key={task.id}
                          >
                            <button
                              type="button"
                              className={`task-list-item ${task.id === currentTask?.id ? 'selected' : ''}`}
                              onClick={() => setSelectedTaskId(task.id)}
                            >
                              <div className="task-item-main">
                        <span className="task-item-title">{task.task_type === 'mission' ? 'MISSION · ' : ''}{task.title}</span>
                                <span className="task-item-date">{task.created_at ? new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                              </div>
                              <span className={`task-pill-state status-${task.status}`}>{formatTaskStatus(task.status)}</span>
                            </button>
                            <button
                              type="button"
                              className="task-hide-button"
                              aria-label={`${hiddenRecentTaskIds.has(task.id) ? 'Restore' : 'Remove'} ${task.title} ${hiddenRecentTaskIds.has(task.id) ? 'to' : 'from'} recent tasks`}
                              title={hiddenRecentTaskIds.has(task.id) ? 'Restore to recent tasks' : 'Remove from recent tasks'}
                              onClick={() => hiddenRecentTaskIds.has(task.id)
                                ? setHiddenRecentTaskIds((current) => {
                                  const next = new Set(current)
                                  next.delete(task.id)
                                  return next
                                })
                                : hideRecentTask(task.id)}
                            >
                              {hiddenRecentTaskIds.has(task.id) ? '↶' : '×'}
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeNav === 'Memory' && (
              <div className="memory-view-container">
                <div className="view-header">
                  <div>
                    <span className="section-badge">PERSISTENT KNOWLEDGE</span>
                    <h2 className="view-title">Long-Term Memory</h2>
                  </div>
                  <div className="memory-filter-row">
                    {['all', 'IDENTITY', 'RELATIONSHIP', 'PREFERENCE', 'PROJECT', 'GOAL', 'CONTEXT'].map((f) => (
                      <button
                        key={f}
                        type="button"
                        className={`filter-btn ${memoryFilter === f ? 'active' : ''}`}
                        onClick={() => setMemoryFilter(f)}
                      >
                        {f.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="memory-profile-grid">
                  <section className="memory-profile-card">
                    <span className="section-badge">MY PROFILE</span>
                    <h3>{personalProfile?.preferred_name || 'Name not stored'}</h3>
                    <p>{personalProfile?.location || 'Location unknown'} · {personalProfile?.timezone || 'Timezone unknown'}</p>
                    <p>{personalProfile?.languages?.join(', ') || 'Language preference unknown'}</p>
                    <label className="memory-edit-label" htmlFor="profile-name">Preferred name</label>
                    <div className="memory-edit-row">
                      <input id="profile-name" value={profileNameDraft} onChange={(event) => setProfileNameDraft(event.target.value)} placeholder="Not set" />
                      <button type="button" onClick={() => void saveProfileName()}>Save</button>
                    </div>
                    {profileNotice && <small className="memory-date" role="status">{profileNotice}</small>}
                  </section>
                  <section className="memory-profile-card">
                    <span className="section-badge">WORK & EDUCATION</span>
                    <p>{personalProfile?.work && Object.keys(personalProfile.work).length ? JSON.stringify(personalProfile.work) : 'No work context stored.'}</p>
                    <p>{personalProfile?.education && Object.keys(personalProfile.education).length ? JSON.stringify(personalProfile.education) : 'No education context stored.'}</p>
                  </section>
                  <section className="memory-profile-card">
                    <span className="section-badge">IMPORTANT PEOPLE</span>
                    {relationships.length ? relationships.map((person) => <p key={person.person_id}><strong>{person.name}</strong> · {person.relationship_type}</p>) : <p>No relationships stored.</p>}
                  </section>
                  <section className="memory-profile-card">
                    <span className="section-badge">IMPORTANT DATES</span>
                    {importantDates.length ? importantDates.map((date) => <p key={date.id}><strong>{date.name}</strong> · {date.date_value}</p>) : <p>No important dates stored.</p>}
                  </section>
                </div>

                <input
                  className="memory-search-input"
                  value={memorySearch}
                  onChange={(event) => setMemorySearch(event.target.value)}
                  placeholder="Search personal memory"
                  aria-label="Search personal memory"
                />

                <div className="memory-cards-grid">
                  {filteredMemories.length === 0 ? (
                    <div className="empty-state-box">
                      <div className="empty-state-icon">🧠</div>
                      <h3>No personal memories found</h3>
                      <p>Teach LEON explicitly from chat or voice. Only approved durable context appears here.</p>
                    </div>
                  ) : (
                    filteredMemories.map((mem) => (
                      <div key={mem.id} className="memory-card">
                        <div className="memory-card-top">
                          <span className="memory-type-badge">{mem.category}</span>
                          <span className="memory-date">{mem.confidence} · {mem.privacy_level}</span>
                        </div>
                        <p className="memory-content"><strong>{mem.key}</strong><br />{typeof mem.value === 'string' ? mem.value : JSON.stringify(mem.value)}</p>
                        <small className="memory-date">{mem.source} · Updated {new Date(mem.updated_at).toLocaleDateString()}</small>
                        <button type="button" className="memory-forget-button" onClick={() => void forgetMemory(mem.id)}>Forget</button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {activeNav === 'Media' && (
              <div className="media-view-container">
                <div className="view-header">
                  <div>
                    <span className="section-badge">MEDIA & DISCOVERY</span>
                    <h2 className="view-title">Media Center</h2>
                  </div>
                  <span className={`badge-pill ${spotify?.authenticated ? 'online' : 'offline'}`}>
                    {spotify?.error_code === 'SPOTIFY_SCOPE_REQUIRED' ? '● Permission needed' : spotify?.authenticated ? '● Connected' : 'Disconnected'}
                  </span>
                </div>

                {spotifyNotice && (
                  <p className={`spotify-notice ${spotifyNotice.includes('successfully') ? 'success' : ''}`} role="status">
                    {spotifyNotice}
                  </p>
                )}
                {!spotifyConfigured && (
                  <p className="spotify-setup-hint">
                    To connect Spotify, add your Spotify Developer app client ID and secret to the backend environment,
                    register the exact <code>SPOTIFY_REDIRECT_URI</code> in the Spotify app settings, then restart the backend.
                  </p>
                )}

                <div className="media-player-grid">
                  {/* Now Playing Card */}
                  <div className="player-main-card">
                    <div className="album-art-box">
                      {media?.album_art_url ? (
                        <img className="album-art-image" src={media.album_art_url} alt="Current Spotify album artwork" />
                      ) : (
                        <div className={`vinyl-disc ${media?.state === 'PLAYING' ? 'spinning' : ''}`}>
                          <div className="vinyl-center" />
                        </div>
                      )}
                    </div>

                    <div className="track-details">
                      <span className="track-status-label">{media?.state === 'PLAYING' ? 'NOW PLAYING' : media?.state === 'PAUSED' ? 'PAUSED' : 'IDLE'}</span>
                      <h3 className="track-title">{media?.title || (spotify?.authenticated ? 'Nothing currently playing' : 'Spotify is not connected')}</h3>
                      <p className="track-artist">{media?.artist || (spotify?.authenticated ? 'Enable LEON Player to start browser playback' : 'Authenticate Spotify to enable full media control')}</p>
                    </div>

                    {media?.duration_ms ? (
                      <div className="spotify-progress" aria-label="Playback progress">
                        <div className="spotify-progress-track"><div style={{ width: `${Math.min(100, ((media.progress_ms ?? 0) / media.duration_ms) * 100)}%` }} /></div>
                        <span>{Math.floor((media.progress_ms ?? 0) / 60000)}:{String(Math.floor(((media.progress_ms ?? 0) % 60000) / 1000)).padStart(2, '0')} / {Math.floor(media.duration_ms / 60000)}:{String(Math.floor((media.duration_ms % 60000) / 1000)).padStart(2, '0')}</span>
                      </div>
                    ) : null}

                    <div className="player-controls-row" aria-label="Spotify playback controls">
                      <button
                        type="button"
                        className="control-btn"
                        onClick={() => void handleSpotifyControl('previous')}
                        disabled={spotifyBusy || !spotify?.authenticated || !spotifyPlayer.deviceId}
                        title="Previous track"
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2"/></svg>
                      </button>

                      <button
                        type="button"
                        className="control-btn-play"
                        onClick={() => void handleSpotifyControl(media?.state === 'PLAYING' ? 'pause' : 'resume')}
                        disabled={spotifyBusy || !spotify?.authenticated || !spotifyPlayer.deviceId}
                        title={media?.state === 'PLAYING' ? 'Pause' : 'Play'}
                      >
                        {media?.state === 'PLAYING' ? (
                          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                        ) : (
                          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        )}
                      </button>

                      <button
                        type="button"
                        className="control-btn"
                        onClick={() => void handleSpotifyControl('next')}
                        disabled={spotifyBusy || !spotify?.authenticated || !spotifyPlayer.deviceId}
                        title="Next track"
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2"/></svg>
                      </button>
                    </div>
                  </div>

                  {/* Device & Status Card */}
                  <div className="media-info-card">
                    <h4>Device & Configuration</h4>
                    <div className="info-list">
                      <div className="info-row">
                        <span>LEON Player</span>
                        <strong>{spotifyPlayer.deviceId ? 'READY' : spotifyPlayer.state === 'AUTOPLAY_BLOCKED' ? 'NEEDS ACTIVATION' : spotifyPlayer.state.replace(/_/g, ' ')}</strong>
                      </div>
                      <div className="info-row">
                        <span>Configuration</span>
                        <strong>{spotifyConfigured ? 'Configured in backend' : 'Client ID / Secret missing'}</strong>
                      </div>
                      <div className="info-row">
                        <span>Account Access</span>
                        <strong>{spotify?.error_code === 'SPOTIFY_SCOPE_REQUIRED' ? 'Permission needed' : spotify?.authenticated ? 'Authorized' : 'Requires Login'}</strong>
                      </div>
                      <div className="info-row">
                        <span>Account Plan</span>
                        <strong>{spotify?.premium_available === true ? 'Premium' : spotify?.premium_available === false ? 'Not eligible' : 'Unknown'}</strong>
                      </div>
                    </div>

                    {spotifyPlayer.errorMessage && <p className="spotify-config-note" role="alert">{spotifyPlayer.errorMessage}</p>}
                    {spotify?.error_code === 'SPOTIFY_SCOPE_REQUIRED' && (
                      <p className="spotify-config-note" role="alert">
                        Spotify needs additional Web Playback permission. Reauthorize your account to enable the LEON Player.
                      </p>
                    )}

                    {!spotify?.authenticated && (
                      <p className="spotify-config-note">
                        If Spotify shows <code>client_id: Invalid</code>, replace the backend client ID with the real ID from your Spotify Developer app.
                        Also register the exact <code>SPOTIFY_REDIRECT_URI</code> shown in the backend environment.
                      </p>
                    )}

                    <div className="media-action-buttons">
                      {spotify?.authenticated && !spotifyPlayer.deviceId && (
                        <button
                          type="button"
                          className="btn-connect"
                          onClick={() => void (spotify?.error_code === 'SPOTIFY_SCOPE_REQUIRED' ? startSpotifyConnect() : spotifyPlayer.state === 'SDK_NOT_READY' ? retryPlayer() : enablePlayer())}
                          disabled={spotifyBusy || spotifyPlayer.state === 'SDK_LOADING'}
                        >
                          {spotifyPlayer.state === 'SDK_LOADING' ? 'Initializing Player…' : spotify?.error_code === 'SPOTIFY_SCOPE_REQUIRED' ? 'Reauthorize Spotify' : spotifyPlayer.state === 'ERROR' ? 'Retry Player' : 'Enable LEON Player'}
                        </button>
                      )}
                      {spotify?.authenticated ? (
                        <button
                          type="button"
                          className="btn-disconnect"
                          onClick={() => void removeSpotifyConnection()}
                          disabled={spotifyBusy}
                        >
                          Disconnect Spotify
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn-connect"
                          onClick={() => void startSpotifyConnect()}
                          disabled={spotifyBusy || !spotifyConfigured}
                        >
                          {spotifyConfigured ? 'Authorize Spotify' : 'Setup Spotify Credentials'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <section className="media-link-groups" aria-label="Media, social and news websites">
                  {mediaLinkGroups.map((group) => (
                    <div className="media-link-group" key={group.title}>
                      <h3>{group.title}</h3>
                      <div className="media-link-grid">
                        {group.links.map((link) => (
                          <a
                            className="media-link-card"
                            href={link.url}
                            key={link.name}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <span className="media-link-name">{link.name}</span>
                            <span className="media-link-description">{link.description}</span>
                            <span className="media-link-open" aria-hidden="true">↗</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  ))}
                </section>
              </div>
            )}

            {activeNav === 'System' && (
              <div className="system-view-container">
                <div className="view-header">
                  <div>
                    <span className="section-badge">DIAGNOSTICS</span>
                    <h2 className="view-title">System Infrastructure</h2>
                  </div>
                  <span className={`status-pill ${connection === 'online' ? 'online' : connection === 'offline' ? 'offline' : 'connecting'}`}>
                    <span className="status-dot" />
                    {connection === 'online' ? 'ONLINE' : connection === 'offline' ? 'OFFLINE' : 'CONNECTING'}
                  </span>
                </div>

                <div className="system-grid">
                  <div className="system-stat-card">
                    <span className="stat-label">API SERVICE</span>
                    <strong className="stat-value">{health?.service || 'LEON Core'}</strong>
                    <small className="stat-sub">Version {health?.version || '1.0.0'}</small>
                  </div>

                  <div className="system-stat-card">
                    <span className="stat-label">VOICE SYNTHESIS (TTS)</span>
                    <strong className="stat-value">Voice service</strong>
                    <small className="stat-sub">Status is reported when used</small>
                  </div>

                  <div className="system-stat-card">
                    <span className="stat-label">VISION PIPELINE</span>
                    <strong className="stat-value">Vision service</strong>
                    <small className="stat-sub">Status is reported when used</small>
                  </div>

                  <div className="system-stat-card">
                    <span className="stat-label">STORAGE</span>
                    <strong className="stat-value status-online">SQLite</strong>
                    <small className="stat-sub">{memories.length} memories stored</small>
                  </div>
                </div>

                <div className="system-details-box">
                  <h4>Component Statuses</h4>
                  <div className="subsystem-rows">
                    <div className="subsystem-item">
                      <span className={`subsystem-dot ${connection === 'online' ? 'live' : ''}`} />
                      <span className="subsystem-name">Local HTTP Server</span>
                      <span className="subsystem-state">{connection === 'online' ? 'ONLINE' : connection === 'offline' ? 'OFFLINE' : 'CONNECTING'}</span>
                    </div>
                    <div className="subsystem-item">
                      <span className="subsystem-dot" />
                      <span className="subsystem-name">Speech-to-Text Transcriber</span>
                      <span className="subsystem-state">NOT CHECKED</span>
                    </div>
                    <div className="subsystem-item">
                      <span className={`subsystem-dot ${spotify?.authenticated ? 'live' : ''}`} />
                      <span className="subsystem-name">Spotify API Integration</span>
                      <span className="subsystem-state">{spotify?.authenticated ? 'ONLINE' : 'STANDBY'}</span>
                    </div>
                    <div className="subsystem-item">
                      <span className="subsystem-dot" />
                      <span className="subsystem-name">Task Automation Worker</span>
                      <span className="subsystem-state">NOT CHECKED</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeNav === 'Vision' && (
              <div className="vision-view-container">
                <VisionPanel />
              </div>
            )}

            {activeNav === 'Computer' && (
              <div className="computer-view-container">
                <ComputerUsePanel />
              </div>
            )}
          </section>

          {/* Right Side Activity / Workbench */}
          <aside className="workspace-aside">
            {/* Quick Task Status Card */}
            <div className="aside-card">
              <div className="aside-card-header">
                <span className="section-badge">{activeTask ? 'ACTIVE TASK' : 'CURRENT TASK'}</span>
                <span className={`task-chip ${activeTask?.status ?? 'quiet'}`}>
                  {activeTask ? formatTaskStatus(activeTask.status) : 'Idle'}
                </span>
              </div>
              <h4 className="current-task-title">{activeTask?.title ?? 'No active task'}</h4>
              <p className="current-task-sub">
                {activeTask?.current_stage || 'LEON is ready for your next instruction.'}
              </p>
              {activeTask && (
                <div className="task-mini-progress">
                  <div className="mini-progress-bar" style={{ width: `${Math.max(0, Math.min(100, activeTask.progress))}%` }} />
                </div>
              )}
            </div>

            {/* Quick Intelligence / News Card */}
            <div className="aside-card">
              <div className="aside-card-header">
                <span className="section-badge">LATEST BRIEFINGS</span>
                <span className="badge-count">{newsEvents.length}</span>
              </div>
              <div className="news-feed-list">
                {newsEvents.length === 0 ? (
                  <p className="news-empty">No updates at this moment.</p>
                ) : (
                  newsEvents.slice(0, 3).map((event) => (
                    <button
                      key={event.id}
                      type="button"
                      className="news-item-button"
                      onClick={() => setSelectedBriefing(event)}
                    >
                      <span className="news-title">{event.title}</span>
                      <span className="news-meta">
                        {event.importance.toUpperCase()} · {new Date(event.last_seen_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </aside>
        </div>

        {/* Bottom Command & Voice Deck */}
        <footer className="command-footer-dock">
          {/* Assistant Reply Line */}
          {reply && (
            <div className="reply-bubble" aria-live="polite">
              <div className="reply-avatar">L</div>
              <div className="reply-text-box">
                <p>{reply}</p>
                <div className="reply-actions" aria-label="Reply actions">
                  {pendingConfirmation && (
                    <>
                      <button type="button" className="reply-action-button primary" onClick={() => void confirmPendingCommand()}>
                        Confirm action
                      </button>
                      <button type="button" className="reply-action-button" onClick={() => { setPendingConfirmation(null); setPendingConfirmationId(null) }}>
                        Cancel
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    className="reply-action-button"
                    onClick={() => readAloudState === 'playing' || readAloudState === 'loading'
                      ? stopReplySpeech()
                      : void readReplyAloud()}
                  >
                    {readAloudState === 'loading' ? 'Preparing audio…' : readAloudState === 'playing' ? 'Stop reading' : 'Read aloud'}
                  </button>
                  {voiceAudio && (
                    <button
                      type="button"
                      className="reply-action-button"
                      onClick={() => void playVoiceReply()}
                      title="Play response voice"
                    >
                      Listen
                    </button>
                  )}
                  <button type="button" className="reply-action-button" onClick={() => void copyReply()}>
                    Copy
                  </button>
                  <button type="button" className="reply-action-button" onClick={downloadReply}>
                    Download
                  </button>
                  <button type="button" className="reply-action-button" onClick={() => void rateReply(5)}>
                    Helpful
                  </button>
                  <button type="button" className="reply-action-button" onClick={() => void rateReply(1)}>
                    Needs improvement
                  </button>
                  {replyActionNotice && <span className="reply-action-notice" role="status">{replyActionNotice}</span>}
                </div>
              </div>
            </div>
          )}

          {/* Voice transcript display */}
          {voiceTranscript && (
            <div className="voice-transcript-banner">
              <span className="voice-tag">YOU</span>
              <p>{voiceTranscript}</p>
            </div>
          )}

          {voiceError && (
            <div className="voice-error-banner" role="alert">
              <span>⚠</span> {voiceError}
            </div>
          )}

          {/* Command Form */}
          <form className="command-bar-form" onSubmit={handleSubmit}>
            {/* Voice Mic Button */}
            <button
              type="button"
              className={`mic-button ${voiceState === 'listening' ? 'recording' : ''}`}
              onClick={voiceState === 'listening' ? stopListening : () => void startListening()}
              disabled={voiceState === 'processing' || voiceState === 'speaking'}
              title={voiceState === 'listening' ? 'Stop recording' : 'Start voice input'}
              data-sound="click"
            >
              {voiceState === 'listening' ? (
                <div className="pulse-mic-icon">
                  <span className="pulse-ring" />
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                </div>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
              )}
            </button>

            {/* Text Input */}
            <input
              id="command-input"
              className="command-input-field"
              value={command}
              placeholder="Ask LEON anything or give a task... (Press Enter to send)"
              onFocus={() => {
                playSound('focus')
                if (interaction === 'idle') showState('focus')
              }}
              onBlur={() => {
                if (interaction === 'focus') showState('idle')
              }}
              onChange={(event) => setCommand(event.target.value)}
            />

            {/* Send Button */}
            <button
              type="submit"
              className="btn-send-command"
              disabled={!command.trim()}
              data-sound="send"
              title="Send command"
            >
              <span>Send</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </form>
        </footer>
      </div>
    </main>
  )
}
