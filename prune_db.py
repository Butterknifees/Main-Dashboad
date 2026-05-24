import os
import sqlite3

DB_FILE = "Gemini/personal finance accounting/nav_data.db" if os.path.exists("Gemini/personal finance accounting") else "nav_data.db"

def prune_database():
    if not os.path.exists(DB_FILE):
        print(f"Error: {DB_FILE} not found.")
        return
        
    # Create an automatic backup of the original database before pruning for safety
    backup_file = DB_FILE.replace(".db", "_backup.db")
    print(f"Creating a backup of the original database at {backup_file}...")
    import shutil
    try:
        shutil.copy2(DB_FILE, backup_file)
        print("Backup created successfully.")
    except Exception as e:
        print(f"Error creating database backup: {e}")
        print("Aborting pruning run for safety.")
        return
        
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

    # We want to identify the blacklisted schemes.
    # Blacklist criteria:
    # 1. Any scheme name containing "Regular" (case-insensitive)
    # 2. Any scheme name NOT containing "Direct" or "Dir" (unless it's some special direct fund, but standard direct funds always have Direct/Dir)
    # 3. Any scheme name containing "IDCW", "Dividend", "Payout", or "Reinvestment" (case-insensitive)
    
    print("Identifying schemes to delete...")
    
    # Fetch all scheme codes and names to filter in Python for safety, or run directly in SQL.
    # SQL query to identify schemes to keep (Direct Growth plans):
    # - Must contain "Direct" or "Dir"
    # - Must NOT contain "Regular"
    # - Must NOT contain "IDCW", "Dividend", "Payout", "Reinvestment"
    # - For extra safety, we'll keep Growth funds or other funds that don't match the IDCW/Regular patterns.
    
    # We will delete schemes that match any of the following:
    # - scheme_name LIKE '%Regular%'
    # - (scheme_name NOT LIKE '%Direct%' AND scheme_name NOT LIKE '%Dir%') -- deletes regular plans that don't have the word Regular but are not Direct
    # - scheme_name LIKE '%IDCW%'
    # - scheme_name LIKE '%Dividend%'
    # - scheme_name LIKE '%Payout%'
    # - scheme_name LIKE '%Reinvestment%'
    
    # Let's run a test select first to see how many we are deleting
    cursor.execute("""
        SELECT COUNT(*) FROM schemes 
        WHERE scheme_name LIKE '%Regular%'
           OR (scheme_name NOT LIKE '%Direct%' AND scheme_name NOT LIKE '%Dir%')
           OR scheme_name LIKE '%IDCW%'
           OR scheme_name LIKE '%Dividend%'
           OR scheme_name LIKE '%Payout%'
           OR scheme_name LIKE '%Reinvestment%'
    """)
    to_delete_count = cursor.fetchone()[0]
    print(f"Identified {to_delete_count} schemes to delete (out of {total_schemes_before} total).")

    # Delete from nav_history first (foreign key constraints)
    print("Deleting NAV history of blacklisted schemes...")
    cursor.execute("""
        DELETE FROM nav_history 
        WHERE scheme_code IN (
            SELECT scheme_code FROM schemes 
            WHERE scheme_name LIKE '%Regular%'
               OR (scheme_name NOT LIKE '%Direct%' AND scheme_name NOT LIKE '%Dir%')
               OR scheme_name LIKE '%IDCW%'
               OR scheme_name LIKE '%Dividend%'
               OR scheme_name LIKE '%Payout%'
               OR scheme_name LIKE '%Reinvestment%'
        )
    """)
    history_deleted = cursor.rowcount
    print(f"Deleted {history_deleted} history rows.")

    # Delete from schemes
    print("Deleting blacklisted scheme metadata...")
    cursor.execute("""
        DELETE FROM schemes 
        WHERE scheme_name LIKE '%Regular%'
           OR (scheme_name NOT LIKE '%Direct%' AND scheme_name NOT LIKE '%Dir%')
           OR scheme_name LIKE '%IDCW%'
           OR scheme_name LIKE '%Dividend%'
           OR scheme_name LIKE '%Payout%'
           OR scheme_name LIKE '%Reinvestment%'
    """)
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
