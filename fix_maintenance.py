import psycopg2

conn = psycopg2.connect('postgresql://neondb_owner:npg_T3vODNYwA5Rg@ep-green-glitter-afigkd43-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require')
cur = conn.cursor()

# Check current value
cur.execute("SELECT setting_key, setting_value FROM bot_settings WHERE setting_key = 'maintenance_mode'")
rows = cur.fetchall()
print('BEFORE:', rows)

# Update to false
cur.execute("UPDATE bot_settings SET setting_value = 'false' WHERE setting_key = 'maintenance_mode'")
print('Rows updated:', cur.rowcount)

# If no row exists, insert one
if cur.rowcount == 0:
    cur.execute("INSERT INTO bot_settings (setting_key, setting_value) VALUES ('maintenance_mode', 'false')")
    print('Inserted new row')

conn.commit()

# Verify
cur.execute("SELECT setting_key, setting_value FROM bot_settings WHERE setting_key = 'maintenance_mode'")
print('AFTER:', cur.fetchall())
conn.close()
print('DONE')
