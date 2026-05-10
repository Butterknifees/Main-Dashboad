import yfinance as yf
import pandas as pd
import os

# Tickers identified from your order history
etf_tickers = [
    "HDFCGOLD.NS", "TATSILV.NS", "CHEMICAL.NS", "MODEFENCE.NS", 
    "SILVERIETF.NS", "PHARMABEES.NS", "PSUBNKIETF.NS", 
    "EBBETF0433.NS", "NIFTYBEES.NS", "MIDCAPIETF.NS"
]

def fetch_etf_historical():
    print(f"Fetching 1 year of historical market prices for {len(etf_tickers)} ETFs from NSE...")
    
    # Download data
    data = yf.download(etf_tickers, period="1y", group_by='ticker')
    
    # Save the data
    output_dir = "Gemini/personal finance accounting"
    output_file = os.path.join(output_dir, "etf_historical_data.csv")
    
    # Flattening MultiIndex columns
    data.columns = ['_'.join(col).strip() for col in data.columns.values]
    
    data.to_csv(output_file)
    print(f"Data successfully saved to {output_file}")
    
    # Summary
    print(f"\nDate Range: {data.index[0].date()} to {data.index[-1].date()}")
    
    # Check for any failed tickers (where most columns are NaN)
    for ticker in etf_tickers:
        if data[f"{ticker}_Close"].isna().all():
            print(f"WARNING: No data found for {ticker}")

if __name__ == "__main__":
    fetch_etf_historical()
