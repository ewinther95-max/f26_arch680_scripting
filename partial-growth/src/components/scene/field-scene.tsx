"use client";

import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { buildCladding } from "@/lib/cladding";
import {
  buildTopography,
  cutFloorGeometry,
  cutWallGeometry,
  groundWithHole,
  postPositions,
  slabGeometry,
  stairGeometry,
  worldHole,
} from "@/lib/geometry";
import { MASS, REACH_ROOT_X, type Growth } from "@/lib/growth";
import { PALETTE } from "@/lib/palette";

const MAX_INSTANCES = 6500;

function assignGeometry(
  mesh: THREE.Mesh | null,
  geometry: THREE.BufferGeometry | null,
) {
  if (!mesh) return;
  mesh.geometry = geometry ?? new THREE.BufferGeometry();
}

function Cladding({ growth }: { growth: Growth }) {
  const data = useMemo(() => buildCladding(growth), [growth]);
  const ref = useRef<THREE.InstancedMesh>(null);
  const geometry = useMemo(() => new THREE.BoxGeometry(1, 1, 1), []);
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: PALETTE.ceramic,
        roughness: 0.42,
        metalness: 0.04,
        polygonOffset: true,
        polygonOffsetFactor: -1,
        polygonOffsetUnits: -1,
      }),
    [],
  );

  useLayoutEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    mesh.count = data.count;
    for (let i = 0; i < data.count; i++) {
      mesh.setMatrixAt(i, data.matrices[i]);
      mesh.setColorAt(i, data.colors[i]);
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
  }, [data]);

  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  return (
    <instancedMesh
      ref={ref}
      args={[geometry, material, MAX_INSTANCES]}
      frustumCulled
    />
  );
}

