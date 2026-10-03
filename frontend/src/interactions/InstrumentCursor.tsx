import { useEffect, useRef } from 'react'

export function InstrumentCursor() {
  const cursor = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = cursor.current
    const media = window.matchMedia('(hover: hover) and (pointer: fine)')
    if (!element || !media.matches) return

    let targetX = window.innerWidth / 2
    let targetY = window.innerHeight / 2
    let currentX = targetX
    let currentY = targetY
    let frame = 0

    const settle = () => {
      currentX += (targetX - currentX) * 0.34
      currentY += (targetY - currentY) * 0.34
      element.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`
      if (Math.abs(targetX - currentX) + Math.abs(targetY - currentY) > 0.4) {
        frame = window.requestAnimationFrame(settle)
      } else {
        frame = 0
      }
    }

    const move = (event: PointerEvent) => {
      if (event.pointerType === 'touch') return
      targetX = event.clientX
      targetY = event.clientY
      if (!element.dataset.visible) element.dataset.visible = 'true'
      if (!frame) frame = window.requestAnimationFrame(settle)
    }

    const over = (event: PointerEvent) => {
      const target = event.target
      if (target instanceof Element && target.closest('button, [role="button"], canvas')) {
        element.dataset.control = 'true'
      }
    }

    const out = (event: PointerEvent) => {
      const target = event.relatedTarget
      if (!(target instanceof Element) || !target.closest('button, [role="button"], canvas')) {
        delete element.dataset.control
      }
    }

    const down = (event: PointerEvent) => {
      if (event.pointerType !== 'touch') element.dataset.pressed = 'true'
    }
    const up = () => delete element.dataset.pressed

    window.addEventListener('pointermove', move, { passive: true })
    document.addEventListener('pointerover', over, true)
    document.addEventListener('pointerout', out, true)
    window.addEventListener('pointerdown', down, { passive: true })
    window.addEventListener('pointerup', up, { passive: true })

    return () => {
      window.removeEventListener('pointermove', move)
      document.removeEventListener('pointerover', over, true)
      document.removeEventListener('pointerout', out, true)
      window.removeEventListener('pointerdown', down)
      window.removeEventListener('pointerup', up)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  return (
    <div className="instrument-cursor" ref={cursor} aria-hidden="true">
      <span className="cursor-needle" />
      <span className="cursor-ring" />
      <span className="cursor-tail" />
    </div>
  )
}
