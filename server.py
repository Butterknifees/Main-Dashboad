from flask import Flask, send_from_directory, request, jsonify, Response
import os
import csv
import datetime
import subprocess

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    holdings_path = os.path.join('data', 'starting_holdings.csv')
    exists = os.path.exists(holdings_path)
    status_data = {
        'exists': exists,
        'date': None,
        'count': 0,
        'total_value': 0.0
    }
    if exists:
        try:
            with open(holdings_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    status_data['date'] = rows[0].get('date')
                    status_data['count'] = len(rows)
                    for r in rows:
                        try:
                            val = float(r.get('value') or 0)
                            if val == 0:
                                val = float(r.get('qty') or 0) * float(r.get('price') or 0)
                            status_data['total_value'] += val
                        except:
                            pass
        except Exception as e:
            status_data['error'] = str(e)
            
    return jsonify(status_data)

@app.route('/api/upload_holdings', methods=['POST'])
def upload_holdings():
    data = request.json
    if not data or 'date' not in data or 'holdings' not in data:
        return jsonify({'error': 'Invalid request payload. Must include date and holdings.'}), 400
        
    date_str = data['date']
    holdings = data['holdings']
    
    holdings_path = os.path.join('data', 'starting_holdings.csv')
    os.makedirs('data', exist_ok=True)
    
    try:
        with open(holdings_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'id', 'name', 'qty', 'price', 'value'])
            writer.writeheader()
            for h in holdings:
                writer.writerow({
                    'date': date_str,
                    'id': h['id'],
                    'name': h.get('name') or h['id'],
                    'qty': float(h['qty']),
                    'price': float(h['price']),
                    'value': float(h.get('value') or (float(h['qty']) * float(h['price'])))
                })
        return jsonify({'success': True, 'message': f'Saved starting holdings as of {date_str}.'})
    except Exception as e:
        return jsonify({'error': f'Failed to write starting holdings file: {str(e)}'}), 500

@app.route('/api/upload_transactions', methods=['POST'])
def upload_transactions():
    data = request.json
    if not data or 'transactions' not in data:
        return jsonify({'error': 'Invalid request payload. Must include transactions.'}), 400
        
    txs = data['transactions']
    if not txs:
        return jsonify({'success': True, 'message': 'No transactions uploaded.'})
        
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'tradebook-uploaded-{timestamp}.csv'
    dir_path = os.path.join('data', 'appending')
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)
    
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['symbol', 'isin', 'trade_date', 'exchange', 'segment', 'series', 'trade_type', 'auction', 'quantity', 'price']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for t in txs:
                writer.writerow({
                    'symbol': t.get('name') or t['id'],
                    'isin': t['id'],
                    'trade_date': t['date'],
                    'exchange': t.get('exchange') or 'BSE',
                    'segment': t.get('segment') or 'MF',
                    'series': t.get('series') or '',
                    'trade_type': t['type'].lower(),
                    'auction': 'false',
                    'quantity': float(t['qty']),
                    'price': float(t['price'])
                })
        return jsonify({'success': True, 'message': f'Successfully saved transactions as {filename}'})
    except Exception as e:
        return jsonify({'error': f'Failed to save transactions: {str(e)}'}), 500

@app.route('/api/clear_holdings', methods=['POST'])
def clear_holdings():
    holdings_path = os.path.join('data', 'starting_holdings.csv')
    errors = []
    deleted_holdings = False
    if os.path.exists(holdings_path):
        try:
            os.remove(holdings_path)
            deleted_holdings = True
        except Exception as e:
            errors.append(f"starting_holdings.csv: {str(e)}")
            
    import glob
    uploaded_files = glob.glob(os.path.join('data', 'appending', 'tradebook-uploaded-*.csv'))
    deleted_tx_count = 0
    for fpath in uploaded_files:
        try:
            os.remove(fpath)
            deleted_tx_count += 1
        except Exception as e:
            errors.append(f"{os.path.basename(fpath)}: {str(e)}")
            
    if errors:
        return jsonify({'error': f"Failed to clear some configurations: {'; '.join(errors)}"}), 500
        
    return jsonify({
        'success': True, 
        'message': f"Successfully cleared portfolio configurations. Removed holdings: {deleted_holdings}, deleted {deleted_tx_count} transaction files."
    })

@app.route('/api/run_pipeline')
def run_pipeline():
    def generate():
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        # Locate local venv python executable
        python_exe = os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'python')
        if not os.path.exists(python_exe):
            python_exe = 'python'
            
        yield "Starting performance analytics pipeline...\n"
        process = subprocess.Popen(
            [python_exe, 'portfolio_analysis_v2.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        
        for line in iter(process.stdout.readline, ''):
            yield line
            
        process.stdout.close()
        process.wait()
        
        if process.returncode == 0:
            yield "\n[SUCCESS] Performance metrics successfully updated.\n"
        else:
            yield f"\n[ERROR] Pipeline failed with exit code: {process.returncode}\n"
            
    return Response(generate(), mimetype='text/plain')

if __name__ == '__main__':
    print("*" * 60)
    print("Hisaab Backend Server is running!")
    print("Open your browser and navigate to:")
    print("    http://localhost:5001/")
    print("To upload files, navigate to:")
    print("    http://localhost:5001/upload.html")
    print("*" * 60)
    app.run(host='0.0.0.0', port=5001, debug=True)
