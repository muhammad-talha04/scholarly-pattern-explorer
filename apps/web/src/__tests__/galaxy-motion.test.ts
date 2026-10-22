import { DRIFT_AMP, DRIFT_HZ, ORBIT_SPEED, phaseOf, posedPosition } from "@/features/galaxy/stars";

const node = {
  pos: [1, 0.2, 0] as [number, number, number],
  center: [0, 0, 0] as [number, number, number],
  clusterId: "methods",
};

it("holds the resting layout when motion is off", () => {
  expect(posedPosition(node, 4, 0)).toEqual([1, 0.2, 0]);
});

it("orbits around the cluster centre and bobs while motion is on", () => {
  const time = 1.4;
  const moved = posedPosition(node, time, 1);
  const ang = time * ORBIT_SPEED;
  expect(moved[0]).toBeCloseTo(Math.cos(ang));
  expect(moved[2]).toBeCloseTo(Math.sin(ang));
  expect(moved[1]).toBeCloseTo(0.2 + Math.sin(time * DRIFT_HZ + phaseOf(node.clusterId)) * DRIFT_AMP);
  expect(Math.hypot(moved[0], moved[2])).toBeCloseTo(1);
});
