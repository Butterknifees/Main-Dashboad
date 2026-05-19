import pandas as pd
import os

BASE_PATH = "Gemini/personal finance accounting/"

def check_mf():
    files = [
        'Mutual_Funds_Order_History_01-04-2025_04-05-2026.xlsx',
        'Mutual_Funds_Order_History_01-04-2026_17-05-2026.xlsx'
    ]
    print("MF Files:")
    for f in files:
        path = BASE_PATH + f
        if os.path.exists(path):
            df = pd.read_excel(path, header=11).dropna(how='all')
            if not df.empty and 'Date' in df.columns:
                dates = pd.to_datetime(df['Date'], errors='coerce')
                dates = dates.dropna()
                if not dates.empty:
                    print(f"  {f}: {dates.min().date()} to {dates.max().date()} ({len(df)} rows)")
                else:
                    print(f"  {f}: No valid dates found in 'Date' column")
            else:
                print(f"  {f}: Empty or missing 'Date' column")
        else:
            print(f"  {f}: File not found")

def check_stocks():
    files = [
        'Stocks_Order_History_3181700510_01-04-2025_03-05-2026.xlsx',
        'Stocks_Order_History_3181700510_01-04-2026_16-05-2026.xlsx'
    ]
    print("\nStock Files:")
    for f in files:
        path = BASE_PATH + f
        if os.path.exists(path):
            df = pd.read_excel(path, header=5)
            if not df.empty and 'Execution date and time' in df.columns:
                dates = pd.to_datetime(df['Execution date and time'], dayfirst=True, errors='coerce')
                dates = dates.dropna()
                if not dates.empty:
                    print(f"  {f}: {dates.min().date()} to {dates.max().date()} ({len(df)} rows)")
                else:
                    print(f"  {f}: No valid dates found")
            else:
                print(f"  {f}: Empty or missing 'Execution date and time' column")
        else:
            print(f"  {f}: File not found")

if __name__ == "__main__":
    check_mf()
    check_stocks()
