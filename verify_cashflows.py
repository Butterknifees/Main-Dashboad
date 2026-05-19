import pandas as pd
import os
from datetime import datetime
import csv
from collections import defaultdict

BASE_PATH = "Gemini/personal finance accounting/"

def analyze_raw_cashflows():
    all_tx = []
    seen_tx = set()

    def add_tx(tx):
        sig = (tx['date'].strftime('%Y-%m-%d'), tx['id'], round(tx['qty'], 4), round(tx['price'], 4), tx['type'])
        if sig not in seen_tx:
            seen_tx.add(sig)
            all_tx.append(tx)

    # Load all sources
    try:
        with open(BASE_PATH + 'tradebook-IZP332-MF.csv', mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                add_tx({'date': datetime.strptime(row['trade_date'], '%Y-%m-%d'), 'id': row['isin'], 'qty': float(row['quantity']), 'price': float(row['price']), 'type': row['trade_type'].lower()})
        
        for f in ['Mutual_Funds_Order_History_01-04-2025_04-05-2026.xlsx', 'Mutual_Funds_Order_History_01-04-2026_17-05-2026.xlsx']:
            if os.path.exists(BASE_PATH + f):
                df = pd.read_excel(BASE_PATH + f, header=11).dropna(how='all')
                for _, row in df.iterrows():
                    if pd.isna(row['Scheme Name']): continue
                    amt = float(str(row['Amount']).replace(',', ''))
                    qty = float(row['Units'])
                    add_tx({'date': pd.to_datetime(row['Date']), 'id': str(row['Scheme Name']).strip(), 'qty': qty, 'price': amt/qty, 'type': 'buy' if str(row['Transaction Type']).upper() in ['PURCHASE', 'SIP'] else 'sell'})

        for f in ['Stocks_Order_History_3181700510_01-04-2025_03-05-2026.xlsx', 'Stocks_Order_History_3181700510_01-04-2026_16-05-2026.xlsx']:
            if os.path.exists(BASE_PATH + f):
                df = pd.read_excel(BASE_PATH + f, header=5)
                for _, row in df.iterrows():
                    if pd.isna(row['Stock name']) or row['Order status'] != 'Executed': continue
                    qty = float(row['Quantity'])
                    val = float(row['Value'])
                    add_tx({'date': pd.to_datetime(row['Execution date and time'], dayfirst=True), 'id': str(row['ISIN']).strip(), 'qty': qty, 'price': val/qty, 'type': row['Type'].lower()})
    except Exception as e:
        print(f"Error loading: {e}")

    total_invested = 0
    total_withdrawn = 0
    for tx in all_tx:
        amt = tx['qty'] * tx['price']
        if tx['type'] == 'buy':
            total_invested += amt
        else:
            total_withdrawn += amt
    
    print(f"Total Invested (Buys): ₹{total_invested:,.2f}")
    print(f"Total Withdrawn (Sells): ₹{total_withdrawn:,.2f}")
    print(f"Net Principal Invested: ₹{total_invested - total_withdrawn:,.2f}")

if __name__ == "__main__":
    analyze_raw_cashflows()
