import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import "./globals.css";
import "./marker-cluster.css";
import { COUNTRY } from "@/config/country";
import { CARRIER_LABELS, CARRIER_ORDER } from "@/lib/carriers";
import { t } from "@/lib/strings";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: t.meta.title,
  description: t.meta.description(CARRIER_ORDER.map((c) => CARRIER_LABELS[c]).join(', ')),
  openGraph: {
    title: t.meta.ogTitle,
    description: t.meta.ogDescription(CARRIER_ORDER.length),
    type: "website",
    locale: COUNTRY.ogLocale,
    url: COUNTRY.siteUrl,
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: t.header.appTitle,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang={COUNTRY.htmlLang}>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
        <Analytics />
      </body>
    </html>
  );
}
