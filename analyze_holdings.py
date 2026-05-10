import csv
from datetime import datetime
from collections import defaultdict

def analyze_trades(file_path):
    holdings = defaultdict(float)
    isin_to_symbol = {}
    cash_flows = []

    with open(file_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            isin = row['isin']
            symbol = row['symbol']
            date = datetime.strptime(row['trade_date'], '%Y-%m-%d')
            quantity = float(row['quantity'])
            price = float(row['price'])
            trade_type = row['trade_type'].lower()
            
            isin_to_symbol[isin] = symbol
            
            amount = quantity * price
            if trade_type == 'buy':
                holdings[isin] += quantity
                cash_flows.append((date, -amount))
            elif trade_type == 'sell':
                holdings[isin] -= quantity
                cash_flows.append((date, amount))

    open_positions = {isin: qty for isin, qty in holdings.items() if qty > 0.0001}
    
    print("Open Positions as of March 31, 2026:")
    for isin, qty in open_positions.items():
        print(f"ISIN: {isin} | Symbol: {isin_to_symbol[isin]} | Quantity: {qty:.4f}")
    
    return open_positions, cash_flows, isin_to_symbol

if __name__ == "__main__":
    file_path = 'tradebook-IZP332-MF.csv'
    analyze_trades(file_path)
