import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_FILE = "Gemini/personal finance accounting/nav_data.db" if os.path.exists("Gemini/personal finance accounting") else "nav_data.db"
OUTPUT_FILE = "Gemini/personal finance accounting/grouped_funds.json" if os.path.exists("Gemini/personal finance accounting") else "grouped_funds.json"

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
        "Foreign Funds": [],
        "Large & Mid Cap": [],
        "Large Cap": [],
        "Mid Cap": [],
        "Small Cap": [],
        "Flexi/Multi Cap": [],
        "Arbitrage": [],
        "Multi Asset": [],
        "Hybrid": [],
        "Liquid": [],
        "Overnight": [],
        "Money Market": [],
        "Ultra Short": [],
        "Duration": [],
        "Credit Risk": [],
        "Debt (Other)": [],
        "Sectoral/Thematic": [],
        "Index/Other": []
    }
    
    def get_bucket(cat_str, name_str):
        c = cat_str.lower() if cat_str else ""
        n = name_str.lower()
        
        # 1. Foreign Funds (Overseas, Nasdaq, S&P 500, International, US, Greater China, Taiwan, Japan, etc.)
        # Check FoF Overseas category first or keywords in name
        foreign_keywords = [
            "overseas", "global", "international", "foreign", "nasdaq", "s&p 500", "sp 500", 
            "us equity", "us treasury", "taiwan", "greater china", "japan", "brazil", "world"
        ]
        if "overseas" in c or any(k in n for k in foreign_keywords):
            return "Foreign Funds"
            
        # 2. Large & Mid Cap (must be evaluated before Large Cap and Mid Cap)
        if "large & mid" in c or "large & mid" in n or "large and mid" in c or "large and mid" in n:
            return "Large & Mid Cap"
            
        # 3. Large Cap
        if "large cap" in c or "large cap" in n:
            return "Large Cap"
            
        # 4. Mid Cap
        if "mid cap" in c or "mid cap" in n:
            return "Mid Cap"
            
        # 5. Small Cap
        if "small cap" in c or "small cap" in n:
            return "Small Cap"
            
        # 6. Multi Asset (must be evaluated before Flexi/Multi Cap and Hybrid)
        if "multi asset" in c or "multi asset" in n or "multi-asset" in c or "multi-asset" in n:
            return "Multi Asset"
            
        # 7. Flexi/Multi Cap (but NOT Multi Asset)
        if "flexi cap" in c or "multi cap" in c or "flexi cap" in n or "multi cap" in n:
            return "Flexi/Multi Cap"
            
        # 8. Arbitrage (must be evaluated before Hybrid)
        if "arbitrage" in c or "arbitrage" in n:
            return "Arbitrage"
            
        # 9. Hybrid (Aggressive Hybrid, Dynamic Asset Allocation, Balanced Advantage, Equity Savings, Conservative Hybrid - but NOT Multi Asset or Arbitrage)
        hybrid_keywords = ["hybrid", "balanced", "equity savings", "dynamic asset allocation"]
        if any(k in c for k in hybrid_keywords) or any(k in n for k in hybrid_keywords):
            return "Hybrid"
            
        # 10. Liquid (Debt - Liquid)
        if "liquid" in c or "liquid" in n:
            return "Liquid"
            
        # 11. Overnight (Debt - Overnight)
        if "overnight" in c or "overnight" in n:
            return "Overnight"
            
        # 12. Money Market (Debt - Money Market)
        if "money market" in c or "money market" in n:
            return "Money Market"
            
        # 13. Ultra Short (Debt - Ultra Short)
        if "ultra short" in c or "ultra short" in n or "ultra-short" in c or "ultra-short" in n:
            return "Ultra Short"
            
        # 14. Duration (Debt - Short/Medium/Long/Dynamic Duration, low duration)
        if "duration" in c or "duration" in n:
            return "Duration"
            
        # 15. Credit Risk
        if "credit risk" in c or "credit risk" in n:
            return "Credit Risk"
            
        # 16. Debt (Other) - Gilt, Bond, Treasury, Floater, G-Sec, etc. (excluding specific subclasses above)
        debt_keywords = ["debt", "gilt", "bond", "treasury", "short term", "medium term", "long term", "low duration", "floater", "g-sec"]
        if any(k in c for k in debt_keywords) or any(k in n for k in debt_keywords):
            return "Debt (Other)"
            
        # 17. Sectoral/Thematic
        sectoral_keywords = [
            "sectoral", "thematic", "pharma", "healthcare", "technology", "tech", 
            "infrastructure", "banking", "financial", "fmcg", "consumer", "digital", 
            "energy", "auto", "power", "services", "telecom", "commodity", "pharma", 
            "it ", "media", "metal", "realty", "mnc", "manufacturing", "opportunities",
            "dividend yield", "special situations", "business cycle", "transportation", 
            "defense", "esg", "consumption", "commodities", "infrastructure"
        ]
        if "sectoral" in c or "thematic" in c or any(k in n for k in sectoral_keywords): 
            return "Sectoral/Thematic"
            
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
