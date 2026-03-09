import argparse
import logging
from pipelines.ingest_pipeline import cpic_ingestion_pipeline

# Configure basic logging for CLI
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Run CPIC Ingestion via ZenML Pipeline")
    parser.add_argument("--gene", type=str, required=True, help="Gene name (e.g. CYP2C19)")
    parser.add_argument("--drug", type=str, required=True, help="Drug name (e.g. Clopidogrel)")
    
    args = parser.parse_args()
    
    logger.info(f"🚀 Starting ZenML pipeline for Gene: {args.gene}, Drug: {args.drug}")
    
    # Run the compiled pipeline
    cpic_ingestion_pipeline(gene=args.gene, drug=args.drug)
    
    logger.info("✅ Pipeline execution triggered.")
    logger.info("View runs with 'zenml pipeline runs list' or in the MLflow UI.")

if __name__ == "__main__":
    main()
