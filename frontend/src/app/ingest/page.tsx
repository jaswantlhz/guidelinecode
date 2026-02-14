"use client";

import { useState, useEffect } from "react";
import { api, type IngestResponse, type StatusResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function IngestPage() {
    const [gene, setGene] = useState("");
    const [drug, setDrug] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<IngestResponse | null>(null);
    const [error, setError] = useState("");
    const [status, setStatus] = useState<StatusResponse | null>(null);
    const [polling, setPolling] = useState(false);

    // Fetch pipeline status on mount
    useEffect(() => {
        api.status().then(setStatus).catch(() => { });
    }, []);

    // Poll ingestion status
    useEffect(() => {
        if (!polling || !gene || !drug) return;
        const interval = setInterval(async () => {
            try {
                const s = await api.ingestStatus(gene, drug);
                setResult(s);
                if (s.status === "completed" || s.status === "failed") {
                    setPolling(false);
                    setLoading(false);
                    api.status().then(setStatus).catch(() => { });
                }
            } catch {
                // ignore polling errors
            }
        }, 3000);
        return () => clearInterval(interval);
    }, [polling, gene, drug]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!gene.trim() || !drug.trim()) return;
        setLoading(true);
        setError("");
        setResult(null);

        try {
            const res = await api.ingest({ gene, drug });
            setResult(res);
            if (res.status === "pending" || res.status === "fetching_pdf") {
                setPolling(true);
            } else {
                setLoading(false);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "An error occurred");
            setLoading(false);
        }
    };

    const statusColor = (s: string) => {
        switch (s) {
            case "completed": return "bg-green-500/20 text-green-400 border-green-500/30";
            case "failed": return "bg-red-500/20 text-red-400 border-red-500/30";
            case "pending": return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
            default: return "bg-blue-500/20 text-blue-400 border-blue-500/30";
        }
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <section className="space-y-2">
                <h1 className="text-3xl font-bold">
                    <span className="gradient-text">Guideline Ingestion</span>
                </h1>
                <p className="text-black">
                    Fetch, parse, and index CPIC guideline PDFs into the vector database for RAG-powered Q&A.
                </p>
            </section>

            {/* Stats Bar */}
            {status && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                        { label: "Status", value: status.status === "ok" ? "Online" : "Offline", icon: "🟢" },
                        { label: "Guidelines", value: status.indexed_guidelines.toString(), icon: "📄" },
                        { label: "Chunks", value: status.total_chunks.toString(), icon: "🧩" },
                        { label: "Embeddings", value: status.embedding_model, icon: "🧠" },
                    ].map((s, i) => (
                        <Card key={i} className="glass border-border/40">
                            <CardContent className="pt-4 pb-4">
                                <div className="flex items-center gap-2">
                                    <span className="text-xl">{s.icon}</span>
                                    <div>
                                        <p className="text-xs text-muted-foreground">{s.label}</p>
                                        <p className="font-semibold text-sm">{s.value}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Ingest Form */}
            <Card className="glass border-border/40">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        Ingest New Guideline
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="ingest-gene">Gene Symbol</Label>
                                <Input
                                    id="ingest-gene"
                                    placeholder="e.g. CYP2D6"
                                    value={gene}
                                    onChange={(e) => setGene(e.target.value)}
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="ingest-drug">Drug Name</Label>
                                <Input
                                    id="ingest-drug"
                                    placeholder="e.g. amitriptyline"
                                    value={drug}
                                    onChange={(e) => setDrug(e.target.value)}
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                    required
                                />
                            </div>
                        </div>

                        <div className="rounded-lg bg-accent/5 border border-accent/20 p-4">
                            <p className="text-sm text-muted-foreground">
                                <span className="text-accent font-medium">Pipeline: </span>
                                Fetch PDF from CPIC → Parse with PyMuPDF → Chunk & Normalize →
                                Embed with all-MiniLM-L6-v2 → Store in FAISS + SQLite
                            </p>
                        </div>

                        <Button
                            type="submit"
                            disabled={loading || !gene.trim() || !drug.trim()}
                            className="w-full md:w-auto bg-primary hover:bg-primary/80 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <span className="animate-spin">⚛</span> Processing...
                                </span>
                            ) : (
                                <span className="flex items-center gap-2">Start Ingestion</span>
                            )}
                        </Button>
                    </form>
                </CardContent>
            </Card>

            {/* Error */}
            {error && (
                <Card className="border-destructive/50 bg-destructive/10">
                    <CardContent className="pt-6">
                        <p className="text-destructive flex items-center gap-2">
                            <span>⚠️</span> {error}
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Result */}
            {result && (
                <Card className="glass border-border/40 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base">Ingestion Status</CardTitle>
                            <Badge variant="outline" className={statusColor(result.status)}>
                                {result.status.toUpperCase()}
                            </Badge>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <p className="text-muted-foreground">{result.message}</p>
                        {result.guideline_id && (
                            <p className="text-sm text-primary mt-2">
                                Guideline ID: <span className="font-mono">{result.guideline_id}</span>
                            </p>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
