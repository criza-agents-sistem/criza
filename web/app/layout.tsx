import type { Metadata } from "next";
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
  title: "CRIZA",
  description: "Casos que CRIZA acompaña",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-neutral-50 text-neutral-900">
        <header className="border-b border-neutral-200 bg-white">
          <div className="mx-auto flex max-w-4xl items-center gap-6 px-6 py-4">
            <a href="/" className="text-lg font-semibold">CRIZA</a>
            <nav className="flex gap-4 text-sm text-neutral-500">
              <a href="/" className="hover:text-neutral-900">Casos</a>
              <a href="/conductor" className="hover:text-neutral-900">Conductor</a>
              <a href="/especialistas" className="hover:text-neutral-900">Especialistas</a>
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
