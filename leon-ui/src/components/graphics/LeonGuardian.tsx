import React, { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import { COLORS, type LeonState } from '../../theme';
import { useMousePosition } from '../../hooks/useMousePosition';
import { Grid } from '@react-three/drei';

// --- Error Boundary ---
class ErrorBoundary extends React.Component<{ fallback: React.ReactNode, children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { fallback: React.ReactNode, children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() { return { hasError: true }; }
  render() { return this.state.hasError ? this.props.fallback : this.props.children; }
}

// --- Configuration ---
const CONFIG = {
  armorDark: '#1a1d22',
  armorLight: '#252830',
  jointColor: '#3a3f4a',
  glowBaseIntensity: 0.3,
  glowActiveIntensity: 0.8,
  glowExecutingIntensity: 1.2
};

// --- Helper Functions ---
function getTargetEmissiveIntensity(state: LeonState): number {
  switch (state) {
    case 'idle': return CONFIG.glowBaseIntensity;
    case 'listening': return 0.6;
    case 'thinking': return CONFIG.glowActiveIntensity;
    case 'executing': return CONFIG.glowExecutingIntensity;
    case 'success': return 1.5; // Brief flash
    case 'error': return 0.4;
    default: return CONFIG.glowBaseIntensity;
  }
}

// --- Components ---

function CameraRig({ mouseX, mouseY }: { mouseX: number; mouseY: number; state: LeonState }) {
  useFrame((stateCtx, delta) => {
    const { camera } = stateCtx;
    const time = stateCtx.clock.elapsedTime;
    
    // Base camera position
    const targetX = mouseX * 0.3;
    const targetY = 0.3 + mouseY * 0.2 + Math.sin(time * 0.5) * 0.02;
    const targetZ = 3.5;
    
    // Smooth camera movement
    camera.position.x = THREE.MathUtils.damp(camera.position.x, targetX, 2, delta);
    camera.position.y = THREE.MathUtils.damp(camera.position.y, targetY, 2, delta);
    camera.position.z = THREE.MathUtils.damp(camera.position.z, targetZ, 2, delta);
    
    // Look at target (chest area)
    const lookAtTarget = new THREE.Vector3(mouseX * 0.1, 0.2, 0);
    camera.lookAt(lookAtTarget);
  });
  
  return null;
}

function GuardianEntity({ state, mouseX, mouseY }: { state: LeonState, mouseX: number, mouseY: number }) {
  const groupRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);
  const chestRef = useRef<THREE.Group>(null);
  
  // Materials that need to animate color
  const emissiveMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const visorMatRef = useRef<THREE.MeshStandardMaterial>(null);
  
  const targetColor = useMemo(() => new THREE.Color(COLORS.state[state].accent), [state]);
  
  // Geometries
  const { headGeo, visorGeo, neckGeo, chestGeo, coreGeo, shoulderGeo, upperArmGeo } = useMemo(() => {
    return {
      headGeo: new THREE.BoxGeometry(0.3, 0.4, 0.35, 2, 2, 2),
      visorGeo: new THREE.BoxGeometry(0.25, 0.1, 0.36, 1, 1, 1),
      neckGeo: new THREE.CylinderGeometry(0.08, 0.08, 0.15, 8),
      chestGeo: new THREE.BoxGeometry(0.7, 0.6, 0.4, 2, 2, 2),
      coreGeo: new THREE.CylinderGeometry(0.08, 0.08, 0.05, 6),
      shoulderGeo: new THREE.BoxGeometry(0.25, 0.25, 0.25),
      upperArmGeo: new THREE.CylinderGeometry(0.06, 0.05, 0.4, 8)
    };
  }, []);

  // Materials
  const armorMat = useMemo(() => new THREE.MeshStandardMaterial({ 
    color: CONFIG.armorDark, roughness: 0.7, metalness: 0.8 
  }), []);
  
  const armorLightMat = useMemo(() => new THREE.MeshStandardMaterial({ 
    color: CONFIG.armorLight, roughness: 0.6, metalness: 0.9 
  }), []);

  const jointMat = useMemo(() => new THREE.MeshStandardMaterial({ 
    color: CONFIG.jointColor, roughness: 0.5, metalness: 0.5 
  }), []);

  useFrame((stateCtx, delta) => {
    const time = stateCtx.clock.elapsedTime;
    
    // Animate Colors & Emissive
    if (emissiveMatRef.current && visorMatRef.current) {
      const targetIntensity = getTargetEmissiveIntensity(state);
      
      // Add pulsing for thinking/executing
      let currentIntensity = targetIntensity;
      if (state === 'thinking') {
        currentIntensity += Math.sin(time * 3) * 0.2;
      } else if (state === 'executing') {
        currentIntensity += Math.sin(time * 8) * 0.3;
      }
      
      emissiveMatRef.current.color.lerp(targetColor, delta * 3);
      emissiveMatRef.current.emissive.lerp(targetColor, delta * 3);
      emissiveMatRef.current.emissiveIntensity = THREE.MathUtils.damp(
        emissiveMatRef.current.emissiveIntensity, currentIntensity, 4, delta
      );
      
      visorMatRef.current.emissive.lerp(targetColor, delta * 3);
      visorMatRef.current.emissiveIntensity = THREE.MathUtils.damp(
        visorMatRef.current.emissiveIntensity, currentIntensity * 0.8, 4, delta
      );
    }
    
    // Animation - Breathing and Posture
    if (chestRef.current) {
      // Breathing scale
      const breatheScale = 1 + Math.sin(time * 1.5) * 0.005;
      chestRef.current.scale.setScalar(breatheScale);
      
      // Posture changes based on state
      let targetRotX = 0;
      if (state === 'listening') targetRotX = 0.05;
      if (state === 'executing') targetRotX = 0.1;
      
      chestRef.current.rotation.x = THREE.MathUtils.damp(chestRef.current.rotation.x, targetRotX, 2, delta);
    }
    
    // Animation - Head Tracking
    if (headRef.current) {
      // Track mouse with damping
      const targetRotY = mouseX * 0.5;
      const targetRotX = -mouseY * 0.3;
      
      // Add slight organic drift
      const driftX = Math.sin(time * 0.7) * 0.02;
      const driftY = Math.cos(time * 0.5) * 0.02;
      
      headRef.current.rotation.y = THREE.MathUtils.damp(headRef.current.rotation.y, targetRotY + driftY, 3, delta);
      headRef.current.rotation.x = THREE.MathUtils.damp(headRef.current.rotation.x, targetRotX + driftX, 3, delta);
    }
    
    // Overall group gentle floating
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(time * 1.2) * 0.02;
    }
  });

  return (
    <group ref={groupRef}>
      {/* CHEST / TORSO */}
      <group ref={chestRef} position={[0, -0.1, 0]}>
        <mesh geometry={chestGeo} material={armorMat} />
        
        {/* Core */}
        <mesh geometry={coreGeo} position={[0, 0, 0.2]} rotation={[Math.PI/2, 0, 0]}>
          <meshStandardMaterial ref={emissiveMatRef} color="#000" emissive="#000" toneMapped={false} />
        </mesh>
        
        {/* Shoulders & Arms */}
        {[-1, 1].map((sign, i) => (
          <group key={i} position={[sign * 0.45, 0.2, 0]}>
            <mesh geometry={shoulderGeo} material={armorLightMat} />
            <mesh geometry={upperArmGeo} position={[0, -0.3, 0]} material={armorMat} />
            {/* Emissive Joint Detail */}
            <mesh position={[sign * 0.13, -0.1, 0]}>
              <boxGeometry args={[0.02, 0.1, 0.1]} />
              <meshStandardMaterial color={targetColor} emissive={targetColor} emissiveIntensity={0.5} toneMapped={false} />
            </mesh>
          </group>
        ))}
      </group>

      {/* NECK */}
      <mesh geometry={neckGeo} position={[0, 0.3, 0]} material={jointMat} />

      {/* HEAD */}
      <group ref={headRef} position={[0, 0.55, 0]}>
        <mesh geometry={headGeo} material={armorLightMat} />
        {/* Visor */}
        <mesh geometry={visorGeo} position={[0, 0.05, 0.02]}>
          <meshStandardMaterial 
            ref={visorMatRef}
            color="#111" 
            metalness={0.9} 
            roughness={0.1}
            emissive="#000"
            toneMapped={false}
          />
        </mesh>
        {/* Antenna/Sensor */}
        <mesh position={[0.18, 0, 0]} material={armorMat}>
          <boxGeometry args={[0.04, 0.15, 0.08]} />
        </mesh>
      </group>
    </group>
  );
}

