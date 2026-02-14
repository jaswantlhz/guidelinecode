import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { NavBar } from "@/components/nav-bar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
    title: "CPIC RAG — Pharmacogenomics Intelligence",
    description:
        "AI-powered pharmacogenomics decision support using CPIC guidelines",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="dark">
            <body
                className={`${inter.variable} font-sans antialiased bg-background text-foreground min-h-screen`}
            >
                <NavBar />
                <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
            </body>
        </html>
    );
}
