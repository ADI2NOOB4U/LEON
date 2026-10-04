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

const modes: { value: VisionMode; label: string; desc: string }[] = [
  { value: 'general', label: 'General', desc: 'Detailed scene description' },
  { value: 'ocr', label: 'OCR & Text', desc: 'Extract readable text' },
  { value: 'screen', label: 'Screen / UI', desc: 'Analyze user interfaces' },
  { value: 'document', label: 'Document', desc: 'Analyze documents and charts' },
  { value: 'object', label: 'Objects', desc: 'Identify key items and layout' },
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
    return 'Camera access was denied. Allow camera access in your browser and try again.'
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError') {
    return 'No compatible camera was found on this device.'
  }
  if (name === 'NotReadableError') {
    return 'The camera is currently in use by another application.'
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
  const [prompt, setPrompt] = useState('What do you see in this image?')
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
      setError('Camera access is not available in this browser environment.')
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
      setError('Please select a PNG, JPEG, or WebP image.')
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
      setError('Please capture a snapshot or upload an image first.')
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
      setError(cause instanceof Error ? cause.message : 'Vision analysis failed.')
    }
  }

  const isBusy = state === 'REQUESTING_PERMISSION' || state === 'CAPTURING' || state === 'ANALYZING'

  return (
    <div className="vision-view-container" aria-label="Vision Analysis Studio">
      <div className="vision-header-bar">
        <div>
          <span className="section-badge">VISION STUDIO</span>
          <h2 className="vision-main-title">Visual Intelligence</h2>
        </div>
        <div className={`vision-status-chip state-${state.toLowerCase()}`}>
          <span className="pulse-dot" />
          {state === 'REQUESTING_PERMISSION'
            ? 'Requesting Camera'
            : state === 'CAMERA_READY'
            ? 'Camera Live'
            : state === 'CAPTURING'
            ? 'Capturing Frame'
            : state === 'SNAPSHOT_READY'
            ? 'Image Ready'
            : state === 'ANALYZING'
            ? 'Analyzing...'
            : state === 'RESULT'
            ? 'Analysis Complete'
            : state === 'ERROR'
            ? 'Action Needed'
            : 'Standby'}
        </div>
      </div>

      <div className="vision-stage-layout">
        {/* Viewport Box */}
        <div className="vision-viewport-card">
          <div className="viewport-inner">
            <video
              ref={video}
              muted
              playsInline
              aria-label="Live camera feed"
              className="viewport-video"
              hidden={!stream.current || Boolean(preview)}
            />
            {preview ? (
              <img src={preview} alt="Snapshot to analyze" className="viewport-preview-img" />
            ) : null}

            {!preview && !stream.current ? (
              <div className="viewport-empty-placeholder">
                <div className="empty-icon-circle">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                    <circle cx="12" cy="13" r="4"/>
                  </svg>
                </div>
                <h3>Camera feed is inactive</h3>
                <p>Start your camera or select an image file to begin analysis.</p>
              </div>
            ) : null}
            <canvas ref={canvas} hidden />
          </div>

          {/* Controls toolbar */}
          <div className="viewport-toolbar">
            {!stream.current && state !== 'REQUESTING_PERMISSION' ? (
              <button
                type="button"
                className="btn-primary"
                onClick={() => void startCamera()}
                disabled={isBusy}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                Activate Camera
              </button>
            ) : null}

            {stream.current && !isBusy ? (
              <button type="button" className="btn-accent" onClick={capture}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
                Take Snapshot
              </button>
            ) : null}

            {stream.current || state === 'REQUESTING_PERMISSION' ? (
              <button type="button" className="btn-secondary" onClick={stopCamera}>
                {state === 'REQUESTING_PERMISSION' ? 'Cancel' : 'Stop Camera'}
              </button>
            ) : null}

            <label className="btn-file-upload">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Upload Image
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
        </div>

        {/* Configuration & Action Area */}
        <div className="vision-config-card">
          <div className="config-form-group">
            <label className="form-label" htmlFor="vision-prompt-input">
              Analysis Prompt
            </label>
            <input
              id="vision-prompt-input"
              className="form-input"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="e.g., What is in this image? Transcribe text, summarize content..."
              maxLength={4000}
            />
          </div>

          <div className="config-form-group">
            <label className="form-label">Analysis Mode</label>
            <div className="mode-pill-grid">
              {modes.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`mode-pill-btn ${mode === opt.value ? 'selected' : ''}`}
                  onClick={() => setMode(opt.value)}
                >
                  <strong>{opt.label}</strong>
                  <small>{opt.desc}</small>
                </button>
              ))}
            </div>
          </div>

          <button
            className="btn-analyze-submit"
            type="button"
            onClick={() => void analyze()}
            disabled={!snapshot || state === 'ANALYZING'}
          >
            {state === 'ANALYZING' ? (
              <>
                <span className="spinner-icon" />
                Analyzing with Vision Model...
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                Analyze Snapshot
              </>
            )}
          </button>

          {error && (
            <div className="vision-error-box" role="alert">
              <span>⚠</span> {error}
            </div>
          )}
        </div>
      </div>

      {/* Analysis Result Output */}
      {result && (
        <div className="vision-result-card" aria-live="polite">
          <div className="result-header">
            <div className="result-title-group">
              <span className="result-badge">AI ANALYSIS</span>
              <h3>Vision Model Response</h3>
            </div>
            <span className="result-meta">
              {result.model} · {result.width}×{result.height}px
            </span>
          </div>
          <div className="result-body">
            <p>{result.description}</p>
          </div>
        </div>
      )}
    </div>
  )
}