function Environment({ state }: { state: LeonState }) {
  const particlesRef = useRef<THREE.InstancedMesh>(null);
  const color = useMemo(() => new THREE.Color(COLORS.state[state].particles), [state]);
  
  const particleCount = 80;
  
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const particlesData = useMemo(() => {
    return Array.from({ length: particleCount }).map(() => ({
      pos: new THREE.Vector3(
        (Math.random() - 0.5) * 6,
        (Math.random() - 0.5) * 6,
        (Math.random() - 0.5) * 6 - 2
      ),
      speed: 0.02 + Math.random() * 0.05,
      phase: Math.random() * Math.PI * 2
    }));
  }, []);

  const particleMatRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame((stateCtx, delta) => {
    const time = stateCtx.clock.elapsedTime;
    
    if (particleMatRef.current) {
      particleMatRef.current.color.lerp(color, delta * 2);
    }
    
    if (particlesRef.current) {
      // Speed modifier based on state
      let speedMod = 1;
      if (state === 'thinking' || state === 'executing') speedMod = 2.5;
      if (state === 'error') speedMod = 0.5;
      
      particlesData.forEach((data, i) => {
        data.pos.y += data.speed * speedMod * delta;
        if (data.pos.y > 3) data.pos.y = -3;
        
        dummy.position.copy(data.pos);
        dummy.position.x += Math.sin(time + data.phase) * 0.01;
        
        // Scale pulse
        const scale = 1 + Math.sin(time * 3 + data.phase) * 0.5;
        dummy.scale.setScalar(scale);
        
        dummy.updateMatrix();
        particlesRef.current!.setMatrixAt(i, dummy.matrix);
      });
      particlesRef.current.instanceMatrix.needsUpdate = true;
    }
  });

  return (
    <group>
      {/* Holographic Floor Grid */}
      <Grid 
        position={[0, -1.5, 0]} 
        infiniteGrid 
        fadeDistance={10} 
        fadeStrength={1} 
        cellColor={COLORS.state[state].accent}
        sectionColor={COLORS.state[state].primary}
        cellThickness={0.5}
      />
      
      {/* Particles */}
      <instancedMesh ref={particlesRef} args={[undefined, undefined, particleCount]}>
        <planeGeometry args={[0.03, 0.03]} />
        <meshBasicMaterial ref={particleMatRef} color={color} transparent opacity={0.6} depthWrite={false} blending={THREE.AdditiveBlending} />
      </instancedMesh>
      
      {/* Subtle Background Pillars */}
      {[-2, 2].map((x, i) => (
        <mesh key={i} position={[x, 0, -4]}>
          <boxGeometry args={[0.4, 10, 0.4]} />
          <meshStandardMaterial color="#050508" roughness={0.9} />
        </mesh>
      ))}
    </group>
  );
}

