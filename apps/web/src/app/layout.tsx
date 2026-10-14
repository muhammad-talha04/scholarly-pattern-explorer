import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { MotionProvider } from "@/components/MotionProvider";

export const metadata: Metadata = { title: "Scholarly Pattern Explorer", description: "Search research by meaning, see emerging patterns and research gaps." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <MotionProvider>
          <Nav />
          <main className="mx-auto max-w-7xl px-4 pb-16 pt-20">{children}</main>
        </MotionProvider>
      </body>
    </html>
  );
}
