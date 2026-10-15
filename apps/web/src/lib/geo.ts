/** Approximate country centroids (lat, lng) for globe placement. */
export const CENTROIDS: Record<string, [number, number]> = {
  US: [39, -98], CN: [35, 104], GB: [54, -2], DE: [51, 10], IN: [21, 78], JP: [36, 138], CA: [56, -106],
  FR: [46, 2], KR: [36, 128], AU: [-25, 134], BR: [-10, -52], PK: [30, 70], IT: [42, 12], NL: [52, 5],
  SG: [1.3, 103.8], ZA: [-29, 24], NG: [9, 8], SA: [24, 45], ES: [40, -4], SE: [62, 15], CH: [47, 8],
  RU: [61, 100], MX: [23, -102], TR: [39, 35], IR: [32, 53], EG: [27, 30], ID: [-2, 118], BD: [24, 90],
};
export function latLngToVec(lat: number, lng: number, r: number): [number, number, number] {
  const phi = ((90 - lat) * Math.PI) / 180, theta = ((lng + 180) * Math.PI) / 180;
  return [-r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta)];
}
