import * as THREE from "three";
import { reliefField } from "@/lib/field";
import {
  MASS,
  REACH_ROOT_X,
  halfWidthAt,
  lerp,
  planPolygon,
  profileSamples,
  smoothstep,
  type Growth,
} from "@/lib/growth";
import { PALETTE } from "@/lib/palette";

/** Shape Y is stored as -Z so rotateX(-90°) lays the plan on the ground, normal up. */
function shapeFromPlan(poly: [number, number][]) {
  const shape = new THREE.Shape();
  poly.forEach(([x, z], index) => {
    const y = -z;
    if (index === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  });
  shape.closePath();
  return shape;
}

export function extrudePlan(
  poly: [number, number][],
  y0: number,
  y1: number,
) {
  const depth = Math.max(0.02, y1 - y0);
  const geometry = new THREE.ExtrudeGeometry(shapeFromPlan(poly), {
    depth,
    bevelEnabled: false,
  });
  geometry.rotateX(-Math.PI / 2);
  geometry.translate(0, y0, 0);
  geometry.computeVertexNormals();
  return geometry;
}

export function groundWithHole(hole: [number, number][] | null, size = 220) {
  const shape = new THREE.Shape();
  shape.moveTo(-size, -size);
  shape.lineTo(size, -size);
  shape.lineTo(size, size);
  shape.lineTo(-size, size);
  shape.closePath();

  if (hole && hole.length >= 3) {
    const path = new THREE.Path();
    const reversed = [...hole].reverse();
    reversed.forEach(([x, z], index) => {
      const y = -z;
      if (index === 0) path.moveTo(x, y);
      else path.lineTo(x, y);
    });
    shape.holes.push(path);
  }

  const geometry = new THREE.ShapeGeometry(shape);
  geometry.rotateX(-Math.PI / 2);
  geometry.computeVertexNormals();
  return geometry;
}

function pushQuad(
  positions: number[],
  normals: number[],
  a: THREE.Vector3,
  b: THREE.Vector3,
  c: THREE.Vector3,
  d: THREE.Vector3,
) {
  const normal = new THREE.Vector3()
    .subVectors(b, a)
    .cross(new THREE.Vector3().subVectors(c, a))
    .normalize();
  for (const vertex of [a, b, c, a, c, d]) {
    positions.push(vertex.x, vertex.y, vertex.z);
    normals.push(normal.x, normal.y, normal.z);
  }
}

/** Earth walls of the cut. The mouth edge, against the mass, is left open. */
export function cutWallGeometry(growth: Growth) {
  if (growth.cutDepth < 0.04) return null;
  const samples = profileSamples(growth, 0, 1, 6);
  const positions: number[] = [];
  const normals: number[] = [];
  const y0 = -growth.cutDepth;
  const y1 = 0;

  const addWall = (x0: number, z0: number, x1: number, z1: number) => {
    const outward = Math.sign((z0 + z1) / 2) || 1;
    const a = new THREE.Vector3(x0, y0, z0);
    const b = new THREE.Vector3(x1, y0, z1);
    const c = new THREE.Vector3(x1, y1, z1);
    const d = new THREE.Vector3(x0, y1, z0);
    const trial = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(d, a));
    if (trial.z * outward < 0) pushQuad(positions, normals, a, d, c, b);
    else pushQuad(positions, normals, a, b, c, d);
  };

  for (let i = 0; i < samples.length - 1; i++) {
    const s0 = samples[i];
    const s1 = samples[i + 1];
    addWall(s0.x, -s0.h, s1.x, -s1.h);
    addWall(s1.x, s1.h, s0.x, s0.h);
  }

  const end = samples[samples.length - 1];
  addWall(end.x, -end.h, end.x, end.h);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  return geometry;
}

export function cutFloorGeometry(growth: Growth) {
  if (growth.cutDepth < 0.04) return null;
  const samples = profileSamples(growth, 0, 1, 6);
  return extrudePlan(planPolygon(samples), -growth.cutDepth - 0.08, -growth.cutDepth);
}

export function slabGeometry(growth: Growth, t0: number, t1: number, y0: number, y1: number) {
  if (t1 - t0 < 0.02) return null;
  const samples = profileSamples(growth, t0, t1, 5);
  if (samples[samples.length - 1].x - samples[0].x < 0.15) return null;
  return extrudePlan(planPolygon(samples), y0, y1);
}

export function stairGeometry(growth: Growth) {
  if (growth.stairRun < 0.2 || growth.walkY >= -0.08) return null;
  const drop = -growth.walkY;
  const risers = clampCount(Math.round(growth.stairRun / 0.4), 2, 8);
  const rise = drop / risers;
  const tread = growth.stairRun / risers;
  const width = growth.width0;
  const geometries: THREE.BufferGeometry[] = [];

  for (let i = 0; i < risers; i++) {
    const yTop = -rise * (i + 1);
    const yBottom = -growth.cutDepth + 0.02;
    const height = Math.max(0.05, yTop - yBottom);
    const box = new THREE.BoxGeometry(tread, height, width);
    box.translate(
      REACH_ROOT_X + i * tread + tread / 2,
      yBottom + height / 2,
      0,
    );
    geometries.push(box);
  }

  return geometries;
}

