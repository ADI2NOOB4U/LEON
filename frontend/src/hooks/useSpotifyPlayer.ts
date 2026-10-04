import { useCallback, useEffect, useRef, useState } from 'react'
import { clearSpotifyDevice, fetchSpotifyToken, registerSpotifyDevice } from '../api/client'

export interface SpotifyTrackState {
  id: string | null
  name: string | null
  artist: string | null
  album: string | null
  albumArtUrl: string | null
  positionMs: number
  durationMs: number
  isPlaying: boolean
}

export type SpotifyPlayerState =
  | 'NOT_CONFIGURED'
  | 'AUTH_REQUIRED'
  | 'SDK_LOADING'
  | 'SDK_READY'
  | 'SDK_NOT_READY'
  | 'ACCOUNT_UNAVAILABLE'
  | 'PLAYBACK_READY'
  | 'AUTOPLAY_BLOCKED'
  | 'ERROR'

export interface SpotifyPlayerSnapshot {
  state: SpotifyPlayerState
  sdkLoaded: boolean
  sdkConnected: boolean
  deviceId: string | null
  deviceName: string
  errorCode: string | null
  errorMessage: string | null
  track: SpotifyTrackState | null
}

interface SpotifyPlayerInstance {
  connect(): Promise<boolean>
  disconnect(): void
  activateElement(): Promise<void>
  addListener(event: string, callback: (payload?: any) => void): boolean
  removeListener?(event: string, callback?: (payload?: any) => void): boolean
}

interface SpotifySdk {
  Player: new (options: {
    name: string
    volume: number
    getOAuthToken: (callback: (token: string) => void) => void
  }) => SpotifyPlayerInstance
}

declare global {
  interface Window {
    Spotify?: SpotifySdk
    onSpotifyWebPlaybackSDKReady?: () => void
  }
}

const SDK_URL = 'https://sdk.scdn.co/spotify-player.js'
const EMPTY_TRACK: SpotifyTrackState = {
  id: null,
  name: null,
  artist: null,
  album: null,
  albumArtUrl: null,
  positionMs: 0,
  durationMs: 0,
  isPlaying: false,
}

let sdkPromise: Promise<SpotifySdk> | null = null

function loadSpotifySdk(): Promise<SpotifySdk> {
  if (window.Spotify) return Promise.resolve(window.Spotify)
  if (sdkPromise) return sdkPromise

  sdkPromise = new Promise<SpotifySdk>((resolve, reject) => {
    const previousReady = window.onSpotifyWebPlaybackSDKReady
    window.onSpotifyWebPlaybackSDKReady = () => {
      previousReady?.()
      if (window.Spotify) resolve(window.Spotify)
      else reject(new Error('Spotify Web Playback SDK loaded without a player API.'))
    }
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SDK_URL}"]`)
    if (existing) {
      existing.addEventListener('error', () => reject(new Error('Spotify Web Playback SDK could not be loaded.')), { once: true })
      return
    }
    const script = document.createElement('script')
    script.src = SDK_URL
    script.async = true
    script.onerror = () => reject(new Error('Spotify Web Playback SDK could not be loaded.'))
    document.head.appendChild(script)
  }).catch((error) => {
    sdkPromise = null
    throw error
  })
  return sdkPromise
}

function trackFromSdkState(state: any): SpotifyTrackState | null {
  const item = state?.track_window?.current_track
  if (!item) return null
  return {
    id: item.id ?? null,
    name: item.name ?? null,
    artist: item.artists?.map((artist: { name?: string }) => artist.name).filter(Boolean).join(', ') || null,
    album: item.album?.name ?? null,
    albumArtUrl: item.album?.images?.[0]?.url ?? null,
    positionMs: Number(state.position ?? 0),
    durationMs: Number(item.duration_ms ?? 0),
    isPlaying: !state.paused,
  }
}

