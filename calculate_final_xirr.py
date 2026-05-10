import pandas as pd
import csv
from datetime import datetime
from collections import defaultdict
import numpy as np

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

def parse_csv_tradebook(file_path):
    cash_flows = []
    holdings = defaultdict(float)
    names = {}
    with open(file_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_key = row['isin']
            names[id_key] = row['symbol']
            date = datetime.strptime(row['trade_date'], '%Y-%m-%d')
            qty = float(row['quantity'])
            price = float(row['price'])
            if row['trade_type'].lower() == 'buy':
                cash_flows.append((date, -qty * price))
                holdings[id_key] += qty
            else:
                cash_flows.append((date, qty * price))
                holdings[id_key] -= qty
    return cash_flows, holdings, names

def parse_mf_excel(file_path):
    df = pd.read_excel(file_path, header=11).dropna(how='all')
    cash_flows = []
    holdings = defaultdict(float)
    names = {}
    for _, row in df.iterrows():
        if pd.isna(row['Scheme Name']): continue
        name = row['Scheme Name'].strip()
        date = pd.to_datetime(row['Date'])
        amt_str = str(row['Amount']).replace(',', '')
        amount = float(amt_str)
        qty = float(row['Units'])
        names[name] = name
        if str(row['Transaction Type']).upper() in ['PURCHASE', 'SIP']:
            cash_flows.append((date, -amount))
            holdings[name] += qty
        elif str(row['Transaction Type']).upper() in ['REDEMPTION', 'SELL']:
            cash_flows.append((date, amount))
            holdings[name] -= qty
    return cash_flows, holdings, names

def parse_stocks_excel(file_path):
    df = pd.read_excel(file_path, header=5)
    cash_flows = []
    holdings = defaultdict(float)
    names = {}
    for _, row in df.iterrows():
        if pd.isna(row['Stock name']) or row['Order status'] != 'Executed': continue
        isin = row['ISIN']
        name = row['Stock name']
        names[isin] = name
        date = pd.to_datetime(row['Execution date and time'], dayfirst=True)
        qty = float(row['Quantity'])
        amount = float(row['Value'])
        if str(row['Type']).upper() == 'BUY':
            cash_flows.append((date, -amount))
            holdings[isin] += qty
        elif str(row['Type']).upper() == 'SELL':
            cash_flows.append((date, amount))
            holdings[isin] -= qty
    return cash_flows, holdings, names

def get_latest_prices(stk_h_file, mf_h_file):
    prices = {}
    
    # Stocks Prices
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
    
    # MF Prices
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

def main():
    base_path = 'Gemini/personal finance accounting/'
    csv_file = base_path + 'tradebook-IZP332-MF.csv'
    mf_order_file = base_path + 'Mutual_Funds_Order_History_01-04-2025_04-05-2026.xlsx'
    stk_order_file = base_path + 'Stocks_Order_History_3181700510_01-04-2025_03-05-2026.xlsx'
    stk_h_file = base_path + 'Stocks_Holdings_Statement_3181700510_03-05-2026.xlsx'
    mf_h_file = base_path + 'Mutual_Funds_3181700510_04-05-2026_04-05-2026.xlsx'
    
    all_cash_flows = []
    total_holdings = defaultdict(float)
    all_names = {}

    # 1. Parse Transactions
    cf1, h1, n1 = parse_csv_tradebook(csv_file)
    cf2, h2, n2 = parse_mf_excel(mf_order_file)
    cf3, h3, n3 = parse_stocks_excel(stk_order_file)
    
    for cf in [cf1, cf2, cf3]: all_cash_flows.extend(cf)
    for h in [h1, h2, h3]:
        for k, v in h.items(): total_holdings[k] += v
    all_names.update(n1); all_names.update(n2); all_names.update(n3)

    # 2. Get Prices
    prices = get_latest_prices(stk_h_file, mf_h_file)
    # Manual overrides from user
    prices['INF179K01VX0'] = 46.5583
    prices['INF109K012M7'] = 252.235
    
    # 3. Calculate Terminal Value
    terminal_value = 0
    calculation_date = datetime(2026, 5, 4)
    print("--- Final Portfolio Holdings and Values ---")
    for key, qty in total_holdings.items():
        if qty > 0.001:
            price = prices.get(key)
            if price:
                value = qty * price
                terminal_value += value
                print(f"{all_names[key]:<50} | Qty: {qty:>10.4f} | Price: {price:>8.2f} | Value: {value:>10.2f}")
            else:
                print(f"WARNING: No price found for {all_names[key]} ({key})")
    
    print(f"\nTotal Terminal Value: {terminal_value:.2f}")
    
    all_cash_flows.append((calculation_date, terminal_value))
    all_cash_flows.sort(key=lambda x: x[0])
    
    dates = [cf[0] for cf in all_cash_flows]
    payments = [cf[1] for cf in all_cash_flows]
    
    try:
        final_irr = xirr(dates, payments)
        print(f"\nFinal Consolidated Portfolio IRR (Annualized): {final_irr * 100:.2f}%")
    except Exception as e:
        print(f"Error calculating XIRR: {e}")

if __name__ == "__main__":
    main()