function clampCount(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function worldHole(growth: Growth, x: number, z: number): [number, number][] | null {
  if (growth.cutDepth < 0.04) return null;
  const samples = profileSamples(growth, 0, 1, 6);
  return planPolygon(samples).map(([px, pz]) => [px + x, pz + z]);
}

export function postPositions(growth: Growth) {
  if (growth.support < 0.4 || growth.underside < 0.1 || growth.cutDepth > 0.05) {
    return [] as { x: number; z: number }[];
  }
  const start = REACH_ROOT_X + Math.max(growth.stairRun, growth.length * 0.18);
  const freeEnd = growth.fly > 0.25 ? 0.78 : 0.88;
  const end = REACH_ROOT_X + growth.length * freeEnd;
  if (end - start < 0.8) return [];
  const span = end - start;
  const count = Math.max(1, Math.round(span / 4.4));
  const posts: { x: number; z: number }[] = [];
  for (let i = 0; i < count; i++) {
    const x = start + ((i + 0.5) * span) / count;
    const t = (x - REACH_ROOT_X) / growth.length;
    const inset = halfSafe(growth, t) * 0.55;
    posts.push({ x, z: -inset }, { x, z: inset });
  }
  return posts;
}

function halfSafe(growth: Growth, t: number) {
  const samples = profileSamples(growth, t, t, 1);
  return samples[0]?.h ?? growth.width0 / 2;
}

export function cutWallFaces(growth: Growth) {
  if (growth.cutDepth < 0.08) return [] as FaceSpec[];
  const samples = profileSamples(growth, 0, 1, 4);
  const faces: FaceSpec[] = [];
  const y0 = -growth.cutDepth;

  const push = (x0: number, z0: number, x1: number, z1: number) => {
    faces.push({
      origin: [x0, y0, z0],
      u: [x1 - x0, 0, z1 - z0],
      v: [0, -y0, 0],
    });
  };

  for (let i = 0; i < samples.length - 1; i++) {
    const s0 = samples[i];
    const s1 = samples[i + 1];
    push(s0.x, -s0.h, s1.x, -s1.h);
    push(s1.x, s1.h, s0.x, s0.h);
  }
  const end = samples[samples.length - 1];
  push(end.x, -end.h, end.x, end.h);
  return faces;
}

export type FaceSpec = {
  origin: [number, number, number];
  u: [number, number, number];
  v: [number, number, number];
  mouth?: boolean;
};

/** Local ground folded by the same field. The cut is left open. Far from the mass the patch falls flat. */
export function buildTopography(growth: Growth) {
  const x0 = -18;
  const x1 = REACH_ROOT_X + Math.max(growth.length, 4) + 8;
  const z0 = -16;
  const z1 = 16;
  const nx = 64;
  const nz = 48;
  const positions = new Float32Array((nx + 1) * (nz + 1) * 3);
  const colors = new Float32Array((nx + 1) * (nz + 1) * 3);
  const earth = new THREE.Color(PALETTE.ground);
  const tint = new THREE.Color("#d7ebe4");
  const amp = lerp(0.12, 1.15, growth.budget) * lerp(0.55, 1, growth.grain);
  const intact = growth.cutDepth < 0.05 ? 0.28 : 1;

  const insideCut = (x: number, z: number) => {
    if (growth.cutDepth < 0.08 || growth.length < 0.2) return false;
    const t = (x - REACH_ROOT_X) / growth.length;
    if (t < -0.02 || t > 1.02) return false;
    return Math.abs(z) < halfWidthAt(growth, Math.min(1, Math.max(0, t))) + 0.15;
  };

  let p = 0;
  for (let j = 0; j <= nz; j++) {
    for (let i = 0; i <= nx; i++) {
      const x = x0 + ((x1 - x0) * i) / nx;
      const z = z0 + ((z1 - z0) * j) / nz;
      const dist = Math.hypot(x - (REACH_ROOT_X - 0.4), z - MASS.depth / 4);
      const falloff = 1 - smoothstep(growth.cladRadius * 0.2, growth.cladRadius * 1.7, dist);
      const field = reliefField(x, 0, z, growth.grain);
      let y = 0.01;
      if (!insideCut(x, z)) y += Math.max(0, field) * amp * falloff * intact;
      positions[p] = x;
      positions[p + 1] = y;
      positions[p + 2] = z;
      const mix = Math.min(1, Math.max(0, (y - 0.01) * 2.4));
      colors[p] = earth.r + (tint.r - earth.r) * mix;
      colors[p + 1] = earth.g + (tint.g - earth.g) * mix;
      colors[p + 2] = earth.b + (tint.b - earth.b) * mix;
      p += 3;
    }
  }

  const indices: number[] = [];
  for (let j = 0; j < nz; j++) {
    for (let i = 0; i < nx; i++) {
      const x = x0 + ((x1 - x0) * (i + 0.5)) / nx;
      const z = z0 + ((z1 - z0) * (j + 0.5)) / nz;
      if (insideCut(x, z)) continue;
      const a = j * (nx + 1) + i;
      const b = a + 1;
      const c = a + nx + 1;
      const d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}
