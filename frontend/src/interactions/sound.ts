export type LeonSound = 'click' | 'hover' | 'focus' | 'message' | 'taskStart' | 'complete' | 'error'

type SoundShape = {
  frequency: number
  endFrequency: number
  duration: number
  volume: number
  wave: OscillatorType
}

const sounds: Record<LeonSound, SoundShape> = {
  click: { frequency: 510, endFrequency: 390, duration: 0.055, volume: 0.035, wave: 'triangle' },
  hover: { frequency: 760, endFrequency: 680, duration: 0.035, volume: 0.012, wave: 'sine' },
  focus: { frequency: 420, endFrequency: 540, duration: 0.085, volume: 0.018, wave: 'sine' },
  message: { frequency: 340, endFrequency: 610, duration: 0.14, volume: 0.026, wave: 'sine' },
  taskStart: { frequency: 190, endFrequency: 285, duration: 0.21, volume: 0.034, wave: 'triangle' },
  complete: { frequency: 460, endFrequency: 690, duration: 0.18, volume: 0.026, wave: 'sine' },
  error: { frequency: 260, endFrequency: 175, duration: 0.17, volume: 0.024, wave: 'triangle' },
}

const muteKey = 'leon-sound-muted'
const volumeKey = 'leon-sound-volume'
let muted = false
let volume = 0.7
if (typeof window !== 'undefined') {
  try {
    muted = window.localStorage.getItem(muteKey) === 'true'
    const storedVolume = window.localStorage.getItem(volumeKey)
    if (storedVolume !== null) {
      const parsedVolume = Number(storedVolume)
      if (Number.isFinite(parsedVolume)) volume = Math.min(1, Math.max(0, parsedVolume))
    }
  } catch {
    muted = false
  }
}
let context: AudioContext | null = null
let lastHoverAt = 0

export function getMuted() {
  return muted
}

export function getVolume() {
  return volume
}

export function setMuted(value: boolean) {
  muted = value
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(muteKey, String(value))
    } catch {
      // Mute still applies for this session when storage is unavailable.
    }
  }
}

export function setVolume(value: number) {
  volume = Math.min(1, Math.max(0, value))
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(volumeKey, String(volume))
    } catch {
      // Volume still applies for this session when storage is unavailable.
    }
  }
}

export function unlockSound() {
  if (muted || typeof window === 'undefined') return
  const AudioContextConstructor = window.AudioContext
  if (!AudioContextConstructor) return
  context ??= new AudioContextConstructor()
  if (context.state === 'suspended') void context.resume().catch(() => undefined)
}

export function playSound(sound: LeonSound) {
  if (muted || volume === 0 || !context || context.state !== 'running') return
  const now = context.currentTime
  if (sound === 'hover') {
    if (now - lastHoverAt < 0.42) return
    lastHoverAt = now
  }

  const shape = sounds[sound]
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = shape.wave
  oscillator.frequency.setValueAtTime(shape.frequency, now)
  oscillator.frequency.exponentialRampToValueAtTime(shape.endFrequency, now + shape.duration)
  gain.gain.setValueAtTime(0.0001, now)
  gain.gain.exponentialRampToValueAtTime(shape.volume * volume, now + Math.min(0.018, shape.duration / 3))
  gain.gain.exponentialRampToValueAtTime(0.0001, now + shape.duration)
  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start(now)
  oscillator.stop(now + shape.duration + 0.01)
}
