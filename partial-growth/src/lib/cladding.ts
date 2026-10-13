import * as THREE from "three";
import { reliefField } from "@/lib/field";
import { cutWallFaces, type FaceSpec } from "@/lib/geometry";
import { MASS, REACH_ROOT_X, lerp, type Growth } from "@/lib/growth";

const MAX_INSTANCES = 6500;

const matrixPool: THREE.Matrix4[] = [];
const colorPool: THREE.Color[] = [];
const basis = new THREE.Matrix4();
const quaternion = new THREE.Quaternion();
const position = new THREE.Vector3();
const scale = new THREE.Vector3();
const xAxis = new THREE.Vector3();
const yAxis = new THREE.Vector3();
const zAxis = new THREE.Vector3();
const glaze = new THREE.Color("#145e66");
const ridge = new THREE.Color("#9fe0d6");

export type CladdingData = {
  count: number;
  matrices: THREE.Matrix4[];
  colors: THREE.Color[];
};

function massFaces(): FaceSpec[] {
  const w = MASS.width;
  const d = MASS.depth;
  const h = MASS.height;
  return [
    { origin: [-w / 2, 0, d / 2], u: [w, 0, 0], v: [0, h, 0] },
    { origin: [w / 2, 0, -d / 2], u: [-w, 0, 0], v: [0, h, 0] },
    { origin: [w / 2, 0, d / 2], u: [0, 0, -d], v: [0, h, 0], mouth: true },
    { origin: [-w / 2, h, d / 2], u: [w, 0, 0], v: [0, 0, -d] },
  ];
}

function inMouth(x: number, y: number, z: number, growth: Growth) {
  if (Math.abs(x - REACH_ROOT_X) > 0.28) return false;
  if (Math.abs(z) > growth.mouthWidth / 2) return false;
  return y >= growth.mouthBottom - 0.08 && y <= growth.mouthTop + 0.08;
}

export function buildCladding(growth: Growth): CladdingData {
  const grain = growth.grain;
  const tile = lerp(0.26, 0.58, grain);
  const radius = growth.cladRadius;
  const center = new THREE.Vector3(REACH_ROOT_X - 0.35, 2.05, MASS.depth / 2 - 0.2);
  const depthScale = lerp(0.05, 0.3, growth.budget) * lerp(0.7, 1.25, grain);
  let count = 0;

  const paint = (field: number, id: number) => {
    const color = colorPool[count] ?? new THREE.Color();
    const t = THREE.MathUtils.clamp((field + 0.15) / 1.05, 0, 1);
    color.copy(glaze).lerp(ridge, t * t);
    const n = Math.sin(id * 12.9898) * 43758.5453;
    const frac = n - Math.floor(n);
    color.multiplyScalar(0.88 + frac * 0.14);
    colorPool[count] = color;
  };

  const push = (
    px: number,
    py: number,
    pz: number,
    ux: number,
    uy: number,
    uz: number,
    vx: number,
    vy: number,
    vz: number,
    nx: number,
    ny: number,
    nz: number,
    sx: number,
    sy: number,
    sz: number,
    field: number,
    id: number,
  ) => {
    if (count >= MAX_INSTANCES) return;
    position.set(px, py, pz);
    xAxis.set(ux, uy, uz);
    yAxis.set(vx, vy, vz);
    zAxis.set(nx, ny, nz);
    basis.makeBasis(xAxis, yAxis, zAxis);
    quaternion.setFromRotationMatrix(basis);
    scale.set(sx, sy, sz);
    const matrix = matrixPool[count] ?? new THREE.Matrix4();
    matrix.compose(position, quaternion, scale);
    matrixPool[count] = matrix;
    paint(field, id);
    count += 1;
  };

  let id = 0;
  for (const face of [...massFaces(), ...cutWallFaces(growth)]) {
    const uLen = Math.hypot(face.u[0], face.u[1], face.u[2]);
    const vLen = Math.hypot(face.v[0], face.v[1], face.v[2]);
    if (uLen < 0.05 || vLen < 0.05) continue;
    const ux = face.u[0] / uLen;
    const uy = face.u[1] / uLen;
    const uz = face.u[2] / uLen;
    let vx = face.v[0] / vLen;
    let vy = face.v[1] / vLen;
    let vz = face.v[2] / vLen;
    let nx = uy * vz - uz * vy;
    let ny = uz * vx - ux * vz;
    let nz = ux * vy - uy * vx;
    const nLen = Math.hypot(nx, ny, nz) || 1;
    nx /= nLen;
    ny /= nLen;
    nz /= nLen;
    if (ny < 0) {
      vx *= -1;
      vy *= -1;
      vz *= -1;
      nx *= -1;
      ny *= -1;
      nz *= -1;
    }

    const cols = Math.max(1, Math.ceil(uLen / tile));
    const rows = Math.max(1, Math.ceil(vLen / tile));
    let stride = 1;
    while ((cols / stride) * (rows / stride) > 1800) stride += 1;

    for (let row = 0; row < rows; row += stride) {
      for (let col = 0; col < cols; col += stride) {
        id += 1;
        const uPos = (col + 0.5) * tile;
        const vPos = (row + 0.5) * tile;
        if (uPos > uLen - tile * 0.35 || vPos > vLen - tile * 0.35) continue;
        const px = face.origin[0] + ux * uPos + vx * vPos;
        const py = face.origin[1] + uy * uPos + vy * vPos;
        const pz = face.origin[2] + uz * uPos + vz * vPos;
        const dist = Math.hypot(px - center.x, py - center.y, pz - center.z);
        if (dist > radius * (0.86 + 0.14 * ((id * 17) % 10) / 10)) continue;
        if (face.mouth && inMouth(px, py, pz, growth)) continue;

        const field = reliefField(px, py, pz, grain);
        const depth = 0.02 + Math.max(0, field) * depthScale * 1.8;
        push(
          px + nx * depth * 0.5,
          py + ny * depth * 0.5,
          pz + nz * depth * 0.5,
          ux, uy, uz, vx, vy, vz, nx, ny, nz,
          tile * 0.9,
          tile * 0.9,
          depth,
          field,
          id,
        );
      }
    }
  }

  const frontZ = MASS.depth / 2;
  if (growth.budget > 0.22) {
    const seatW = 1.15;
    const depth = 0.5;
    const height = 0.45;
    const start = Math.max(-MASS.width / 2 + 0.7, center.x - radius * 0.92);
    const end = Math.min(REACH_ROOT_X - 1.05, center.x + radius * 0.15);
    for (let x = start + seatW * 0.5; x < end; x += seatW) {
      id += 1;
      const field = reliefField(x, height, frontZ, grain);
      push(
        x,
        height / 2,
        frontZ + depth * 0.5 + 0.04,
        1, 0, 0,
        0, 1, 0,
        0, 0, 1,
        seatW,
        height,
        depth,
        0.72,
        id,
      );
      if (field > 0.25) {
        id += 1;
        const cap = lerp(0.06, 0.16, field);
        push(
          x,
          height + cap / 2,
          frontZ + depth * 0.42,
          1, 0, 0,
          0, 1, 0,
          0, 0, 1,
          seatW * 0.98,
          cap,
          depth * 0.62,
          field,
          id,
        );
      }
    }
  }

  return {
    count,
    matrices: matrixPool.slice(0, count),
    colors: colorPool.slice(0, count),
  };
}
