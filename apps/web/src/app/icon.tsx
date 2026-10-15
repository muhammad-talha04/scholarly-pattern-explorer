import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "#070814", color: "#7dd3fc", fontSize: 22 }}>
        ◎
      </div>
    ),
    { ...size },
  );
}
