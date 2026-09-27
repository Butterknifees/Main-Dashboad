#!/usr/bin/env python3
"""
Hisaab Automated Sync Pipeline
Runs the complete data refresh:
1. Ingests & discovers any newly added Stock/MF Excel sheets or CSV tradebooks in data/
2. Fetches latest stock/ETF prices from Yahoo Finance
3. Fetches latest AMFI NAVs for mutual funds
4. Recalculates full portfolio analytics, XIRR, Sharpe, volatility
5. Generates dashboard_data.json and simulator_data.json
6. Syncs database and caches to portfolio-data repository
"""

import os
import sys
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIVATE_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "portfolio-data"))
PYTHON_BIN = sys.executable

def run_step(description, script_name):
    print(f"\n{'='*50}\n▶ {description} ({script_name})\n{'='*50}")
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"Error: {script_name} not found at {script_path}")
        return False
    
    res = subprocess.run([PYTHON_BIN, script_path], cwd=BASE_DIR)
    if res.returncode != 0:
        print(f"Warning: {script_name} exited with code {res.returncode}")
        return False
    return True

def sync_to_private_repo():
    print(f"\n{'='*50}\n▶ Syncing backfilled data to portfolio-data repository\n{'='*50}")
    if not os.path.exists(PRIVATE_DATA_DIR):
        print("Note: portfolio-data directory not found locally; skipping private repo file copy.")
        return

    files_to_sync = [
        "nav_data.db",
        "etf_historical_data.csv",
        "nifty_universe_historical_data.csv"
    ]
    for f in files_to_sync:
        src = os.path.join(BASE_DIR, f)
        dst = os.path.join(PRIVATE_DATA_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  ✓ Copied {f} to portfolio-data repo")

    # Sync data/ folder transactions to private-data/data/
    src_data = os.path.join(BASE_DIR, "data")
    dst_data = os.path.join(PRIVATE_DATA_DIR, "data")
    if os.path.exists(src_data):
        os.makedirs(dst_data, exist_ok=True)
        for item in os.listdir(src_data):
            s = os.path.join(src_data, item)
            d = os.path.join(dst_data, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
        print("  ✓ Synced all transaction spreadsheets to portfolio-data/data/")

def main():
    print("🚀 Starting Hisaab Portfolio Sync Engine...")
    
    # 1. Fetch ETF & stock prices
    run_step("1. Updating ETF & Stock Prices via Yahoo Finance", "fetch_etf_history.py")
    
    # 2. Fetch Nifty Universe prices
    run_step("2. Updating Nifty Universe Prices", "fetch_nifty_universe.py")
    
    # 3. Update Mutual Fund NAVs from AMFI
    run_step("3. Updating Mutual Fund NAVs from AMFI", "daily_tracker.py")
    
    # 4. Sync TRI benchmarks
    run_step("4. Syncing TRI Benchmark Indices", "sync_tri_benchmarks.py")
    
    # 5. Run full portfolio performance & deduplication
    run_step("5. Ingesting Transactions & Recalculating Performance", "portfolio_analysis_v2.py")
    
    # 6. Prepare backtest simulator datasets
    run_step("6. Preparing Backtest Simulator Datasets", "prepare_simulator.py")
    
    # 7. Mirror to private repo folder
    sync_to_private_repo()
    
    print("\n🎉 Portfolio Sync Completed Successfully!")

if __name__ == "__main__":
    main()
