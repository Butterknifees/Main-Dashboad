const fs = require('fs');
const XLSX = require('xlsx');

// Load our target file
const filepath = './data/Stocks_Order_History_3181700510_01-04-2025_18-05-2026.xlsx';
const workbook = XLSX.readFile(filepath);
const sheetName = workbook.SheetNames[0];
const worksheet = workbook.Sheets[sheetName];
const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' });
const filteredRows = rows.filter(r => r && r.some(c => c !== null && c !== ''));

console.log(`Loaded ${rows.length} raw rows. Filtered to ${filteredRows.length} non-empty rows.`);

// Define the exact functions we implemented in upload.html
function findHeaderRow(rows, type) {
    let bestIdx = 0;
    let maxScore = -1;
    
    for (let i = 0; i < Math.min(rows.length, 50); i++) {
        if (!rows[i]) continue;
        const rowStr = rows[i].map(s => String(s || '').toLowerCase().trim());
        let score = 0;
        
        if (type === 'holdings') {
            rowStr.forEach(cell => {
                if (cell === 'isin') score += 3;
                else if (cell.includes('isin')) score += 1.5;
                
                if (cell === 'symbol') score += 2;
                else if (cell.includes('symbol')) score += 1;
                
                if (cell === 'scheme name' || cell === 'stock name') score += 3;
                else if (cell.includes('scheme') || cell.includes('stock') || cell.includes('name')) score += 1;
                
                if (cell === 'quantity' || cell === 'qty' || cell === 'units') score += 3;
                else if (cell.includes('quantity') || cell.includes('qty') || cell.includes('units') || cell.includes('shares')) score += 1;
                
                if (cell === 'avg price' || cell === 'average price' || cell === 'average buy price' || cell === 'avg buy price') score += 3;
                else if (cell.includes('price') || cell.includes('avg') || cell.includes('average') || cell.includes('cost') || cell.includes('nav')) score += 1;
                
                if (cell === 'closing price' || cell === 'closing value') score += 2;
            });
        } else {
            rowStr.forEach(cell => {
                if (cell === 'isin') score += 3;
                else if (cell.includes('isin')) score += 1.5;
                
                if (cell === 'symbol') score += 2;
                else if (cell.includes('symbol')) score += 1;
                
                if (cell === 'scheme name' || cell === 'stock name') score += 3;
                else if (cell.includes('scheme') || cell.includes('stock') || cell.includes('name')) score += 1;
                
                if (cell === 'quantity' || cell === 'qty' || cell === 'units') score += 3;
                else if (cell.includes('quantity') || cell.includes('qty') || cell.includes('units')) score += 1;
                
                if (cell === 'price' || cell === 'rate' || cell === 'nav') score += 3;
                else if (cell.includes('price') || cell.includes('rate') || cell.includes('nav') || cell.includes('value') || cell.includes('amount')) score += 1;
                
                if (cell === 'date' || cell === 'execution date' || cell === 'trade date' || cell === 'execution date and time') score += 3;
                else if (cell.includes('date') || cell.includes('time')) score += 1;
                
                if (cell === 'type' || cell === 'transaction type' || cell === 'buy/sell' || cell === 'action') score += 2;
                else if (cell.includes('type') || cell.includes('action') || cell.includes('side') || cell.includes('buy') || cell.includes('sell')) score += 1;
            });
        }
        
        if (score > maxScore) {
            maxScore = score;
            bestIdx = i;
        }
    }
    return maxScore >= 3 ? bestIdx : 0;
}

function autoDetectMapping(type, headers) {
    if (type === 'holdings') {
        const idCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s === 'isin' || s === 'scheme code' || s.includes('isin') || s.includes('scheme code') || s.includes('instrument') || s.includes('symbol');
        });
        const nameCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s.includes('name') || s.includes('scheme name') || s.includes('stock name') || s.includes('description') || s === 'symbol';
        });
        const qtyCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s.includes('qty') || s.includes('quantity') || s.includes('units') || s.includes('shares');
        });
        const priceCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s === 'average buy price' || s === 'avg buy price' || s === 'avg price' || (s.includes('price') && !s.includes('closing') && !s.includes('buy value')) || s.includes('avg') || s.includes('average') || s.includes('cost') || s.includes('nav');
        });
        const valueCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s.includes('buy value') || s.includes('closing value') || s.includes('invested value') || s === 'value' || s.includes('value') || s === 'amount' || s.includes('amount') || s.includes('total');
        });
        return { id: idCol, name: nameCol, qty: qtyCol, price: priceCol, value: valueCol };
    } else {
        const dateCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s.includes('date') || s.includes('time');
        });
        const idCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s === 'isin' || s === 'scheme code' || s.includes('isin') || s.includes('scheme code') || s.includes('instrument') || s.includes('symbol');
        });
        const nameCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s.includes('name') || s.includes('scheme name') || s.includes('stock name') || s.includes('description') || s === 'symbol';
        });
        const qtyCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s.includes('qty') || s.includes('quantity') || s.includes('units');
        });
        const priceCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return (s.includes('price') && !s.includes('total') && !s.includes('value')) || s.includes('rate') || s.includes('nav');
        });
        const typeCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s.includes('type') || s.includes('action') || s.includes('buy/sell') || s.includes('side') || s === 'trade_type';
        });
        const valueCol = headers.findIndex(h => {
            const s = h.toLowerCase();
            return s === 'value' || s.includes('value') || s === 'amount' || s.includes('amount') || s.includes('total');
        });
        return { date: dateCol, id: idCol, name: nameCol, qty: qtyCol, price: priceCol, type: typeCol, value: valueCol };
    }
}

