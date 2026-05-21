import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

# Tickers identified from your order history
etf_tickers = [
    "HDFCGOLD.NS", "TATSILV.NS", "CHEMICAL.NS", "MODEFENCE.NS", 
    "SILVERIETF.NS", "PHARMABEES.NS", "PSUBNKIETF.NS", 
    "EBBETF0433.NS", "NIFTYBEES.NS", "MIDCAPIETF.NS",
    "GOLDIETF.NS", "FMCGIETF.NS", "SETFNN50.NS", "BANKBEES.NS",
    "SMLCSE.NS"
]

def fetch_etf_historical():
    output_dir = "Gemini/personal finance accounting"
    output_file = os.path.join(output_dir, "etf_historical_data.csv")
    
    start_date = None
    existing_df = None
    
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_csv(output_file, index_col=0, parse_dates=True)
            if not existing_df.empty:
                last_date = existing_df.index.max()
                # Fetch starting from 5 days before the last date to ensure overlaps are filled
                start_date = (last_date - timedelta(days=5)).strftime("%Y-%m-%d")
                print(f"Existing data found. Last date: {last_date.date()}. Syncing incrementally from: {start_date}")
        except Exception as e:
            print(f"Warning: Error reading existing CSV: {e}. Falling back to full download.")

    if start_date:
        print(f"Fetching market prices for {len(etf_tickers)} ETFs starting from {start_date}...")
        data = yf.download(etf_tickers, start=start_date, group_by='ticker')
    else:
        print(f"Fetching 1 year of historical market prices for {len(etf_tickers)} ETFs from NSE...")
        data = yf.download(etf_tickers, period="1y", group_by='ticker')
    
    if data.empty:
        print("No new data fetched.")
        return
        
    # Flattening MultiIndex columns
    data.columns = ['_'.join(col).strip() for col in data.columns.values]
    
    if existing_df is not None:
        # Merge: overwrite older overlapping rows with the newly downloaded ones
        combined_df = pd.concat([existing_df[~existing_df.index.isin(data.index)], data])
        combined_df = combined_df.sort_index()
    else:
        combined_df = data
    
    combined_df.to_csv(output_file)
    print(f"Data successfully saved to {output_file}")
    print(f"Date Range: {combined_df.index[0].date()} to {combined_df.index[-1].date()}")
    
    # Check for any failed tickers (where most columns are NaN)
    for ticker in etf_tickers:
        col_name = f"{ticker}_Close"
        if col_name in combined_df.columns:
            if combined_df[col_name].isna().all():
                print(f"WARNING: No data found for {ticker}")
        else:
            print(f"WARNING: Column {col_name} not found in output")

if __name__ == "__main__":
    fetch_etf_historical()
