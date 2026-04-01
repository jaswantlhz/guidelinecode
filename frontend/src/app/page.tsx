"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type QueryResponse, type RagasMetrics } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

/* ── Helpers ─────────────────────────────────────────────── */
function metricColor(v: number): string {
    if (v >= 0.75) return "from-emerald-500 to-green-400";
    if (v >= 0.45) return "from-amber-500 to-yellow-400";
    return "from-rose-500 to-red-400";
}

function metricBadgeColor(v: number): string {
    if (v >= 0.75) return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    if (v >= 0.45) return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    return "bg-rose-500/15 text-rose-400 border-rose-500/30";
}

function MetricBar({
    label,
    value,
    tooltip,
}: {
    label: string;
    value: number;
    tooltip: string;
}) {
    const pct = Math.round(value * 100);
    return (
        <div className="space-y-1.5" title={tooltip}>
            <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground font-medium">{label}</span>
                <Badge
                    variant="outline"
                    className={`text-xs font-mono ${metricBadgeColor(value)}`}
                >
                    {pct}%
                </Badge>
            </div>
            <div className="h-2 w-full rounded-full bg-muted/50 overflow-hidden">
                <div
                    className={`h-full rounded-full bg-gradient-to-r ${metricColor(value)} transition-all duration-700 ease-out`}
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

function RagasPanel({ metrics }: { metrics: RagasMetrics }) {
    const overall = (
        (metrics.context_precision + metrics.faithfulness + metrics.answer_relevancy) /
        3
    );
    return (
        <Card className="glass border-border/40">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <span className="text-lg">📊</span> RAGAS Evaluation Metrics
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Badge
                            variant="outline"
                            className={`text-xs font-semibold ${metricBadgeColor(overall)}`}
                        >
                            Overall {Math.round(overall * 100)}%
                        </Badge>
                        <Badge variant="outline" className="text-xs bg-primary/10 text-primary border-primary/30">
                            {metrics.source_count} sources
                        </Badge>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <MetricBar
                        label="Context Precision"
                        value={metrics.context_precision}
                        tooltip="Average cross-encoder reranker score for retrieved source chunks. Higher = more relevant context fed to the LLM."
                    />
                    <MetricBar
                        label="Faithfulness"
                        value={metrics.faithfulness}
                        tooltip="Fraction of unique answer vocabulary that appears in the retrieved source passages. Higher = answer is grounded in context."
                    />
                    <MetricBar
                        label="Answer Relevancy"
                        value={metrics.answer_relevancy}
                        tooltip="Proxy for how well the answer length and density matches the context. Penalises both hollow short and padded long answers."
                    />
                </div>
                <Separator className="opacity-20" />
                <p className="text-xs text-muted-foreground leading-relaxed">
                    <span className="font-semibold text-foreground/60">Note:</span>{" "}
                    These are reference-free proxy metrics computed from retrieval and
                    generation pipeline signals — no judge LLM required. They follow the
                    RAGAS framework spirit:{" "}
                    <em>context precision</em> from the cross-encoder reranker,{" "}
                    <em>faithfulness</em> from token overlap, and{" "}
                    <em>answer relevancy</em> from answer-to-context density.
                </p>
            </CardContent>
        </Card>
    );
}

/* ── Page ────────────────────────────────────────────────── */
export default function QueryPage() {
    const [question, setQuestion] = useState("");
    const [gene, setGene] = useState("");
    const [drug, setDrug] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<QueryResponse | null>(null);
    const [error, setError] = useState("");

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!question.trim()) return;
        setLoading(true);
        setError("");
        setResult(null);

        try {
            const res = await api.query({
                question,
                gene: gene || undefined,
                drug: drug || undefined,
            });
            setResult(res);
        } catch (err) {
            setError(err instanceof Error ? err.message : "An error occurred");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            {/* Hero */}
            <section className="text-center space-y-4 py-8">
                <h1 className="text-4xl md:text-5xl font-bold">
                    <span className="gradient-text">Pharmacogenomics</span>{" "}
                    <span className="text-foreground">Intelligence</span>
                </h1>
                <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
                    Ask clinical questions about CPIC guidelines. Our RAG-powered AI retrieves
                    relevant guideline sections and generates evidence-based answers.
                </p>
            </section>

            {/* Query Form */}
            <Card className="glass border-border/40 animate-pulse-glow">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        Ask a Question
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="gene">Gene (optional)</Label>
                                <Input
                                    id="gene"
                                    placeholder="e.g. CYP2D6"
                                    value={gene}
                                    onChange={(e) => setGene(e.target.value)}
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="drug">Drug (optional)</Label>
                                <Input
                                    id="drug"
                                    placeholder="e.g. amitriptyline"
                                    value={drug}
                                    onChange={(e) => setDrug(e.target.value)}
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="question">Your Question</Label>
                            <Textarea
                                id="question"
                                placeholder="What is the recommended dose adjustment for CYP2D6 poor metabolizers taking amitriptyline?"
                                value={question}
                                onChange={(e) => setQuestion(e.target.value)}
                                rows={4}
                                className="bg-background/50 border-border/50 focus:border-primary transition-colors resize-none"
                            />
                        </div>
                        <Button
                            type="submit"
                            disabled={loading || !question.trim()}
                            className="w-full md:w-auto bg-primary hover:bg-primary/80 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <span className="animate-spin">⏳</span> Analyzing Guidelines...
                                </span>
                            ) : (
                                <span className="flex items-center gap-2">🔍 Query Guidelines</span>
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
                <div className="space-y-6 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">

                    {/* Answer Card — full-width, large */}
                    <Card className="glass border-border/40">
                        <CardHeader>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <CardTitle className="flex items-center gap-2 text-xl">
                                    🤖 AI Response
                                </CardTitle>
                                <div className="flex flex-wrap items-center gap-2">
                                    <Badge
                                        variant="outline"
                                        className="bg-primary/10 text-primary border-primary/30 text-sm"
                                    >
                                        {result.model_used}
                                    </Badge>
                                    {result.sources.length > 0 && (
                                        <Badge
                                            variant="outline"
                                            className="bg-accent/10 text-accent border-accent/30 text-sm"
                                        >
                                            {result.sources.length} sources retrieved
                                        </Badge>
                                    )}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {/* Large, roomy answer body */}
                            <div
                                className="markdown-body prose prose-invert max-w-none
                                    text-base leading-8
                                    [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-4 [&_h1]:mt-6
                                    [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-3 [&_h2]:mt-5 [&_h2]:text-primary
                                    [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4
                                    [&_p]:mb-4 [&_p]:text-foreground/90
                                    [&_ul]:space-y-2 [&_ul]:pl-5 [&_ul]:mb-4
                                    [&_ol]:space-y-2 [&_ol]:pl-5 [&_ol]:mb-4
                                    [&_li]:text-foreground/90
                                    [&_strong]:text-foreground [&_strong]:font-bold
                                    [&_em]:text-accent [&_em]:not-italic [&_em]:font-medium
                                    [&_table]:w-full [&_table]:border-collapse [&_table]:my-4
                                    [&_th]:border [&_th]:border-border/50 [&_th]:bg-muted/50 [&_th]:px-4 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold
                                    [&_td]:border [&_td]:border-border/30 [&_td]:px-4 [&_td]:py-2
                                    [&_tr:hover]:bg-muted/20
                                    [&_blockquote]:border-l-4 [&_blockquote]:border-primary/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-muted-foreground
                                    [&_code]:bg-muted/60 [&_code]:rounded [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-sm [&_code]:font-mono
                                    [&_pre]:bg-muted/60 [&_pre]:rounded-lg [&_pre]:p-4 [&_pre]:overflow-x-auto"
                            >
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {result.answer}
                                </ReactMarkdown>
                            </div>
                        </CardContent>
                    </Card>

                    {/* RAGAS Metrics Panel */}
                    {result.metrics && <RagasPanel metrics={result.metrics} />}

                    {/* Sources */}
                    {result.sources.length > 0 && (
                        <Card className="glass border-border/40">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-base">
                                    📚 Retrieved Sources ({result.sources.length})
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {result.sources.map((src, i) => (
                                    <div key={i}>
                                        <div className="rounded-xl bg-background/50 p-5 border border-border/30 hover:border-primary/30 transition-all duration-200 hover:shadow-md hover:shadow-primary/5">
                                            <div className="flex flex-wrap items-center gap-2 mb-3">
                                                <span className="text-xs font-mono text-muted-foreground/60 bg-muted/40 rounded px-2 py-0.5">
                                                    #{i + 1}
                                                </span>
                                                {src.section && (
                                                    <Badge variant="outline" className="text-xs">
                                                        {src.section}
                                                    </Badge>
                                                )}
                                                {src.page ? (
                                                    <Badge
                                                        variant="outline"
                                                        className="text-xs bg-accent/10 text-accent border-accent/30"
                                                    >
                                                        Page {src.page}
                                                    </Badge>
                                                ) : null}
                                                {src.pmid && (
                                                    <a
                                                        href={`https://pubmed.ncbi.nlm.nih.gov/${src.pmid}`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded-full px-2 py-0.5 hover:bg-blue-500/20 transition-colors"
                                                    >
                                                        PMID: {src.pmid}
                                                    </a>
                                                )}
                                                {src.score != null && (
                                                    <span
                                                        className={`ml-auto text-xs font-mono ${metricBadgeColor(src.score)} border rounded-full px-2 py-0.5`}
                                                    >
                                                        Score: {src.score.toFixed(3)}
                                                    </span>
                                                )}
                                            </div>
                                            {src.title && (
                                                <p className="text-sm font-semibold text-foreground/80 mb-2">
                                                    {src.title}
                                                </p>
                                            )}
                                            <p className="text-sm text-muted-foreground leading-relaxed">
                                                {src.text}
                                            </p>
                                        </div>
                                        {i < result.sources.length - 1 && (
                                            <Separator className="my-3 opacity-20" />
                                        )}
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}
        </div>
    );
}
