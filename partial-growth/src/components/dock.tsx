"use client";

import { Slider } from "@/components/ui/slider";
import type { Growth } from "@/lib/growth";
import { readings } from "@/lib/readings";

type DockProps = {
  budget: number;
  grain: number;
  section: number;
  growth: Growth;
  onBudget: (value: number) => void;
  onGrain: (value: number) => void;
  onSection: (value: number) => void;
};

function readValue(value: number | readonly number[]) {
  return typeof value === "number" ? value : value[0];
}

function Control({
  label,
  low,
  mid,
  high,
  value,
  onChange,
}: {
  label: string;
  low: string;
  mid?: string;
  high: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="grid gap-1.5">
      <span className="text-[11px] font-medium tracking-wide text-stone-700">{label}</span>
      <Slider
        aria-label={label}
        value={[value]}
        min={0}
        max={1}
        step={0.01}
        largeStep={0.1}
        onValueChange={(next) => onChange(readValue(next))}
      />
      <span className="flex justify-between text-[10px] uppercase tracking-[0.14em] text-stone-400">
        <span>{low}</span>
        {mid ? <span>{mid}</span> : <span />}
        <span>{high}</span>
      </span>
    </label>
  );
}

export function Dock({
  budget,
  grain,
  section,
  growth,
  onBudget,
  onGrain,
  onSection,
}: DockProps) {
  const notes = readings(growth);

  return (
    <aside className="flex flex-col gap-6 border-stone-900/10 bg-[#f7f4ee] px-5 py-6 sm:px-6 lg:border-l lg:py-8">
      <div>
        <p className="text-[10px] font-medium uppercase tracking-[0.22em] text-stone-500">
          Settle
        </p>
        <p className="mt-1 font-serif text-2xl leading-tight text-stone-900" aria-live="polite">
          {growth.title}
        </p>
        <p className="mt-2 text-sm leading-snug text-stone-600">{growth.caption}</p>
      </div>
      <div className="grid gap-4">
        <Control label="Budget" low="Low" high="High" value={budget} onChange={onBudget} />
        <Control label="Grain" low="Fine" high="Broad" value={grain} onChange={onGrain} />
        <Control
          label="Section"
          low="Carve"
          mid="Link"
          high="Cantilever"
          value={section}
          onChange={onSection}
        />
      </div>
      <ul className="grid gap-4">
        {notes.map((note) => (
          <li key={note.label}>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-stone-500">
              {note.label}
            </p>
            <p className="mt-1 text-sm leading-snug text-stone-700">{note.text}</p>
          </li>
        ))}
      </ul>
    </aside>
  );
}
