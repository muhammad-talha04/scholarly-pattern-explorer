/** ISO 3166-1 alpha-2 codes for territories / special regions that are not sovereign UN members. */
export const NON_SOVEREIGN = new Set([
  "HK", "MO", "TW", "PR", "RE", "GP", "MQ", "GF", "YT", "NC", "PF", "PM", "BL", "MF", "WF",
  "GU", "AS", "VI", "MP", "UM", "GI", "FO", "GL", "AX", "BM", "KY", "VG", "AI", "MS", "TC",
  "FK", "SH", "IO", "PN", "GS", "AW", "CW", "SX", "BQ", "IM", "JE", "GG", "CX", "CC", "NF",
  "HM", "TK", "NU", "CK", "EH", "PS", "XK", "SJ", "BV", "TF", "AQ",
]);

export function isRegion(code: string | null | undefined): boolean {
  return !!code && NON_SOVEREIGN.has(code.toUpperCase());
}
