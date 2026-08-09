import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Preflight",
  description:
    "Never get rejected for something a machine could have measured. " +
    "Destination-aware delivery compliance for finished media.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        {children}
      </body>
    </html>
  );
}
