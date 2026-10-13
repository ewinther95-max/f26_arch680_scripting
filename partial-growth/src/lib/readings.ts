import type { Growth } from "@/lib/growth";

export type Reading = {
  label: string;
  text: string;
};

export function readings(growth: Growth): Reading[] {
  const relief =
    growth.budget < 0.28
      ? "A small patch of relief. Most of the mass stays brick."
      : growth.grain < 0.45
        ? "Tight folds on the near corner. The glaze sits in the grooves."
        : "Broad folds. Each tile takes a different depth from the same field.";

  const ground =
    growth.kind === "step"
      ? "The fold opens a short threshold. The rest of the ground stays flat."
      : growth.kind === "passage"
        ? "The fold runs through the ground far enough to walk."
        : growth.kind === "room"
          ? "The fold widens into a sunken court, with a mouth at the mass."
          : growth.kind === "cantilever"
            ? "Under the arm the ground is intact. The fold does not cut it."
            : "The ground stays whole. Only a light ripple of the field remains.";

  const seat =
    growth.budget > 0.22
      ? "A bench runs in front of the wall. Ridges in the field make it thicker."
      : "The field is too small to thicken into a seat.";

  const mass =
    growth.kind === "cantilever"
      ? "The arm leaves the mass and holds a lookout over open ground."
      : growth.kind === "link"
        ? "The arm leaves the mass and rests on posts at grade."
        : "The arm leaves the mass by entering the ground.";

  return [
    { label: "Relief", text: relief },
    { label: "Ground", text: ground },
    { label: "Seat", text: seat },
    { label: "Mass", text: mass },
  ];
}
