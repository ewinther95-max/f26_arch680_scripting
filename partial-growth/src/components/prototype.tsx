"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { Dock } from "@/components/dock";
import { clampSite, computeGrowth } from "@/lib/growth";

const FieldScene = dynamic(
  () => import("@/components/scene/field-scene").then((mod) => mod.FieldScene),
  {
    ssr: false,
    loading: () => (
      <div className="grid h-full place-items-center bg-[#d5dee3] text-sm text-stone-600">
        Drawing the field…
      </div>
    ),
  },
);

export function Prototype() {
  const [budget, setBudget] = useState(0.78);
  const [grain, setGrain] = useState(0.22);
  const [section, setSection] = useState(0.04);
  const [nucleation, setNucleation] = useState({ x: 0, z: 0 });
  const growth = useMemo(
    () => computeGrowth({ budget, grain, section }),
    [budget, grain, section],
  );

  return (
    <div className="min-h-dvh bg-[#f3efe6] text-stone-800">
      <header className="border-b border-stone-900/10 px-5 py-5 sm:px-8 sm:py-6">
        <p className="text-[10px] font-medium uppercase tracking-[0.22em] text-stone-500">
          Evan Winther
        </p>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h1 className="font-serif text-3xl leading-none text-stone-900 sm:text-4xl">
            Partial growth
          </h1>
          <p className="max-w-md text-sm leading-snug text-stone-600 sm:text-right">
            A page for testing one field against the mass, the ground, and a seat.
          </p>
        </div>
      </header>
      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <section className="border-b border-stone-900/10 lg:border-b-0">
          <div className="relative h-[68vh] min-h-[420px] bg-[#d5dee3] lg:h-[calc(100dvh-7.5rem)]">
            <FieldScene
              growth={growth}
              x={nucleation.x}
              z={nucleation.z}
              onPlace={(x, z) => setNucleation(clampSite(x, z))}
            />
          </div>
          <p className="px-5 py-3 text-[12px] leading-snug text-stone-500 sm:px-8">
            Click the ground in the frame to move where the field starts. The rest of the site stays empty.
          </p>
        </section>
        <Dock
          budget={budget}
          grain={grain}
          section={section}
          growth={growth}
          onBudget={setBudget}
          onGrain={setGrain}
          onSection={setSection}
        />
      </div>
    </div>
  );
}
