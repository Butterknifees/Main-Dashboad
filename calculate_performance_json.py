import sqlite3
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

# Fallback paths to work relative to workspace or parent dir
DB_FILE = "nav_data_backup.db" if os.path.exists("nav_data_backup.db") else "Gemini/personal finance accounting/nav_data_backup.db"
OUTPUT_FILE = "mutual_fund_performance.json" if os.path.exists("nav_data_backup.db") else "Gemini/personal finance accounting/mutual_fund_performance.json"

def calculate_returns():
    print(f"Connecting to database: {DB_FILE}...")
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file not found at {DB_FILE}")
        return
        
    conn = sqlite3.connect(DB_FILE)
    
    # 1. Fetch all schemes that are Growth options
    query_schemes = """
        SELECT scheme_code, scheme_name, category
        FROM schemes
        WHERE (scheme_name LIKE '%Growth%' OR scheme_name LIKE '%Gr%')
          AND scheme_name NOT LIKE '%IDCW%'
          AND scheme_name NOT LIKE '%Dividend%'
          AND scheme_name NOT LIKE '%Payout%'
          AND scheme_name NOT LIKE '%Reinvestment%'
    """
    schemes_df = pd.read_sql_query(query_schemes, conn)
    print(f"Loaded {len(schemes_df)} Growth schemes.")
    
    # 2. Get all NAV history to load in memory for fast lookup
    print("Loading NAV history...")
    history_df = pd.read_sql_query("SELECT scheme_code, nav, date FROM nav_history ORDER BY date ASC", conn)
    print(f"Loaded {len(history_df)} NAV records.")
    
    # Pre-parse dates to datetime
    history_df['date_dt'] = pd.to_datetime(history_df['date'])
    history_df['nav'] = pd.to_numeric(history_df['nav'], errors='coerce')
    history_df = history_df.dropna(subset=['nav'])
    
    # Group NAV history by scheme_code for fast access
    print("Processing history indexes...")
    scheme_history = {}
    for code, group in history_df.groupby('scheme_code'):
        dates = group['date_dt'].tolist()
        navs = group['nav'].tolist()
        scheme_history[code] = {
            'dates': dates,
            'navs': navs
        }
    
    print("Calculating performance metrics...")
    
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
    
    # For each scheme, calculate 1m and 1y returns
    results = []
    
    for idx, row in schemes_df.iterrows():
        code = row['scheme_code']
        name = row['scheme_name']
        cat = row['category']
        
        if code not in scheme_history:
            continue
            
        hist = scheme_history[code]
        dates = hist['dates']
        navs = hist['navs']
        
        if len(navs) < 2:
            continue
            
        latest_date = dates[-1]
        latest_nav = navs[-1]
        
        # 1 Month Ago target date
        target_1m = latest_date - timedelta(days=30)
        # 1 Year Ago target date
        target_1y = latest_date - timedelta(days=365)
        
        idx_1m = -1
        idx_1y = -1
        
        min_diff_1m = timedelta(days=7) # maximum 7 days difference allowed
        min_diff_1y = timedelta(days=15) # maximum 15 days difference allowed
        
        for i, dt in enumerate(dates):
            diff_1m = abs(dt - target_1m)
            if diff_1m < min_diff_1m:
                min_diff_1m = diff_1m
                idx_1m = i
                
            diff_1y = abs(dt - target_1y)
            if diff_1y < min_diff_1y:
                min_diff_1y = diff_1y
                idx_1y = i
                
        # Calculate returns if valid index found
        ret_1m = None
        ret_1y = None
        
        if idx_1m != -1:
            nav_1m = navs[idx_1m]
            if nav_1m > 0:
                ret_1m = ((latest_nav - nav_1m) / nav_1m) * 100
                
        if idx_1y != -1:
            nav_1y = navs[idx_1y]
            if nav_1y > 0:
                ret_1y = ((latest_nav - nav_1y) / nav_1y) * 100
                
        # We only want to include funds with a valid 1-year return for ranking
        if ret_1y is None:
            continue
            
        name_lower = name.lower()
        is_direct = "direct" in name_lower or "dir" in name_lower
        plan_type = "Direct" if is_direct else "Regular"
        
        bucket = get_bucket(cat, name)
        
        results.append({
            "code": code,
            "name": name,
            "category": cat,
            "bucket": bucket,
            "plan_type": plan_type,
            "return_1m": round(ret_1m, 2) if ret_1m is not None else None,
            "return_1y": round(ret_1y, 2),
            "latest_nav": round(latest_nav, 4),
            "latest_date": latest_date.strftime("%Y-%m-%d")
        })
        
    print(f"Calculated performance for {len(results)} schemes.")
    
    # 3. Group by bucket and plan_type, and calculate stats
    grouped_performance = {}
    
    for r in results:
        cat_key = f"{r['bucket']} ({r['plan_type']})"
        if cat_key not in grouped_performance:
            grouped_performance[cat_key] = []
        grouped_performance[cat_key].append(r)
        
    final_output = {}
    
    for cat_name, funds in grouped_performance.items():
        # Sort funds by 1y return descending
        funds.sort(key=lambda x: x['return_1y'], reverse=True)
        
        # Assign rank
        for rank_idx, f in enumerate(funds):
            f['rank'] = rank_idx + 1
            
        # Calculate stats for the category
        returns_1y = [f['return_1y'] for f in funds]
        
        best_fund = funds[0]
        average_return = np.mean(returns_1y)
        median_return = np.median(returns_1y)
        
        final_output[cat_name] = {
            "stats": {
                "best_fund_name": best_fund['name'],
                "best_fund_return": best_fund['return_1y'],
                "average_return": round(float(average_return), 2),
                "median_return": round(float(median_return), 2),
                "total_funds": len(funds)
            },
            "funds": funds
        }
        
    # Write to JSON
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(final_output, f, indent=4)
        
    print(f"Exported performance JSON successfully to {OUTPUT_FILE}.")
    conn.close()

if __name__ == "__main__":
    calculate_returns()
