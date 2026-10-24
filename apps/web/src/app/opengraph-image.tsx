import { ImageResponse } from "next/og";
import { accent, ink } from "@/lib/theme";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Scholarly Pattern Explorer: a map of computer science research";

// Fixed dot layout (no randomness) so the card is identical on every build.
const DOTS = Array.from({ length: 70 }, (_, i) => ({ x: 640 + ((i * 137) % 520), y: 60 + ((i * 89) % 510), r: 3 + (i % 4) * 2, o: 0.35 + (i % 5) * 0.12 }));

export default function OgImage() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", position: "relative", background: ink, color: "white", fontFamily: "sans-serif" }}>
        {DOTS.map((d, i) => (
          <div key={i} style={{ position: "absolute", left: d.x, top: d.y, width: d.r * 2, height: d.r * 2, borderRadius: d.r, background: accent, opacity: d.o }} />
        ))}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 72px", width: 640 }}>
          <div style={{ fontSize: 30, color: accent }}>Scholarly Pattern Explorer</div>
          <div style={{ fontSize: 60, fontWeight: 700, lineHeight: 1.1, marginTop: 24 }}>A map of computer science research</div>
          <div style={{ fontSize: 26, color: "#9AA4B8", marginTop: 24 }}>Search papers, compare countries, and spot emerging patterns in a sample of 100,000 OpenAlex computer science papers.</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
