from __future__ import annotations

import sqlite3
from types import SimpleNamespace


class DummyAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def aclose(self) -> None:
        return None


class FakeMessage:
    def __init__(
        self,
        text: str = "",
        *,
        user_id: int = 1,
        chat_id: int = 100,
        message_id: int = 1,
        username: str = "tester",
        first_name: str = "Tester",
    ) -> None:
        self.text = text
        self.message_id = message_id
        self.from_user = SimpleNamespace(id=user_id, username=username, first_name=first_name)
        self.chat = SimpleNamespace(id=chat_id)
        self.answers: list[dict] = []
        self.photos: list[dict] = []
        self.audios: list[dict] = []
        self.edits: list[dict] = []

    async def answer(self, text: str, **kwargs):
        payload = {"text": text, **kwargs}
        self.answers.append(payload)
        return SimpleNamespace(chat=self.chat, message_id=len(self.answers))

    async def answer_photo(self, photo=None, caption: str | None = None, **kwargs):
        payload = {"photo": photo, "caption": caption, **kwargs}
        self.photos.append(payload)
        return SimpleNamespace(chat=self.chat, message_id=len(self.photos))

    async def answer_audio(self, audio=None, caption: str | None = None, title: str | None = None, **kwargs):
        payload = {"audio": audio, "caption": caption, "title": title, **kwargs}
        self.audios.append(payload)
        return SimpleNamespace(chat=self.chat, message_id=len(self.audios))

    async def edit_text(self, text: str, **kwargs):
        payload = {"text": text, **kwargs}
        self.edits.append(payload)
        return SimpleNamespace(chat=self.chat, message_id=self.message_id)


class FakeCallbackQuery:
    def __init__(
        self,
        data: str,
        *,
        message: FakeMessage | None = None,
        user_id: int = 1,
        username: str = "tester",
        first_name: str = "Tester",
    ) -> None:
        self.data = data
        self.message = message or FakeMessage(user_id=user_id, username=username, first_name=first_name)
        self.from_user = SimpleNamespace(id=user_id, username=username, first_name=first_name)
        self.answers: list[dict] = []

    async def answer(self, text: str | None = None, **kwargs):
        payload = {"text": text, **kwargs}
        self.answers.append(payload)
        return payload


def table_row_count(db_path: str, table: str, where_sql: str = "", params: tuple = ()) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        sql = f"SELECT COUNT(*) FROM {table}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        cur.execute(sql, params)
        return int(cur.fetchone()[0])
    finally:
        conn.close()
