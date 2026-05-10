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
BASE_PATH = "Gemini/personal finance accounting/"

def xirr(dates, payments):
    def xnpv(rate, dates, payments):
        d0 = dates[0]
        return sum([p / (1.0 + rate)**((d - d0).days / 365.0) for d, p in zip(dates, payments)])

    def xnpv_derivative(rate, dates, payments):
        d0 = dates[0]
        return sum([-p * ((d - d0).days / 365.0) * (1.0 + rate)**(-((d - d0).days / 365.0) - 1.0) for d, p in zip(dates, payments)])

    rate = 0.1
    for _ in range(100):
        f = xnpv(rate, dates, payments)
        df = xnpv_derivative(rate, dates, payments)
        if abs(df) < 1e-12: break
        new_rate = rate - f / df
        if abs(new_rate - rate) < 1e-8: return new_rate
        rate = new_rate
    return rate

def load_transactions():
    all_tx = []
    # 1. CSV Tradebook
    with open(BASE_PATH + 'tradebook-IZP332-MF.csv', mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_tx.append({
                'date': datetime.strptime(row['trade_date'], '%Y-%m-%d'),
                'id': row['isin'],
                'name': row['symbol'],
                'qty': float(row['quantity']),
                'price': float(row['price']),
                'type': row['trade_type'].lower(),
                'source': 'MF_DB'
            })
    # 2. MF Excel
    df_mf = pd.read_excel(BASE_PATH + 'Mutual_Funds_Order_History_01-04-2025_04-05-2026.xlsx', header=11).dropna(how='all')
    for _, row in df_mf.iterrows():
        if pd.isna(row['Scheme Name']): continue
        name = str(row['Scheme Name']).strip()
        amt_str = str(row['Amount']).replace(',', '')
        all_tx.append({
            'date': pd.to_datetime(row['Date']),
            'id': name,
            'name': name,
            'qty': float(row['Units']),
            'price': float(amt_str) / float(row['Units']),
            'type': 'buy' if str(row['Transaction Type']).upper() in ['PURCHASE', 'SIP'] else 'sell',
            'source': 'MF_DB'
        })
    # 3. Stocks/ETFs Excel
    df_stk = pd.read_excel(BASE_PATH + 'Stocks_Order_History_3181700510_01-04-2025_03-05-2026.xlsx', header=5)
    for _, row in df_stk.iterrows():
        if pd.isna(row['Stock name']) or row['Order status'] != 'Executed': continue
        isin = str(row['ISIN']).strip()
        all_tx.append({
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
    stk_h_file = BASE_PATH + 'Stocks_Holdings_Statement_3181700510_03-05-2026.xlsx'
    mf_h_file = BASE_PATH + 'Mutual_Funds_3181700510_04-05-2026_04-05-2026.xlsx'
    
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

def get_prices(assets):
    price_map = {}
    conn = sqlite3.connect(DB_FILE)
    ticker_to_isin = {
        "HDFCGOLD": "INF179K01VX0",
        "CHEMICAL": "INF174KA1XV0",
        "MODEFENCE": "INF247L01DJ0",
        "PHARMABEES": "INF204KC1089",
        "PSUBNKIETF": "INF109KC10S8",
        "NIFTYBEES": "INF204KB14I2",
        "MIDCAPIETF": "INF109KC11W8"
    }

    # 1. Load MF NAVs
    for asset in assets:
        aid = asset['id']
        if asset['source'] == 'MF_DB':
            query = "SELECT n.date, n.nav FROM nav_history n JOIN schemes s ON n.scheme_code = s.scheme_code WHERE s.scheme_code = ? OR s.scheme_name = ? OR s.isin_growth = ? OR s.isin_div = ?"
            df = pd.read_sql_query(query, conn, params=(aid, aid, aid, aid))
            for _, r in df.iterrows():
                d = str(r['date'])[:10]
                price_map.setdefault(d, {})[aid] = float(r['nav'])
    conn.close()
    
    # 2. Load ETF/Stock Prices
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
    
    # 3. Inject latest holdings prices
    latest_prices = get_latest_holdings_prices()
    all_dates = sorted(price_map.keys())
    if not all_dates: return {}
    last_date = all_dates[-1]
    if latest_prices:
        for k, v in latest_prices.items():
            price_map[last_date][k] = v

    # --- STABILIZATION: Exhaustive Price Repair ---
    asset_ids = list(set([a['id'] for a in assets] + list(latest_prices.keys())))
    for aid in asset_ids:
        last_val = None
        for d in all_dates:
            if price_map[d].get(aid, 0) > 0:
                last_val = price_map[d][aid]
            elif last_val is not None:
                price_map[d][aid] = last_val
        first_val = None
        for d in reversed(all_dates):
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
    
    price_map = get_prices(assets)
    if not price_map: return
    
    tx_dates = [tx['date'] for tx in transactions]
    start_date = min(tx_dates)
    all_price_dates = [datetime.strptime(d, '%Y-%m-%d') for d in price_map.keys()]
    end_date = max(all_price_dates)
    
    all_dates = sorted([d for d in price_map.keys() if start_date <= datetime.strptime(d, '%Y-%m-%d') <= end_date])
    if not all_dates: return

    # Manual Overrides
    for d in all_dates:
        price_map[d]['INF179K01VX0'] = 46.5583
        price_map[d]['INF109K012M7'] = 252.235

    current_holdings = defaultdict(float)
    daily_returns = []
    daily_values = []
    cash_flows = []
    tx_df = pd.DataFrame(transactions)
    tx_df['date_str'] = tx_df['date'].dt.strftime('%Y-%m-%d')

    for i, d in enumerate(all_dates):
        todays_tx = tx_df[tx_df['date_str'] == d]
        for _, tx in todays_tx.iterrows():
            amt = tx['qty'] * tx['price']
            if tx['type'] == 'buy':
                current_holdings[tx['id']] += tx['qty']
                cash_flows.append((datetime.strptime(d, '%Y-%m-%d'), -amt))
            else:
                current_holdings[tx['id']] -= tx['qty']
                cash_flows.append((datetime.strptime(d, '%Y-%m-%d'), amt))

        day_val = sum(qty * price_map[d].get(aid, 0) for aid, qty in current_holdings.items() if qty > 0.001)
        daily_values.append(day_val)

        if i > 0:
            val_today, val_yesterday = 0, 0
            for aid, qty in current_holdings.items():
                if qty > 0.001:
                    val_today += qty * price_map[d].get(aid, 0)
                    val_yesterday += qty * price_map[all_dates[i-1]].get(aid, 0)
            
            if val_yesterday > 0: daily_returns.append((val_today / val_yesterday) - 1)
            else: daily_returns.append(0)
    
    last_date = all_dates[-1]
    final_value = daily_values[-1]
    
    temp_cf = list(cash_flows)
    temp_cf.append((datetime.strptime(last_date, '%Y-%m-%d'), final_value))
    consolidated_cf = defaultdict(float)
    for dt, amt in temp_cf: consolidated_cf[dt] += amt
    cf_list = sorted(consolidated_cf.items())
    
    clean_returns = [r for r in daily_returns if np.isfinite(r) and abs(r) > 1e-6]
    try: portfolio_xirr = xirr([c[0] for c in cf_list], [c[1] for c in cf_list])
    except: portfolio_xirr = 0
    volatility = np.std(clean_returns) * 100 if clean_returns else 0
    
    portfolio_nav = [100.0]
    for r in daily_returns: portfolio_nav.append(portfolio_nav[-1] * (1 + r))

    start_idx = 0
    for idx, val in enumerate(daily_values):
        if val > 1.0:
            start_idx = idx
            break
    
    trimmed_dates = all_dates[start_idx:]
    trimmed_values = daily_values[start_idx:]
    trimmed_nav = portfolio_nav[start_idx:]

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
            "total_value": [sanitize(round(v, 2)) for v in trimmed_values]
        },
        "assets": [
            {"id": aid, "name": next((a['name'] for a in assets if a['id'] == aid), aid), "value": sanitize(round(qty * price_map[last_date].get(aid, 0), 2))}
            for aid, qty in current_holdings.items() if qty > 0.001
        ]
    }
    
    import json
    with open(BASE_PATH + 'dashboard_data.json', 'w') as f:
        json.dump(dashboard_data, f, indent=4)
    print(f"Dashboard data successfully stabilized and exported.")

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

if __name__ == "__main__":
    main()
