import { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import { COLORS, type LeonState } from '../../theme';
import { useMousePosition } from '../../hooks/useMousePosition';

const PARTICLE_COUNT = 1800;
const TRAIL_COUNT = 180;
const TRAIL_LENGTH = 5;
const TUNING: Record<LeonState, { speed: number; density: number; chaos: number; scale: number }> = {
  idle: { speed: 0.08, density: 0.24, chaos: 0.035, scale: 1 },
  listening: { speed: 0.24, density: 0.48, chaos: 0.09, scale: 1.04 },
  thinking: { speed: 0.42, density: 0.76, chaos: 0.2, scale: 1.1 },
  executing: { speed: 0.62, density: 0.68, chaos: 0.075, scale: 1.07 },
  success: { speed: 0.8, density: 0.56, chaos: 0.04, scale: 1.12 },
  error: { speed: 0.3, density: 0.62, chaos: 0.34, scale: 1.04 },
};
const BLOOM: Record<LeonState, number> = { idle: 1.05, listening: 1.55, thinking: 2.1, executing: 2.0, success: 2.3, error: 1.75 };

function VoidParticles({ state, mouseX, mouseY }: { state: LeonState; mouseX: number; mouseY: number }) {
  const pointsRef = useRef<THREE.Points>(null);
  const pointsMaterial = useRef<THREE.PointsMaterial>(null);
  const trailsRef = useRef<THREE.LineSegments>(null);
  const trailsMaterial = useRef<THREE.LineBasicMaterial>(null);
  const stateRef = useRef(state);
  const mouseRef = useRef({ x: mouseX, y: mouseY });
  const previousState = useRef(state);
  const burstAt = useRef(-100);
  const positions = useMemo(() => new Float32Array(PARTICLE_COUNT * 3), []);
  const trailPositions = useMemo(() => new Float32Array(TRAIL_COUNT * (TRAIL_LENGTH - 1) * 2 * 3), []);
  const trailHistory = useMemo(() => Array.from({ length: TRAIL_COUNT }, () => Array.from({ length: TRAIL_LENGTH }, () => new THREE.Vector3())), []);
  const seeds = useMemo(() => Array.from({ length: PARTICLE_COUNT }, () => ({
    radius: 2.65 + Math.random() * 2.05,
    theta: Math.random() * Math.PI * 2,
    phi: Math.acos(2 * Math.random() - 1),
    speed: 0.35 + Math.random() * 0.9,
    phase: Math.random() * Math.PI * 2,
    band: Math.random(),
    size: 0.55 + Math.random() * 1.2,
  })), []);
  stateRef.current = state;
  mouseRef.current = { x: mouseX, y: mouseY };

  useEffect(() => {
    if (previousState.current !== state) burstAt.current = 0;
    previousState.current = state;
  }, [state]);

  useFrame(({ clock }) => {
    const points = pointsRef.current;
    const material = pointsMaterial.current;
    if (!points || !material) return;
    const t = clock.getElapsedTime();
    const tuning = TUNING[stateRef.current];
    const accent = new THREE.Color(COLORS.state[stateRef.current].accent);
    material.color.lerp(accent, 0.055);
    material.opacity += ((0.1 + tuning.density * 0.43) - material.opacity) * 0.045;
    material.size += ((stateRef.current === 'thinking' ? 0.052 : 0.04) - material.size) * 0.045;
    if (trailsMaterial.current) {
      trailsMaterial.current.color.lerp(accent, 0.06);
      trailsMaterial.current.opacity += ((0.08 + tuning.density * 0.25) - trailsMaterial.current.opacity) * 0.05;
    }

    const burstAge = t - burstAt.current;
    const burst = burstAge >= 0 && burstAge < 0.75 ? Math.sin((1 - burstAge / 0.75) * Math.PI) : 0;
    for (let i = 0; i < PARTICLE_COUNT; i += 1) {
      const p = seeds[i];
      const directed = stateRef.current === 'executing';
      const stream = directed ? (p.band - 0.5) * 1.5 : 0;
      const orbit = p.theta + t * tuning.speed * p.speed + stream * t * 0.16;
      const pulse = Math.sin(t * (0.7 + tuning.speed * 2) + p.phase) * tuning.chaos;
      const radius = p.radius * tuning.scale + pulse + Math.sin(t * 0.5 + p.phase) * 0.055 + burst * (0.12 + p.band * 0.62);
      const vertical = Math.sin(p.phi) * radius;
      const attraction = Math.max(0, 1 - p.radius / 5.5) * 0.09;
      positions[i * 3] = Math.cos(orbit) * vertical + mouseRef.current.x * attraction;
      positions[i * 3 + 1] = Math.cos(p.phi) * radius + (directed ? (p.band - 0.5) * 0.7 : 0) + mouseRef.current.y * attraction;
      positions[i * 3 + 2] = Math.sin(orbit) * vertical;
    }
    points.geometry.attributes.position.needsUpdate = true;

    const trailAttr = trailsRef.current?.geometry.attributes.position as THREE.BufferAttribute | undefined;
    if (trailAttr) {
      let offset = 0;
      for (let i = 0; i < TRAIL_COUNT; i += 1) {
        const particleIndex = i * 7;
        const x = positions[particleIndex * 3];
        const y = positions[particleIndex * 3 + 1];
        const z = positions[particleIndex * 3 + 2];
        const history = trailHistory[i];
        for (let j = TRAIL_LENGTH - 1; j > 0; j -= 1) history[j].copy(history[j - 1]);
        history[0].set(x, y, z);
        for (let j = 0; j < TRAIL_LENGTH - 1; j += 1) {
          const newer = history[j];
          const older = history[j + 1];
          trailPositions[offset++] = newer.x;
          trailPositions[offset++] = newer.y;
          trailPositions[offset++] = newer.z;
          trailPositions[offset++] = older.x;
          trailPositions[offset++] = older.y;
          trailPositions[offset++] = older.z;
        }
      }
      trailAttr.needsUpdate = true;
    }
  });

  return (
    <group>
      <lineSegments ref={trailsRef} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[trailPositions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial ref={trailsMaterial} color={COLORS.state.idle.accent} transparent opacity={0.16} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </lineSegments>
      <points ref={pointsRef} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial ref={pointsMaterial} color={COLORS.state.idle.accent} size={0.04} sizeAttenuation transparent opacity={0.24} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </points>
    </group>
  );
}

function VoidCore({ state }: { state: LeonState }) {
  const groupRef = useRef<THREE.Group>(null);
  const shellRef = useRef<THREE.Mesh>(null);
  const shellMaterial = useRef<THREE.ShaderMaterial>(null);
  const rimMaterial = useRef<THREE.ShaderMaterial>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const tuning = TUNING[stateRef.current];
    if (groupRef.current) {
      groupRef.current.rotation.y += 0.0005 + tuning.speed * 0.0018;
      groupRef.current.rotation.x = Math.sin(t * 0.16) * 0.075;
    }
    if (shellRef.current) {
      const breath = 1 + Math.sin(t * (0.42 + tuning.speed * 0.3)) * 0.018;
      shellRef.current.scale.setScalar(tuning.scale * breath);
    }
    if (shellMaterial.current) {
      const uniforms = shellMaterial.current.uniforms;
      uniforms.uTime.value = t;
      uniforms.uColor.value.lerp(new THREE.Color(COLORS.state[stateRef.current].primary), 0.045);
      uniforms.uAccent.value.lerp(new THREE.Color(COLORS.state[stateRef.current].glow), 0.045);
      uniforms.uDistortion.value += ((stateRef.current === 'thinking' || stateRef.current === 'executing' ? 0.19 : 0.11) - uniforms.uDistortion.value) * 0.04;
    }
    if (rimMaterial.current) {
      rimMaterial.current.uniforms.uTime.value = t;
      rimMaterial.current.uniforms.uColor.value.lerp(new THREE.Color(COLORS.state[stateRef.current].glow), 0.045);
      rimMaterial.current.uniforms.uIntensity.value += ((0.45 + tuning.density * 0.65) - rimMaterial.current.uniforms.uIntensity.value) * 0.05;
    }
  });

  return (
    <group ref={groupRef}>
      <mesh ref={shellRef}>
        <sphereGeometry args={[2.32, 96, 96]} />
        <shaderMaterial
          ref={shellMaterial}
          uniforms={{
            uTime: { value: 0 },
            uColor: { value: new THREE.Color(COLORS.state[state].primary) },
            uAccent: { value: new THREE.Color(COLORS.state[state].glow) },
            uDistortion: { value: 0.11 },
          }}
          vertexShader={`uniform float uTime; uniform float uDistortion; varying vec3 vNormal; varying vec3 vViewPosition; varying vec3 vPosition; void main(){ vec3 p=position; float wave=sin(position.y*2.7+uTime*0.72)*cos(position.x*2.1-uTime*0.48)+sin(position.z*3.1+uTime*0.56)*0.45; p+=normalize(position)*wave*uDistortion; vec4 mv=modelViewMatrix*vec4(p,1.0); vNormal=normalize(normalMatrix*normal); vViewPosition=-mv.xyz; vPosition=position; gl_Position=projectionMatrix*mv; }`}
          fragmentShader={`uniform float uTime; uniform vec3 uColor; uniform vec3 uAccent; varying vec3 vNormal; varying vec3 vViewPosition; varying vec3 vPosition; void main(){ vec3 n=normalize(vNormal); vec3 v=normalize(vViewPosition); float rim=pow(1.0-max(dot(n,v),0.0),2.5); float currents=0.5+0.5*sin(vPosition.y*4.0+vPosition.x*2.0+uTime*0.5); vec3 color=mix(vec3(0.004,0.008,0.016),uColor,0.10+currents*0.06); color+=uAccent*rim*0.28; gl_FragColor=vec4(color,0.98); }`}
          transparent
          depthWrite
        />
      </mesh>
      <mesh scale={1.008}>
        <sphereGeometry args={[2.32, 64, 64]} />
        <shaderMaterial
          ref={rimMaterial}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uniforms={{ uColor: { value: new THREE.Color(COLORS.state[state].glow) }, uTime: { value: 0 }, uIntensity: { value: 0.6 } }}
          vertexShader={`varying vec3 vNormal; varying vec3 vViewPosition; varying vec3 vPosition; void main(){ vec4 mvPosition=modelViewMatrix*vec4(position,1.0); vNormal=normalize(normalMatrix*normal); vViewPosition=-mvPosition.xyz; vPosition=position; gl_Position=projectionMatrix*mvPosition; }`}
          fragmentShader={`uniform vec3 uColor; uniform float uTime; uniform float uIntensity; varying vec3 vNormal; varying vec3 vViewPosition; varying vec3 vPosition; void main(){ vec3 n=normalize(vNormal); vec3 v=normalize(vViewPosition); float rim=pow(1.0-max(dot(n,v),0.0),3.2); float flow=0.72+0.28*sin(vPosition.y*3.2+uTime*0.45+sin(vPosition.x*2.0)); gl_FragColor=vec4(uColor, rim*flow*uIntensity); }`}
        />
      </mesh>
      {[3.02, 3.38, 3.78].map((radius, index) => (
        <mesh key={radius} rotation={[Math.PI / 2 + index * 0.35, index * 0.7, index * 0.18]}>
          <torusGeometry args={[radius, index === 0 ? 0.009 : 0.005, 8, 192]} />
          <meshBasicMaterial color={COLORS.state[state].accent} transparent opacity={[0.22, 0.12, 0.065][index]} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
      ))}
      <mesh scale={1.06}>
        <sphereGeometry args={[2.32, 32, 32]} />
        <meshBasicMaterial color={COLORS.state[state].glow} transparent opacity={0.025} side={THREE.BackSide} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

function Atmosphere({ state }: { state: LeonState }) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const stars = useMemo(() => {
    const values = new Float32Array(240 * 3);
    for (let i = 0; i < 240; i += 1) {
      const radius = 7 + Math.random() * 7;
      const theta = Math.random() * Math.PI * 2;
      const y = Math.random() * 2 - 1;
      const planar = Math.sqrt(1 - y * y);
      values[i * 3] = radius * planar * Math.cos(theta);
      values[i * 3 + 1] = radius * y;
      values[i * 3 + 2] = radius * planar * Math.sin(theta);
    }
    return values;
  }, []);

  useFrame(({ clock }) => {
    if (!materialRef.current) return;
    materialRef.current.uniforms.uTime.value = clock.getElapsedTime();
    materialRef.current.uniforms.uColor.value.lerp(new THREE.Color(COLORS.state[stateRef.current].primary), 0.025);
  });

  return (
    <>
      <mesh>
        <planeGeometry args={[200, 200]} />
        <shaderMaterial
          ref={materialRef}
          depthWrite={false}
          uniforms={{ uTime: { value: 0 }, uColor: { value: new THREE.Color(COLORS.state[state].primary) } }}
          vertexShader={`varying vec2 vUv; void main(){vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`}
          fragmentShader={`uniform float uTime; uniform vec3 uColor; varying vec2 vUv; float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);} float noise(vec2 p){vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),f.x),mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0,1.0)),f.x),f.y);} void main(){vec2 p=vUv-0.5; float n=noise(p*5.0+uTime*0.012)*0.65+noise(p*10.0-uTime*0.008)*0.35; float cloud=smoothstep(0.45,0.88,n)*smoothstep(0.72,0.08,length(p)); float vignette=1.0-smoothstep(0.28,0.78,length(p)); vec3 nebula=mix(vec3(0.012,0.022,0.04),uColor,0.22+cloud*0.35); gl_FragColor=vec4(nebula,cloud*0.12+vignette*0.025);}`}
        />
      </mesh>
      <points position={[0, 0, -1]} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[stars, 3]} />
        </bufferGeometry>
        <pointsMaterial color="#8cb9dc" size={0.018} transparent opacity={0.34} depthWrite={false} sizeAttenuation toneMapped={false} />
      </points>
    </>
  );
}

