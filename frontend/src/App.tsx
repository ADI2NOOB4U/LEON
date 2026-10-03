import { useEffect, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { motion } from 'motion/react'
import { InstrumentCursor } from './interactions/InstrumentCursor'
import { getMuted, playSound, setMuted as setSoundMuted, unlockSound } from './interactions/sound'
import type { InteractionState } from './graphics/motion'
import { LeonCoreHero } from './components/LeonCoreHero'
import { VisionPanel } from './components/VisionPanel'
import { interactionVariants } from './graphics/motion'
import { connectSpotify, dismissNewsEvent, disconnectSpotify, fetchMediaStatus, fetchMemory, fetchNewsEvents, fetchSpotifyStatus, fetchTasks, sendCommand, sendVoiceTurn } from './api/client'
import { useHealthPolling } from './hooks/useHealthPolling'
import type { HealthConnectionState } from './api/healthPoller'
import type { HealthStatus, MediaStatus, Memory, NewsEvent, SpotifyStatus, Task, VoiceState, VoiceTurnResponse } from './types/api'

const nav = [
  { glyph: '◌', label: 'Sanctum' },
  { glyph: '⌁', label: 'Missions' },
  { glyph: '⌑', label: 'Memory' },
  { glyph: '◈', label: 'Media' },
  { glyph: '⌘', label: 'Systems' },
  { glyph: '◉', label: 'Vision' },
]

const activeStatuses = new Set(['queued', 'planning', 'running', 'executing', 'verifying'])

function stateFromTask(status?: string): InteractionState {
  if (status === 'queued' || status === 'planning') return 'thinking'
  if (status === 'running' || status === 'executing' || status === 'verifying') return 'executing'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  return 'idle'
}

function morphingVoidState(state: InteractionState): 'idle' | 'listening' | 'thinking' | 'executing' | 'success' | 'error' {
  return state === 'hover' || state === 'focus' ? 'idle' : state
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
  const [activeNav, setActiveNav] = useState('Sanctum')
  const [interaction, showState] = useResettableState()
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [command, setCommand] = useState('')
  const [reply, setReply] = useState('')
  const [memories, setMemories] = useState<Memory[]>([])
  const [newsEvents, setNewsEvents] = useState<NewsEvent[]>([])
  const [activeAlert, setActiveAlert] = useState<NewsEvent | null>(null)
  const [selectedBriefing, setSelectedBriefing] = useState<NewsEvent | null>(null)
  const { connection, health } = useHealthPolling()
  const [media, setMedia] = useState<MediaStatus | null>(null)
  const [spotify, setSpotify] = useState<SpotifyStatus | null>(null)
  const [spotifyBusy, setSpotifyBusy] = useState(false)
  const [muted, setMuted] = useState(getMuted)
  const [coreHovered, setCoreHovered] = useState(false)
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [voiceError, setVoiceError] = useState('')
  const [voiceAudio, setVoiceAudio] = useState('')
  const voiceRequest = useRef(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const microphone = useRef<MediaStream | null>(null)
  const replyAudio = useRef<HTMLAudioElement | null>(null)
  const previousStatuses = useRef(new Map<number, string>())
  const lastAlertId = useRef<number | null>(null)
  const mediaLoaded = useRef(false)

  const startSpotifyConnect = async () => {
    setSpotifyBusy(true)
    try {
      const result = await connectSpotify()
      window.location.assign(result.authorization_url)
    } catch (error) {
      setReply(error instanceof Error ? error.message : 'Spotify is not configured yet.')
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
    } finally {
      setSpotifyBusy(false)
    }
  }

  const handleSpotifyControl = async (action: 'previous' | 'pause' | 'resume' | 'next') => {
    if (!spotify?.authenticated) return
    setSpotifyBusy(true)
    try {
      const commandText = action === 'previous'
        ? 'Previous song'
        : action === 'pause'
          ? 'Pause Spotify'
          : action === 'resume'
            ? 'Resume Spotify'
            : 'Next song'
      const result = await sendCommand(commandText)
      setReply(result.message)
      await refreshSpotifyStatus()
      await fetchMediaStatus().then(setMedia).catch(() => setMedia(null))
    } catch (error) {
      setReply(error instanceof Error ? error.message : 'Spotify control failed.')
    } finally {
      setSpotifyBusy(false)
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const spotifyState = params.get('spotify')
    if (spotifyState) {
      void refreshSpotifyStatus()
      const nextUrl = `${window.location.pathname}${window.location.hash}`
      window.history.replaceState({}, '', nextUrl)
    }
  }, [])

  useEffect(() => {
    const root = document.documentElement
    let raf = 0
    let nextX = 50
    let nextY = 50
    let x = 50
    let y = 50
    let lastTime = performance.now()
    let lastX = 0
    let lastY = 0
    const renderPointer = () => {
      x += (nextX - x) * 0.12
      y += (nextY - y) * 0.12
      root.style.setProperty('--pointer-x', `${x}%`)
      root.style.setProperty('--pointer-y', `${y}%`)
      raf = x !== nextX || y !== nextY ? requestAnimationFrame(renderPointer) : 0
    }
    const move = (event: globalThis.PointerEvent) => {
      if (event.pointerType === 'touch') return
      const now = performance.now()
      const distance = Math.hypot(event.clientX - lastX, event.clientY - lastY)
      const speed = Math.min(1, distance / Math.max(16, now - lastTime) / 1.4)
      root.style.setProperty('--pointer-speed', speed.toFixed(3))
      nextX = (event.clientX / window.innerWidth) * 100
      nextY = (event.clientY / window.innerHeight) * 100
      lastX = event.clientX
      lastY = event.clientY
      lastTime = now
      if (!raf) raf = requestAnimationFrame(renderPointer)
    }
    const visibility = () => root.toggleAttribute('data-page-paused', document.hidden)
    window.addEventListener('pointermove', move, { passive: true })
    document.addEventListener('visibilitychange', visibility)
    return () => {
      window.removeEventListener('pointermove', move)
      document.removeEventListener('visibilitychange', visibility)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  useEffect(() => () => {
    recorder.current?.stop()
    microphone.current?.getTracks().forEach((track) => track.stop())
    replyAudio.current?.pause()
  }, [])

  useEffect(() => {
    let active = true
    let refreshTimer: number | undefined

    const load = async () => {
      if (!active) return

      if (!mediaLoaded.current) {
        const [nextMedia, nextSpotify] = await Promise.allSettled([fetchMediaStatus(), fetchSpotifyStatus()])
        if (active) {
          setMedia(nextMedia.status === 'fulfilled' ? nextMedia.value : null)
          setSpotify(nextSpotify.status === 'fulfilled' ? nextSpotify.value : null)
          mediaLoaded.current = true
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
                showState('success', 1500)
              } else if (task.status === 'failed') {
                playSound('error')
                showState('error', 1500)
              }
            }
            previousStatuses.current.set(task.id, task.status)
          }
          setTasks(nextTasks)
        }
      } catch {
        if (active) {
          setTasks([])
        }
      }

      if (!active) return
      try {
        const nextMemory = await fetchMemory()
        if (active) setMemories(nextMemory)
      } catch {
        if (active) setMemories([])
      }

      if (!active) return
      try {
        const nextEvents = await fetchNewsEvents()
        if (active) {
          setNewsEvents(nextEvents)
          const activeEvent = [...nextEvents]
            .filter((event) => Number(event.alerted) === 1)
            .sort((a, b) => new Date(b.last_alerted_at ?? b.last_seen_at).getTime() - new Date(a.last_alerted_at ?? a.last_seen_at).getTime())[0]
          if (activeEvent && activeEvent.id !== lastAlertId.current) {
            lastAlertId.current = activeEvent.id
            setActiveAlert(activeEvent)
          }
        }
      } catch {
        if (active) setNewsEvents([])
      }

      if (active) refreshTimer = window.setTimeout(() => void load(), 7000)
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
  const activeTask = tasks.find((task) => activeStatuses.has(task.status)) ?? null
  const currentTask = tasks.find((task) => task.id === selectedTaskId) ?? activeTask ?? tasks[0] ?? null
  const coreState = interaction !== 'idle'
    ? interaction
    : coreHovered
      ? 'hover'
      : stateFromTask(activeTask?.status)
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
    if (sound === 'click' || sound === 'focus') playSound(sound)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = command.trim()

    if (!text) {
      return
    }

    unlockSound()
    playSound('message')
    showState('thinking')
    setCommand('')

    try {
      const result = await sendCommand(text)
      setReply(result.message)

      if (result.task) {
        setTasks((current) => [result.task!, ...current.filter((task) => task.id !== result.task!.id)])
        setSelectedTaskId(result.task.id)
        previousStatuses.current.set(result.task.id, result.task.status)
        playSound('taskStart')
        showState('executing', 1800)
      } else {
        playSound('complete')
        showState('success', 1400)
      }
    } catch {
      playSound('error')
      showState('error', 1800)
      setReply('The request could not be completed. Check the connection and try again.')
    }
  }

  const playVoiceReply = async (audioSource = voiceAudio) => {
    if (!audioSource) return
    const audio = new Audio(audioSource)
    replyAudio.current?.pause()
    replyAudio.current = audio
    audio.onended = () => {
      setVoiceState('idle')
      showState('idle')
    }
    audio.onerror = () => {
      setVoiceError('LEON replied, but the audio could not be played.')
      setVoiceState('error')
      showState('error')
    }
    try {
      await audio.play()
      setVoiceState('speaking')
      showState('success')
    } catch {
      setVoiceState('idle')
      setVoiceError('LEON replied. Press play to hear the response.')
    }
  }

  const sendRecording = async (recording: Blob) => {
    if (voiceRequest.current) return
    if (!recording.size) {
      setVoiceState('error')
      setVoiceError('No audio was captured. Try again.')
      showState('error', 1800)
      return
    }

    voiceRequest.current = true
    setVoiceState('processing')
    showState('thinking')
    try {
      const result = await sendVoiceTurn(recording)
      setVoiceTranscript(result.transcript)
      setReply(result.assistant)
      const audioSource = `data:${result.audio_content_type};base64,${result.audio_base64}`
      setVoiceAudio(audioSource)
      if (result.audio_error) {
        setVoiceState('error')
        setVoiceError(result.audio_error)
        showState('error', 1800)
        return
      }
      await playVoiceReply(audioSource)
    } catch (error) {
      setVoiceState('error')
      setVoiceError(error instanceof Error ? error.message : 'The voice request failed.')
      showState('error', 1800)
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

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
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
          // Try the next browser-supported container before falling back to its default.
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
        setVoiceError('The microphone recording failed. Try again.')
        showState('error', 1800)
      }
      activeRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        microphone.current = null
        recorder.current = null
        if (recorderFailed) return
        const chunkWithType = chunks.find(
          (chunk): chunk is Blob => chunk instanceof Blob && Boolean(chunk.type),
        )
        const recordingType = activeRecorder.mimeType
          || chunkWithType?.type
          || ''
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
      setVoiceError(name === 'NotAllowedError'
        ? 'Microphone access was denied. Allow microphone access and try again.'
        : name === 'NotFoundError'
          ? 'No microphone was found on this device.'
          : 'The microphone could not be started.')
      showState('error', 1800)
    }
  }

  const stopListening = () => {
    if (recorder.current?.state === 'recording') {
      recorder.current.stop()
      setVoiceState('processing')
      showState('thinking')
    }
  }

  const dismissAlert = async (event: NewsEvent | null = activeAlert) => {
    if (!event) return
    try {
      await dismissNewsEvent(event.id)
    } catch {
      // Ignore transient dismiss failures; the alert should still close locally.
    }
    setActiveAlert(null)
    setSelectedBriefing(null)
  }

  const briefing = selectedBriefing

  return (
    <main className={`app-shell state-${visualState}`} onPointerOverCapture={handlePointerOver} onClickCapture={handleClickCapture} onPointerDownCapture={unlockSound} onKeyDownCapture={unlockSound}>
      <div className="world-field" aria-hidden="true">
        <span className="world-glow world-glow-a" />
        <span className="world-glow world-glow-b" />



      </div>
      <div className="grain" />
      <InstrumentCursor />

      {activeAlert && !selectedBriefing && (
        <div className="alert-toast" role="dialog" aria-live="assertive" aria-label="Major development alert">
          <div className="alert-header">
            <span className="section-kicker">LEON</span>
            <span className="alert-level">{String(activeAlert.importance).toUpperCase()} ALERT</span>
          </div>
          <h2>{activeAlert.title}</h2>
          <p>{activeAlert.summary || 'Track the latest verified, reported, and uncertain details in the briefing.'}</p>
          <div className="alert-actions">
            <button type="button" onClick={() => setSelectedBriefing(activeAlert)} data-sound="click">Read Briefing</button>
            <button type="button" className="alert-secondary" onClick={() => void dismissAlert(activeAlert)} data-sound="click">Dismiss</button>
          </div>
        </div>
      )}

      {briefing && (
        <div className="briefing-overlay" aria-label="Briefing view">
          <div className="briefing-panel">
            <div className="briefing-head">
              <div>
                <span className="section-kicker">INTELLIGENCE BRIEFING</span>
                <h2>{briefing.title}</h2>
              </div>
              <button type="button" className="close-button" onClick={() => {
                setSelectedBriefing(null)
                if (activeAlert && activeAlert.id === briefing.id) {
                  void dismissAlert(activeAlert)
                }
              }} aria-label="Close briefing">✕</button>
            </div>
            <div className="briefing-meta">
              <span>Importance: {briefing.importance}</span>
              <span>Source: {briefing.source || 'tracked public report'}</span>
              <span>{briefing.first_seen_at ? new Date(briefing.first_seen_at).toLocaleString() : 'timestamp unavailable'}</span>
            </div>
            <div className="briefing-grid">
              <div className="briefing-section">
                <h3>What happened</h3>
                <p>{briefing.briefing?.what_happened || briefing.summary || briefing.title}</p>
              </div>
              <div className="briefing-section">
                <h3>When / where</h3>
                <p><strong>When:</strong> {briefing.briefing?.when_it_happened || briefing.last_seen_at || 'Not specified'}<br /><strong>Where:</strong> {briefing.briefing?.where || briefing.location || 'Global / unspecified'}</p>
              </div>
              <div className="briefing-section">
                <h3>Why it matters</h3>
                <p>{briefing.briefing?.why_it_matters || 'The event is material because it affects public safety, diplomacy, security, or significant geopolitical developments.'}</p>
              </div>
              <div className="briefing-section">
                <h3>Confirmed / uncertain</h3>
                <p><strong>Confirmed:</strong> {briefing.briefing?.what_is_confirmed || 'Reporting remains limited or is still being verified.'}<br /><strong>Uncertain:</strong> {briefing.briefing?.what_is_uncertain || 'Current uncertainty remains around timing, exact scope, and official confirmation.'}</p>
              </div>
              <div className="briefing-section full-width">
                <h3>Timeline</h3>
                <ul>
                  {(briefing.briefing?.timeline && briefing.briefing.timeline.length > 0 ? briefing.briefing.timeline : [{ label: briefing.title, time: briefing.last_seen_at }]).map((item, index) => (
                    <li key={`${item.label ?? 'event'}-${index}`}><span>{item.time ? new Date(item.time).toLocaleString() : 'Unspecified time'}</span> — {item.label || briefing.title}</li>
                  ))}
                </ul>
              </div>
              <div className="briefing-section full-width">
                <h3>Source links</h3>
                <ul>
                  {(briefing.briefing?.source_links && briefing.briefing.source_links.length > 0 ? briefing.briefing.source_links : [{ title: briefing.source || 'Lead source', url: briefing.source_url || '#' }]).map((link, index) => (
                    <li key={`${link.url ?? 'source'}-${index}`}>
                      {link.url && link.url !== '#' ? <a href={link.url} target="_blank" rel="noreferrer">{link.title || link.url}</a> : <span>{link.title || 'Lead source'}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      <aside className="rail">
        <div className="mark" aria-label="LEON">L<span>·</span></div>

        <div className="rail-nav">
          {nav.map(({ glyph, label }) => (
            <button
              key={label}
              className={activeNav === label ? 'nav-item active' : 'nav-item'}
              onClick={() => setActiveNav(label)}
              aria-current={activeNav === label ? 'page' : undefined}
              data-sound="click"
            >
              <span className="nav-glyph" aria-hidden="true">{glyph}</span>
              <small>{label}</small>
            </button>
          ))}
        </div>

        <button
          className="sound-toggle"
          type="button"
          aria-label={muted ? 'Unmute LEON sounds' : 'Mute LEON sounds'}
          aria-pressed={muted}
          data-sound="click"
          onClick={() => {
            const nextMuted = !muted
            setMuted(nextMuted)
            setSoundMuted(nextMuted)
          }}
          title={muted ? 'Sound off' : 'Sound on'}
        >
          <span aria-hidden="true">{muted ? '◖' : '◗'}</span>
          <small>{muted ? 'sound off' : 'sound on'}</small>
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">LEON <span>/</span> PERSONAL MACHINE</p>
            <h1>{activeNav}</h1>
          </div>

          <div className="top-meta">
            <span className="connection" role="status" title={media?.provider ?? 'No active media'}>
              <i /> MEDIA {media?.success && media.state === 'PLAYING' ? `▶ ${media.title ?? 'Playing'}` : 'No active media'}
            </span>
            <span className="connection" role="status" title="Spotify authorization status">
              <i /> SPOTIFY {spotify?.authenticated ? 'CONNECTED' : 'NOT CONNECTED'}
            </span>
            {spotify?.authenticated ? (
              <button className="top-action" type="button" onClick={() => void removeSpotifyConnection()} disabled={spotifyBusy}>
                Disconnect
              </button>
            ) : (
              <button className="top-action" type="button" onClick={() => void startSpotifyConnect()} disabled={spotifyBusy || !spotifyConfigured}>
                {spotifyConfigured ? 'Connect Spotify' : 'Spotify setup needed'}
              </button>
            )}
            <span className={connected ? 'connection live' : 'connection'} role="status">
              <i /> {connection === 'online' ? 'ONLINE' : connection === 'offline' ? 'OFFLINE' : 'CONNECTING'}
            </span>
            <span className="top-signal" aria-label="live system signal"><i /><i /><i /><i /></span>
          </div>
        </header>

        <div className="content-grid">
          <section className="core-stage" aria-label="LEON core">
            <div className="stage-heading">
              <div>
                <span className="section-kicker">CORE</span>
                <p className="stage-subtitle">Personal system</p>
              </div>
              <motion.span
                className={`state-readout ${coreState}`}
                variants={interactionVariants}
                animate={coreState}
                initial="idle"
                role="status"
              >
                <i />{coreState}
              </motion.span>
            </div>

            {activeNav === 'Vision' ? (
              <VisionPanel />
            ) : activeNav === 'Memory' ? (
              <div className="stage-message">
                <span className="message-mark">L·</span>
                <h2>{memories.length ? `${memories.length} memories in orbit.` : 'Memory is quiet.'}</h2>
                <p>{memories.length ? 'Context available to LEON is held close to the current mission.' : 'No memory has been stored in the service yet.'}</p>
                <div className="memory-network" aria-label="Memory network">
                  {memories.slice(0, 6).map((memory, index) => (
                    <div className={`memory-node memory-node-${index % 4}`} key={memory.id} title={memory.content}>
                      <span>{memory.type.slice(0, 1).toUpperCase()}</span>
                      <small>{memory.content}</small>
                    </div>
                  ))}
                  {!memories.length && <span className="network-empty">awaiting context</span>}
                </div>
              </div>
            ) : activeNav === 'Media' ? (
              <div className="media-panel" aria-live="polite">
                <div className="media-header">
                  <div>
                    <span className="section-kicker">MEDIA</span>
                    <h2>Spotify</h2>
                  </div>
                  <span className={`media-badge ${spotify?.authenticated ? 'online' : 'offline'}`}>
                    {spotify?.authenticated ? '● Connected' : 'Not connected'}
                  </span>
                </div>

                {spotify?.configured === false ? (
                  <div className="media-status-card warning">
                    <p>Spotify isn't configured.</p>
                    <p>Add the Spotify client ID and secret to the backend environment, then reload LEON.</p>
                  </div>
                ) : spotify?.authenticated ? (
                  <>
                    <div className="media-list">
                      <div className="media-row">
                        <span>Device</span>
                        <strong>{spotify.device_name || 'No device detected'}</strong>
                      </div>
                      <div className="media-row">
                        <span>Now Playing</span>
                        <strong>{media?.title || 'Nothing is playing right now'}</strong>
                        {media?.artist && <small>{media.artist}</small>}
                      </div>
                    </div>
                    <div className="spotify-controls">
                      <button type="button" onClick={() => void handleSpotifyControl('previous')} disabled={spotifyBusy}>Previous</button>
                      <button type="button" onClick={() => void handleSpotifyControl(media?.state === 'PLAYING' ? 'pause' : 'resume')} disabled={spotifyBusy}>{media?.state === 'PLAYING' ? 'Pause' : 'Play'}</button>
                      <button type="button" onClick={() => void handleSpotifyControl('next')} disabled={spotifyBusy}>Next</button>
                    </div>
                  </>
                ) : (
                  <div className="media-status-card">
                    <p>Spotify is not connected.</p>
                    <button className="top-action" type="button" onClick={() => void startSpotifyConnect()} disabled={spotifyBusy || !spotifyConfigured}>
                      {spotifyConfigured ? 'Connect Spotify' : 'Spotify setup needed'}
                    </button>
                  </div>
                )}
              </div>
            ) : activeNav === 'Systems' ? (
              <div className="system-readout">
                <span className="section-kicker">CONNECTION</span>
                  <strong>{connection === 'online' ? 'ONLINE' : connection === 'offline' ? 'OFFLINE' : 'CONNECTING'}</strong>
                <p>{health ? `${health.service} · ${health.version}` : 'The LEON service could not be reached.'}</p>
                <div className="system-matrix" aria-label="System conditions">
                  {['LOCAL', connected ? 'MODEL READY' : 'DEGRADED', voiceState === 'idle' ? 'VOICE READY' : 'VOICE ACTIVE', activeTask ? 'TASK ACTIVE' : 'STANDING BY'].map((signal) => <span key={signal}><i />{signal}</span>)}
                </div>
              </div>
            ) : (
              <div
                className="core-wrap"
                onPointerEnter={() => setCoreHovered(true)}
                onPointerLeave={() => setCoreHovered(false)}
              >
                <div
                  style={{ width: '100%', height: '100%' }}
                  onClick={() => {
                    playSound('focus')
                    showState('focus', 650)
                  }}
                >
                  <LeonCoreHero state={visualState === 'offline' ? 'offline' : coreState} connectionState={connection} connected={connected} voiceState={voiceState} activeNav={activeNav} />
                </div>

              </div>
            )}

            <div className="stage-foot">
              <span><i className={connected ? 'pulse-dot live' : 'pulse-dot'} />{connected ? 'Service available' : 'Local interface'}</span>
              <span>{currentTask ? `${activeTask ? 'Active' : selectedTaskId ? 'Selected' : 'Last task'} · ${currentTask.title}` : 'No active work'}</span>
            </div>
          </section>

          <aside className="workbench" id="missions">
            <div className="workbench-head">
              <span className="section-kicker">TASKS</span>
              <span className="task-count">{tasks.length.toString().padStart(2, '0')}</span>
            </div>

            <div className="current-work">
              <div className="current-work-top">
                <span className={`task-status ${currentTask?.status ?? 'quiet'}`}><i />{currentTask?.status ?? 'Standing by'}</span>
                {currentTask && <span className="task-id">#{currentTask.id}</span>}
              </div>
              <h2>{currentTask?.title ?? 'Nothing in motion'}</h2>
              <p>{currentTask?.current_stage || (currentTask ? 'No further update' : 'Send a request to begin.')}</p>
              {currentTask && (
                <div className="progress-track" aria-label={`Task progress ${currentTask.progress}%`}>
                  <span style={{ width: `${Math.max(0, Math.min(100, currentTask.progress))}%` }} />
                </div>
              )}
              <div className="task-event-line" aria-hidden="true">
                <span className={currentTask ? 'on' : ''}>CORE</span><b /><span className={activeTask ? 'on' : ''}>PLAN</span><b /><span className={currentTask?.status === 'completed' ? 'on' : ''}>DONE</span>
              </div>
            </div>

            <div className="task-log" aria-label="Recent tasks">
              <div className="list-heading"><span>Recent tasks</span><span>SELECT TO INSPECT</span></div>
              {tasks.length === 0 ? (
                <p className="empty-state">Your task history will appear here.</p>
              ) : tasks.slice(0, 5).map((task) => (
                <button
                  className={`task-row${task.id === currentTask?.id ? ' selected' : ''}`}
                  key={task.id}
                  type="button"
                  onClick={() => setSelectedTaskId(task.id)}
                  data-sound="click"
                >
                  <span className="task-row-mark" aria-hidden="true" />
                  <span className="task-row-title">{task.title}</span>
                  <span className="task-row-state">{task.status}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="command-area" aria-label="Command interface">
            <div className="reply-line" aria-live="polite">
              <span className="reply-mark">L·</span>
              <p>{reply || 'Ready when you are.'}</p>
            </div>
            <form className="command-deck" onSubmit={handleSubmit}>
              <span className="portal-scan" aria-hidden="true" />
              <label className="command-glyph" htmlFor="command-input" aria-label="Command">↳</label>
              <input
                id="command-input"
                value={command}
                placeholder="Give LEON a task or ask a question"
                onFocus={() => {
                  playSound('focus')
                  if (interaction === 'idle') showState('focus')
                }}
                onBlur={() => {
                  if (interaction === 'focus') showState('idle')
                }}
                onChange={(event) => setCommand(event.target.value)}
              />
              <button type="submit" disabled={!command.trim()} data-sound="send">
                <span>Send</span><span aria-hidden="true">↗</span>
              </button>
            </form>
            <p className="command-note">Enter to send</p>
            <section className={`voice-deck voice-${voiceState}`} aria-label="Voice conversation">
              <div className="voice-deck-heading">
                <span className="section-kicker">VOICE</span>
                <span className="voice-state" role="status" aria-live="polite">{voiceState}</span>
              </div>
              <p className="voice-transcript" aria-live="polite">
                {voiceError || (voiceTranscript ? `You · ${voiceTranscript}` : 'No voice transcript yet.')}
              </p>
              <div className="voice-actions">
                <button
                  className="voice-listen"
                  type="button"
                  onClick={voiceState === 'listening' ? stopListening : () => void startListening()}
                  disabled={voiceState === 'processing' || voiceState === 'speaking'}
                  aria-label={voiceState === 'listening' ? 'Stop listening' : 'Start listening'}
                  aria-pressed={voiceState === 'listening'}
                  data-sound="click"
                >
                  <span aria-hidden="true">{voiceState === 'listening' ? '■' : '●'}</span>
                  {voiceState === 'listening' ? 'Stop listening' : 'Start listening'}
                </button>
                <button
                  className="voice-play"
                  type="button"
                  onClick={() => void playVoiceReply()}
                  disabled={!voiceAudio || voiceState === 'speaking'}
                  aria-label="Play LEON reply"
                  title="Play LEON reply"
                  data-sound="click"
                >
                  <span aria-hidden="true">▶</span>
                </button>
              </div>
            </section>
          </section>
        </div>
      </section>
    </main>
  )
}
