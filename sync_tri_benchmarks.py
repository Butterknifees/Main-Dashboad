import pandas as pd
import json
import os
from nsepython import index_total_returns
from datetime import datetime, timedelta
import time

def sync_tri_benchmarks():
    base_path = "Gemini/personal finance accounting/"
    mapping_file = os.path.join(base_path, "benchmark_mapping.json")
    output_file = os.path.join(base_path, "benchmark_tri_history.csv")
    
    if not os.path.exists(mapping_file):
        print(f"Error: {mapping_file} not found.")
        return

    with open(mapping_file, 'r') as f:
        mapping = json.load(f)

    # Identify unique NSE benchmarks (filtering out non-NSE ones like LBMA)
    nse_benchmarks = sorted(list(set([v['benchmark'] for k, v in mapping.items() if v['benchmark'].startswith('NIFTY')])))
    
    start_date = None
    end_date = datetime.now().strftime("%d-%b-%Y")
    existing_df = None
    
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_csv(output_file, index_col=0, parse_dates=True)
            if not existing_df.empty:
                last_date = existing_df.index.max()
                # Sync starting from 5 days before the last date
                start_date = (last_date - timedelta(days=5)).strftime("%d-%b-%Y")
                print(f"Existing TRI history found. Last date: {last_date.date()}. Syncing incrementally from: {start_date}")
        except Exception as e:
            print(f"Warning: Error reading existing TRI CSV: {e}. Falling back to full download.")

    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%d-%b-%Y")
        print(f"Syncing full 1 year of TRI data from {start_date} to {end_date}...")
    
    all_benchmark_data = {}

    for benchmark in nse_benchmarks:
        print(f"Fetching TRI for: {benchmark}...")
        try:
            # Fetch data
            data = index_total_returns(benchmark, start_date, end_date)
            
            if data is not None and len(data) > 0:
                df = pd.DataFrame(data)
                # Standardize columns
                df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=True)
                df['TotalReturnsIndex'] = pd.to_numeric(df['TotalReturnsIndex'], errors='coerce')
                df = df.dropna(subset=['TotalReturnsIndex'])
                df = df.sort_values('Date')
                # We only need Date and TotalReturnsIndex
                df = df[['Date', 'TotalReturnsIndex']].rename(columns={'TotalReturnsIndex': benchmark})
                df = df.set_index('Date')
                all_benchmark_data[benchmark] = df
                print(f"  Successfully fetched {len(df)} days.")
            else:
                print(f"  Warning: No data returned for {benchmark}")
            
            # Rate limiting
            time.sleep(2)
        except Exception as e:
            print(f"  Error fetching {benchmark}: {str(e)}")

    if not all_benchmark_data:
        print("No new TRI data was successfully fetched.")
        # If we fetched nothing new, just keep existing or stop
        return

    # Merge all new benchmarks
    new_df = pd.concat(all_benchmark_data.values(), axis=1)
    
    if existing_df is not None:
        # Merge existing and new data, replacing overlapping dates with the fresh download
        combined_df = pd.concat([existing_df[~existing_df.index.isin(new_df.index)], new_df])
        combined_df = combined_df.sort_index()
    else:
        combined_df = new_df
    
    # Forward fill to handle holiday mismatches between different indices
    combined_df = combined_df.ffill().bfill()
    
    combined_df.to_csv(output_file)
    print(f"\nSuccessfully saved TRI history to {output_file}")
    print(f"Indices saved: {', '.join(all_benchmark_data.keys())}")

if __name__ == "__main__":
    sync_tri_benchmarks()

