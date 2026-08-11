import type { Metadata, Viewport } from "next";
import { Inter, DM_Sans, DM_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-dm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "EnviroWealth — Carbon Credit Eligibility Assessor",
  description:
    "AI-powered screening tool for Indian landowners to assess carbon credit eligibility across CCTS, Verra VM0047, Gold Standard, and Plan Vivo methodologies. Get an instant, confidential eligibility verdict for your land parcel.",
  keywords: [
    "carbon credits India",
    "CCTS eligibility",
    "VM0047",
    "carbon credit consultant",
    "land eligibility assessment",
    "agroforestry carbon",
    "voluntary carbon market India",
  ],
  authors: [{ name: "EnviroWealth" }],
  openGraph: {
    title: "EnviroWealth — Carbon Credit Eligibility Assessor",
    description:
      "Instant AI-powered eligibility screening for carbon credits. Find out if your land qualifies — free, confidential, and in minutes.",
    type: "website",
    locale: "en_IN",
  },
  twitter: {
    card: "summary_large_image",
    title: "EnviroWealth — Carbon Credit Eligibility Assessor",
    description: "Instant eligibility screening for carbon credits. Free, confidential, in minutes.",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#081410",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${dmSans.variable} ${dmMono.variable}`}>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