function Mass({ growth }: { growth: Growth }) {
  const mouthHeight = Math.max(0.4, growth.mouthTop - growth.mouthBottom);
  const mouthCenter = (growth.mouthTop + growth.mouthBottom) / 2;
  return (
    <group>
      <mesh position={[0, MASS.height / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[MASS.width, MASS.height, MASS.depth]} />
        <meshStandardMaterial color={PALETTE.mass} roughness={0.92} metalness={0} />
      </mesh>
      <mesh position={[0, MASS.floorLine, 0]}>
        <boxGeometry args={[MASS.width + 0.035, 0.05, MASS.depth + 0.035]} />
        <meshStandardMaterial color={PALETTE.joint} roughness={0.88} />
      </mesh>
      <mesh position={[REACH_ROOT_X - 0.38, mouthCenter, 0]}>
        <boxGeometry args={[0.72, mouthHeight, growth.mouthWidth]} />
        <meshStandardMaterial color={PALETTE.mouth} roughness={1} />
      </mesh>
      <mesh
        position={[REACH_ROOT_X + 0.012, mouthCenter, 0]}
        rotation={[0, Math.PI / 2, 0]}
      >
        <planeGeometry args={[growth.mouthWidth, mouthHeight]} />
        <meshBasicMaterial color="#1a1714" />
      </mesh>
    </group>
  );
}

function SlabMesh({
  growth,
  t0,
  t1,
  y0,
  y1,
  color,
}: {
  growth: Growth;
  t0: number;
  t1: number;
  y0: number;
  y1: number;
  color: string;
}) {
  const ref = useRef<THREE.Mesh>(null);
  useLayoutEffect(() => {
    const geometry = slabGeometry(growth, t0, t1, y0, y1);
    assignGeometry(ref.current, geometry);
    return () => geometry?.dispose();
  }, [growth, t0, t1, y0, y1]);

  return (
    <mesh ref={ref} name="slab" castShadow receiveShadow>
      <meshStandardMaterial color={color} roughness={0.74} metalness={0} side={THREE.DoubleSide} />
    </mesh>
  );
}

function Stairs({ growth }: { growth: Growth }) {
  const ref = useRef<THREE.Group>(null);
  useLayoutEffect(() => {
    const group = ref.current;
    if (!group) return;
    const geometries = stairGeometry(growth) ?? [];
    const material = new THREE.MeshStandardMaterial({
      color: PALETTE.timber,
      roughness: 0.76,
      metalness: 0,
    });
    const meshes = geometries.map((geometry) => {
      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      group.add(mesh);
      return mesh;
    });
    return () => {
      for (const mesh of meshes) {
        group.remove(mesh);
        mesh.geometry.dispose();
      }
      material.dispose();
    };
  }, [growth]);
  return <group ref={ref} />;
}

function Posts({ growth }: { growth: Growth }) {
  const posts = useMemo(() => postPositions(growth), [growth]);
  const height = Math.max(0.08, growth.underside);
  return (
    <group>
      {posts.map((post, index) => (
        <mesh
          key={`${post.x.toFixed(2)}-${post.z.toFixed(2)}-${index}`}
          position={[post.x, height / 2, post.z]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[0.34, height, 0.34]} />
          <meshStandardMaterial color={PALETTE.timberDark} roughness={0.8} />
        </mesh>
      ))}
    </group>
  );
}

function Reach({ growth }: { growth: Growth }) {
  const slabStartT = growth.length > 0 ? growth.stairRun / growth.length : 0;
  const split = growth.endSplit < 0.99 ? growth.endSplit : 1;
  const mainEnd = Math.max(split, slabStartT);
  return (
    <group>
      <SlabMesh
        growth={growth}
        t0={slabStartT}
        t1={mainEnd}
        y0={growth.underside}
        y1={growth.walkY}
        color={PALETTE.timber}
      />
      {split < 0.99 ? (
        <SlabMesh
          growth={growth}
          t0={split}
          t1={1}
          y0={growth.underside - growth.endExtra}
          y1={growth.walkY}
          color={PALETTE.timberDark}
        />
      ) : null}
      <Stairs growth={growth} />
      <Posts growth={growth} />
    </group>
  );
}

function Excavation({ growth }: { growth: Growth }) {
  const walls = useRef<THREE.Mesh>(null);
  const floor = useRef<THREE.Mesh>(null);
  useLayoutEffect(() => {
    const wallGeometry = cutWallGeometry(growth);
    const floorGeometry = cutFloorGeometry(growth);
    assignGeometry(walls.current, wallGeometry);
    assignGeometry(floor.current, floorGeometry);
    return () => {
      wallGeometry?.dispose();
      floorGeometry?.dispose();
    };
  }, [growth]);

  if (growth.cutDepth < 0.04) return null;
  return (
    <group>
      <mesh ref={walls} name="cut-walls" castShadow receiveShadow>
        <meshStandardMaterial color={PALETTE.earthWall} roughness={0.96} metalness={0} />
      </mesh>
      <mesh ref={floor} name="cut-floor" receiveShadow>
        <meshStandardMaterial
          color={PALETTE.earthFloor}
          roughness={1}
          metalness={0}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

function makeGroundTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.fillStyle = PALETTE.ground;
  context.fillRect(0, 0, 256, 256);
  const image = context.getImageData(0, 0, 256, 256);
  for (let i = 0; i < image.data.length; i += 4) {
    const n = (Math.random() - 0.5) * 16;
    image.data[i] = Math.min(255, Math.max(0, image.data[i] + n));
    image.data[i + 1] = Math.min(255, Math.max(0, image.data[i + 1] + n));
    image.data[i + 2] = Math.min(255, Math.max(0, image.data[i + 2] + n - 2));
  }
  context.putImageData(image, 0, 0);
  const map = new THREE.CanvasTexture(canvas);
  map.wrapS = THREE.RepeatWrapping;
  map.wrapT = THREE.RepeatWrapping;
  map.repeat.set(48, 48);
  map.colorSpace = THREE.SRGBColorSpace;
  map.anisotropy = 4;
  return map;
}

function Topography({ growth }: { growth: Growth }) {
  const ref = useRef<THREE.Mesh>(null);
  useLayoutEffect(() => {
    const geometry = buildTopography(growth);
    assignGeometry(ref.current, geometry);
    return () => geometry.dispose();
  }, [growth]);
  return (
    <mesh ref={ref} name="topography" receiveShadow castShadow>
      <meshStandardMaterial vertexColors roughness={0.96} metalness={0} />
    </mesh>
  );
}

function Ground({
  growth,
  x,
  z,
}: {
  growth: Growth;
  x: number;
  z: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const texture = useMemo(() => makeGroundTexture(), []);
  useEffect(() => () => texture?.dispose(), [texture]);

  useLayoutEffect(() => {
    const geometry = groundWithHole(worldHole(growth, x, z));
    assignGeometry(ref.current, geometry);
    return () => geometry.dispose();
  }, [growth, x, z]);

  return (
    <mesh ref={ref} name="ground" receiveShadow>
      <meshStandardMaterial
        color={PALETTE.ground}
        map={texture}
        roughness={0.98}
        metalness={0}
        side={THREE.DoubleSide}
        polygonOffset
        polygonOffsetFactor={1}
        polygonOffsetUnits={1}
      />
    </mesh>
  );
}

function FieldPicker({ onPlace }: { onPlace: (x: number, z: number) => void }) {
  const down = useRef<{ x: number; y: number } | null>(null);
  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, 0.03, 0]}
      onPointerDown={(event) => {
        down.current = { x: event.clientX, y: event.clientY };
      }}
      onPointerUp={(event) => {
        if (!down.current) return;
        const dx = event.clientX - down.current.x;
        const dy = event.clientY - down.current.y;
        down.current = null;
        if (dx * dx + dy * dy > 16) return;
        onPlace(event.point.x, event.point.z);
      }}
    >
      <planeGeometry args={[440, 440]} />
      <meshBasicMaterial transparent opacity={0} depthWrite={false} />
    </mesh>
  );
}

