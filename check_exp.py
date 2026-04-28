import sqlite3, json

db = sqlite3.connect(r'C:\Users\mingjwan\.leaper\brain.db')
db.row_factory = sqlite3.Row

# Check experience entries
rows = db.execute('''
    SELECT id, content, keywords, entry_type, confidence, metadata, 
           length(content) as clen, created_at
    FROM leaper_brain 
    WHERE entry_type = 'experience'
    ORDER BY created_at DESC
    LIMIT 10
''').fetchall()

print(f'Experience entries: {len(rows)}\n')
for r in rows:
    print(f'--- {r["id"][:8]} | conf={r["confidence"]} | {r["clen"]}c | {r["created_at"]}')
    print(f'Content: {r["content"]}')
    print(f'Keywords: {r["keywords"]}')
    meta = r["metadata"]
    if meta:
        try:
            m = json.loads(meta)
            print(f'Metadata: topic={m.get("topic")}, complexity={m.get("complexity")}, success={m.get("task_success")}')
        except:
            print(f'Metadata(raw): {meta[:200]}')
    print()

# Check raw entries count and sample
raw_count = db.execute('SELECT COUNT(*) FROM leaper_brain WHERE entry_type = "raw"').fetchone()[0]
print(f'Raw entries: {raw_count}')

# Sample recent raw
raws = db.execute('''
    SELECT content, source, length(content) as clen, created_at
    FROM leaper_brain 
    WHERE entry_type = 'raw'
    ORDER BY created_at DESC 
    LIMIT 3
''').fetchall()
for r in raws:
    print(f'  raw | {r["clen"]}c | src={r["source"]} | {r["content"][:80]}...')

db.close()
