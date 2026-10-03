import { Canvas, useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { InteractionState } from './motion'
import { COLORS } from '../styles/colorTokens'

export type { InteractionState } from './motion'

const stateEnergy: Record<InteractionState, number> = {
  idle: 0.24,
  hover: 0.36,
  focus: 0.43,
  listening: 0.62,
  thinking: 0.68,
  executing: 0.92,
  success: 0.58,
  error: 0.32,
}

function DustField({ state }: { state: InteractionState }) {
  const points = useRef<THREE.Points>(null)
  const geometry = useMemo(() => {
    const positions = new Float32Array(96 * 3)
    for (let index = 0; index < 96; index += 1) {
      const angle = Math.random() * Math.PI * 2
      const radius = 2.4 + Math.random() * 2.2
      positions[index * 3] = Math.cos(angle) * radius
      positions[index * 3 + 1] = (Math.random() - 0.5) * 4.2
      positions[index * 3 + 2] = Math.sin(angle) * radius - 1.4
    }
    const dust = new THREE.BufferGeometry()
    dust.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return dust
  }, [])
  useEffect(() => () => geometry.dispose(), [geometry])
  const tokenState = state === 'hover' || state === 'focus' ? 'idle' : state
  return <points ref={points} geometry={geometry}><pointsMaterial color={COLORS[tokenState].particle} size={0.016} transparent opacity={0.4} sizeAttenuation /></points>
}

function Core({ state, onActivate }: { state: InteractionState; onActivate?: () => void }) {
  const root = useRef<THREE.Group>(null)
  const core = useRef<THREE.Mesh>(null)
  const material = useRef<THREE.MeshStandardMaterial>(null)
  const color = useMemo(
    () => new THREE.Color(COLORS[state === 'hover' || state === 'focus' ? 'idle' : state].accent),
    [state],
  )
  const energy = stateEnergy[state]

  useFrame(({ clock, pointer }, delta) => {
    if (!root.current || !core.current || !material.current) return
    const time = clock.getElapsedTime()
    const targetScale = 0.98 + energy * 0.075 + Math.sin(time * 0.62) * 0.008
    root.current.rotation.y = THREE.MathUtils.damp(root.current.rotation.y, pointer.x * 0.28 + time * 0.012, 2.4, delta)
    root.current.rotation.x = THREE.MathUtils.damp(root.current.rotation.x, -pointer.y * 0.18, 2.1, delta)
    root.current.rotation.z = THREE.MathUtils.damp(root.current.rotation.z, pointer.x * pointer.y * 0.08, 2, delta)
    core.current.scale.setScalar(THREE.MathUtils.damp(core.current.scale.x, targetScale, 2.8, delta))
    material.current.emissiveIntensity = THREE.MathUtils.damp(material.current.emissiveIntensity, 0.34 + energy * 0.5, 2, delta)
    material.current.color.lerp(color, 1 - Math.exp(-delta * 1.8))
  })

  return <group ref={root}>
    <mesh
      ref={core}
      onClick={(event) => { event.stopPropagation(); onActivate?.() }}
      onPointerOver={(event) => { event.stopPropagation() }}
    >
      <octahedronGeometry args={[0.48, 0]} />
      <meshStandardMaterial ref={material} color="#d0b77f" roughness={0.32} metalness={0.72} emissive={COLORS[state === 'hover' || state === 'focus' ? 'idle' : state].accent} emissiveIntensity={0.45} flatShading />
    </mesh>
    <mesh position={[0, 0.02, 0.51]}>
      <sphereGeometry args={[0.105, 18, 14]} />
      <meshStandardMaterial color={COLORS[state === 'hover' || state === 'focus' ? 'idle' : state].particle} roughness={0.22} metalness={0.38} emissive={COLORS[state === 'hover' || state === 'focus' ? 'idle' : state].accent} emissiveIntensity={0.48} />
    </mesh>
    <mesh position={[0, 0.68, 0]}>
      <octahedronGeometry args={[0.075, 0]} />
      <meshStandardMaterial color="#bdb19a" roughness={0.38} metalness={0.7} />
    </mesh>
    <mesh position={[0, -0.68, 0]} rotation={[Math.PI, 0, 0]}>
      <octahedronGeometry args={[0.075, 0]} />
      <meshStandardMaterial color="#bdb19a" roughness={0.38} metalness={0.7} />
    </mesh>
    <mesh rotation={[0, 0, 0.62]} position={[0, 0, -0.08]}>
      <boxGeometry args={[0.026, 2.35, 0.026]} />
      <meshStandardMaterial color="#8d8064" metalness={0.72} roughness={0.44} />
    </mesh>
    <mesh rotation={[0, 0, -0.62]} position={[0, 0, 0.08]}>
      <boxGeometry args={[0.026, 2.35, 0.026]} />
      <meshStandardMaterial color="#8d8064" metalness={0.72} roughness={0.44} />
    </mesh>
    <mesh rotation={[0.4, 0.1, 0.2]}>
      <torusGeometry args={[1.28, 0.012, 6, 96]} />
      <meshStandardMaterial color="#b6a478" metalness={0.68} roughness={0.5} transparent opacity={0.58} />
    </mesh>
    <mesh rotation={[1.25, 0.5, -0.35]}>
      <torusGeometry args={[1.47, 0.007, 5, 96]} />
      <meshBasicMaterial color="#81938d" transparent opacity={0.38} />
    </mesh>
    <mesh rotation={[0.06, -0.14, 0]}>
      <torusGeometry args={[1.08, 0.004, 4, 96]} />
      <meshBasicMaterial color="#e1d4b4" transparent opacity={0.52} />
    </mesh>
  </group>
}

export function LeonCore({ state, onActivate }: { state: InteractionState; onActivate?: () => void }) {
  return (
    <Canvas
      aria-label="Interactive LEON core"
      dpr={[1, 1.35]}
      gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
      camera={{ fov: 38, position: [0, 0, 4.6] }}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onActivate?.()
        }
      }}
    >
      <ambientLight intensity={0.65} color="#b9b3a4" />
      <pointLight position={[2.2, 2.1, 3]} color="#d9bd83" intensity={12} distance={8} />
      <pointLight position={[-2, -1, 1]} color="#71847d" intensity={3.2} distance={6} />
      <Core state={state} onActivate={onActivate} />
      <DustField state={state} />
    </Canvas>
  )
}
