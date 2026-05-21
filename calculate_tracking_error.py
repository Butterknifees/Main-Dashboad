import pandas as pd
import numpy as np
import json
import os
import sqlite3
from datetime import datetime, timedelta

def calculate_tracking_errors():
    base_path = "Gemini/personal finance accounting/"
    tri_file = os.path.join(base_path, "benchmark_tri_history.csv")
    db_file = os.path.join(base_path, "nav_data.db")
    output_file = os.path.join(base_path, "tracking_error_data.json")

    # 1. Load TRI Benchmarks
    df_tri = pd.read_csv(tri_file, index_col=0, parse_dates=True)
    benchmarks = df_tri.columns.tolist()
    
    # 2. Setup Results Structure
    results = {b: {"ETF": [], "Index Fund": []} for b in benchmarks}

    # 3. Connect to DB and Fetch all Passive Funds
    conn = sqlite3.connect(db_file)
    query = """
        SELECT scheme_code, scheme_name 
        FROM schemes 
        WHERE (scheme_name LIKE '%Index%' OR scheme_name LIKE '%ETF%')
          AND (scheme_name NOT LIKE '%FOF%' AND scheme_name NOT LIKE '%Fund of Fund%')
          AND (scheme_name LIKE '%Direct%' OR scheme_name LIKE '%ETF%')
    """
    df_schemes = pd.read_sql_query(query, conn)
    print(f"Found {len(df_schemes)} potential passive funds. Analyzing...")

    def get_matching_benchmark(name):
        name_lower = name.lower()
        # Order matters: more specific benchmarks first
        
        # Special handling for "Value", "Momentum", "Low Vol" to prevent lumping into Nifty 50
        thematic_keywords = ["value", "momentum", "low vol", "alpha", "quality", "digital", "defence", "defense", "ev ", "msci"]
        for kw in thematic_keywords:
            if kw in name_lower and "NIFTY " + kw.upper() not in benchmarks:
                # If it's a specific thematic index we don't have TRI for, skip
                if kw != "defence" and kw != "defense": # We have Defence TRI
                    return None

        if "next 50" in name_lower: return "NIFTY NEXT 50"
        if "midcap 150" in name_lower: return "NIFTY MIDCAP 150"
        if "smallcap 250" in name_lower: return "NIFTY SMALLCAP 250"
        if "largemidcap 250" in name_lower: return "NIFTY LARGEMIDCAP 250"
        if "nifty 500" in name_lower: 
            if "momentum" in name_lower: return None
            return "NIFTY 500" if "NIFTY 500" in benchmarks else None
        
        if "nifty 50" in name_lower: return "NIFTY 50"
        
        # Sectoral
        if "bank" in name_lower:
            if "private" in name_lower: return "NIFTY PRIVATE BANK"
            if "psu" in name_lower: return "NIFTY PSU BANK"
            return "NIFTY BANK"
        if "it" in name_lower and "index" in name_lower: return "NIFTY IT"
        if "pharma" in name_lower: return "NIFTY PHARMA"
        if "fmcg" in name_lower: return "NIFTY FMCG"
        if "auto" in name_lower: return "NIFTY AUTO"
        if "realty" in name_lower: return "NIFTY REALTY"
        if "metal" in name_lower: return "NIFTY METAL"
        if "infra" in name_lower: return "NIFTY INFRASTRUCTURE"
        if "energy" in name_lower: return "NIFTY ENERGY"
        if "consumption" in name_lower: return "NIFTY CONSUMPTION"
        if "defence" in name_lower or "defense" in name_lower: return "NIFTY INDIA DEFENCE"
        
        return None

    for _, row in df_schemes.iterrows():
        name = row['scheme_name']
        code = row['scheme_code']
        
        benchmark = get_matching_benchmark(name)
        if not benchmark: continue
        
        # Categorize
        cat = "ETF" if "ETF" in name else "Index Fund"
        
        # Fetch NAV
        nav_query = "SELECT date, nav FROM nav_history WHERE scheme_code = ? ORDER BY date"
        df_nav = pd.read_sql_query(nav_query, conn, params=(code,))
        if len(df_nav) < 60: continue # Need at least 3 months for meaningful TE
        
        df_nav['date'] = pd.to_datetime(df_nav['date'])
        df_nav = df_nav.set_index('date')
        
        # Align with TRI
        combined = pd.concat([df_nav['nav'], df_tri[benchmark]], axis=1).dropna()
        combined = combined[(combined['nav'] > 0) & (combined[benchmark] > 0)]
        if len(combined) < 20: continue
        
        # Only take last 1 year of available data
        combined = combined.tail(252)
        
        combined['nav_ret'] = combined['nav'].pct_change()
        combined['bench_ret'] = combined[benchmark].pct_change()
        combined = combined.dropna()
        
        combined['diff'] = combined['nav_ret'] - combined['bench_ret']
        te = combined['diff'].std() * np.sqrt(252) * 100
        avg_diff = combined['diff'].mean() * 252 * 100
        
        results[benchmark][cat].append({
            "name": name,
            "code": code,
            "tracking_error": round(te, 4),
            "avg_difference": round(avg_diff, 4),
            "data_points": len(combined)
        })

    conn.close()

    # Final Cleanup: Remove benchmarks with no funds
    final_results = {k: v for k, v in results.items() if len(v['ETF']) > 0 or len(v['Index Fund']) > 0}

    with open(output_file, 'w') as f:
        json.dump(final_results, f, indent=4)
    
    print(f"Tracking error analysis complete. Data saved to {output_file}")

if __name__ == "__main__":
    calculate_tracking_errors()
