"use client";

import { useState, useEffect } from "react";
import { api, type PhenotypeResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function PhenotypePage() {
    const [gene, setGene] = useState("");
    const [diplotype, setDiplotype] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<PhenotypeResponse | null>(null);
    const [error, setError] = useState("");
    const [genes, setGenes] = useState<string[]>([]);
    const [diplotypes, setDiplotypes] = useState<string[]>([]);

    // Fetch available genes on mount
    useEffect(() => {
        api.genes().then((d) => setGenes(d.genes)).catch(() => { });
    }, []);

    // Fetch diplotypes when gene changes
    useEffect(() => {
        if (!gene.trim()) {
            setDiplotypes([]);
            return;
        }
        api.diplotypes(gene).then((d) => setDiplotypes(d.diplotypes)).catch(() => { });
    }, [gene]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!gene.trim() || !diplotype.trim()) return;
        setLoading(true);
        setError("");
        setResult(null);

        try {
            const res = await api.phenotype({ gene, diplotype });
            setResult(res);
        } catch (err) {
            setError(err instanceof Error ? err.message : "An error occurred");
        } finally {
            setLoading(false);
        }
    };

    const phenotypeColor = (p: string) => {
        if (p.includes("Ultrarapid")) return "bg-purple-500/20 text-purple-400 border-purple-500/30";
        if (p.includes("Normal") || p.includes("Extensive")) return "bg-green-500/20 text-green-400 border-green-500/30";
        if (p.includes("Intermediate") || p.includes("Rapid") || p.includes("Decreased")) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
        if (p.includes("Poor") || p.includes("High")) return "bg-red-500/20 text-red-400 border-red-500/30";
        return "bg-muted text-muted-foreground border-border";
    };

    const activityScoreBar = (score: number | null) => {
        if (score === null) return null;
        const pct = Math.min((score / 4) * 100, 100);
        return (
            <div className="space-y-1">
                <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Activity Score</span>
                    <span className="font-mono text-primary">{score.toFixed(1)}</span>
                </div>
                <div className="h-2 rounded-full bg-muted/50 overflow-hidden">
                    <div
                        className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all duration-700 ease-out"
                        style={{ width: `${pct}%` }}
                    />
                </div>
            </div>
        );
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <section className="space-y-2">
                <h1 className="text-3xl font-bold">
                    <span className="gradient-text">Phenotype Resolution</span>
                </h1>
                <p className="black">
                    Resolve genotypes to clinical phenotypes and dosing recommendations using CPIC activity scores.
                </p>
            </section>

            {/* Form */}
            <Card className="glass border-border/40">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        Genotype → Phenotype Lookup
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="pheno-gene">Gene</Label>
                                <Input
                                    id="pheno-gene"
                                    placeholder="e.g. CYP2D6"
                                    value={gene}
                                    onChange={(e) => setGene(e.target.value)}
                                    list="gene-list"
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                    required
                                />
                                <datalist id="gene-list">
                                    {genes.map((g) => (
                                        <option key={g} value={g} />
                                    ))}
                                </datalist>
                                {genes.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1">
                                        {genes.map((g) => (
                                            <button
                                                key={g}
                                                type="button"
                                                onClick={() => setGene(g)}
                                                className={`text-xs px-2 py-0.5 rounded-md border transition-colors cursor-pointer ${gene === g
                                                    ? "bg-primary/20 text-primary border-primary/30"
                                                    : "bg-muted/30 text-muted-foreground border-border/30 hover:bg-primary/10"
                                                    }`}
                                            >
                                                {g}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="pheno-diplotype">Diplotype</Label>
                                <Input
                                    id="pheno-diplotype"
                                    placeholder="e.g. *1/*2"
                                    value={diplotype}
                                    onChange={(e) => setDiplotype(e.target.value)}
                                    list="diplotype-list"
                                    className="bg-background/50 border-border/50 focus:border-primary transition-colors"
                                    required
                                />
                                <datalist id="diplotype-list">
                                    {diplotypes.map((d) => (
                                        <option key={d} value={d} />
                                    ))}
                                </datalist>
                                {diplotypes.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1">
                                        {diplotypes.map((d) => (
                                            <button
                                                key={d}
                                                type="button"
                                                onClick={() => setDiplotype(d)}
                                                className={`text-xs px-2 py-0.5 rounded-md border transition-colors cursor-pointer ${diplotype === d
                                                    ? "bg-primary/20 text-primary border-primary/30"
                                                    : "bg-muted/30 text-muted-foreground border-border/30 hover:bg-primary/10"
                                                    }`}
                                            >
                                                {d}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        <Button
                            type="submit"
                            disabled={loading || !gene.trim() || !diplotype.trim()}
                            className="w-full md:w-auto bg-primary hover:bg-primary/80 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <span className="animate-spin">⚛</span> Resolving...
                                </span>
                            ) : (
                                <span className="flex items-center gap-2">Resolve Phenotype</span>
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
                            <CardTitle className="flex items-center gap-2">

                                Result
                            </CardTitle>
                            <Badge variant="outline" className={phenotypeColor(result.phenotype)}>
                                {result.phenotype}
                            </Badge>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="rounded-lg bg-background/50 p-3 border border-border/30">
                                <p className="text-xs text-muted-foreground">Gene</p>
                                <p className="font-semibold text-lg font-mono">{result.gene}</p>
                            </div>
                            <div className="rounded-lg bg-background/50 p-3 border border-border/30">
                                <p className="text-xs text-muted-foreground">Diplotype</p>
                                <p className="font-semibold text-lg font-mono">{result.diplotype}</p>
                            </div>
                        </div>

                        {activityScoreBar(result.activity_score)}

                        <div className="rounded-lg bg-primary/5 border border-primary/20 p-4">
                            <p className="text-xs text-muted-foreground mb-1 font-medium">Clinical Recommendation</p>
                            <p className="text-foreground/90">{result.recommendation}</p>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