function Scene({ state, mouseX, mouseY }: { state: LeonState, mouseX: number, mouseY: number }) {
  const lightColor = useMemo(() => new THREE.Color(COLORS.state[state].accent), [state]);
  
  return (
    <>
      <CameraRig mouseX={mouseX} mouseY={mouseY} state={state} />
      
      {/* Lighting */}
      <ambientLight intensity={0.15} />
      <directionalLight position={[5, 5, 2]} intensity={1.2} color="#f8f9fa" />
      {/* Rim light mapped to state */}
      <pointLight position={[-3, 2, -2]} intensity={2} color={lightColor} distance={10} />
      {/* Core highlight */}
      <pointLight position={[0, 0, 1]} intensity={0.5} color={lightColor} distance={3} />

      <Environment state={state} />
      <GuardianEntity state={state} mouseX={mouseX} mouseY={mouseY} />
      
      <EffectComposer enableNormalPass={false}>
        <Bloom luminanceThreshold={0.2} mipmapBlur intensity={1.5} />
      </EffectComposer>
    </>
  );
}

export function LeonGuardian({ state }: { state: LeonState }) {
  const mouse = useMousePosition();
  
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <ErrorBoundary 
        fallback={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: COLORS.state[state].accent }}>
            <h2>LEON: {state.toUpperCase()}</h2>
            <p>WebGL Error - Guardian Offline</p>
          </div>
        }
      >
        <Canvas 
          gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }} 
          dpr={[1, 1.5]} 
          style={{ background: 'transparent' }}
        >
          <Scene state={state} mouseX={mouse.normalizedX} mouseY={mouse.normalizedY} />
        </Canvas>
      </ErrorBoundary>
    </div>
  );
}
