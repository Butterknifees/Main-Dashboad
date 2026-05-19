import sqlite3
import json
from datetime import datetime, timedelta

DB_FILE = "Gemini/personal finance accounting/nav_data.db"
OUTPUT_FILE = "Gemini/personal finance accounting/grouped_funds.json"

def group_funds():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Base query: Filter for Direct Growth funds
    # Using count of history points (>100) as a proxy for age
    query = """
    SELECT s.scheme_code, s.scheme_name, s.category
    FROM schemes s
    JOIN nav_history n ON s.scheme_code = n.scheme_code
    WHERE (s.scheme_name LIKE '%Direct%' OR s.scheme_name LIKE '%Dir%')
      AND (s.scheme_name LIKE '%Growth%')
      AND (s.scheme_name NOT LIKE '%Regular%')
      AND (s.scheme_name NOT LIKE '%IDCW%')
      AND (s.scheme_name NOT LIKE '%Dividend%')
      AND (s.scheme_name NOT LIKE '%Payout%')
      AND (s.scheme_name NOT LIKE '%Reinvestment%')
    GROUP BY s.scheme_code
    HAVING COUNT(*) > 100
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # 2. Categorization Logic
    categories = {
        "Large Cap": [],
        "Mid Cap": [],
        "Small Cap": [],
        "Flexi/Multi Cap": [],
        "Sectoral/Thematic": [],
        "Debt": [],
        "Hybrid/Arbitrage": [],
        "Index/Other": []
    }
    
    def get_bucket(cat_str, name_str):
        c = cat_str.lower()
        n = name_str.lower()
        
        if "large cap" in c or "large & mid" in c: return "Large Cap"
        if "mid cap" in c: return "Mid Cap"
        if "small cap" in c: return "Small Cap"
        if "flexi cap" in c or "multi cap" in c: return "Flexi/Multi Cap"
        if "sectoral" in c or "thematic" in c: return "Sectoral/Thematic"
        if "debt" in c or "liquid" in c or "overnight" in c or "money market" in c or "gilt" in c or "bond" in c or "duration" in c: return "Debt"
        if "hybrid" in c or "arbitrage" in c or "balanced" in c or "equity savings" in c: return "Hybrid/Arbitrage"
        return "Index/Other"

    for code, name, cat in rows:
        bucket = get_bucket(cat, name)
        categories[bucket].append({
            "code": code,
            "name": name,
            "category": cat
        })

    # Sort each list by name
    for bucket in categories:
        categories[bucket].sort(key=lambda x: x['name'])

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(categories, f, indent=4)
    
    print(f"Successfully grouped {len(rows)} funds into {len(categories)} categories.")
    for cat, funds in categories.items():
        print(f"  - {cat}: {len(funds)} funds")

if __name__ == "__main__":
    group_funds()
