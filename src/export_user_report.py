import sys
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime
from src.app.settings import Settings

PROJECT_ROOT = Path(__file__).parent.parent
SETTINGS = Settings.from_env(project_root=PROJECT_ROOT)

DB_PATH = SETTINGS.bot_db_path
REPORTS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

OUT_XLSX = REPORTS_DIR / SETTINGS.report_xlsx

def main():
    conn = sqlite3.connect(DB_PATH)

    # 1) Полный лог событий
    df_events = pd.read_sql_query(
        """
        SELECT
          datetime(ts, 'unixepoch', 'localtime') AS ts_local,
          date(ts, 'unixepoch', 'localtime')     AS day_local,
          user_id,
          username,
          first_name,
          chat_id,
          event_type,
          mode,
          mode_from,
          mode_to,
          message_id,
          text_len,
          photo_provider,
          photo_model,
          ok,
          note
        FROM user_events
        ORDER BY ts ASC
        """,
        conn,
    )

    # 2) Сколько сообщений (user message) по пользователю/дню/персонажу
    df_messages_agg = pd.read_sql_query(
        """
        SELECT
          date(ts, 'unixepoch', 'localtime') AS day_local,
          user_id,
          mode,
          COUNT(*) AS messages
        FROM user_events
        WHERE event_type = 'message'
        GROUP BY day_local, user_id, mode
        ORDER BY day_local DESC, messages DESC
        """,
        conn,
    )

    # 3) Переключения
    df_switches = pd.read_sql_query(
        """
        SELECT
          datetime(ts, 'unixepoch', 'localtime') AS ts_local,
          user_id,
          username,
          first_name,
          mode_from,
          mode_to,
          ok,
          note
        FROM user_events
        WHERE event_type = 'switch_mode'
        ORDER BY ts ASC
        """,
        conn,
    )

    # 4) Фото: кнопка/запрос/результат
    df_photo = pd.read_sql_query(
        """
        SELECT
          datetime(ts, 'unixepoch', 'localtime') AS ts_local,
          date(ts, 'unixepoch', 'localtime')     AS day_local,
          user_id,
          username,
          first_name,
          event_type,
          mode,
          photo_provider,
          photo_model,
          ok,
          note,
          message_id,
          text_len
        FROM user_events
        WHERE event_type IN ('photo_button','photo_request','photo_result')
        ORDER BY ts ASC
        """,
        conn,
    )

    conn.close()

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = OUT_XLSX.with_name(
        OUT_XLSX.stem + f"_{stamp}" + OUT_XLSX.suffix
    )


    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_events.to_excel(writer, sheet_name="events", index=False)
        df_messages_agg.to_excel(writer, sheet_name="messages_agg", index=False)
        df_switches.to_excel(writer, sheet_name="switches", index=False)
        df_photo.to_excel(writer, sheet_name="photo", index=False)

    print(f"OK: {out}")

if __name__ == "__main__":
    main()
