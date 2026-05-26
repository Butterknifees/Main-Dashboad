import sqlite3
import requests
import time
import os
from datetime import datetime, timedelta

DB_FILE = "Gemini/personal finance accounting/nav_data.db" if os.path.exists("Gemini/personal finance accounting") else "nav_data.db"
BASE_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schemes (
            scheme_code TEXT PRIMARY KEY,
            isin_growth TEXT,
            isin_div TEXT,
            scheme_name TEXT,
            category TEXT,
            amc TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nav_history (
            scheme_code TEXT,
            nav REAL,
            date TEXT,
            PRIMARY KEY (scheme_code, date),
            FOREIGN KEY (scheme_code) REFERENCES schemes (scheme_code)
        )
    ''')
    # Add index for faster performance on date-based queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nav_date ON nav_history(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scheme_code ON nav_history(scheme_code)')
    conn.commit()
    return conn

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

def backfill(days=None):
    conn = init_db()
    cursor = conn.cursor()
    
    # Auto-detect days needed if not provided
    if days is None:
        cursor.execute("SELECT MAX(date) FROM nav_history")
        latest_date_str = cursor.fetchone()[0]
        if latest_date_str:
            latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
            # Fetch from latest_date up to today
            days = (datetime.now() - latest_date).days + 1
            print(f"Auto-detected: Fetching last {days} days to sync with latest record ({latest_date_str}).")
        else:
            days = 365 # Default for empty DB
            print(f"Empty database: Fetching default {days} days.")

    today = datetime.now()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        iso_date = target_date.strftime("%Y-%m-%d")
        date_str = target_date.strftime("%d-%b-%Y")
        
        # Check if we already have data for this day
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM nav_history WHERE date = ? LIMIT 1", (iso_date,))
        if cursor.fetchone():
            print(f"[{i+1}/{days}] Skipping {date_str} - Data already exists.")
            continue

        print(f"[{i+1}/{days}] Fetching data for {date_str}...")
        
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
            
        time.sleep(2)
        
    conn.close()
    print("\nBackfill operation complete.")

if __name__ == "__main__":
    # Calling backfill() without arguments will auto-detect the gap
    backfill()
