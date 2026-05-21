from nsepython import index_total_returns
from datetime import datetime, timedelta
import pandas as pd
import json

def test_tri_fetch():
    print("Testing Nifty 50 TRI fetch using nsepython...")
    
    # Define range: Last 30 days for a quick test
    end_date = datetime.now().strftime("%d-%b-%Y")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
    
    print(f"Range: {start_date} to {end_date}")
    
    try:
        # Fetch TRI data
        # Note: The library function might return a list of dicts or a dataframe depending on version
        data = index_total_returns("NIFTY 50", start_date, end_date)
        
        if data is None or (isinstance(data, list) and len(data) == 0):
            print("Error: No data returned from nsepython.")
            return

        print("\nSuccess! Sample Data:")
        if isinstance(data, pd.DataFrame):
            print(data.head())
        else:
            print(json.dumps(data[:3], indent=2))
            
    except Exception as e:
        print(f"\nFailed to fetch data: {str(e)}")
        print("\nNote: NSE often blocks automated requests. You may need to use a browser to download the CSV manually if this persists.")

if __name__ == "__main__":
    test_tri_fetch()
