from pipelines.ingest_pipeline import cpic_ingestion_pipeline

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run CPIC Ingestion via ZenML Pipeline")
    parser.add_argument("--gene", type=str, required=True, help="Gene name (e.g. CYP2C19)")
    parser.add_argument("--drug", type=str, required=True, help="Drug name (e.g. Clopidogrel)")
    args = parser.parse_args()
    
    cpic_ingestion_pipeline(gene=args.gene, drug=args.drug)
