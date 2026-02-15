import pandas as pd
import os

file_path = r"f:\Main_files\drug_Code\guidelinecode\agent\tools\cpic_gene-drug_pairs.xlsx"

try:
    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    print("First 5 rows:")
    print(df.head())
except Exception as e:
    print(f"Error reading file: {e}")
