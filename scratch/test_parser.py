import pandas as pd
import math

def find_header_row(rows, file_type):
    best_idx = 0
    max_score = -1
    for i, row in enumerate(rows[:50]):
        row_str = [str(cell).strip().lower() for cell in row if not pd.isna(cell)]
        score = 0
        if file_type == 'holdings':
            for cell in row_str:
                if cell == 'isin': score += 3
                elif 'isin' in cell: score += 1.5
                if cell == 'symbol': score += 2
                elif 'symbol' in cell: score += 1
                if cell in ['scheme name', 'stock name']: score += 3
                elif any(x in cell for x in ['scheme', 'stock', 'name']): score += 1
                if cell in ['quantity', 'qty', 'units']: score += 3
                elif any(x in cell for x in ['quantity', 'qty', 'units', 'shares']): score += 1
                if cell in ['avg price', 'average price', 'average buy price', 'avg buy price']: score += 3
                elif any(x in cell for x in ['price', 'avg', 'average', 'cost', 'nav']): score += 1
                if cell in ['closing price', 'closing value']: score += 2
        else:
            for cell in row_str:
                if cell == 'isin': score += 3
                elif 'isin' in cell: score += 1.5
                if cell == 'symbol': score += 2
                elif 'symbol' in cell: score += 1
                if cell in ['scheme name', 'stock name']: score += 3
                elif any(x in cell for x in ['scheme', 'stock', 'name']): score += 1
                if cell in ['quantity', 'qty', 'units']: score += 3
                elif any(x in cell for x in ['quantity', 'qty', 'units']): score += 1
                if cell in ['price', 'rate', 'nav']: score += 3
                elif any(x in cell for x in ['price', 'rate', 'nav', 'value', 'amount']): score += 1
                if cell in ['date', 'execution date', 'trade date', 'execution date and time']: score += 3
                elif any(x in cell for x in ['date', 'time']): score += 1
                if cell in ['type', 'transaction type', 'buy/sell', 'action']: score += 2
                elif any(x in cell for x in ['type', 'action', 'side', 'buy', 'sell']): score += 1
        
        if score > max_score:
            max_score = score
            best_idx = i
            
    return best_idx if max_score >= 3 else 0

def auto_detect_mapping(file_type, headers):
    headers_lower = [str(h).lower() for h in headers]
    
    def find_index(preds):
        for idx, h in enumerate(headers_lower):
            if any(pred(h) for pred in preds):
                return idx
        return -1

    if file_type == 'holdings':
        id_col = find_index([lambda s: s == 'isin', lambda s: s == 'scheme code'])
        if id_col == -1:
            id_col = find_index([lambda s: 'isin' in s, lambda s: 'scheme code' in s])
        if id_col == -1:
            id_col = find_index([lambda s: 'instrument' in s, lambda s: 'symbol' in s, lambda s: 'code' in s])
        if id_col == -1:
            id_col = find_index([lambda s: 'name' in s])
            
        name_col = find_index([lambda s: 'scheme name' in s, lambda s: 'stock name' in s, lambda s: 'name' in s, lambda s: 'description' in s, lambda s: s == 'symbol'])
        qty_col = find_index([lambda s: 'qty' in s, lambda s: 'quantity' in s, lambda s: 'units' in s, lambda s: 'shares' in s])
        price_col = find_index([lambda s: s == 'average buy price', lambda s: s == 'avg buy price', lambda s: s == 'avg price', lambda s: 'price' in s and 'closing' not in s and 'buy value' not in s, lambda s: 'avg' in s, lambda s: 'average' in s, lambda s: 'cost' in s, lambda s: 'nav' in s])
        value_col = find_index([lambda s: 'buy value' in s, lambda s: 'closing value' in s, lambda s: 'invested value' in s, lambda s: s == 'value', lambda s: 'value' in s, lambda s: s == 'amount', lambda s: 'amount' in s, lambda s: 'total' in s])
        return {'id': id_col, 'name': name_col, 'qty': qty_col, 'price': price_col, 'value': value_col}
    else:
        date_col = find_index([lambda s: 'date' in s, lambda s: 'time' in s])
        
        id_col = find_index([lambda s: s == 'isin', lambda s: s == 'scheme code'])
        if id_col == -1:
            id_col = find_index([lambda s: 'isin' in s, lambda s: 'scheme code' in s])
        if id_col == -1:
            id_col = find_index([lambda s: 'instrument' in s, lambda s: 'symbol' in s, lambda s: 'code' in s])
        if id_col == -1:
            id_col = find_index([lambda s: 'name' in s])
            
        name_col = find_index([lambda s: 'scheme name' in s, lambda s: 'stock name' in s, lambda s: 'name' in s, lambda s: 'description' in s, lambda s: s == 'symbol'])
        qty_col = find_index([lambda s: 'qty' in s, lambda s: 'quantity' in s, lambda s: 'units' in s])
        price_col = find_index([lambda s: 'price' in s and 'total' not in s and 'value' not in s, lambda s: 'rate' in s, lambda s: 'nav' in s])
        type_col = find_index([lambda s: 'type' in s, lambda s: 'action' in s, lambda s: 'buy/sell' in s, lambda s: 'side' in s, lambda s: s == 'trade_type'])
        value_col = find_index([lambda s: s == 'value', lambda s: 'value' in s, lambda s: s == 'amount', lambda s: 'amount' in s, lambda s: 'total' in s])
        return {'date': date_col, 'id': id_col, 'name': name_col, 'qty': qty_col, 'price': price_col, 'type': type_col, 'value': value_col}

