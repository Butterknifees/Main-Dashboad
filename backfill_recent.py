import sqlite3
import requests
import time
import os
from datetime import datetime, timedelta

DB_MAIN = "nav_data.db"
DB_BACKUP = "nav_data_backup.db"
BASE_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"

def parse_and_store(text, conn_main, conn_backup):
    cursor_main = conn_main.cursor() if conn_main else None
    cursor_backup = conn_backup.cursor() if conn_backup else None
    
    current_category = "Unknown"
    current_amc = "Unknown"
    
    lines = text.splitlines()
    if not lines: return 0
    
    # Detect header to determine columns
    header = lines[0].strip().split(';')
    col_map = {col.strip(): i for i, col in enumerate(header)}
    
    updated_main = 0
    updated_backup = 0
    
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
                
                name_lower = name.lower()
                is_direct = "direct" in name_lower or "dir" in name_lower
                is_regular = "regular" in name_lower
                is_idcw = "idcw" in name_lower or "dividend" in name_lower or "payout" in name_lower or "reinvestment" in name_lower
                is_growth = "growth" in name_lower or "gr" in name_lower
                
                # Write to Backup DB (All Growth plans - Direct & Regular, skip IDCW)
                if cursor_backup and not is_idcw and is_growth:
                    cursor_backup.execute('''
                        INSERT INTO schemes (scheme_code, isin_growth, scheme_name, category, amc)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(scheme_code) DO UPDATE SET
                            scheme_name=excluded.scheme_name,
                            category=excluded.category,
                            amc=excluded.amc
                    ''', (code, isin_g, name, current_category, current_amc))
                    
                    cursor_backup.execute('''
                        INSERT OR IGNORE INTO nav_history (scheme_code, nav, date)
                        VALUES (?, ?, ?)
                    ''', (code, nav, iso_date))
                    if cursor_backup.rowcount > 0:
                        updated_backup += 1
                
                # Write to Main DB (Only Direct Growth plans, skip Regular & IDCW)
                if cursor_main and not is_regular and is_direct and not is_idcw:
                    cursor_main.execute('''
                        INSERT INTO schemes (scheme_code, isin_growth, scheme_name, category, amc)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(scheme_code) DO UPDATE SET
                            scheme_name=excluded.scheme_name,
                            category=excluded.category,
                            amc=excluded.amc
                    ''', (code, isin_g, name, current_category, current_amc))
                    
                    cursor_main.execute('''
                        INSERT OR IGNORE INTO nav_history (scheme_code, nav, date)
                        VALUES (?, ?, ?)
                    ''', (code, nav, iso_date))
                    if cursor_main.rowcount > 0:
                        updated_main += 1
                        
            except (ValueError, KeyError, IndexError) as e:
                continue
                
    if conn_main: conn_main.commit()
    if conn_backup: conn_backup.commit()
    return updated_main, updated_backup

def backfill_recent():
    conn_main = sqlite3.connect(DB_MAIN) if os.path.exists(DB_MAIN) else None
    conn_backup = sqlite3.connect(DB_BACKUP) if os.path.exists(DB_BACKUP) else None
    
    # We want to fill the gap from 2026-05-20 to 2026-05-26 (today)
    start_date = datetime(2026, 5, 20)
    end_date = datetime.now()
    
    current_date = start_date
    dates_to_fetch = []
    
    while current_date <= end_date:
        dates_to_fetch.append(current_date)
        current_date += timedelta(days=1)
        
    print(f"Checking dates to fetch: {[d.strftime('%Y-%m-%d') for d in dates_to_fetch]}")
    
    for idx, target_date in enumerate(dates_to_fetch):
        date_str = target_date.strftime("%d-%b-%Y")
        iso_date = target_date.strftime("%Y-%m-%d")
        
        # Check if we already have records for this date in backup DB (if it exists)
        if conn_backup:
            cursor = conn_backup.cursor()
            cursor.execute("SELECT COUNT(*) FROM nav_history WHERE date = ?", (iso_date,))
            count = cursor.fetchone()[0]
            if count > 1000:
                print(f"Skipping {date_str} - Data already exists ({count} records).")
                continue
                
        print(f"[{idx+1}/{len(dates_to_fetch)}] Fetching data for {date_str}...")
        params = {"frmdt": date_str, "todt": date_str}
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            if response.status_code == 200:
                main_count, backup_count = parse_and_store(response.text, conn_main, conn_backup)
                print(f"  -> Added to main DB: {main_count}, backup DB: {backup_count} records.")
            else:
                print(f"  -> Failed (Status: {response.status_code})")
        except Exception as e:
            print(f"  -> Error: {e}")
            
        time.sleep(2.5) # respect server rate limits
        
    if conn_main: conn_main.close()
    if conn_backup: conn_backup.close()
    print("\nRecent backfill complete.")

if __name__ == "__main__":
    backfill_recent()
