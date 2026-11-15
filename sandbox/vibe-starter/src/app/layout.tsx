import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "Buddhi Vibe App",
  description: "Built with Next.js App Router, Tailwind CSS v4, shadcn/ui, Drizzle ORM, BetterAuth, and Vercel AI SDK.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
        >
          Skip to main content
        </a>
        <main id="main-content" tabIndex={-1} className="min-h-screen">
          {children}
        </main>
        <Toaster />
      </body>
    </html>
  );
}
