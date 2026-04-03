"use client";

import { useState, useEffect, useRef } from "react";
import { api, type IngestResponse, type StatusResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Info, CheckCircle2, XCircle, Loader2, ChevronRight } from "lucide-react";

// Pipeline steps matching the backend _STEPS list
const PIPELINE_STEPS = [
    "Checking existing index",
    "Locating guideline PDF",
    "Downloading PDF",
    "Parsing with Unstructured.io",
    "Fetching PubMed abstracts",
    "Storing in MongoDB",
    "Embedding in ChromaDB",
];

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

    // Track elapsed time during ingestion
    const [elapsed, setElapsed] = useState(0);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // Filter logic
    const filteredGenes = availableGenes.filter(g => {
        if (!g.toLowerCase().includes(gene.toLowerCase())) return false;
        if (drug && availableDrugs.includes(drug)) {
            return geneDrugPairs.some(p => p.Drug === drug && p.Gene === g);
        }
        return true;
    });

    const filteredDrugs = availableDrugs.filter(d => {
        if (!d.toLowerCase().includes(drug.toLowerCase())) return false;
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

    // Start / stop elapsed timer
    useEffect(() => {
        if (loading) {
            setElapsed(0);
            timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
        } else {
            if (timerRef.current) clearInterval(timerRef.current);
        }
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [loading]);

    // Poll ingestion job status by job_id
    useEffect(() => {
        if (!polling || !result?.job_id) return;
        const jobId = result.job_id;
        const interval = setInterval(async () => {
            try {
                const s = await api.ingestJob(jobId);
                setResult(s);
                if (s.status === "completed" || s.status === "failed") {
                    setPolling(false);
                    setLoading(false);
                    // Refresh stats card
                    api.status().then(setStatus).catch(() => { });
                }
            } catch {
                // ignore transient polling errors
            }
        }, 2000);
        return () => clearInterval(interval);
    }, [polling, result?.job_id]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!gene.trim() || !drug.trim()) return;
        setLoading(true);
        setError("");
        setResult(null);

        try {
            const res = await api.ingest({ gene, drug });
            setResult(res);
            if (res.status === "pending" || res.status === "running") {
                setPolling(true);
            } else {
                setLoading(false);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "An error occurred");
            setLoading(false);
        }
    };

    // Derived progress values
    const stepIndex = result?.step_index ?? 0;
    const totalSteps = result?.total_steps ?? PIPELINE_STEPS.length;
    const progressPct = result?.status === "completed"
        ? 100
        : Math.round((stepIndex / totalSteps) * 100);

    const statusColor = (s: string) => {
        switch (s) {
            case "completed": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
            case "failed":    return "bg-red-500/20 text-red-400 border-red-500/30";
            case "running":   return "bg-blue-500/20 text-blue-400 border-blue-500/30";
            case "pending":   return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
            default:          return "bg-muted/30 text-muted-foreground border-border/30";
        }
    };

    const isActive = loading || polling;
    const isDone   = result?.status === "completed";
    const isFailed = result?.status === "failed";

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 ease-out">
            {/* Header */}
            <section className="space-y-2 animate-in zoom-in-95 duration-1000">
                <h1 className="text-3xl font-bold tracking-tight text-black">
                    <span className="gradient-text">Guideline Ingestion</span>
                </h1>
                <p className="text-muted-foreground">
                    Fetch, parse, and index CPIC guideline PDFs into the vector database for RAG-powered Q&amp;A.
                </p>
            </section>

            {/* Stats Bar */}
            {status && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                        { label: "Status",     value: status.status === "ok" ? "Online" : "Offline" },
                        { label: "Guidelines", value: status.indexed_guidelines.toString() },
                        { label: "Chunks",     value: status.total_chunks.toString() },
                        { label: "Model",      value: status.embedding_model },
                    ].map((s, i) => (
                        <Card key={i} className="glass border-border/40">
                            <CardContent className="pt-4 pb-4">
                                <p className="text-xs text-muted-foreground">{s.label}</p>
                                <p className="font-semibold text-sm truncate">{s.value}</p>
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
                            <div className="flex flex-wrap gap-1 items-center opacity-90 text-xs">
                                {PIPELINE_STEPS.map((step, i) => (
                                    <span key={step} className="flex items-center gap-1">
                                        <span>{step}</span>
                                        {i < PIPELINE_STEPS.length - 1 && <ChevronRight className="h-3 w-3 opacity-50" />}
                                    </span>
                                ))}
                            </div>
                        </div>

                        <Button
                            id="ingest-submit-btn"
                            type="submit"
                            disabled={isActive || !gene.trim() || !drug.trim()}
                            className="w-full md:w-auto bg-primary hover:bg-primary/80 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
                        >
                            {isActive ? (
                                <span className="flex items-center gap-2">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Processing… ({elapsed}s)
                                </span>
                            ) : (
                                <span className="flex items-center gap-2">Start Ingestion</span>
                            )}
                        </Button>
                    </form>
                </CardContent>
            </Card>

            {/* ── Progress Card ── */}
            {result && (
                <Card className="glass border-border/40 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base flex items-center gap-2">
                                {isDone  && <CheckCircle2 className="h-5 w-5 text-emerald-400" />}
                                {isFailed && <XCircle    className="h-5 w-5 text-red-400" />}
                                {isActive  && <Loader2   className="h-5 w-5 text-blue-400 animate-spin" />}
                                Ingestion Status
                            </CardTitle>
                            <Badge variant="outline" className={statusColor(result.status)}>
                                {result.status.toUpperCase()}
                            </Badge>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-5">
                        {/* Progress Bar */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <span>{result.step ?? "Queued"}</span>
                                <span>{progressPct}%</span>
                            </div>
                            <div className="h-2 w-full rounded-full bg-muted/40 overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-700 ease-out ${
                                        isDone  ? "bg-emerald-500" :
                                        isFailed ? "bg-red-500" :
                                        "bg-primary"
                                    } ${isActive && !isDone ? "animate-pulse" : ""}`}
                                    style={{ width: `${progressPct}%` }}
                                />
                            </div>
                        </div>

                        {/* Step checklist */}
                        <div className="space-y-1.5">
                            {PIPELINE_STEPS.map((step, i) => {
                                const done    = isDone || i < stepIndex;
                                const active  = !isDone && i === stepIndex && isActive;
                                const pending = !done && !active;
                                return (
                                    <div
                                        key={step}
                                        className={`flex items-center gap-2 text-xs transition-colors ${
                                            done    ? "text-emerald-400" :
                                            active  ? "text-primary" :
                                            "text-muted-foreground/50"
                                        }`}
                                    >
                                        {done   && <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />}
                                        {active && <Loader2      className="h-3.5 w-3.5 shrink-0 animate-spin" />}
                                        {pending && <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-current/30 inline-block" />}
                                        {step}
                                    </div>
                                );
                            })}
                        </div>

                        {/* Message */}
                        <p className={`text-sm ${isFailed ? "text-red-400" : "text-muted-foreground"}`}>
                            {result.message}
                        </p>

                        {result.guideline_id && (
                            <p className="text-sm text-primary">
                                Guideline ID: <span className="font-mono">{result.guideline_id}</span>
                            </p>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Error */}
            {error && (
                <Card className="border-destructive/50 bg-destructive/10">
                    <CardContent className="pt-6">
                        <p className="text-destructive flex items-center gap-2">
                            <XCircle className="h-4 w-4" /> {error}
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
