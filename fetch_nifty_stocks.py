import yfinance as yf
import pandas as pd
import os

# Official Nifty 50 Tickers as of 2026
nifty50_tickers = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LTIM.NS",
    "LT.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS"
]

def fetch_nifty50_historical():
    print(f"Fetching 1 year of historical data for {len(nifty50_tickers)} Nifty 50 stocks...")
    
    # Download data for all tickers at once
    # 'group_by' ensures we get a MultiIndex column structure
    data = yf.download(nifty50_tickers, period="1y", group_by='ticker')
    
    # Save the data
    output_dir = "Gemini/personal finance accounting"
    output_file = os.path.join(output_dir, "nifty50_historical_data.csv")
    
    # Flattening MultiIndex columns for CSV export if needed
    # (Ticker, Metric) -> "Ticker_Metric"
    data.columns = ['_'.join(col).strip() for col in data.columns.values]
    
    data.to_csv(output_file)
    print(f"Data successfully saved to {output_file}")
    
    # Print some stats
    print(f"\nShape of downloaded data: {data.shape}")
    print(f"Date Range: {data.index[0].date()} to {data.index[-1].date()}")

if __name__ == "__main__":
    fetch_nifty50_historical()
