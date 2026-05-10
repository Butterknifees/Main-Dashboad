import requests
import json
from datetime import datetime, timedelta
import time

def fetch_amfi_bulk():
    """Download the full AMFI NAV list."""
    url = "https://www.amfiindia.com/spages/NAVAll.txt"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    return ""

def get_large_cap_schemes():
    """Parse AMFI data to find all Large Cap schemes."""
    data = fetch_amfi_bulk()
    schemes = []
    is_large_cap_section = False
    
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        
        if "Equity Scheme - Large Cap Fund" in line:
            is_large_cap_section = True
            continue
        
        # If we hit another category header, stop
        if is_large_cap_section and "Open Ended Schemes(" in line and "Large Cap Fund" not in line:
            is_large_cap_section = False
            continue
            
        if is_large_cap_section and ";" in line:
            parts = line.split(";")
            if len(parts) >= 4:
                scheme_code = parts[0]
                scheme_name = parts[3]
                schemes.append({'code': scheme_code, 'name': scheme_name})
                
    return schemes

def get_historical_data(scheme_code, days=30):
    """Fetch historical data for a specific scheme code for the last N days."""
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if 'data' in data:
            # Filter data for the last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered_data = []
            for entry in data['data']:
                entry_date = datetime.strptime(entry['date'], "%d-%m-%Y")
                if entry_date >= cutoff_date:
                    filtered_data.append(entry)
                else:
                    # Data is usually sorted by date (newest first)
                    break
            return filtered_data
    return []

if __name__ == "__main__":
    print("Identifying Large Cap schemes from AMFI...")
    large_cap_schemes = get_large_cap_schemes()
    print(f"Found {len(large_cap_schemes)} Large Cap schemes.")
    
    # To avoid overwhelming the API or taking too long, let's limit to top 5 for demonstration
    # You can remove the slice [:5] to fetch for all.
    limit = 5
    print(f"\nFetching last 30 days of data for the first {limit} schemes...")
    
    all_results = {}
    for scheme in large_cap_schemes[:limit]:
        print(f"Processing: {scheme['name']} ({scheme['code']})...")
        hist_data = get_historical_data(scheme['code'], days=30)
        all_results[scheme['name']] = hist_data
        # Sleep briefly to be polite to the API
        time.sleep(0.5)
    
    # Save results to a JSON file
    output_file = "Gemini/personal finance accounting/large_cap_historical.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=4)
    
    print(f"\nHistorical data saved to {output_file}")
