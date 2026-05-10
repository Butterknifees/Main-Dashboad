import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

DB_FILE = "Gemini/personal finance accounting/nav_data.db"

def analyze_large_cap_performance():
    conn = sqlite3.connect(DB_FILE)
    
    # 1. Get all Large Cap Direct Plan schemes
    # We check category OR name for 'Large Cap' and search for 'Direct' or '- D'
    # We EXCLUDE IDCW, Dividend, Payout, and Reinvestment to get only Growth funds
    query_schemes = """
        SELECT scheme_code, scheme_name 
        FROM schemes 
        WHERE (category LIKE '%Large Cap Fund%' OR scheme_name LIKE '%Large Cap%')
          AND (scheme_name LIKE '%Direct%' OR scheme_name LIKE '%-D%')
          AND scheme_name NOT LIKE '%IDCW%'
          AND scheme_name NOT LIKE '%Dividend%'
          AND scheme_name NOT LIKE '%Payout%'
          AND scheme_name NOT LIKE '%Reinvestment%'
    """
    schemes_df = pd.read_sql_query(query_schemes, conn)
    
    if schemes_df.empty:
        print("No Large Cap Direct Plan Growth funds found in the database.")
        return

    results = []
    
    # 2. For each scheme, get history and calculate metrics
    for _, row in schemes_df.iterrows():
        code = row['scheme_code']
        name = row['scheme_name']
        
        # Get last 31 days to have 30 days of returns
        history_query = f"""
            SELECT nav, date 
            FROM nav_history 
            WHERE scheme_code = ? 
            ORDER BY date ASC
        """
        hist = pd.read_sql_query(history_query, conn, params=(code,))
        
        if len(hist) < 2:
            continue
            
        # Ensure NAV is numeric
        hist['nav'] = pd.to_numeric(hist['nav'], errors='coerce')
        hist = hist.dropna()
        
        if len(hist) < 2:
            continue

        # Calculate daily % change
        hist['daily_return'] = hist['nav'].pct_change()
        
        # Performance over the full available period in DB (30 days)
        start_nav = hist['nav'].iloc[0]
        end_nav = hist['nav'].iloc[-1]
        total_return = ((end_nav - start_nav) / start_nav) * 100
        
        # Standard Deviation of daily returns (Volatility)
        daily_std = hist['daily_return'].std() * 100
        
        results.append({
            'Scheme Code': code,
            'Scheme Name': name,
            '30D Return (%)': round(total_return, 2),
            'Daily Volatility (Std Dev %)': round(daily_std, 4),
            'Start NAV': start_nav,
            'End NAV': end_nav,
            'Start Date': hist['date'].iloc[0],
            'End Date': hist['date'].iloc[-1]
        })
    
    conn.close()
    
    # 3. Create DataFrame and Rank
    performance_df = pd.DataFrame(results)
    if performance_df.empty:
        print("Not enough data to calculate returns.")
        return
        
    performance_df = performance_df.sort_values(by='30D Return (%)', ascending=False)
    
    # Save full results to CSV
    csv_path = "Gemini/personal finance accounting/large_cap_performance_analysis.csv"
    performance_df.to_csv(csv_path, index=False)
    print(f"\nFull performance analysis saved to: {csv_path}")

    # Display the top 20
    print("\nTop 20 Large Cap Direct Growth Funds (Last 30 Days)")
    print("="*100)
    print(performance_df.head(20)[['Scheme Name', '30D Return (%)', 'Daily Volatility (Std Dev %)']].to_string(index=False))

if __name__ == "__main__":
    analyze_large_cap_performance()