function Lights() {
  const light = useRef<THREE.DirectionalLight>(null);
  const target = useRef<THREE.Object3D>(null);

  useLayoutEffect(() => {
    if (light.current && target.current) {
      light.current.target = target.current;
    }
  }, []);

  useFrame(() => {
    target.current?.updateMatrixWorld();
  });

  return (
    <>
      <hemisphereLight args={[PALETTE.fill, "#b7b0a2", 0.42]} />
      <ambientLight intensity={0.08} />
      <directionalLight
        ref={light}
        position={[24, 7.5, -6]}
        intensity={3.8}
        color={PALETTE.sun}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-bias={-0.0004}
        shadow-normalBias={0.04}
        shadow-camera-near={0.5}
        shadow-camera-far={80}
        shadow-camera-left={-28}
        shadow-camera-right={30}
        shadow-camera-top={26}
        shadow-camera-bottom={-26}
      />
      <directionalLight position={[-12, 14, 18]} intensity={0.28} color={PALETTE.fill} />
      <object3D ref={target} position={[4, 0.2, 0]} />
    </>
  );
}

function CameraRig({ x, z }: { x: number; z: number }) {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as
    | { target: THREE.Vector3; update: () => void }
    | null;
  const anchor = useRef({ x, z, ready: false });

  useLayoutEffect(() => {
    camera.position.set(16, 6.4, 17);
    camera.lookAt(1.4, 1.15, 0.4);
    camera.updateProjectionMatrix();
  }, [camera]);

  // OrbitControls and the camera are mutable three.js objects, updated each frame.
  /* eslint-disable react-hooks/immutability */
  useFrame(() => {
    if (!controls) return;
    if (!anchor.current.ready) {
      controls.target.set(1.4, 1.15, 0.4);
      controls.update();
      anchor.current = { x, z, ready: true };
      return;
    }
    const dx = x - anchor.current.x;
    const dz = z - anchor.current.z;
    if (dx !== 0 || dz !== 0) {
      camera.position.x += dx;
      camera.position.z += dz;
      controls.target.x += dx;
      controls.target.z += dz;
      anchor.current.x = x;
      anchor.current.z = z;
      controls.update();
    }
  });
  /* eslint-enable react-hooks/immutability */

  return null;
}

function SceneBody({
  growth,
  x,
  z,
  onPlace,
}: {
  growth: Growth;
  x: number;
  z: number;
  onPlace: (x: number, z: number) => void;
}) {
  return (
    <>
      <color attach="background" args={[PALETTE.sky]} />
      <fog attach="fog" args={[PALETTE.sky, 70, 210]} />
      <CameraRig x={x} z={z} />
      <OrbitControls
        makeDefault
        enableDamping
        enablePan={false}
        dampingFactor={0.08}
        maxPolarAngle={Math.PI / 2.04}
        minPolarAngle={0.2}
        minDistance={7}
        maxDistance={56}
      />
      <Ground growth={growth} x={x} z={z} />
      <FieldPicker onPlace={onPlace} />
      <group position={[x, 0, z]}>
        <Lights />
        <Topography growth={growth} />
        <Mass growth={growth} />
        <Excavation growth={growth} />
        <Reach growth={growth} />
        <Cladding growth={growth} />
      </group>
    </>
  );
}

export function FieldScene({
  growth,
  x,
  z,
  onPlace,
}: {
  growth: Growth;
  x: number;
  z: number;
  onPlace: (x: number, z: number) => void;
}) {
  return (
    <Canvas
      shadows
      dpr={[1, 1.75]}
      camera={{ position: [16, 6.4, 17], fov: 34, near: 0.1, far: 420 }}
      style={{ width: "100%", height: "100%", cursor: "crosshair" }}
      gl={{
        antialias: true,
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: 1.08,
      }}
      onCreated={({ gl }) => {
        gl.shadowMap.type = THREE.PCFSoftShadowMap;
      }}
    >
      <SceneBody growth={growth} x={x} z={z} onPlace={onPlace} />
    </Canvas>
  );
}
