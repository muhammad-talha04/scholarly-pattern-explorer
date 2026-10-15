import { mesh } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import worldData from "world-atlas/countries-110m.json";
import { latLngToVec } from "./geo";

type World = Topology<{ countries: GeometryCollection }>;
const world = worldData as unknown as World;

/** Coastlines and borders from Natural Earth's 110m countries (world-atlas, public domain). */
export function countryBorders(): [number, number][][] {
  const lines = mesh(world, world.objects.countries);
  return (lines.coordinates ?? []) as [number, number][][];
}

/** SVG path in an equirectangular box. Date-line jumps start a new subpath so Russia does not streak across the map. */
export function bordersPath(width: number, height: number): string {
  const parts: string[] = [];
  for (const line of countryBorders()) {
    let open = false;
    let prev: [number, number] | null = null;
    for (const [lng, lat] of line) {
      const jump = prev != null && Math.abs(lng - prev[0]) > 180;
      const x = ((lng + 180) / 360) * width;
      const y = ((90 - lat) / 180) * height;
      if (!open || jump) {
        parts.push(`M${x.toFixed(1)} ${y.toFixed(1)}`);
        open = true;
      } else parts.push(`L${x.toFixed(1)} ${y.toFixed(1)}`);
      prev = [lng, lat];
    }
  }
  return parts.join(" ");
}

/** Line-segment positions on a sphere. Long chords (the antimeridian cut) are dropped. */
export function borderPositions(radius: number): Float32Array {
  const out: number[] = [];
  for (const line of countryBorders()) {
    for (let i = 1; i < line.length; i++) {
      const [lng0, lat0] = line[i - 1];
      const [lng1, lat1] = line[i];
      if (Math.abs(lng1 - lng0) > 180) continue;
      const a = latLngToVec(lat0, lng0, radius);
      const b = latLngToVec(lat1, lng1, radius);
      const dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2];
      if (dx * dx + dy * dy + dz * dz > 0.35) continue;
      out.push(a[0], a[1], a[2], b[0], b[1], b[2]);
    }
  }
  return new Float32Array(out);
}
