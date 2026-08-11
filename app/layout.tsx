import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dylan Prorok — Large-scale Japanese tattooing, Las Vegas",
  description:
    "A redesign concept for Las Vegas Japanese tattoo artist Dylan Prorok.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
