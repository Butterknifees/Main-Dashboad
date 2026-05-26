import sqlite3
import requests
import time
import os
from datetime import datetime, timedelta

DB_FILE = "nav_data_backup.db"
BASE_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"

def parse_and_store(text, conn):
    cursor = conn.cursor()
    current_category = "Unknown"
    current_amc = "Unknown"
    
    lines = text.splitlines()
    if not lines: return 0
    
    # Detect header to determine columns
    header = lines[0].strip().split(';')
    col_map = {col.strip(): i for i, col in enumerate(header)}
    
    updated_count = 0
    for line in lines[1:]:
        line = line.strip()
        if not line: continue
        
        if "Open Ended Schemes(" in line or "Close Ended Schemes(" in line:
            current_category = line
            continue
        if ";" not in line and "Mutual Fund" in line:
            current_amc = line
            continue
            
        if ";" in line:
            parts = line.split(";")
            try:
                code = parts[col_map['Scheme Code']].strip()
                nav_str = parts[col_map['Net Asset Value']].strip()
                date_str = parts[col_map['Date']].strip()
                
                if nav_str == "N.A." or not nav_str: continue
                nav = float(nav_str)
                
                name = parts[col_map['Scheme Name']].strip() if 'Scheme Name' in col_map else "Unknown"
                isin_g = parts[col_map['ISIN Div Payout/ISIN Growth']].strip() if 'ISIN Div Payout/ISIN Growth' in col_map else ""
                
                dt_obj = datetime.strptime(date_str, "%d-%b-%Y")
                iso_date = dt_obj.strftime("%Y-%m-%d")
                
                cursor.execute('''
                    INSERT INTO schemes (scheme_code, isin_growth, scheme_name, category, amc)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(scheme_code) DO UPDATE SET
                        scheme_name=excluded.scheme_name,
                        category=excluded.category,
                        amc=excluded.amc
                ''', (code, isin_g, name, current_category, current_amc))
                
                cursor.execute('''
                    INSERT OR IGNORE INTO nav_history (scheme_code, nav, date)
                    VALUES (?, ?, ?)
                ''', (code, nav, iso_date))
                
                if cursor.rowcount > 0:
                    updated_count += 1
            except (ValueError, KeyError, IndexError):
                continue
                
    conn.commit()
    return updated_count

def backfill_backup():
    if not os.path.exists(DB_FILE):
        print(f"Error: {DB_FILE} does not exist.")
        return
        
    conn = sqlite3.connect(DB_FILE)
    
    # We want to fill the gap from 2025-05-15 to 2025-07-06
    start_date = datetime(2025, 5, 15)
    end_date = datetime(2025, 7, 7)
    
    current_date = start_date
    dates_to_fetch = []
    
    while current_date <= end_date:
        # Check if we already have records for this date
        iso_date = current_date.strftime("%Y-%m-%d")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nav_history WHERE date = ?", (iso_date,))
        count = cursor.fetchone()[0]
        
        # If count < 1000, we consider it missing/incomplete
        if count < 1000:
            dates_to_fetch.append(current_date)
            
        current_date += timedelta(days=1)
        
    print(f"Found {len(dates_to_fetch)} dates to fetch between 2025-05-15 and 2025-07-07.")
    
    for idx, target_date in enumerate(dates_to_fetch):
        date_str = target_date.strftime("%d-%b-%Y")
        print(f"[{idx+1}/{len(dates_to_fetch)}] Fetching data for {date_str}...")
        
        params = {"frmdt": date_str, "todt": date_str}
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            if response.status_code == 200:
                count = parse_and_store(response.text, conn)
                print(f"  -> Added {count} records.")
            else:
                print(f"  -> Failed (Status: {response.status_code})")
        except Exception as e:
            print(f"  -> Error: {e}")
            
        time.sleep(2.5) # respect server rate limits
        
    conn.close()
    print("\nBackfill operation complete.")

if __name__ == "__main__":
    backfill_backup()
