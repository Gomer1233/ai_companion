import sqlite3
from src.app.settings import Settings

SETTINGS = Settings.from_env()
DB_PATH = SETTINGS.bot_db_path

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
SELECT
  datetime(ts,'unixepoch','localtime') AS ts,
  event_type,
  mode,
  mode_from,
  mode_to,
  llm_model,
  total_tokens,
  tokens_source,
  text_len,
  note
FROM user_events
ORDER BY id DESC
LIMIT 30;
""")


for row in cur.fetchall():
    print(row)

conn.close()
