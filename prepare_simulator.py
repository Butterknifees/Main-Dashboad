import pandas as pd
import json
import os
import numpy as np

def prepare_simulator_data():
    base_path = "Gemini/personal finance accounting/"
    universe_file = base_path + "nifty_universe_historical_data.csv"
    etf_file = base_path + "etf_historical_data.csv"
    output_file = base_path + "simulator_data.json"

    print("Loading Nifty Universe data...")
    df_univ = pd.read_csv(universe_file)
    
    print("Loading ETF (Benchmark) data...")
    df_etf = pd.read_csv(etf_file)
    
    # 1. Clean up columns: Keep only _Close
    # For universe, columns are Ticker_Close
    # For ETF, look for NIFTYBEES.NS_Close
    
    # Get NiftyBees
    benchmark_col = [c for c in df_etf.columns if 'NIFTYBEES' in c and 'Close' in c]
    if not benchmark_col:
        print("Error: Could not find NIFTYBEES in ETF file.")
        return
    benchmark_col = benchmark_col[0]
    
    # Standardize dates
    df_univ['Date'] = pd.to_datetime(df_univ['Date'])
    df_etf['Date'] = pd.to_datetime(df_etf['Date'])
    
    # Merge on Date to align everything
    merged = pd.merge(df_univ, df_etf[['Date', benchmark_col]], on='Date', how='inner')
    merged = merged.sort_values('Date')
    
    # 2. Forward fill any gaps and fill remaining NaNs with 0 for valid JSON
    merged = merged.ffill().bfill().fillna(0)
    
    # 3. Construct clean JSON structure
    dates = merged['Date'].dt.strftime('%Y-%m-%d').tolist()
    benchmark = merged[benchmark_col].tolist()
    
    # Extract asset names (remove _Close suffix)
    assets = {}
    for col in merged.columns:
        if col.endswith('_Close') and col != benchmark_col:
            ticker = col.replace('_Close', '')
            assets[ticker] = merged[col].tolist()
            
    # Final sanitization of all numbers for JSON safety
    def safe_json_list(arr):
        return [round(float(v), 2) if np.isfinite(v) else 0 for v in arr]

    result = {
        "dates": dates,
        "benchmark": safe_json_list(benchmark),
        "assets": {ticker: safe_json_list(prices) for ticker, prices in assets.items()}
    }
    
    print(f"Saving optimized data to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(result, f)
        
    print(f"Total Assets Processed: {len(assets)}")
    print(f"Date Points: {len(dates)}")

if __name__ == "__main__":
    prepare_simulator_data()
