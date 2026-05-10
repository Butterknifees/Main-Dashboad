import sqlite3
import requests
import os
from datetime import datetime

DB_FILE = "Gemini/personal finance accounting/nav_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Table for scheme metadata
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
    # Table for NAV history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nav_history (
            scheme_code TEXT,
            nav REAL,
            date TEXT,
            PRIMARY KEY (scheme_code, date),
            FOREIGN KEY (scheme_code) REFERENCES schemes (scheme_code)
        )
    ''')
    conn.commit()
    return conn

def update_all_schemes():
    """
    Downloads AMFI bulk file and updates EVERY scheme in the database.
    """
    print("Fetching latest NAVs for all schemes from AMFI...")
    url = "https://www.amfiindia.com/spages/NAVAll.txt"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Error downloading AMFI data: {e}")
        return

    conn = init_db()
    cursor = conn.cursor()

    current_category = "Unknown"
    current_amc = "Unknown"
    updated_count = 0
    new_schemes_count = 0

    lines = response.text.splitlines()
    for line in lines:
        line = line.strip()
        if not line: continue

        # Identify Category (e.g., "Open Ended Schemes(Equity Scheme - Large Cap Fund)")
        if "Open Ended Schemes(" in line or "Close Ended Schemes(" in line:
            current_category = line
            continue
        
        # Identify AMC (usually a single line with the AMC name before its schemes)
        if ";" not in line and "(" not in line and "Mutual Fund" in line:
            current_amc = line
            continue

        if ";" in line:
            parts = line.split(";")
            if len(parts) >= 6:
                code = parts[0].strip()
                isin_g = parts[1].strip()
                isin_d = parts[2].strip()
                name = parts[3].strip()
                try:
                    nav = float(parts[4].strip())
                except ValueError:
                    continue # Skip if NAV is "N.A." or invalid
                
                date_str = parts[5].strip()
                # Format date to YYYY-MM-DD for better sorting in SQLite
                try:
                    dt_obj = datetime.strptime(date_str, "%d-%b-%Y")
                    iso_date = dt_obj.strftime("%Y-%m-%d")
                except:
                    iso_date = date_str

                # 1. Update/Insert Scheme Metadata
                cursor.execute('''
                    INSERT INTO schemes (scheme_code, isin_growth, isin_div, scheme_name, category, amc)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(scheme_code) DO UPDATE SET
                        scheme_name=excluded.scheme_name,
                        category=excluded.category,
                        amc=excluded.amc
                ''', (code, isin_g, isin_d, name, current_category, current_amc))
                
                if cursor.rowcount > 0:
                    new_schemes_count += 1

                # 2. Insert NAV history (ignores if date+code already exists)
                cursor.execute('''
                    INSERT OR IGNORE INTO nav_history (scheme_code, nav, date)
                    VALUES (?, ?, ?)
                ''', (code, nav, iso_date))
                
                if cursor.rowcount > 0:
                    updated_count += 1

    conn.commit()
    conn.close()
    print(f"Update Complete.")
    print(f"- New daily records added: {updated_count}")
    print(f"- Total schemes tracked: {new_schemes_count}")

def get_latest_nav_for_scheme(name_query):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    query = f"%{name_query}%"
    cursor.execute('''
        SELECT s.scheme_name, n.nav, n.date 
        FROM schemes s
        JOIN nav_history n ON s.scheme_code = n.scheme_code
        WHERE s.scheme_name LIKE ?
        ORDER BY n.date DESC
        LIMIT 1
    ''', (query,))
    result = cursor.fetchone()
    conn.close()
    return result

if __name__ == "__main__":
    update_all_schemes()
    
    # Quick test
    test_search = "HDFC Gold"
    result = get_latest_nav_for_scheme(test_search)
    if result:
        print(f"\nLast known NAV for {result[0]}: {result[1]} on {result[2]}")