function normalizeFileRows(type, headers, rows, mapping) {
    let normalized = [];
    rows.forEach(r => {
        if (type === 'holdings') {
            const id = mapping.id !== -1 ? String(r[mapping.id] || '').trim() : '';
            const name = mapping.name !== -1 ? String(r[mapping.name] || '').trim() : '';
            const qtyStr = mapping.qty !== -1 ? String(r[mapping.qty] || '').replace(/,/g, '') : '';
            const priceStr = mapping.price !== -1 ? String(r[mapping.price] || '').replace(/,/g, '') : '';
            const valueStr = mapping.value !== -1 ? String(r[mapping.value] || '').replace(/,/g, '') : '';
            
            const qty = parseFloat(qtyStr);
            let price = parseFloat(priceStr);
            
            if (isNaN(price) && !isNaN(qty) && qty > 0 && valueStr) {
                const totalVal = parseFloat(valueStr);
                if (!isNaN(totalVal)) {
                    price = totalVal / qty;
                }
            }
            
            if (id && !isNaN(qty) && qty > 0 && !isNaN(price)) {
                if (id.toLowerCase() === 'isin' || id.toLowerCase().includes('scheme name') || id.toLowerCase().includes('stock name')) return;
                normalized.push({ id, name, qty, price });
            }
        } else {
            const rawDate = mapping.date !== -1 ? String(r[mapping.date] || '').trim() : '';
            const id = mapping.id !== -1 ? String(r[mapping.id] || '').trim() : '';
            const name = mapping.name !== -1 ? String(r[mapping.name] || '').trim() : '';
            const qtyStr = mapping.qty !== -1 ? String(r[mapping.qty] || '').replace(/,/g, '') : '';
            const priceStr = mapping.price !== -1 ? String(r[mapping.price] || '').replace(/,/g, '') : '';
            const valueStr = mapping.value !== -1 ? String(r[mapping.value] || '').replace(/,/g, '') : '';
            const rawType = mapping.type !== -1 ? String(r[mapping.type] || '').trim().toLowerCase() : 'buy';
            
            const qty = parseFloat(qtyStr);
            let price = parseFloat(priceStr);
            
            if (isNaN(price) && !isNaN(qty) && qty > 0 && valueStr) {
                const totalVal = parseFloat(valueStr);
                if (!isNaN(totalVal)) {
                    price = totalVal / qty;
                }
            }
            
            if (id && rawDate && !isNaN(qty) && qty > 0 && !isNaN(price)) {
                if (id.toLowerCase() === 'isin' || id.toLowerCase().includes('scheme name') || id.toLowerCase().includes('stock name')) return;
                
                let dateStr = '';
                let parts;
                if (rawDate.includes('-')) parts = rawDate.split(' ')[0].split('-');
                else if (rawDate.includes('/')) parts = rawDate.split(' ')[0].split('/');
                
                if (parts && parts.length === 3) {
                    if (parts[0].length === 4) {
                        dateStr = `${parts[0]}-${parts[1].padStart(2, '0')}-${parts[2].padStart(2, '0')}`;
                    } else {
                        dateStr = `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
                    }
                } else {
                    try {
                        const d = new Date(rawDate);
                        if (!isNaN(d.getTime())) {
                            dateStr = d.toISOString().split('T')[0];
                        }
                    } catch(e) {}
                }
                
                let txType = 'buy';
                if (rawType.includes('sell') || rawType.includes('redemption') || rawType.includes('payout') || rawType.includes('redeem')) {
                    txType = 'sell';
                }
                
                if (dateStr) {
                    normalized.push({ date: dateStr, id, name, qty, price, type: txType });
                }
            }
        }
    });
    return normalized;
}

// Perform parsing and check results
const headerIdx = findHeaderRow(filteredRows, 'transactions');
const headers = filteredRows[headerIdx];
const dataRows = filteredRows.slice(headerIdx + 1);
const mapping = autoDetectMapping('transactions', headers);
const normalized = normalizeFileRows('transactions', headers, dataRows, mapping);

console.log(`\nHeader Index Found: ${headerIdx}`);
console.log('Headers:', headers);
console.log('Detected Mapping:', mapping);
console.log(`Parsed ${normalized.length} normalized transaction rows.`);

if (normalized.length > 0) {
    console.log('\nFirst 5 parsed transactions:');
    console.log(normalized.slice(0, 5));
} else {
    console.error('ERROR: 0 transactions parsed! Ingestion is failing.');
}
