import { heroConstellation } from "@/features/galaxy/stars";

it("seats a dozen papers with clear gaps", () => {
  const nodes = Array.from({ length: 24 }, (_, i) => ({
    id: `p${i}`,
    support: 1 - (i % 5) * 0.1,
    clusterId: ["a", "b", "c", "d"][i % 4],
    gap: i === 7,
    pos: [0, 0, 0] as [number, number, number],
    center: [0, 0, 0] as [number, number, number],
  }));
  const drawn = heroConstellation(nodes);
  expect(drawn).toHaveLength(12);
  expect(new Set(drawn.map((n) => n.clusterId)).size).toBe(4);
  expect(drawn.some((n) => n.gap)).toBe(true);
  let min = Infinity;
  for (let i = 0; i < drawn.length; i++) {
    for (let j = i + 1; j < drawn.length; j++) {
      const dx = drawn[i].pos[0] - drawn[j].pos[0];
      const dy = drawn[i].pos[1] - drawn[j].pos[1];
      const dz = drawn[i].pos[2] - drawn[j].pos[2];
      min = Math.min(min, Math.hypot(dx, dy, dz));
    }
  }
  expect(min).toBeGreaterThan(1.8);
  expect(drawn.every((n) => Math.hypot(...n.pos) > 2 && Math.hypot(...n.pos) < 6.2)).toBe(true);
  expect(heroConstellation(nodes.slice(0, 2))).toHaveLength(2);
});
