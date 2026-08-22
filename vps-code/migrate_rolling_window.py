"""Migration: Add rolling 24h window columns to users table."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE users ADD COLUMN window_start TIMESTAMP")
    print("Added window_start column")
except psycopg2.errors.DuplicateColumn:
    print("window_start column already exists")

try:
    cur.execute("ALTER TABLE users ADD COLUMN prompt_count INTEGER DEFAULT 0")
    print("Added prompt_count column")
except psycopg2.errors.DuplicateColumn:
    print("prompt_count column already exists")

conn.commit()
conn.close()
print("Migration complete!")
