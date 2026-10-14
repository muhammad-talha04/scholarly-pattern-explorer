import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Scholarly Pattern Explorer",
  description: "Watch research topic combinations emerge and fade, mined from OpenAlex.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