export function useSpotifyPlayer(authenticated: boolean, configured: boolean) {
  const playerRef = useRef<SpotifyPlayerInstance | null>(null)
  const deviceIdRef = useRef<string | null>(null)
  const [snapshot, setSnapshot] = useState<SpotifyPlayerSnapshot>({
    state: configured ? (authenticated ? 'SDK_NOT_READY' : 'AUTH_REQUIRED') : 'NOT_CONFIGURED',
    sdkLoaded: false,
    sdkConnected: false,
    deviceId: null,
    deviceName: 'LEON Player',
    errorCode: null,
    errorMessage: null,
    track: null,
  })

  // Preload the official script after authentication so the user-initiated
  // Enable button can call activateElement without waiting on the network.
  useEffect(() => {
    if (!configured || !authenticated) return
    setSnapshot((current) => current.state === 'NOT_CONFIGURED'
      ? { ...current, state: 'SDK_NOT_READY' }
      : current)
    void loadSpotifySdk()
      .then(() => setSnapshot((current) => ({ ...current, sdkLoaded: true })))
      .catch(() => undefined)
  }, [authenticated, configured])

  const enablePlayer = useCallback(async () => {
    if (!configured || !authenticated) {
      setSnapshot((current) => ({ ...current, state: configured ? 'AUTH_REQUIRED' : 'NOT_CONFIGURED' }))
      return
    }
    setSnapshot((current) => ({ ...current, state: 'SDK_LOADING', errorCode: null, errorMessage: null }))
    try {
      const sdk = await loadSpotifySdk()
      setSnapshot((current) => ({ ...current, sdkLoaded: true }))
      if (!playerRef.current) {
        const player = new sdk.Player({
          name: 'LEON Player',
          volume: 0.8,
          getOAuthToken: async (callback) => {
            try {
              const result = await fetchSpotifyToken()
              callback(result.access_token)
            } catch (error) {
              setSnapshot((current) => ({
                ...current,
                state: 'AUTH_REQUIRED',
                errorCode: 'SPOTIFY_AUTH_REQUIRED',
                errorMessage: error instanceof Error ? error.message : 'Spotify authorization is required.',
              }))
              callback('')
            }
          },
        })
        player.addListener('ready', async (payload) => {
          const nextDeviceId = String(payload?.device_id ?? '')
          if (!nextDeviceId) return
          deviceIdRef.current = nextDeviceId
          await registerSpotifyDevice(nextDeviceId, 'LEON Player')
            .catch(() => undefined)
          setSnapshot((current) => ({
            ...current,
            state: 'PLAYBACK_READY',
            sdkConnected: true,
            deviceId: nextDeviceId,
            deviceName: 'LEON Player',
            errorCode: null,
            errorMessage: null,
          }))
        })
        player.addListener('not_ready', async (payload) => {
          const nextDeviceId = payload?.device_id ? String(payload.device_id) : deviceIdRef.current
          await clearSpotifyDevice(nextDeviceId).catch(() => undefined)
          deviceIdRef.current = null
          setSnapshot((current) => ({ ...current, state: 'SDK_NOT_READY', sdkConnected: false, deviceId: null, errorCode: 'SPOTIFY_DEVICE_UNAVAILABLE', errorMessage: 'The LEON Player device is no longer available.' }))
        })
        player.addListener('player_state_changed', (state) => {
          const track = trackFromSdkState(state)
          setSnapshot((current) => ({ ...current, state: track ? 'PLAYBACK_READY' : 'SDK_READY', track }))
        })
        player.addListener('initialization_error', (payload) => {
          setSnapshot((current) => ({ ...current, state: 'ERROR', errorCode: 'SPOTIFY_SDK_INITIALIZATION_ERROR', errorMessage: payload?.message ?? 'Spotify player initialization failed.' }))
        })
        player.addListener('authentication_error', (payload) => {
          setSnapshot((current) => ({ ...current, state: 'AUTH_REQUIRED', errorCode: 'SPOTIFY_AUTH_REQUIRED', errorMessage: payload?.message ?? 'Spotify authorization is required.' }))
        })
        player.addListener('account_error', (payload) => {
          setSnapshot((current) => ({ ...current, state: 'ACCOUNT_UNAVAILABLE', errorCode: 'PREMIUM_REQUIRED', errorMessage: payload?.message ?? 'This Spotify account cannot use the Web Playback SDK.' }))
        })
        player.addListener('playback_error', (payload) => {
          setSnapshot((current) => ({ ...current, state: 'ERROR', errorCode: 'PLAYBACK_FAILED', errorMessage: payload?.message ?? 'Spotify could not start browser playback.' }))
        })
        player.addListener('autoplay_failed', () => {
          setSnapshot((current) => ({ ...current, state: 'AUTOPLAY_BLOCKED', errorCode: 'AUTOPLAY_BLOCKED', errorMessage: 'Click Enable Player to allow audio in this browser.' }))
        })
        playerRef.current = player
      }

      // This call is made from the Enable Player click path. It is required
      // before transfer/playback in browsers that block autoplay.
      await playerRef.current.activateElement()
      const connected = await playerRef.current.connect()
      setSnapshot((current) => {
        const deviceReady = Boolean(deviceIdRef.current)
        const hasError = Boolean(current.errorCode)
        return {
          ...current,
          sdkConnected: connected,
          state: deviceReady ? 'PLAYBACK_READY' : hasError ? current.state : 'SDK_NOT_READY',
          errorCode: !connected && !hasError ? 'SPOTIFY_SDK_NOT_READY' : current.errorCode,
          errorMessage: !connected && !current.errorMessage ? 'Spotify did not connect the LEON Player.' : current.errorMessage,
        }
      })
    } catch (error) {
      setSnapshot((current) => ({ ...current, state: 'ERROR', errorCode: 'SPOTIFY_SDK_LOAD_FAILED', errorMessage: error instanceof Error ? error.message : 'Spotify Web Playback SDK failed to load.' }))
    }
  }, [authenticated, configured])

  useEffect(() => {
    if (!authenticated) {
      playerRef.current?.disconnect()
      playerRef.current = null
      deviceIdRef.current = null
      setSnapshot({ state: configured ? 'AUTH_REQUIRED' : 'NOT_CONFIGURED', sdkLoaded: false, sdkConnected: false, deviceId: null, deviceName: 'LEON Player', errorCode: null, errorMessage: null, track: null })
    }
  }, [authenticated, configured])

  useEffect(() => {
    if (!snapshot.deviceId) return
    const heartbeat = window.setInterval(() => {
      void registerSpotifyDevice(snapshot.deviceId!, snapshot.deviceName).catch(() => undefined)
    }, 5000)
    return () => window.clearInterval(heartbeat)
  }, [snapshot.deviceId, snapshot.deviceName])

  useEffect(() => () => {
    const deviceId = deviceIdRef.current
    if (deviceId) void clearSpotifyDevice(deviceId)
    playerRef.current?.disconnect()
  }, [])

  return { snapshot, enablePlayer, retryPlayer: enablePlayer }
}

