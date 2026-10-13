import { lerp } from "@/lib/growth";

/**
 * One flowing fold, roughly -1 to 1.
 * Fine grain is a tight ripple. Coarse grain is a broad wave.
 * The same field drives the ceramic relief, the ground, and the seat.
 */
export function reliefField(x: number, y: number, z: number, grain: number) {
  const freq = lerp(3.8, 0.7, grain);
  const along = x * 0.58 + z * 0.92;
  const across = z * 0.3 - x * 0.24 + y * 0.55;
  const bend = Math.sin(across * freq * 0.5);
  const fold = Math.sin(along * freq + bend * 1.4);
  const ridge = Math.cos(across * freq * 1.15 - along * freq * 0.28);
  return fold * 0.7 + ridge * 0.3;
}
