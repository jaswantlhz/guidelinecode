import pandas as pd
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

_TOOLS_DIR = Path(__file__).resolve().parent
path = _TOOLS_DIR / 'cpic_gene-drug_pairs.xlsx'
df1 = pd.read_excel(path)

def get_guideline_pdf(gene, drug, df=df1, folder="pdfs"):
    # Filter the dataframe
    row = df[
        (df["Gene"].str.lower() == gene.lower()) &
        (df["Drug"].str.lower() == drug.lower())
    ]
    
    if row.empty:
        raise ValueError(f"Gene-drug pair ({gene}/{drug}) not found in Excel")
    
    page_url = row.iloc[0]["Guideline"]
    return page_url