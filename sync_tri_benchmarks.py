import pandas as pd
import json
import os
from nsepython import index_total_returns
from datetime import datetime, timedelta
import time

import pandas as pd
import json
import os
import yfinance as yf
from nsepython import index_total_returns
from datetime import datetime, timedelta
import time

def sync_tri_benchmarks():
    base_path = "Gemini/personal finance accounting/" if os.path.exists("Gemini/personal finance accounting") else ""
    mapping_file = os.path.join(base_path, "benchmark_mapping.json")
    output_file = os.path.join(base_path, "benchmark_tri_history.csv")
    nifty50_file = os.path.join(base_path, "nifty50_index.csv")
    
    if not os.path.exists(mapping_file):
        print(f"Error: {mapping_file} not found.")
        return

    with open(mapping_file, 'r') as f:
        mapping = json.load(f)

    # Identify unique NSE benchmarks
    nse_benchmarks = sorted(list(set([v['benchmark'] for k, v in mapping.items() if v['benchmark'].startswith('NIFTY')])))
    
    existing_df = None
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_csv(output_file, index_col=0, parse_dates=True)
            if not existing_df.empty:
                print(f"Existing TRI history found. Last date: {existing_df.index.max().date()}.")
        except Exception as e:
            print(f"Warning: Error reading existing TRI CSV: {e}.")

    # Yahoo Finance ticker mapping for indices
    yf_benchmark_map = {
        'NIFTY 50': '^NSEI',
        'NIFTY BANK': '^NSEBANK',
        'NIFTY IT': '^CNXIT',
        'NIFTY AUTO': '^CNXAUTO',
        'NIFTY FMCG': '^CNXFMCG',
        'NIFTY PHARMA': '^CNXPHARMA',
        'NIFTY REALTY': '^CNXREALTY',
        'NIFTY ENERGY': '^CNXENERGY',
        'NIFTY INFRASTRUCTURE': '^CNXINFRA',
        'NIFTY NEXT 50': 'SETFNN50.NS',
        'NIFTY MIDCAP 150': 'MIDCAPIETF.NS',
        'NIFTY PSU BANK': 'PSUBNKIETF.NS',
        'NIFTY FINANCIAL SERVICES': '^CNXFIN',
        'NIFTY METAL': '^CNXMETAL',
        'NIFTY CONSUMPTION': '^CNXCONSUMP',
        'NIFTY CPSE': 'CPSEETF.NS',
        'NIFTY INDIA DEFENCE': 'MODEFENCE.NS',
        'NIFTY LARGEMIDCAP 250': 'CHEMICAL.NS',
        'NIFTY PRIVATE BANK': 'BANKBEES.NS',
        'NIFTY SMALLCAP 250': 'MIDCAPIETF.NS'
    }

    start_date = "2025-04-01"
    if existing_df is not None and not existing_df.empty:
        start_date = (existing_df.index.max() - timedelta(days=5)).strftime("%Y-%m-%d")

    print(f"Syncing NIFTY 50 and benchmark histories from Yahoo Finance since {start_date}...")
    
    # 1. Update Nifty 50 Index OHLCV file
    try:
        nifty50_df = yf.download('^NSEI', start='2025-04-01', progress=False)
        if not nifty50_df.empty:
            if isinstance(nifty50_df.columns, pd.MultiIndex):
                nifty50_df.columns = nifty50_df.columns.get_level_values(0)
            nifty50_df.to_csv(nifty50_file)
            print(f"  ✓ Updated {nifty50_file} with latest Nifty 50 closing: {nifty50_df['Close'].iloc[-1]:.2f} on {nifty50_df.index[-1].date()}")
    except Exception as e:
        print(f"Warning: Could not update {nifty50_file}: {e}")

    # 2. Download YF data for all mapped benchmark indices
    tickers_to_fetch = list(set([v for v in yf_benchmark_map.values() if v]))
    try:
        yf_data = yf.download(tickers_to_fetch, start=start_date, group_by='ticker', progress=False)
    except Exception as e:
        print(f"Error fetching benchmark data from Yahoo Finance: {e}")
        yf_data = pd.DataFrame()

    if existing_df is None:
        combined_df = pd.DataFrame()
    else:
        combined_df = existing_df.copy()

    if not yf_data.empty:
        # Extract closing prices
        new_dates = yf_data.index
        for b_name, ticker in yf_benchmark_map.items():
            col_series = None
            if isinstance(yf_data.columns, pd.MultiIndex):
                try:
                    col_series = yf_data[ticker]['Close']
                except KeyError:
                    pass
            elif f"{ticker}_Close" in yf_data.columns:
                col_series = yf_data[f"{ticker}_Close"]
            elif 'Close' in yf_data.columns and len(tickers_to_fetch) == 1:
                col_series = yf_data['Close']

            if col_series is not None and not col_series.dropna().empty:
                col_series = col_series.dropna()
                
                # If we have existing TRI history for this benchmark, scale the continuation
                if b_name in combined_df.columns and not combined_df[b_name].dropna().empty:
                    last_valid_idx = combined_df[b_name].dropna().index.max()
                    base_val = combined_df.loc[last_valid_idx, b_name]
                    
                    # Find matching dates in downloaded series
                    sub_series = col_series[col_series.index >= last_valid_idx]
                    if len(sub_series) > 1:
                        # Compute relative growth multiplier
                        growth = sub_series / sub_series.iloc[0]
                        scaled_series = growth * base_val
                        
                        # Merge into combined_df
                        for d, v in scaled_series.items():
                            combined_df.loc[d, b_name] = v
                else:
                    # Directly assign series
                    for d, v in col_series.items():
                        combined_df.loc[d, b_name] = v

    # Forward-fill & backward-fill any gaps
    combined_df = combined_df.sort_index().ffill().bfill()
    combined_df.to_csv(output_file)
    print(f"✓ Successfully updated TRI & Benchmark history in {output_file}")
    print(f"  Date range: {combined_df.index.min().date()} to {combined_df.index.max().date()}")
    if 'NIFTY 50' in combined_df.columns:
        print(f"  Latest NIFTY 50 Benchmark Level: {combined_df['NIFTY 50'].iloc[-1]:.2f}")

if __name__ == "__main__":
    sync_tri_benchmarks()

