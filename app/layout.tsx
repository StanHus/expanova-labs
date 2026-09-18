import type { Metadata } from "next";
import { Newsreader, Inter, JetBrains_Mono, Silkscreen } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const pixel = Silkscreen({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-pixel",
  display: "swap",
});

const display = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const body = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-mono",
  display: "swap",
});

const SITE = "Expanova Labs";
const DESC =
  "A verification-first AI lab. We build systems that prove their work — correctness checked by an objective oracle, not asserted by a model. Intelligence you can check, not claims you have to trust. Blocked beats faked.";

export const metadata: Metadata = {
  metadataBase: new URL("https://expanova-labs.vercel.app"),
  title: {
    default: "Expanova Labs — Verification-first AI",
    template: "%s · Expanova Labs",
  },
  description: DESC,
  applicationName: SITE,
  authors: [{ name: SITE }],
  keywords: [
    "verification-first AI",
    "theorem proving",
    "Lean 4",
    "miniF2F",
    "test-time compute",
    "PNRD#1",
  ],
  openGraph: {
    title: "Expanova Labs — Verification-first AI",
    description: DESC,
    type: "website",
    siteName: SITE,
  },
  twitter: {
    card: "summary_large_image",
    title: "Expanova Labs — Verification-first AI",
    description: DESC,
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${body.variable} ${mono.variable} ${pixel.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
