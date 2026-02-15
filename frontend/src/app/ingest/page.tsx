"use client";

import { useState, useEffect } from "react";
import { api, type IngestResponse, type StatusResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Info } from "lucide-react";

export default function IngestPage() {
    const [gene, setGene] = useState("");
    const [drug, setDrug] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<IngestResponse | null>(null);
    const [error, setError] = useState("");
    const [status, setStatus] = useState<StatusResponse | null>(null);
    const [polling, setPolling] = useState(false);

    const [availableGenes, setAvailableGenes] = useState<string[]>([]);
    const [availableDrugs, setAvailableDrugs] = useState<string[]>([]);
    const [geneDrugPairs, setGeneDrugPairs] = useState<{ Gene: string; Drug: string }[]>([]);

    // Filter logic
    const filteredGenes = availableGenes.filter(g => {
        // 1. Text search
        if (!g.toLowerCase().includes(gene.toLowerCase())) return false;
        // 2. Filter by selected drug (if it's a valid exact match)
        if (drug && availableDrugs.includes(drug)) {
            return geneDrugPairs.some(p => p.Drug === drug && p.Gene === g);
        }
        return true;
    });

    const filteredDrugs = availableDrugs.filter(d => {
        // 1. Text search
        if (!d.toLowerCase().includes(drug.toLowerCase())) return false;
        // 2. Filter by selected gene (if it's a valid exact match)
        if (gene && availableGenes.includes(gene)) {
            return geneDrugPairs.some(p => p.Gene === gene && p.Drug === d);
        }
        return true;
    });

    // Fetch pipeline status and options on mount
    useEffect(() => {
        api.status().then(setStatus).catch(() => { });
        api.ingestOptions().then(opts => {
            setAvailableGenes(opts.genes);
            setAvailableDrugs(opts.drugs);
            setGeneDrugPairs(opts.pairs);
        }).catch(err => console.error("Failed to load options", err));
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
                <p className=" black ">
                    Fetch, parse, and index CPIC guideline PDFs into the vector database for RAG-powered Q&A.
                </p>
            </section>

            {/* Stats Bar */}
            {status && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                        { label: "Status", value: status.status === "ok" ? "Online" : "Offline" },
                        { label: "Guidelines", value: status.indexed_guidelines.toString() },
                        { label: "Chunks", value: status.total_chunks.toString() },
                        { label: "Embeddings", value: status.embedding_model },
                    ].map((s, i) => (
                        <Card key={i} className="glass border-border/40">
                            <CardContent className="pt-4 pb-4">
                                <div className="flex items-center gap-2">
                                    <span className="text-xl"></span>
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
                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Gene Selection */}
                            <div className="space-y-3">
                                <Label htmlFor="ingest-gene">Gene Symbol</Label>
                                <Input
                                    id="ingest-gene"
                                    placeholder="e.g. CYP2D6"
                                    value={gene}
                                    onChange={(e) => setGene(e.target.value)}
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                    required
                                />
                                <div className="h-48 overflow-y-auto border border-border/30 rounded-md p-2 bg-background/30 custom-scrollbar">
                                    <div className="flex flex-wrap gap-2">
                                        {filteredGenes.map(g => (
                                            <button
                                                key={g}
                                                type="button"
                                                onClick={() => setGene(g)}
                                                className={`text-xs px-2 py-1 rounded-md border transition-all ${gene === g
                                                    ? "bg-primary text-primary-foreground border-primary"
                                                    : "bg-muted/50 hover:bg-muted text-muted-foreground border-transparent hover:border-border/50"
                                                    }`}
                                            >
                                                {g}
                                            </button>
                                        ))}
                                        {filteredGenes.length === 0 && (
                                            <p className="text-xs text-muted-foreground w-full text-center py-4">
                                                No matching genes found
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Drug Selection */}
                            <div className="space-y-3">
                                <Label htmlFor="ingest-drug">Drug Name</Label>
                                <Input
                                    id="ingest-drug"
                                    placeholder="e.g. amitriptyline"
                                    value={drug}
                                    onChange={(e) => setDrug(e.target.value)}
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                    required
                                />
                                <div className="h-48 overflow-y-auto border border-border/30 rounded-md p-2 bg-background/30 custom-scrollbar">
                                    <div className="flex flex-wrap gap-2">
                                        {filteredDrugs.map(d => (
                                            <button
                                                key={d}
                                                type="button"
                                                onClick={() => setDrug(d)}
                                                className={`text-xs px-2 py-1 rounded-md border transition-all ${drug === d
                                                    ? "bg-primary text-primary-foreground border-primary"
                                                    : "bg-muted/50 hover:bg-muted text-muted-foreground border-transparent hover:border-border/50"
                                                    }`}
                                            >
                                                {d}
                                            </button>
                                        ))}
                                        {filteredDrugs.length === 0 && (
                                            <p className="text-xs text-muted-foreground w-full text-center py-4">
                                                No matching drugs found
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Pipeline Info Box */}
                        <div className="rounded-md bg-blue-500/10 border border-blue-500/20 p-4 text-sm text-blue-600 dark:text-blue-400">
                            <div className="flex items-center gap-2 font-medium mb-1">
                                <Info className="h-4 w-4" />
                                <span>Pipeline Process</span>
                            </div>
                            <p className="opacity-90">
                                Fetch PDF via Agent → Parse with Unstructured.io → Store in MongoDB → Embed with all-MiniLM-L6-v2 → Store in FAISS
                            </p>
                        </div>

                        <Button
                            type="submit"
                            disabled={loading || !gene.trim() || !drug.trim()}
                            className="w-full md:w-auto bg-primary hover:bg-primary/80 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <span className=""></span> Processing...
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
