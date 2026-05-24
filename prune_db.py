import os
import json
import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "Gemini/personal finance accounting/nav_data.db" if os.path.exists("Gemini/personal finance accounting") else "nav_data.db"
GROUPED_FUNDS_FILE = "Gemini/personal finance accounting/grouped_funds.json" if os.path.exists("Gemini/personal finance accounting") else "grouped_funds.json"
BASE_PATH = "Gemini/personal finance accounting/data/" if os.path.exists("Gemini/personal finance accounting") else "data/"

def get_whitelist_schemes():
    whitelist = set()
    
    # 1. Load from grouped_funds.json
    if os.path.exists(GROUPED_FUNDS_FILE):
        with open(GROUPED_FUNDS_FILE, 'r') as f:
            grouped = json.load(f)
            for cat in grouped:
                for fund in grouped[cat]:
                    whitelist.add(str(fund['code']).strip())
        print(f"Loaded {len(whitelist)} schemes from grouped_funds.json.")
    else:
        print("Warning: grouped_funds.json not found.")

    # 2. Hardcoded model strategy schemes
    model_schemes = ["119771", "147946", "118989"]
    for code in model_schemes:
        whitelist.add(code)
    
    # 3. Load scheme names/codes from transaction sheets
    # We want to scan the Excel files to see if there are any mutual fund schemes mentioned
    mf_files = ['Mutual_Funds_Order_History_01-04-2025_19-05-2026.xlsx']
    for mf_file in mf_files:
        full_path = os.path.join(BASE_PATH, mf_file)
        if os.path.exists(full_path):
            try:
                df = pd.read_excel(full_path, header=11).dropna(how='all')
                if 'Scheme Name' in df.columns:
                    names = df['Scheme Name'].dropna().unique()
                    print(f"Found {len(names)} mutual funds in transaction sheets.")
                    
                    # Connect to SQLite to find the corresponding scheme codes for these names
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    for name in names:
                        name_clean = str(name).strip()
                        cursor.execute("SELECT scheme_code FROM schemes WHERE scheme_name = ? OR isin_growth = ?", (name_clean, name_clean))
                        res = cursor.fetchall()
                        if res:
                            for row in res:
                                whitelist.add(str(row[0]).strip())
                        else:
                            # Try fuzzy match
                            cursor.execute("SELECT scheme_code FROM schemes WHERE scheme_name LIKE ?", (f"%{name_clean}%",))
                            res = cursor.fetchall()
                            for row in res:
                                whitelist.add(str(row[0]).strip())
                    conn.close()
            except Exception as e:
                print(f"Error scanning Excel transaction sheets: {e}")

    return whitelist

def prune_database():
    if not os.path.exists(DB_FILE):
        print(f"Error: {DB_FILE} not found.")
        return
        
    initial_size = os.path.getsize(DB_FILE) / (1024 * 1024)
    print(f"Initial Database Size: {initial_size:.2f} MB")
    
    whitelist = get_whitelist_schemes()
    if not whitelist:
        print("No schemes found for whitelist. Aborting prune.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get total records before pruning
    cursor.execute("SELECT count(*) FROM schemes")
    total_schemes_before = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM nav_history")
    total_history_before = cursor.fetchone()[0]
    
    print(f"Before Pruning: {total_schemes_before} schemes, {total_history_before} NAV history records.")

    # Create temporary table with whitelisted codes
    cursor.execute("CREATE TEMP TABLE whitelist_codes (scheme_code TEXT PRIMARY KEY)")
    cursor.executemany("INSERT OR IGNORE INTO whitelist_codes VALUES (?)", [(code,) for code in whitelist])
    
    # Delete from nav_history first (foreign key dependency)
    print("Deleting unused NAV history...")
    cursor.execute("""
        DELETE FROM nav_history 
        WHERE scheme_code NOT IN (SELECT scheme_code FROM whitelist_codes)
    """)
    history_deleted = cursor.rowcount
    
    # Delete from schemes
    print("Deleting unused scheme metadata...")
    cursor.execute("""
        DELETE FROM schemes 
        WHERE scheme_code NOT IN (SELECT scheme_code FROM whitelist_codes)
    """)
    schemes_deleted = cursor.rowcount

    conn.commit()
    
    # Verify remaining
    cursor.execute("SELECT count(*) FROM schemes")
    total_schemes_after = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM nav_history")
    total_history_after = cursor.fetchone()[0]
    
    print(f"After Pruning: {total_schemes_after} schemes, {total_history_after} NAV history records.")
    print(f"Deleted {schemes_deleted} schemes and {history_deleted} history rows.")

    # Vacuum database to shrink the file size
    print("Vacuuming database (this might take a moment)...")
    cursor.execute("VACUUM")
    conn.close()

    final_size = os.path.getsize(DB_FILE) / (1024 * 1024)
    print(f"Final Database Size: {final_size:.2f} MB")
    print(f"Saved {(initial_size - final_size):.2f} MB.")

if __name__ == "__main__":
    prune_database()
