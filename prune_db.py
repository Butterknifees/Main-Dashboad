import os
import sqlite3
import pandas as pd

DB_FILE = "Gemini/personal finance accounting/nav_data.db" if os.path.exists("Gemini/personal finance accounting") else "nav_data.db"
BACKUP_FILE = "Gemini/personal finance accounting/nav_data_backup.db" if os.path.exists("Gemini/personal finance accounting") else "nav_data_backup.db"
BASE_PATH = "Gemini/personal finance accounting/data/" if os.path.exists("Gemini/personal finance accounting") else "data/"

def restore_backup():
    if os.path.exists(BACKUP_FILE):
        print(f"Restoring backup from {BACKUP_FILE} to {DB_FILE}...")
        import shutil
        shutil.copy2(BACKUP_FILE, DB_FILE)
        print("Backup restored successfully.")
        return True
    return False

def get_user_transaction_schemes(cursor):
    user_items = set()
    
    # 1. CSV Tradebook
    tradebook = os.path.join(BASE_PATH, 'tradebook-IZP332-MF (1).csv')
    if os.path.exists(tradebook):
        try:
            df = pd.read_csv(tradebook)
            if 'isin' in df.columns:
                for val in df['isin'].dropna().unique():
                    user_items.add(str(val).strip())
        except Exception as e:
            print(f"Error reading tradebook: {e}")
            
    # 2. MF Excel
    mf_file = os.path.join(BASE_PATH, 'Mutual_Funds_Order_History_01-04-2025_19-05-2026.xlsx')
    if os.path.exists(mf_file):
        try:
            df = pd.read_excel(mf_file, header=11).dropna(how='all')
            if 'Scheme Name' in df.columns:
                for val in df['Scheme Name'].dropna().unique():
                    user_items.add(str(val).strip())
        except Exception as e:
            print(f"Error reading MF Excel: {e}")
            
    # Resolve ISINs/names to scheme codes using SQLite schemes table
    resolved_codes = set()
    print(f"Found {len(user_items)} unique scheme identifiers/names in transaction history.")
    for item in user_items:
        cursor.execute("""
            SELECT scheme_code FROM schemes 
            WHERE scheme_name = ? OR isin_growth = ? OR isin_div = ? OR scheme_code = ?
        """, (item, item, item, item))
        rows = cursor.fetchall()
        for r in rows:
            resolved_codes.add(r[0])
            
    print(f"Resolved {len(resolved_codes)} scheme codes from transaction history.")
    return resolved_codes

def prune_database():
    # Restore backup first so we start from a clean full database
    if not restore_backup():
        if not os.path.exists(DB_FILE):
            print(f"Error: {DB_FILE} not found and no backup available to restore.")
            return
        print("No backup database found. Pruning current database.")
    
    initial_size = os.path.getsize(DB_FILE) / (1024 * 1024)
    print(f"Initial Database Size: {initial_size:.2f} MB")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get total records before pruning
    cursor.execute("SELECT count(*) FROM schemes")
    total_schemes_before = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM nav_history")
    total_history_before = cursor.fetchone()[0]
    
    print(f"Before Pruning: {total_schemes_before} schemes, {total_history_before} NAV history records.")

    # Get user schemes that we MUST keep
    user_codes = get_user_transaction_schemes(cursor)
    
    # Create placeholders for SQL query exclusion
    placeholders = ",".join(["?"] * len(user_codes))
    user_codes_list = list(user_codes)

    # Count schemes that match blacklist but are NOT in user transaction codes
    query_count = f"""
        SELECT COUNT(*) FROM schemes 
        WHERE (
            scheme_name LIKE '%Regular%'
            OR (scheme_name NOT LIKE '%Direct%' AND scheme_name NOT LIKE '%Dir%')
            OR scheme_name LIKE '%IDCW%'
            OR scheme_name LIKE '%Dividend%'
            OR scheme_name LIKE '%Payout%'
            OR scheme_name LIKE '%Reinvestment%'
        )
        AND scheme_code NOT IN ({placeholders})
    """
    cursor.execute(query_count, user_codes_list)
    to_delete_count = cursor.fetchone()[0]
    print(f"Identified {to_delete_count} schemes to delete (excluding user's transaction schemes).")

    # Delete from nav_history first
    print("Deleting NAV history of blacklisted schemes...")
    query_del_history = f"""
        DELETE FROM nav_history 
        WHERE scheme_code IN (
            SELECT scheme_code FROM schemes 
            WHERE (
                scheme_name LIKE '%Regular%'
                OR (scheme_name NOT LIKE '%Direct%' AND scheme_name NOT LIKE '%Dir%')
                OR scheme_name LIKE '%IDCW%'
                OR scheme_name LIKE '%Dividend%'
                OR scheme_name LIKE '%Payout%'
                OR scheme_name LIKE '%Reinvestment%'
            )
            AND scheme_code NOT IN ({placeholders})
        )
    """
    cursor.execute(query_del_history, user_codes_list)
    history_deleted = cursor.rowcount
    print(f"Deleted {history_deleted} history rows.")

    # Delete from schemes
    print("Deleting blacklisted scheme metadata...")
    query_del_schemes = f"""
        DELETE FROM schemes 
        WHERE (
            scheme_name LIKE '%Regular%'
            OR (scheme_name NOT LIKE '%Direct%' AND scheme_name NOT LIKE '%Dir%')
            OR scheme_name LIKE '%IDCW%'
            OR scheme_name LIKE '%Dividend%'
            OR scheme_name LIKE '%Payout%'
            OR scheme_name LIKE '%Reinvestment%'
        )
        AND scheme_code NOT IN ({placeholders})
    """
    cursor.execute(query_del_schemes, user_codes_list)
    schemes_deleted = cursor.rowcount
    print(f"Deleted {schemes_deleted} scheme rows.")

    conn.commit()
    
    # Verify remaining records
    cursor.execute("SELECT count(*) FROM schemes")
    total_schemes_after = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM nav_history")
    total_history_after = cursor.fetchone()[0]
    
    print(f"After Pruning: {total_schemes_after} schemes, {total_history_after} NAV history records.")
    
    # Vacuum database to reclaim space
    print("Vacuuming database (this might take a moment)...")
    cursor.execute("VACUUM")
    conn.close()

    final_size = os.path.getsize(DB_FILE) / (1024 * 1024)
    print(f"Final Database Size: {final_size:.2f} MB")
    print(f"Saved {(initial_size - final_size):.2f} MB.")

if __name__ == "__main__":
    prune_database()
