import csv
from datetime import datetime
import numpy as np

def xirr(dates, payments):
    """
    Calculate the Internal Rate of Return for a series of cash flows at irregular intervals.
    """
    def xnpv(rate, dates, payments):
        d0 = dates[0]
        return sum([p / (1.0 + rate)**((d - d0).days / 365.0) for d, p in zip(dates, payments)])

    def xnpv_derivative(rate, dates, payments):
        d0 = dates[0]
        return sum([-p * ((d - d0).days / 365.0) * (1.0 + rate)**(-((d - d0).days / 365.0) - 1.0) for d, p in zip(dates, payments)])

    # Newton-Raphson method
    rate = 0.1 # Initial guess
    for _ in range(100):
        f = xnpv(rate, dates, payments)
        df = xnpv_derivative(rate, dates, payments)
        if abs(df) < 1e-12:
            break
        new_rate = rate - f / df
        if abs(new_rate - rate) < 1e-8:
            return new_rate
        rate = new_rate
    return rate

def calculate_portfolio_performance(file_path, navs, end_date):
    cash_flows = []
    holdings = {}
    isin_to_symbol = {}

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
                cash_flows.append((date, -amount))
                holdings[isin] = holdings.get(isin, 0) + quantity
            else:
                cash_flows.append((date, amount))
                holdings[isin] = holdings.get(isin, 0) - quantity

    # Add terminal value as a positive cash flow
    terminal_value = 0
    for isin, qty in holdings.items():
        if qty > 0.0001:
            nav = navs.get(isin)
            if nav:
                value = qty * nav
                terminal_value += value
                print(f"Holding: {isin_to_symbol[isin]} | Qty: {qty:.4f} | NAV: {nav} | Value: {value:.2f}")
            else:
                print(f"Warning: No NAV provided for {isin} ({isin_to_symbol[isin]})")

    if terminal_value > 0:
        cash_flows.append((end_date, terminal_value))
    
    # Sort cash flows by date
    cash_flows.sort(key=lambda x: x[0])
    
    dates = [cf[0] for cf in cash_flows]
    payments = [cf[1] for cf in cash_flows]
    
    performance = xirr(dates, payments)
    return performance

if __name__ == "__main__":
    file_path = 'tradebook-IZP332-MF.csv'
    # Terminal NAVs provided by user
    nav_data = {
        'INF179K01VX0': 46.5583,
        'INF109K012M7': 252.235
    }
    calculation_date = datetime(2026, 3, 31)
    
    try:
        irr_result = calculate_portfolio_performance(file_path, nav_data, calculation_date)
        print(f"\nOverall Portfolio IRR (Annualized): {irr_result * 100:.2f}%")
    except Exception as e:
        print(f"Error calculating IRR: {e}")
