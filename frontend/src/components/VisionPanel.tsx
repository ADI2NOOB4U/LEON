import { useEffect, useRef, useState } from 'react'
import { analyzeVision } from '../api/client'
import type { VisionMode, VisionResponse } from '../types/api'

type VisionState =
  | 'IDLE'
  | 'REQUESTING_PERMISSION'
  | 'CAMERA_READY'
  | 'CAPTURING'
  | 'SNAPSHOT_READY'
  | 'ANALYZING'
  | 'RESULT'
  | 'ERROR'

const modes: { value: VisionMode; label: string }[] = [
  { value: 'general', label: 'General' },
  { value: 'ocr', label: 'OCR' },
  { value: 'screen', label: 'Screen' },
  { value: 'document', label: 'Document' },
  { value: 'object', label: 'Object' },
]

function isVisionMode(value: string): value is VisionMode {
  return modes.some((option) => option.value === value)
}

function stopTracks(activeStream: MediaStream | null) {
  activeStream?.getTracks().forEach((track) => track.stop())
}

function cameraErrorMessage(cause: unknown): string {
  const name = cause instanceof DOMException ? cause.name : ''
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return 'Camera access was denied. Allow camera access and try again.'
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError') {
    return 'No compatible camera was found on this device.'
  }
  if (name === 'NotReadableError') {
    return 'The camera is already in use by another application.'
  }
  return 'The camera could not be started.'
}

