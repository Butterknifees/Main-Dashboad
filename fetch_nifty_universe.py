import yfinance as yf
import pandas as pd
import os
import time
from datetime import datetime, timedelta

def fetch_nifty_universe_historical():
    output_dir = "Gemini/personal finance accounting"
    output_file = os.path.join(output_dir, "nifty_universe_historical_data.csv")
    
    start_date = None
    existing_df = None
    
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_csv(output_file, index_col=0, parse_dates=True)
            if not existing_df.empty:
                last_date = existing_df.index.max()
                # Start 5 days before the last date to ensure overlaps are captured
                start_date = (last_date - timedelta(days=5)).strftime("%Y-%m-%d")
                print(f"Existing data found. Last date: {last_date.date()}. Syncing incrementally from: {start_date}")
        except Exception as e:
            print(f"Warning: Error reading existing CSV: {e}. Falling back to full download.")

    print("Fetching Nifty 500 stock list from NSE...")
    try:
        nifty500_url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        df_list = pd.read_csv(nifty500_url)
        tickers = [symbol + ".NS" for symbol in df_list['Symbol'].tolist()]
        print(f"Found {len(tickers)} stocks in the Nifty 500 universe.")
    except Exception as e:
        print(f"Error fetching ticker list: {e}")
        return

    # Fetching in batches to avoid timeouts/errors
    batch_size = 50
    all_data = []
    
    if start_date:
        print(f"Downloading incremental data since {start_date} in batches of {batch_size}...")
    else:
        print(f"Downloading 1 year of historical data in batches of {batch_size}...")
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1}...")
        
        try:
            # We only need the 'Close' prices to keep file size manageable
            if start_date:
                data = yf.download(batch, start=start_date, interval="1d", group_by='ticker', progress=False)
            else:
                data = yf.download(batch, period="1y", interval="1d", group_by='ticker', progress=False)
            
            if data.empty:
                continue
                
            # Flatten columns: (Ticker, Metric) -> Ticker_Metric
            data.columns = ['_'.join(col).strip() for col in data.columns.values]
            
            # Filter for only _Close columns to save space
            close_cols = [col for col in data.columns if col.endswith('_Close')]
            all_data.append(data[close_cols])
            
            # Small sleep to be polite to the API
            time.sleep(0.5)
        except Exception as e:
            print(f"Error in batch {i//batch_size + 1}: {e}")

    if not all_data:
        print("No new data downloaded.")
        return

    # Merge all batches
    new_df = pd.concat(all_data, axis=1)
    
    if existing_df is not None:
        # Merge existing and new data, replacing overlapping dates with the fresh download
        combined_df = pd.concat([existing_df[~existing_df.index.isin(new_df.index)], new_df])
        combined_df = combined_df.sort_index()
    else:
        combined_df = new_df
    
    combined_df.to_csv(output_file)
    print(f"\nSuccessfully saved universe data to {output_file}")
    print(f"Total Columns: {len(combined_df.columns)}")
    print(f"Date Range: {combined_df.index[0].date()} to {combined_df.index[-1].date()}")

if __name__ == "__main__":
    fetch_nifty_universe_historical()

