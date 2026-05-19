import pandas as pd
import sqlite3
import csv
import os
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

# Paths
DB_FILE = "Gemini/personal finance accounting/nav_data.db"
ETF_FILE = "Gemini/personal finance accounting/etf_historical_data.csv"
STOCK_FILE = "Gemini/personal finance accounting/nifty_universe_historical_data.csv"
BASE_PATH = "Gemini/personal finance accounting/data/"

def xirr(dates, payments):
    if not dates or not payments: return 0

    def xnpv(rate, dates, payments):
        d0 = dates[0]
        try:
            return sum([p / (1.0 + rate)**((d - d0).days / 365.0) for d, p in zip(dates, payments)])
        except (OverflowError, ZeroDivisionError):
            return float('inf')

    def xnpv_derivative(rate, dates, payments):
        d0 = dates[0]
        try:
            return sum([-p * ((d - d0).days / 365.0) * (1.0 + rate)**(-((d - d0).days / 365.0) - 1.0) for d, p in zip(dates, payments)])
        except (OverflowError, ZeroDivisionError):
            return float('inf')

    # Heuristic for initial rate
    total_out = abs(sum([p for p in payments if p < 0]))
    total_in = sum([p for p in payments if p > 0])
    if total_out > 0:
        simple_return = (total_in - total_out) / total_out
        rate = max(-0.99, min(10.0, simple_return))
    else:
        rate = 0.1

    for _ in range(100):
        f = xnpv(rate, dates, payments)
        df = xnpv_derivative(rate, dates, payments)
        if abs(df) < 1e-12 or np.isinf(df): break
        new_rate = rate - f / df
        if abs(new_rate - rate) < 1e-8: return new_rate
        rate = new_rate
        if rate <= -1.0: rate = -0.999 # Keep it above -100%
    return rate