export function VisionPanel() {
  const video = useRef<HTMLVideoElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const cameraRequest = useRef(0)
  const mounted = useRef(false)
  const [state, setState] = useState<VisionState>('IDLE')
  const [prompt, setPrompt] = useState('What do you see?')
  const [mode, setMode] = useState<VisionMode>('general')
  const [snapshot, setSnapshot] = useState<Blob | null>(null)
  const [preview, setPreview] = useState('')
  const [result, setResult] = useState<VisionResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      cameraRequest.current += 1
      stopTracks(stream.current)
      stream.current = null
      if (video.current) video.current.srcObject = null
    }
  }, [])

  useEffect(() => {
    if (!preview) return
    return () => URL.revokeObjectURL(preview)
  }, [preview])

  const stopCamera = () => {
    cameraRequest.current += 1
    const activeStream = stream.current
    stream.current = null
    if (video.current) video.current.srcObject = null
    stopTracks(activeStream)
    setError('')
    if (state !== 'ANALYZING') {
      setState(result ? 'RESULT' : snapshot ? 'SNAPSHOT_READY' : 'IDLE')
    }
  }

  const startCamera = async () => {
    setError('')
    setResult(null)
    setSnapshot(null)
    setPreview('')
    if (!navigator.mediaDevices?.getUserMedia) {
      setState('ERROR')
      setError('Camera access is not available in this browser.')
      return
    }

    const requestId = ++cameraRequest.current
    setState('REQUESTING_PERMISSION')
    let nextStream: MediaStream | null = null

    try {
      nextStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
      if (!mounted.current || cameraRequest.current !== requestId) {
        stopTracks(nextStream)
        return
      }

      stream.current = nextStream
      const element = video.current
      if (!element) {
        stream.current = null
        stopTracks(nextStream)
        setState('ERROR')
        setError('The camera preview could not be initialized.')
        return
      }

      element.srcObject = nextStream
      await element.play()
      if (!mounted.current || cameraRequest.current !== requestId) {
        if (stream.current === nextStream) stream.current = null
        stopTracks(nextStream)
        return
      }
      setState('CAMERA_READY')
    } catch (cause) {
      if (stream.current === nextStream) {
        stream.current = null
        if (video.current) video.current.srcObject = null
      }
      stopTracks(nextStream)
      if (!mounted.current || cameraRequest.current !== requestId) return
      setState('ERROR')
      setError(cameraErrorMessage(cause))
    }
  }

  const capture = () => {
    const element = video.current
    const target = canvas.current
    const activeStream = stream.current
    if (!element || !target || !activeStream || element.srcObject !== activeStream || !element.videoWidth) {
      setState('ERROR')
      setError('The camera preview is not ready. Try activating the camera again.')
      return
    }

    setError('')
    setResult(null)
    setState('CAPTURING')
    const scale = Math.min(1, 1600 / element.videoWidth)
    target.width = Math.round(element.videoWidth * scale)
    target.height = Math.round(element.videoHeight * scale)
    const context = target.getContext('2d')
    if (!context) {
      setState('ERROR')
      setError('A snapshot could not be created from the camera preview.')
      return
    }
    context.drawImage(element, 0, 0, target.width, target.height)
    target.toBlob((blob) => {
      if (!mounted.current) return
      if (!blob) {
        setState('ERROR')
        setError('A snapshot could not be created from the camera preview.')
        return
      }
      setSnapshot(blob)
      setPreview(URL.createObjectURL(blob))
      setState('SNAPSHOT_READY')
    }, 'image/jpeg', 0.9)
  }

  const chooseFile = (file?: File) => {
    if (!file) return
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      setState('ERROR')
      setError('Choose a PNG, JPEG, or WebP image.')
      return
    }

    cameraRequest.current += 1
    const activeStream = stream.current
    stream.current = null
    if (video.current) video.current.srcObject = null
    stopTracks(activeStream)
    setError('')
    setResult(null)
    setSnapshot(file)
    setPreview(URL.createObjectURL(file))
    setState('SNAPSHOT_READY')
  }

  const analyze = async () => {
    if (!snapshot) {
      setState('ERROR')
      setError('Capture a snapshot or choose an image before analyzing.')
      return
    }
    setState('ANALYZING')
    setError('')
    setResult(null)
    try {
      const analysis = await analyzeVision(snapshot, prompt, mode)
      if (!mounted.current) return
      setResult(analysis)
      setState('RESULT')
    } catch (cause) {
      if (!mounted.current) return
      setState('ERROR')
      setError(cause instanceof Error ? cause.message : 'The vision request failed.')
    }
  }

  const isBusy = state === 'REQUESTING_PERMISSION' || state === 'CAPTURING' || state === 'ANALYZING'

  return (
    <section className="vision-panel" aria-label="Vision">
      <div className="vision-heading">
        <span className="section-kicker">VISION</span>
        <span role="status" aria-live="polite">{state.replace(/_/g, ' ')}</span>
      </div>
      <div className="vision-preview">
        <video
          ref={video}
          muted
          playsInline
          aria-label="Live camera preview"
          hidden={!stream.current || Boolean(preview)}
        />
        {preview ? <img src={preview} alt="Selected snapshot for vision analysis" /> : null}
        {!preview && !stream.current ? (
          <p>{state === 'REQUESTING_PERMISSION' ? 'Waiting for camera permission…' : 'Camera is off. Activate the camera or choose an image.'}</p>
        ) : null}
        <canvas ref={canvas} hidden />
      </div>
      <div className="vision-actions">
        {!stream.current && state !== 'REQUESTING_PERMISSION' ? (
          <button type="button" onClick={() => void startCamera()} disabled={isBusy}>
            Activate camera
          </button>
        ) : null}
        {stream.current && !isBusy ? (
          <button type="button" onClick={capture}>Capture snapshot</button>
        ) : null}
        {stream.current || state === 'REQUESTING_PERMISSION' ? (
          <button type="button" onClick={stopCamera}>
            {state === 'REQUESTING_PERMISSION' ? 'Cancel camera request' : 'Stop camera'}
          </button>
        ) : null}
        <label className="vision-file">
          Choose image
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={state === 'ANALYZING'}
            onChange={(event) => {
              chooseFile(event.currentTarget.files?.[0])
              event.currentTarget.value = ''
            }}
          />
        </label>
      </div>
      <label className="vision-prompt">
        Prompt
        <input value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={4000} />
      </label>
      <label className="vision-prompt">
        Mode
        <select
          value={mode}
          onChange={(event) => {
            const nextMode = event.currentTarget.value
            if (isVisionMode(nextMode)) setMode(nextMode)
          }}
        >
          {modes.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <button className="vision-analyze" type="button" onClick={() => void analyze()} disabled={!snapshot || state === 'ANALYZING'}>
        {state === 'ANALYZING' ? 'Analyzing…' : 'Analyze snapshot'}
      </button>
      {error ? <p className="vision-error" role="alert">{error}</p> : null}
      {result ? (
        <div className="vision-result" aria-live="polite">
          <span className="section-kicker">LEON / VISUAL RESPONSE</span>
          <p>{result.description}</p>
          <small>{result.model} · {result.width} × {result.height}</small>
        </div>
      ) : null}
    </section>
  )
}
