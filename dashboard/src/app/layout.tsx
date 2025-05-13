import type { Metadata, Viewport } from "next";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-serif/500.css";
import "@fontsource/ibm-plex-serif/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./globals.css";

export const metadata: Metadata = {
  // Share-image addresses are built from this; set NEXT_PUBLIC_SITE_URL to the real address when the site is published.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://field-force-planner.vercel.app"),
  title: "Field Force Planner: reps and territories for a US pharma launch, from public data",
  description:
    "How many sales reps a US launch needs and how to cut 3,143 counties into balanced, connected territories, from the public NPI registry, Census and CDC data. Sizing as a live-formula Excel model; the alignment as tested code; every assumption in yellow.",
  authors: [{ name: "Mohammad Uzair Khan" }],
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf8f3" },
    { media: "(prefers-color-scheme: dark)", color: "#111817" },
  ],
  width: "device-width",
  initialScale: 1,
};

// Sets the saved theme before first paint so there is no flash of the wrong one.
const themeScript = `try{var t=localStorage.getItem("ff-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