def load_transactions():
    all_tx = []
    seen_tx = set() # To prevent double counting from overlapping files

    def add_tx(tx):
        # Create a unique signature for each transaction
        sig = (
            tx['date'].strftime('%Y-%m-%d'),
            tx['id'],
            round(tx['qty'], 4),
            round(tx['price'], 4),
            tx['type']
        )
        if sig not in seen_tx:
            seen_tx.add(sig)
            all_tx.append(tx)

    # 1. CSV Tradebook
    tradebook_path = BASE_PATH + 'tradebook-IZP332-MF (1).csv'
    if os.path.exists(tradebook_path):
        with open(tradebook_path, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                add_tx({
                    'date': datetime.strptime(row['trade_date'], '%Y-%m-%d'),
                    'id': row['isin'],
                    'name': row['symbol'],
                    'qty': float(row['quantity']),
                    'price': float(row['price']),
                    'type': row['trade_type'].lower(),
                    'source': 'MF_DB'
                })
    # 2. MF Excel
    mf_files = [
        'Mutual_Funds_Order_History_01-04-2025_19-05-2026.xlsx'
    ]
    for mf_file in mf_files:
        full_path = BASE_PATH + mf_file
        if not os.path.exists(full_path): continue
        df_mf = pd.read_excel(full_path, header=11).dropna(how='all')
        for _, row in df_mf.iterrows():
            if pd.isna(row['Scheme Name']): continue
            name = str(row['Scheme Name']).strip()
            amt_str = str(row['Amount']).replace(',', '')
            add_tx({
                'date': pd.to_datetime(row['Date']),
                'id': name,
                'name': name,
                'qty': float(row['Units']),
                'price': float(amt_str) / float(row['Units']),
                'type': 'buy' if str(row['Transaction Type']).upper() in ['PURCHASE', 'SIP'] else 'sell',
                'source': 'MF_DB'
            })
    # 3. Stocks/ETFs Excel
    stk_files = [
        'Stocks_Order_History_3181700510_01-04-2025_18-05-2026.xlsx'
    ]
    for stk_file in stk_files:
        full_path = BASE_PATH + stk_file
        if not os.path.exists(full_path): continue
        df_stk = pd.read_excel(full_path, header=5)
        for _, row in df_stk.iterrows():
            if pd.isna(row['Stock name']) or row['Order status'] != 'Executed': continue
            isin = str(row['ISIN']).strip()
            add_tx({
                'date': pd.to_datetime(row['Execution date and time'], dayfirst=True),
                'id': isin,
                'name': row['Stock name'],
                'qty': float(row['Quantity']),
                'price': float(row['Value']) / float(row['Quantity']),
                'type': row['Type'].lower(),
                'source': 'YF'
            })
    return all_tx

def get_latest_holdings_prices():
    prices = {}
    stk_h_files = ['Stocks_Holdings_Statement_3181700510_01-04-2025.xlsx']
    mf_h_files = ['Mutual_Funds_3181700510_01-04-2025_19-05-2026.xlsx']
    
    for stk_h_file in [BASE_PATH + f for f in stk_h_files]:
        if os.path.exists(stk_h_file):
            df_stk_all = pd.read_excel(stk_h_file, header=None)
            header_idx = -1
            for i, row in df_stk_all.iterrows():
                if 'ISIN' in [str(v).strip() for v in row.values]:
                    header_idx = i
                    break
            if header_idx != -1:
                df_stk = pd.read_excel(stk_h_file, header=header_idx)
                df_stk.columns = [str(c).strip() for c in df_stk.columns]
                for _, row in df_stk.iterrows():
                    isin = str(row.get('ISIN')).strip()
                    if isin == 'nan' or isin == '': continue
                    if 'Closing price' in row:
                        prices[isin] = float(row['Closing price'])
                    elif 'Closing value' in row and 'Quantity' in row:
                        prices[isin] = float(row['Closing value']) / float(row['Quantity'])
    
    mf_h_file = BASE_PATH + mf_h_files[0]
    if os.path.exists(mf_h_file):
        df_mf_all = pd.read_excel(mf_h_file, header=None)
        header_idx = -1
        for i, row in df_mf_all.iterrows():
            if 'Scheme Name' in [str(v).strip() for v in row.values]:
                header_idx = i
                break
        if header_idx != -1:
            df_mf = pd.read_excel(mf_h_file, header=header_idx)
            df_mf.columns = [str(c).strip() for c in df_mf.columns]
            for _, row in df_mf.iterrows():
                name = str(row.get('Scheme Name')).strip()
                if name == 'nan' or name == '': continue
                if 'NAV' in row:
                    prices[name] = float(row['NAV'])
                elif 'Current Value' in row and 'Units' in row:
                    prices[name] = float(row['Current Value']) / float(row['Units'])
    return prices

def get_prices(assets, start_date, end_date):
    price_map = {}
    conn = sqlite3.connect(DB_FILE)
    ticker_to_isin = {
        "HDFCGOLD": "INF179KC1981",
        "CHEMICAL": "INF174KA1XV0",
        "MODEFENCE": "INF247L01DJ0",
        "PHARMABEES": "INF204KC1089",
        "PSUBNKIETF": "INF109KC10S8",
        "NIFTYBEES": "INF204KB14I2",
        "MIDCAPIETF": "INF109KC11W8",
        "FMCGIETF": "INF109KC19V3",
        "EBBETF0433": "INF754K01QX0",
        "TATSILV": "INF277KA1984",
        "SILVERIETF": "INF109KC1Y56",
        "GOLDIETF": "INF109KC1NT3",
        "SETFNN50": "INF109K01Z71",
        "BANKBEES": "INF204KB15I0"
    }
    
    # Manual Name-to-Code mapping for Mutual Funds
    mf_name_map = {
        "HDFC Mid Cap Fund Direct Growth": "118989",
        "Kotak Arbitrage Fund Direct Growth": "119771",
        "INF109KC19V3": "149072"
    }

    for asset in assets:
        aid = asset['id']
        search_id = mf_name_map.get(aid, aid)
        if asset['source'] == 'MF_DB':
            query = "SELECT n.date, n.nav FROM nav_history n JOIN schemes s ON n.scheme_code = s.scheme_code WHERE s.scheme_code = ? OR s.scheme_name = ? OR s.isin_growth = ? OR s.isin_div = ?"
            df = pd.read_sql_query(query, conn, params=(search_id, search_id, search_id, search_id))
            for _, r in df.iterrows():
                d = str(r['date'])[:10]
                price_map.setdefault(d, {})[aid] = float(r['nav'])
    conn.close()
    
    for csv_file in [ETF_FILE, STOCK_FILE]:
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            date_col = df.columns[0]
            for _, row in df.iterrows():
                try: d = pd.to_datetime(row[date_col]).strftime('%Y-%m-%d')
                except: continue
                for col in df.columns[1:]:
                    if col.endswith('_Close'):
                        ticker = col.replace('_Close', '').replace('.NS', '')
                        key = ticker_to_isin.get(ticker, ticker)
                        price_map.setdefault(d, {})[key] = float(row[col])
    
    latest_prices = get_latest_holdings_prices()
    
    # Ensure every date in the forced range exists in price_map
    curr = start_date
    while curr <= end_date:
        d_str = curr.strftime('%Y-%m-%d')
        if d_str not in price_map:
            price_map[d_str] = {}
        curr += timedelta(days=1)
    
    all_dates = sorted(price_map.keys())
    if not all_dates: return {}
    last_date = all_dates[-1]
    if latest_prices:
        for k, v in latest_prices.items():
            price_map[last_date][k] = v

    asset_ids = list(set([a['id'] for a in assets] + list(latest_prices.keys())))
    sorted_all_dates = sorted(price_map.keys())
    for aid in asset_ids:
        last_val = None
        for d in sorted_all_dates:
            if price_map[d].get(aid, 0) > 0:
                last_val = price_map[d][aid]
            elif last_val is not None:
                price_map[d][aid] = last_val
        
        # Backward fill for dates before the first price point
        first_val = None
        for d in reversed(sorted_all_dates):
            if price_map[d].get(aid, 0) > 0:
                first_val = price_map[d][aid]
            elif first_val is not None:
                price_map[d][aid] = first_val
    return price_map

def main():
    transactions = load_transactions()
    if not transactions: return
    
    assets = []
    seen = set()
    for tx in transactions:
        if tx['id'] not in seen:
            assets.append({'id': tx['id'], 'source': tx['source'], 'name': tx['name']})
            seen.add(tx['id'])

    # Add model portfolio assets to ensure their prices are fetched
    model_assets_meta = [
        {'id': 'INF204KB14I2', 'source': 'STOCK', 'name': 'Nifty 50 ETF'},
        {'id': 'INF109KC11W8', 'source': 'STOCK', 'name': 'Midcap ETF'},
        {'id': '147946', 'source': 'MF_DB', 'name': 'Bandhan Small Cap Fund'},
        {'id': '119771', 'source': 'MF_DB', 'name': 'Kotak Arbitrage Fund'},
        {'id': 'INF179KC1981', 'source': 'STOCK', 'name': 'HDFC Gold ETF'},
        {'id': 'INF109KC1Y56', 'source': 'STOCK', 'name': 'Silver ETF'}
    ]
    for ma in model_assets_meta:
        if ma['id'] not in seen:
            assets.append(ma)
            seen.add(ma['id'])
    
    # Forced Analysis Period: April 1, 2025 to May 19, 2026
    start_date = datetime(2025, 4, 1)
    end_date = datetime(2026, 5, 19)
    
    price_map = get_prices(assets, start_date, end_date)
    if not price_map: return
    
    all_dates = sorted([d for d in price_map.keys() if start_date <= datetime.strptime(d, '%Y-%m-%d') <= end_date])
    if not all_dates: return

    current_holdings = defaultdict(float)
    daily_returns = []
    daily_values = []
    cash_flows = []
    tx_df = pd.DataFrame(transactions)
    tx_df['date_str'] = tx_df['date'].dt.strftime('%Y-%m-%d')

    # Configuration for Exception Days (e.g., Budget Day or days with partial reporting)
    # These days will be treated as flat holidays (market return = 0) even if some prices exist.
    EXCEPTION_HOLIDAYS = ["2026-02-01"]

    prev_val = 0
    for i, d in enumerate(all_dates):
        todays_tx = tx_df[tx_df['date_str'] == d]
        buy_amt = 0
        sell_amt = 0
        
        for _, tx in todays_tx.iterrows():
            amt = tx['qty'] * tx['price']
            if tx['type'] == 'buy':
                current_holdings[tx['id']] += tx['qty']
                cash_flows.append((datetime.strptime(d, '%Y-%m-%d'), -amt))
                buy_amt += amt
            else:
                current_holdings[tx['id']] -= tx['qty']
                cash_flows.append((datetime.strptime(d, '%Y-%m-%d'), amt))
                sell_amt += amt

        # Closing value at the end of day d
        day_val = sum(qty * price_map[d].get(aid, 0) for aid, qty in current_holdings.items() if qty > 0.001)
        
        # If it's a weekend/holiday (day_val=0) OR a specifically marked exception day, 
        # force the portfolio valuation to be neutral (market return = 0)
        if (day_val == 0 or d in EXCEPTION_HOLIDAYS) and prev_val > 0:
            # Neutral value = (prev_val + buy_amt) - sell_amt
            day_val = prev_val + buy_amt - sell_amt
            
        daily_values.append(day_val)

        # Base for return calculation is previous value + today's buys
        base = prev_val + buy_amt
        if base > 0:
            # (Ending Value + Cash from Sells) / (Starting Value + Cash for Buys) - 1
            day_return = (day_val + sell_amt - base) / base
            daily_returns.append(day_return)
        else:
            daily_returns.append(0)
            
        prev_val = day_val
    
    last_date = all_dates[-1]
    final_value = daily_values[-1]
    
    # Consolidate and Print Cash Flows for debugging
    temp_cf = list(cash_flows)
    temp_cf.append((datetime.strptime(last_date, '%Y-%m-%d'), final_value))
    consolidated_cf = defaultdict(float)
    for dt, amt in temp_cf: consolidated_cf[dt] += amt
    cf_list = sorted(consolidated_cf.items())
    
    print("\nDEBUG: Consolidated Cash Flows for XIRR:")
    for dt, amt in cf_list:
        print(f"  {dt.strftime('%Y-%m-%d')}: {amt:,.2f}")
    
    try: portfolio_xirr = xirr([c[0] for c in cf_list], [c[1] for c in cf_list])
    except: portfolio_xirr = 0
    
    clean_returns = [r for r in daily_returns if np.isfinite(r) and abs(r) > 1e-6]
    volatility = np.std(clean_returns) * 100 if clean_returns else 0
    
    portfolio_nav = [100.0]
    for r in daily_returns: portfolio_nav.append(portfolio_nav[-1] * (1 + r))

    # NAV and Plotting Alignment
    # Start the plot from the date of the first actual transaction
    first_tx_date = tx_df['date'].min().strftime('%Y-%m-%d')
    start_idx = 0
    try: start_idx = all_dates.index(first_tx_date)
    except: start_idx = 0
    
    trimmed_dates = all_dates[start_idx:]
    trimmed_values = daily_values[start_idx:]
    # Portfolio NAV is already calculated globally; slice it to start from first_tx
    trimmed_nav = portfolio_nav[1:][start_idx:]
    # Reset Portfolio NAV to 100 at the first transaction date
    if trimmed_nav:
        nav_base = trimmed_nav[0]
        trimmed_nav = [(v / nav_base) * 100 for v in trimmed_nav]

    # Model Portfolio Calculation (10,000,000 start, fixed quantities)
    model_config = {
        "INF204KB14I2": 0.30,  # Nifty 50
        "INF109KC11W8": 0.20,  # Midcap
        "147946": 0.10,        # Bandhan Small Cap
        "119771": 0.30,        # Kotak Arbitrage
        "INF179KC1981": 0.07,  # Gold
        "INF109KC1Y56": 0.03   # Silver
    }
    model_nav = []
    if trimmed_dates:
        d_start = trimmed_dates[0]
        initial_corpus = 10000000.0
        model_qtys = {}
        for aid, weight in model_config.items():
            price = price_map[d_start].get(aid, 0)
            if price > 0:
                model_qtys[aid] = (initial_corpus * weight) / price
            else:
                model_qtys[aid] = 0
        
        for d in trimmed_dates:
            day_val = sum(model_qtys[aid] * price_map[d].get(aid, 0) for aid in model_config)
            model_nav.append((day_val / initial_corpus) * 100)

    benchmark_nav = []
    try:
        nifty_file = "Gemini/personal finance accounting/nifty50_index.csv"
        if os.path.exists(nifty_file):
            df_nifty = pd.read_csv(nifty_file, header=[0, 1], index_col=0)
            df_nifty.index = pd.to_datetime(df_nifty.index).strftime('%Y-%m-%d')
            # Extract the Close column for ^NSEI
            bench_map = df_nifty['Close']['^NSEI'].to_dict()
            
            last_bench_val = None
            for d in trimmed_dates:
                val = bench_map.get(d, last_bench_val)
                if val is not None:
                    benchmark_nav.append(val)
                    last_bench_val = val
                else: benchmark_nav.append(0)
                
            if benchmark_nav and benchmark_nav[0] > 0:
                start_bench = benchmark_nav[0]
                benchmark_nav = [(v / start_bench) * 100 for v in benchmark_nav]
        else:
            benchmark_nav = [0] * len(trimmed_dates)
    except Exception as e:
        print(f"Error fetching benchmark: {e}")
        benchmark_nav = [0] * len(trimmed_dates)

    def sanitize(val):
        if isinstance(val, float) and (np.isnan(val) or np.isinf(val)): return 0
        return val

    dashboard_data = {
        "metrics": {
            "xirr": sanitize(round(portfolio_xirr * 100, 2)),
            "daily_volatility": sanitize(round(volatility, 4)),
            "annualized_volatility": sanitize(round(volatility * np.sqrt(252), 2)),
            "final_value": sanitize(round(final_value, 2)),
            "period": f"{trimmed_dates[0]} to {trimmed_dates[-1]}"
        },
        "history": {
            "dates": trimmed_dates,
            "nav": [sanitize(round(v, 2)) for v in trimmed_nav],
            "benchmark": [sanitize(round(v, 2)) for v in benchmark_nav],
            "model_nav": [sanitize(round(v, 2)) for v in model_nav],
            "total_value": [sanitize(round(v, 2)) for v in trimmed_values]
        },
        "assets": [
            {"id": aid, "name": next((a['name'] for a in assets if a['id'] == aid), aid), "value": sanitize(round(qty * price_map[last_date].get(aid, 0), 2))}
            for aid, qty in current_holdings.items() if qty > 0.001
        ]
    }
    
    with open('Gemini/personal finance accounting/dashboard_data.json', 'w') as f:
        json.dump(dashboard_data, f, indent=4)
    
    # Also update the deploy folder if it exists
    deploy_path = 'Gemini/personal finance accounting/deploy/dashboard_data.json'
    with open(deploy_path, 'w') as f:
        json.dump(dashboard_data, f, indent=4)
    
    print(f"Dashboard data successfully stabilized and exported to root and deploy/.")

    print("\n" + "="*50)
    print("PORTFOLIO PERFORMANCE & VOLATILITY REPORT")
    print("="*50)
    print(f"Analysis Period:   {all_dates[0]} to {all_dates[-1]}")
    print(f"Final Portfolio Value: ₹{final_value:,.2f}")
    print(f"Overall XIRR (Annualized): {portfolio_xirr*100:.2f}%")
    print(f"Daily Volatility (Std Dev): {volatility:.4f}%")
    if clean_returns:
        print(f"Annualized Volatility:     {volatility * np.sqrt(252):.2f}%")
    print(f"Total Trading Days Analyzed: {len(clean_returns)}")
    print("="*50)

import json
if __name__ == "__main__":
    main()
