import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Supplier screening",
  description: "Screen a supplier against sanctions lists",
};

const links = [
  ["/", "Screen"],
  ["/batch", "Batch"],
  ["/history", "History"],
  ["/info", "Info"],
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-white text-zinc-950">
        <header className="border-b border-zinc-200">
          <nav className="mx-auto flex max-w-3xl gap-4 px-4 py-3 text-sm">
            {links.map(([href, label]) => (
              <Link key={href} href={href} className="underline">
                {label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto grid max-w-3xl gap-6 px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