function Scene({ state, mouseX, mouseY }: { state: LeonState; mouseX: number; mouseY: number }) {
  const cameraRef = useRef<THREE.PerspectiveCamera>(null);
  const sceneGroup = useRef<THREE.Group>(null);
  const pointer = useRef({ x: 0, y: 0 });
  pointer.current = { x: mouseX, y: mouseY };

  useFrame(() => {
    const camera = cameraRef.current;
    const group = sceneGroup.current;
    if (camera) {
      camera.position.x += (pointer.current.x * 0.36 - camera.position.x) * 0.025;
      camera.position.y += (pointer.current.y * 0.24 - camera.position.y) * 0.025;
      camera.lookAt(0, 0, 0);
    }
    if (group) {
      group.rotation.y += (pointer.current.x * 0.035 - group.rotation.y) * 0.018;
      group.rotation.x += (-pointer.current.y * 0.022 - group.rotation.x) * 0.018;
    }
  });

  return (
    <>
      <perspectiveCamera ref={cameraRef} position={[0, 0, 11]} fov={48} />
      <Atmosphere state={state} />
      <ambientLight intensity={0.035} />
      <pointLight position={[4, 3, 6]} color={COLORS.state[state].glow} intensity={1.1} distance={12} />
      <group ref={sceneGroup}>
        <VoidCore state={state} />
        <VoidParticles state={state} mouseX={mouseX} mouseY={mouseY} />
      </group>
      <Bloom intensity={BLOOM[state]} luminanceThreshold={0.24} luminanceSmoothing={0.88} mipmapBlur />
    </>
  );
}

export function NeuralLattice({ state }: { state: LeonState }) {
  const mouse = useMousePosition();
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }} dpr={[1, 1.5]} style={{ background: 'transparent' }}>
        <Scene state={state} mouseX={mouse.normalizedX} mouseY={mouse.normalizedY} />
      </Canvas>
    </div>
  );
}
