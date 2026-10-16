import type { Metadata } from "next";
import { Fraunces, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { MotionProvider } from "@/components/MotionProvider";
import { Shell } from "@/components/Shell";
import { themeCss } from "@/lib/theme";
import { SITE_NAME, SITE_URL } from "@/lib/seo";

const sans = Space_Grotesk({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const display = Fraunces({ subsets: ["latin"], variable: "--font-display", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description: "Explore a two-year sample of AI research papers from OpenAlex: topics, countries, emerging patterns and research gaps.",
  applicationName: SITE_NAME,
  openGraph: { type: "website", siteName: SITE_NAME, locale: "en_US" },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body className="font-sans">
        <style>{themeCss}</style>
        <MotionProvider>
          <Shell>{children}</Shell>
        </MotionProvider>
      </body>
    </html>
  );
}
