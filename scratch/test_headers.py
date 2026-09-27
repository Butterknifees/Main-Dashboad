import os
import glob
import pandas as pd

BASE_PATH = './data'

print("--- Checking Excel Files ---")
excel_files = glob.glob(os.path.join(BASE_PATH, '*.xlsx')) + glob.glob(os.path.join(BASE_PATH, 'appending', '*.xlsx'))
for path in excel_files:
    print(f"\nFile: {path}")
    try:
        df_all = pd.read_excel(path, header=None)
        print(f"Shape: {df_all.shape}")
        
        # Test headers scanning
        found_idx = -1
        for i, row in df_all.iterrows():
            row_strs = [str(v).strip().lower() for v in row.values if not pd.isna(v)]
            # check if any cell matches header keywords
            is_header = False
            # criteria for holdings or transactions
            if any(k in row_strs for k in ['isin', 'scheme code', 'scheme name', 'scheme', 'stock name', 'symbol', 'instrument', 'security']):
                is_header = True
            
            if is_header:
                found_idx = i
                print(f"Detected header row index: {i}")
                print(f"Row values: {row.tolist()}")
                break
        
        if found_idx == -1:
            print("Failed to detect any header row!")
        else:
            # Let's inspect the loaded dataframe with the detected header
            df = pd.read_excel(path, header=found_idx)
            print("Columns found:")
            print(df.columns.tolist())
            print("First 3 rows of data:")
            print(df.head(3))
    except Exception as e:
        print(f"Error reading {path}: {e}")
