import yfinance as yf
import pandas as pd
import os
import time

def fetch_nifty_universe_historical():
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
    
    print(f"Downloading 1 year of historical data in batches of {batch_size}...")
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1}...")
        
        try:
            # We only need the 'Close' prices to keep file size manageable
            data = yf.download(batch, period="1y", interval="1d", group_by='ticker', progress=False)
            
            # Flatten columns: (Ticker, Metric) -> Ticker_Metric
            data.columns = ['_'.join(col).strip() for col in data.columns.values]
            
            # Filter for only _Close columns to save space
            close_cols = [col for col in data.columns if col.endswith('_Close')]
            all_data.append(data[close_cols])
            
            # Small sleep to be polite to the API
            time.sleep(1)
        except Exception as e:
            print(f"Error in batch {i//batch_size + 1}: {e}")

    if not all_data:
        print("No data downloaded.")
        return

    # Merge all batches
    final_df = pd.concat(all_data, axis=1)
    
    output_dir = "Gemini/personal finance accounting"
    output_file = os.path.join(output_dir, "nifty_universe_historical_data.csv")
    
    final_df.to_csv(output_file)
    print(f"\nSuccessfully saved universe data to {output_file}")
    print(f"Total Columns: {len(final_df.columns)}")
    print(f"Date Range: {final_df.index[0].date()} to {final_df.index[-1].date()}")

if __name__ == "__main__":
    fetch_nifty_universe_historical()
