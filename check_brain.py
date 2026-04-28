import sqlite3
db = sqlite3.connect(r'C:\Users\mingjwan\.leaper\brain.db')
db.row_factory = sqlite3.Row
cols = db.execute('PRAGMA table_info(leaper_brain)').fetchall()
print('Columns:', [c['name'] for c in cols])

by_type = db.execute('SELECT entry_type, COUNT(*) as c FROM leaper_brain GROUP BY entry_type ORDER BY c DESC').fetchall()
print('\nBy type:')
for r in by_type:
    et = r['entry_type'] or 'null'
    print(f'  {et}: {r["c"]}')

print('\nRecent 5:')
rows = db.execute('SELECT entry_type, confidence, length(content) as clen, updated_at FROM leaper_brain ORDER BY updated_at DESC LIMIT 5').fetchall()
for r in rows:
    print(f'  {r["updated_at"]} | type={r["entry_type"]} | conf={r["confidence"]} | {r["clen"]}c')
db.close()
