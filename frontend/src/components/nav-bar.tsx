"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

const links = [
    { href: "/", label: "Query" },
    { href: "/ingest", label: "Ingest" },
    { href: "/phenotype", label: "Phenotype" },
];

export function NavBar() {
    const pathname = usePathname();
    const [open, setOpen] = useState(false);

    return (
        <header className="sticky top-0 z-50 border-b border-border/40">
            <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-2 group">
                    <span className="text-lg font-bold gradient-text tracking-tight">
                        CPIC RAG
                    </span>
                </Link>

                {/* Desktop nav */}
                <nav className="hidden md:flex items-center gap-1">
                    {links.map((l) => (
                        <Link key={l.href} href={l.href}>
                            <Button
                                variant={pathname === l.href ? "secondary" : "ghost"}
                                className={`gap-2 transition-all duration-200 ${pathname === l.href
                                    ? "bg-primary/15 text-primary border border-primary/20"
                                    : "hover:bg-primary/10"
                                    }`}
                            >
                                {l.label}
                            </Button>
                        </Link>
                    ))}
                </nav>

                {/* Mobile nav */}
                <Sheet open={open} onOpenChange={setOpen}>
                    <SheetTrigger asChild className="md:hidden">
                        <Button variant="ghost" size="icon">
                            <span className="text-xl">☰</span>
                        </Button>
                    </SheetTrigger>
                    <SheetContent side="right" className="glass w-64">
                        <nav className="flex flex-col gap-2 mt-8">
                            {links.map((l) => (
                                <Link key={l.href} href={l.href} onClick={() => setOpen(false)}>
                                    <Button
                                        variant={pathname === l.href ? "secondary" : "ghost"}
                                        className="w-full justify-start gap-3"
                                    >

                                        {l.label}
                                    </Button>
                                </Link>
                            ))}
                        </nav>
                    </SheetContent>
                </Sheet>
            </div>
        </header>
    );
}
