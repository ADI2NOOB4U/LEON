import { OrbitControls, PerspectiveCamera, Sparkles } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { animate, motionValue } from 'motion'
import { threeEffect } from 'motion/three'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'

export type CoreState = 'idle' | 'thinking' | 'executing' | 'completed' | 'error'

const stateEnergy: Record<CoreState, number> = {
  idle: 0.38,
  thinking: 0.7,
  executing: 1,
  completed: 0.58,
  error: 0.5,
}

function CameraRig({ state }: { state: CoreState }) {
  const { camera } = useThree()
  useFrame(({ clock }) => {
    const energy = stateEnergy[state]
    const t = clock.getElapsedTime()
    const distance = 5.35 - energy * 0.32
    camera.position.lerp(new THREE.Vector3(Math.sin(t * 0.11) * 0.22, 0.12 + Math.cos(t * 0.16) * 0.11, distance), 0.025)
    camera.lookAt(0, 0, 0)
  })
  return null
}

function ParticleField() {
  const points = useRef<THREE.Points>(null)
  const geometry = useMemo(() => {
    const positions = new Float32Array(700 * 3)
    for (let index = 0; index < 700; index += 1) {
      const radius = 3 + Math.random() * 8
      const theta = Math.random() * Math.PI * 2
      positions[index * 3] = Math.cos(theta) * radius
      positions[index * 3 + 1] = (Math.random() - 0.5) * 7
      positions[index * 3 + 2] = Math.sin(theta) * radius - 3
    }
    const field = new THREE.BufferGeometry()
    field.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return field
  }, [])
  useFrame((_, delta) => { if (points.current) points.current.rotation.y += delta * 0.006 })
  useEffect(() => () => geometry.dispose(), [geometry])
  return <points ref={points} geometry={geometry}><pointsMaterial color="#d7c59a" size={0.018} transparent opacity={0.52} sizeAttenuation /></points>
}

function Core({ state }: { state: CoreState }) {
  const root = useRef<THREE.Group>(null)
  const core = useRef<THREE.Mesh>(null)
  const material = useRef<THREE.MeshStandardMaterial>(null)
  const energy = stateEnergy[state]

  useEffect(() => {
    if (!root.current || !material.current) return
    const rotation = motionValue(0)
    const glow = motionValue(material.current.emissiveIntensity)
    const detachRotation = threeEffect(root.current, { rotateY: rotation })
    const detachGlow = threeEffect(material.current, { emissiveIntensity: glow })
    const spin = animate(rotation, Math.PI * 2, { duration: 32, ease: 'linear', repeat: Infinity })
    const glowAnimation = animate(glow, 0.32 + energy * 0.55, { duration: 0.7, ease: [0.16, 1, 0.3, 1] })
    return () => { detachRotation(); detachGlow(); spin.stop(); glowAnimation.stop() }
  }, [energy])

  useFrame(({ clock }, delta) => {
    if (!core.current) return
    const t = clock.getElapsedTime()
    const pulse = Math.sin(t * (0.8 + energy * 2.2)) * (0.012 + energy * 0.022)
    core.current.scale.setScalar(1 + pulse)
    core.current.rotation.x += delta * 0.035
  })

  return <group ref={root}>
    <mesh ref={core}><icosahedronGeometry args={[1.04, 4]} /><meshStandardMaterial ref={material} color="#a88952" roughness={0.24} metalness={0.88} emissive="#23190d" emissiveIntensity={0.48} /></mesh>
    <mesh><sphereGeometry args={[0.76, 32, 32]} /><meshBasicMaterial color="#f0d998" transparent opacity={0.1} blending={THREE.AdditiveBlending} /></mesh>
    {[0, 1, 2].map((index) => <mesh key={index} rotation={[index * 0.62, index * 0.42, index * 0.28]}>
      <torusGeometry args={[1.4 + index * 0.22, 0.009, 8, 160]} /><meshBasicMaterial color={index === 1 ? '#839895' : '#c6a76c'} transparent opacity={index === 1 ? 0.3 : 0.56} />
    </mesh>)}
  </group>
}

export function LeonCore({ state }: { state: CoreState }) {
  return <Canvas dpr={[1, 1.75]} gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }} camera={{ fov: 42, position: [0, 0.1, 5.4] }}>
    <fog attach="fog" args={['#090a0d', 4, 13]} />
    <PerspectiveCamera makeDefault fov={42} position={[0, 0.1, 5.4]} />
    <ambientLight intensity={0.55} color="#a8a39a" />
    <pointLight position={[2.5, 2.8, 3]} color="#ddbd77" intensity={20} distance={10} />
    <pointLight position={[-2, -1, 1]} color="#71908a" intensity={5} distance={7} />
    <Core state={state} /><ParticleField /><Sparkles count={52} scale={[8, 5, 5]} size={1.4} speed={0.12} color="#c3b18a" />
    <CameraRig state={state} />
    <OrbitControls enablePan={false} enableZoom={false} minPolarAngle={Math.PI / 2.7} maxPolarAngle={Math.PI / 1.45} rotateSpeed={0.35} />
  </Canvas>
}
