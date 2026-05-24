import pandas as pd
import json
import os
import numpy as np

import sqlite3

def prepare_simulator_data():
    base_path = "Gemini/personal finance accounting/"
    universe_file = base_path + "nifty_universe_historical_data.csv"
    etf_file = base_path + "etf_historical_data.csv"
    grouped_funds_file = base_path + "grouped_funds.json"
    db_file = base_path + "nav_data.db"
    output_file = base_path + "simulator_data.json"

    print("Loading Nifty Universe data...")
    df_univ = pd.read_csv(universe_file)
    
    print("Loading ETF (Benchmark) data...")
    df_etf = pd.read_csv(etf_file)

    print("Loading Filtered Mutual Funds...")
    if os.path.exists(grouped_funds_file):
        with open(grouped_funds_file, 'r') as f:
            grouped_funds = json.load(f)
    else:
        print("Error: grouped_funds.json not found. Run group_funds.py first.")
        return

    all_scheme_codes = []
    for cat in grouped_funds:
        for fund in grouped_funds[cat]:
            all_scheme_codes.append(fund['code'])

    # 1. Standardize dates from ETF file as the primary timeline
    if 'Date' not in df_etf.columns and len(df_etf.columns) > 0:
        df_etf = df_etf.rename(columns={df_etf.columns[0]: 'Date'})
    if 'Date' not in df_univ.columns and len(df_univ.columns) > 0:
        df_univ = df_univ.rename(columns={df_univ.columns[0]: 'Date'})
        
    df_etf['Date'] = pd.to_datetime(df_etf['Date'])
    df_univ['Date'] = pd.to_datetime(df_univ['Date'])
    
    # Get NiftyBees for benchmark
    benchmark_col = [c for c in df_etf.columns if 'NIFTYBEES' in c and 'Close' in c][0]
    # Merge on Date to align everything
    # Keep all ETF columns, not just the benchmark
    merged = pd.merge(df_univ, df_etf, on='Date', how='inner')
    merged = merged.sort_values('Date')
    
    # 2. DATA CLEANING: Replace zeros with NaN and forward fill
    # This is critical because a 0 price causes -100% return, and then Infinity next day
    merged = merged.replace(0, np.nan)
    
    # Filter out rows where benchmark is STILL NaN (if it was NaN everywhere)
    # But usually we just want to ensure it has a valid starting point
    merged = merged.ffill().bfill()

    # Final check: remove any remaining rows where benchmark is missing
    merged = merged[merged[benchmark_col].notna()]
    
    dates_str = merged['Date'].dt.strftime('%Y-%m-%d').tolist()

    # 2. Fetch Mutual Fund NAVs from DB for aligned dates
    print(f"Fetching NAVs for {len(all_scheme_codes)} schemes...")
    conn = sqlite3.connect(db_file)
    mf_data = {}

    # Optimization: Chunk the scheme codes for the SQL query
    chunk_size = 500
    for i in range(0, len(all_scheme_codes), chunk_size):
        chunk = all_scheme_codes[i:i+chunk_size]
        placeholders = ','.join(['?'] * len(chunk))
        query = f"SELECT scheme_code, date, nav FROM nav_history WHERE scheme_code IN ({placeholders})"
        df_mf = pd.read_sql_query(query, conn, params=chunk)

        for code, group in df_mf.groupby('scheme_code'):
            # Reindex to match the timeline
            group['date'] = pd.to_datetime(group['date'])
            group = group.set_index('date').reindex(merged['Date']).ffill().bfill()
            mf_data[code] = group['nav'].tolist()
    conn.close()

    # 3. Construct clean JSON structure
    benchmark = merged[benchmark_col].tolist()

    assets = {}
    # Add Stocks and ETFs
    for col in merged.columns:
        if col.endswith('_Close'):
            ticker = col.replace('_Close', '')
            assets[ticker] = merged[col].tolist()

    # Add Mutual Funds

    for code, navs in mf_data.items():
        assets[code] = navs
            
    # Final sanitization
    def safe_json_list(arr):
        return [round(float(v), 4) if np.isfinite(v) else 0 for v in arr]

    result = {
        "dates": dates_str,
        "benchmark": safe_json_list(benchmark),
        "assets": {id: safe_json_list(prices) for id, prices in assets.items()},
        "categories": grouped_funds # Pass through the grouping for UI
    }
    
    print(f"Saving optimized data to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(result, f)
        
    print(f"Total Assets (Stocks + MFs): {len(assets)}")
    print(f"Date Points: {len(dates_str)}")

if __name__ == "__main__":
    prepare_simulator_data()