def normalize_file_rows(file_type, headers, rows, mapping):
    normalized = []
    for r in rows:
        if file_type == 'holdings':
            aid = str(r[mapping['id']]).strip() if mapping['id'] != -1 and not pd.isna(r[mapping['id']]) else ''
            name = str(r[mapping['name']]).strip() if mapping['name'] != -1 and not pd.isna(r[mapping['name']]) else ''
            qty_str = str(r[mapping['qty']]).replace(',', '') if mapping['qty'] != -1 and not pd.isna(r[mapping['qty']]) else ''
            price_str = str(r[mapping['price']]).replace(',', '') if mapping['price'] != -1 and not pd.isna(r[mapping['price']]) else ''
            value_str = str(r[mapping['value']]).replace(',', '') if mapping['value'] != -1 and not pd.isna(r[mapping['value']]) else ''
            
            try: qty = float(qty_str)
            except: qty = float('nan')
            
            try: price = float(price_str)
            except: price = float('nan')
            
            if math.isnan(price) and not math.isnan(qty) and qty > 0 and value_str:
                try:
                    total_val = float(value_str)
                    price = total_val / qty
                except:
                    pass
            
            # Fallback to name as ID
            if not aid and name:
                aid = name
            
            if aid and not math.isnan(qty) and qty > 0 and not math.isnan(price):
                if aid.lower() == 'isin' or 'scheme name' in aid.lower() or 'stock name' in aid.lower():
                    continue
                normalized.append({'id': aid, 'name': name, 'qty': qty, 'price': price})
        else:
            raw_date = str(r[mapping['date']]).strip() if mapping['date'] != -1 and not pd.isna(r[mapping['date']]) else ''
            aid = str(r[mapping['id']]).strip() if mapping['id'] != -1 and not pd.isna(r[mapping['id']]) else ''
            name = str(r[mapping['name']]).strip() if mapping['name'] != -1 and not pd.isna(r[mapping['name']]) else ''
            qty_str = str(r[mapping['qty']]).replace(',', '') if mapping['qty'] != -1 and not pd.isna(r[mapping['qty']]) else ''
            price_str = str(r[mapping['price']]).replace(',', '') if mapping['price'] != -1 and not pd.isna(r[mapping['price']]) else ''
            value_str = str(r[mapping['value']]).replace(',', '') if mapping['value'] != -1 and not pd.isna(r[mapping['value']]) else ''
            raw_type = str(r[mapping['type']]).strip().lower() if mapping['type'] != -1 and not pd.isna(r[mapping['type']]) else 'buy'
            
            try: qty = float(qty_str)
            except: qty = float('nan')
            
            try: price = float(price_str)
            except: price = float('nan')
            
            if math.isnan(price) and not math.isnan(qty) and qty > 0 and value_str:
                try:
                    total_val = float(value_str)
                    price = total_val / qty
                except:
                    pass
            
            # Fallback to name as ID
            if not aid and name:
                aid = name
            
            if aid and raw_date and not math.isnan(qty) and qty > 0 and not math.isnan(price):
                if aid.lower() == 'isin' or 'scheme name' in aid.lower() or 'stock name' in aid.lower():
                    continue
                
                # Simple date normalizer mimicking JS Date behavior
                date_str = ''
                try:
                    dt = pd.to_datetime(raw_date)
                    date_str = dt.strftime('%Y-%m-%d')
                except:
                    pass
                
                tx_type = 'buy'
                if any(x in raw_type for x in ['sell', 'redemption', 'payout', 'redeem']):
                    tx_type = 'sell'
                    
                if date_str:
                    normalized.append({'date': date_str, 'id': aid, 'name': name, 'qty': qty, 'price': price, 'type': tx_type})
    return normalized

def run_test_on_file(filepath, file_type):
    df = pd.read_excel(filepath, header=None)
    raw_rows = df.values.tolist()
    filtered_rows = [r for r in raw_rows if any(not pd.isna(x) and x != '' for x in r)]

    header_idx = find_header_row(filtered_rows, file_type)
    headers = [str(x) for x in filtered_rows[header_idx]]
    data_rows = filtered_rows[header_idx + 1:]
    mapping = auto_detect_mapping(file_type, headers)
    normalized = normalize_file_rows(file_type, headers, data_rows, mapping)

    print(f"\n--- Testing: {filepath} ---")
    print("Headers index:", header_idx)
    print("Headers:", headers)
    print("Detected mapping:", mapping)
    print("Total rows parsed:", len(normalized))
    if normalized:
        print("First 3 rows:")
        for row in normalized[:3]:
            print(row)

# Run tests
run_test_on_file('./data/Stocks_Order_History_3181700510_01-04-2025_18-05-2026.xlsx', 'transactions')
run_test_on_file('./data/Mutual_Funds_Order_History_01-04-2025_19-05-2026.xlsx', 'transactions')
