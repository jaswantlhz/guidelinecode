"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type QueryResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

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

    const confidenceColor = (c: number) => {
        if (c >= 0.8) return "bg-green-500/20 text-green-400 border-green-500/30";
        if (c >= 0.5) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
        return "bg-red-500/20 text-red-400 border-red-500/30";
    };

    return (
        <div className="space-y-8">
            {/* Hero */}
            <section className="text-center space-y-4 py-8">
                <h1 className="text-4xl md:text-5xl font-bold">
                    <span className="gradient-text">Pharmacogenomics</span>{" "}
                    <span className="text-foreground">Intelligence</span>
                </h1>
                <p className="text-black text-lg max-w-2xl mx-auto">
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
                                rows={3}
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
                                    <span className="animate-spin"></span> Analyzing Guidelines...
                                </span>
                            ) : (
                                <span className="flex items-center gap-2"> Query Guidelines</span>
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
                <div className="space-y-4 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
                    {/* Answer Card */}
                    <Card className="glass border-border/40">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <CardTitle className="flex items-center gap-2">
                                    AI Response
                                </CardTitle>
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline" className={confidenceColor(result.confidence)}>
                                        Confidence: {(result.confidence * 100).toFixed(0)}%
                                    </Badge>
                                    <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30">
                                        {result.model_used}
                                    </Badge>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="markdown-body">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {result.answer}
                                </ReactMarkdown>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Sources */}
                    {result.sources.length > 0 && (
                        <Card className="glass border-border/40">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-base">
                                    Retrieved Sources ({result.sources.length})
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {result.sources.map((src, i) => (
                                    <div key={i}>
                                        <div className="rounded-lg bg-background/50 p-4 border border-border/30 hover:border-primary/30 transition-colors">
                                            <div className="flex items-center gap-2 mb-2">
                                                {src.section && (
                                                    <Badge variant="outline" className="text-xs">
                                                        {src.section}
                                                    </Badge>
                                                )}
                                                {src.page && (
                                                    <Badge variant="outline" className="text-xs bg-accent/10 text-accent border-accent/30">
                                                        Page {src.page}
                                                    </Badge>
                                                )}
                                                {src.score !== null && (
                                                    <span className="text-xs text-muted-foreground ml-auto">
                                                        Score: {src.score.toFixed(3)}
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-sm text-muted-foreground leading-relaxed">
                                                {src.text}
                                            </p>
                                        </div>
                                        {i < result.sources.length - 1 && <Separator className="my-2 opacity-30" />}
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
