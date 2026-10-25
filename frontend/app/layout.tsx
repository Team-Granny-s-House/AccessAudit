import type { Metadata } from "next";
import Link from "next/link";
import { Atkinson_Hyperlegible } from "next/font/google";
import "./globals.css";

const atkinson = Atkinson_Hyperlegible({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-atkinson",
});

export const metadata: Metadata = {
  title: "AccessAudit",
  description: "Can a keyboard or screen-reader user actually finish the task? AccessAudit finds out.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${atkinson.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a href="#main" className="skip-link site-chrome">
          Skip to main content
        </a>
        <header className="site-chrome on-navy bg-navy text-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="text-xl font-bold tracking-tight text-white no-underline">
              AccessAudit
            </Link>
            <p className="hidden text-sm text-slate-200 sm:block">
              Can a keyboard or screen-reader user actually finish the task?
            </p>
          </div>
        </header>
        <div className="flex flex-1 flex-col">{children}</div>
        <footer className="site-chrome border-t border-border">
          <p className="mx-auto max-w-6xl px-4 py-4 text-sm text-ink-soft">
            AccessAudit tests real tasks with the keyboard only, using TinyFish cloud browsers. A fast first pass,
            not a replacement for testing with disabled users.
          </p>
        </footer>
      </body>
    </html>
  );
}
