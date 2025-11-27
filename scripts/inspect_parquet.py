import pandas as pd

try:
    df = pd.read_parquet("ml_source/market_data_normalized.parquet")
    print("Columns:", df.columns.tolist())
    print("Shape:", df.shape)
except Exception as e:
    print(e)
