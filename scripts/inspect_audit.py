import sqlite3
import json

db_path = 'logs/swim_audit.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('SELECT payload FROM audit_log WHERE message_type = "DISTRIBUTED_FLOW_CONSENSUS" ORDER BY id DESC LIMIT 1')
row = c.fetchone()
if row:
    payload = json.loads(row[0])
    print(json.dumps(payload, indent=2))
else:
    print("No consensus found.")
conn.close()
