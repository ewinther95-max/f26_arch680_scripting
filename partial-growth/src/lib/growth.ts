export const MASS = {
  width: 12,
  depth: 6.3,
  height: 6.55,
  floorLine: 3.22,
} as const;

export const REACH_ROOT_X = MASS.width / 2;

const SITE_LIMIT = 70;

export type GrowthInput = {
  budget: number;
  grain: number;
  section: number;
};

export type SpatialKind = "step" | "passage" | "room" | "link" | "cantilever";

export type Growth = {
  budget: number;
  grain: number;
  section: number;
  length: number;
  width0: number;
  width1: number;
  walkY: number;
  slabThickness: number;
  cutDepth: number;
  underside: number;
  support: number;
  fly: number;
  cladRadius: number;
  mouthWidth: number;
  mouthBottom: number;
  mouthTop: number;
  stairRun: number;
  endSplit: number;
  endExtra: number;
  kind: SpatialKind;
  title: string;
  caption: string;
};

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export function smoothstep(edge0: number, edge1: number, value: number) {
  const t = clamp((value - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

export function clampSite(x: number, z: number) {
  return {
    x: clamp(x, -SITE_LIMIT, SITE_LIMIT),
    z: clamp(z, -SITE_LIMIT, SITE_LIMIT),
  };
}

/** Half-width of the reach at t, where 0 is the mouth and 1 is the far end. */
export function halfWidthAt(growth: Growth, t: number) {
  const h0 = growth.width0 / 2;
  const h1 = growth.width1 / 2;
  const flareStart = growth.fly > 0.25 ? 0.64 : 0.48;
  return lerp(h0, h1, smoothstep(flareStart, 1, t));
}

export type ProfileSample = { t: number; x: number; h: number };

export function profileSamples(
  growth: Growth,
  t0: number,
  t1: number,
  count = 6,
): ProfileSample[] {
  const samples: ProfileSample[] = [];
  const n = Math.max(1, count);
  for (let i = 0; i <= n; i++) {
    const t = lerp(t0, t1, i / n);
    samples.push({
      t,
      x: REACH_ROOT_X + growth.length * t,
      h: halfWidthAt(growth, t),
    });
  }
  return samples;
}

/** Closed plan, CCW in the XZ plane, from the mouth out to t1. */
export function planPolygon(
  samples: ProfileSample[],
  margin = 0,
): [number, number][] {
  const left: [number, number][] = [];
  const right: [number, number][] = [];
  for (const sample of samples) {
    const h = sample.h + margin;
    left.push([sample.x, -h]);
    right.push([sample.x, h]);
  }
  return [...left, ...right.reverse()];
}

function nameReach(growth: {
  length: number;
  cutDepth: number;
  walkY: number;
  support: number;
  fly: number;
}): Pick<Growth, "kind" | "title" | "caption"> {
  const below = growth.cutDepth > 0.16 && growth.walkY < 0.22;
  if (below) {
    if (growth.length >= 13 && growth.cutDepth >= 1.2) {
      return {
        kind: "room",
        title: "Room",
        caption: "A sunken court, with a mouth at the mass.",
      };
    }
    if (growth.length < 6.8 || growth.cutDepth < 0.62) {
      return {
        kind: "step",
        title: "Step",
        caption: "A short threshold cut into the flat ground.",
      };
    }
    return {
      kind: "passage",
      title: "Passage",
      caption: "The cut runs far enough to walk through.",
    };
  }
  if (growth.support > 0.35 && growth.fly < 0.72) {
    return {
      kind: "link",
      title: "Link",
      caption: "A supported connection leaving the mass at grade.",
    };
  }
  return {
    kind: "cantilever",
    title: "Cantilever / lookout",
    caption: "A platform held over intact ground.",
  };
}

/**
 * One reach, sampled from the section slider.
 * Below grade the walk surface is the floor of a cut. At grade it is a
 * supported link. Above grade the same surface is a cantilever whose end
 * thickens into a lookout. The ground stays flat except where the cut opens.
 */
export function computeGrowth(input: GrowthInput): Growth {
  const budget = clamp(input.budget, 0, 1);
  const grain = clamp(input.grain, 0, 1);
  const section = clamp(input.section, 0, 1);

  const length = lerp(3.3, 18.5, Math.pow(budget, 0.9));
  const depthFull = lerp(0.42, 2.55, budget);
  const thin = 0.12;
  const fly = smoothstep(0.56, 0.9, section);
  const slabThickness = lerp(thin, lerp(0.3, 0.48, budget), fly);

  const buriedWalk = -depthFull + thin;
  const gradeWalk = thin;
  const highWalk = lerp(3.4, 4.45, budget);
  const walkY =
    section < 0.36
      ? lerp(buriedWalk, gradeWalk, smoothstep(0, 0.36, section))
      : lerp(gradeWalk, highWalk, smoothstep(0.36, 0.78, section));

  const underside = walkY - slabThickness;
  const cutDepth = underside < -0.03 ? -underside : 0;
  const support =
    smoothstep(0.4, 0.52, section) * (1 - smoothstep(0.66, 0.86, section));

  const width0 = lerp(2.2, 3.4, budget);
  const room =
    smoothstep(0.58, 1, budget) * smoothstep(0.85, 1.7, cutDepth);
  const width1 =
    width0 * (1 + room * 1.7 + smoothstep(0.15, 1, fly) * 0.85);

  const cladRadius = lerp(1.85, 7.4, Math.pow(budget, 0.8));
  const mouthWidth = width0 * 0.86;
  const elevated = smoothstep(0.52, 0.78, section);
  const mouthBottom = lerp(0.05, Math.max(0.05, walkY - 0.04), elevated);
  const mouthTop = Math.min(MASS.height - 0.16, mouthBottom + 2.62);

  let stairRun = 0;
  if (cutDepth > 0.24 && walkY < -0.1) {
    const drop = -walkY;
    const risers = clamp(Math.round(drop / 0.18), 2, 8);
    const wanted = risers * 0.42;
    const cap = length < 6.8 ? length * 0.92 : Math.min(length * 0.36, 3.8);
    stairRun = Math.min(wanted, cap, length * 0.92);
  }

  const endSplit = fly > 0.12 ? 0.66 : 1;
  const endExtra = lerp(0, 0.46, fly);

  const named = nameReach({ length, cutDepth, walkY, support, fly });

  return {
    budget,
    grain,
    section,
    length,
    width0,
    width1,
    walkY,
    slabThickness,
    cutDepth,
    underside,
    support,
    fly,
    cladRadius,
    mouthWidth,
    mouthBottom,
    mouthTop,
    stairRun,
    endSplit,
    endExtra,
    ...named,
  };
}
