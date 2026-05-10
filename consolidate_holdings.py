import pandas as pd
import csv
from datetime import datetime
from collections import defaultdict

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
        # Clean amount string "79,996" -> 79996
        amt_str = str(row['Amount']).replace(',', '')
        amount = float(amt_str)
        qty = float(row['Units'])
        
        names[name] = name
        if row['Transaction Type'].upper() in ['PURCHASE', 'SIP']:
            cash_flows.append((date, -amount))
            holdings[name] += qty
        elif row['Transaction Type'].upper() in ['REDEMPTION', 'SELL']:
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
        
        if row['Type'].upper() == 'BUY':
            cash_flows.append((date, -amount))
            holdings[isin] += qty
        elif row['Type'].upper() == 'SELL':
            cash_flows.append((date, amount))
            holdings[isin] -= qty
    return cash_flows, holdings, names

def consolidate_data():
    csv_file = 'tradebook-IZP332-MF.csv'
    mf_xlsx = 'Mutual_Funds_Order_History_01-04-2025_04-05-2026.xlsx'
    stk_xlsx = 'Stocks_Order_History_3181700510_01-04-2025_03-05-2026.xlsx'
    
    all_cash_flows = []
    total_holdings = defaultdict(float)
    all_names = {}

    # CSV
    cf1, h1, n1 = parse_csv_tradebook(csv_file)
    all_cash_flows.extend(cf1)
    for k, v in h1.items(): total_holdings[k] += v
    all_names.update(n1)
    
    # MF Excel
    cf2, h2, n2 = parse_mf_excel(mf_xlsx)
    all_cash_flows.extend(cf2)
    for k, v in h2.items(): total_holdings[k] += v
    all_names.update(n2)
    
    # Stocks Excel
    cf3, h3, n3 = parse_stocks_excel(stk_xlsx)
    all_cash_flows.extend(cf3)
    for k, v in h3.items(): total_holdings[k] += v
    all_names.update(n3)
    
    print("Open Positions (Net Quantity > 0.001):")
    for key, qty in total_holdings.items():
        if qty > 0.001:
            print(f"ID/ISIN: {key} | Name: {all_names[key]} | Qty: {qty:.4f}")

if __name__ == "__main__":
    consolidate_data()
