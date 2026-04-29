from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.http.app import create_app
from src.adapters.http.dependencies import AppDependencies, ReadinessState
from src.app.settings import Settings
from src.core.contracts import DeferredJob, JobStatus, JobType, UserRef
from src.db.bootstrap import apply_postgres_schema
from src.db.cutover import export_sqlite_snapshot, import_snapshot_to_repositories
from src.db.factory import create_repositories
from src.db.migrations import migrate_database
from src.db.postgres import PostgresRepositories
from src.db.repositories import SQLiteRepositories


pytestmark = pytest.mark.postgres


@pytest.fixture()
def postgres_settings() -> Settings:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")

    return Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "DB_BACKEND": "postgres",
            "DATABASE_URL": database_url,
            "HTTP_CORS_ORIGINS": "http://localhost:3000",
        },
        project_root=Path("D:/projects/Lina_AI"),
    )


@pytest.fixture()
def postgres_repo(postgres_settings: Settings):
    apply_postgres_schema(postgres_settings.database_url)
    repo = create_repositories(postgres_settings, include_relationship_state=True, history_limit=3)
    assert isinstance(repo, PostgresRepositories)
    yield repo


def test_postgres_repository_round_trips_session_conversation_history_and_jobs(postgres_repo) -> None:
    unique_id = int(f"9{int(time.time()) % 100000}{uuid.uuid4().int % 10000:04d}")
    user_ref = UserRef(str(unique_id))
    now_ts = int(time.time())

    conversation = postgres_repo.ensure_default_conversation(user_ref, active_mode="basic")
    session = postgres_repo.create_session(user_ref, issued_at=now_ts, expires_at=now_ts + 900)
    postgres_repo.append_history(user_ref, conversation.conversation_ref, "basic", "user", "hello-postgres")
    postgres_repo.create_job(
        DeferredJob(
            job_id=f"job-{uuid.uuid4().hex}",
            user_ref=user_ref,
            conversation_ref=conversation.conversation_ref,
            mode="basic",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=25,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )

    assert postgres_repo.load_session(session.session_token).user_ref == user_ref
    assert postgres_repo.touch_session(session.session_token, last_seen_at=now_ts + 10).last_seen_at == now_ts + 10
    assert postgres_repo.load_active_conversation_for_user(user_ref).conversation_ref == conversation.conversation_ref
    assert postgres_repo.load_history(user_ref, conversation.conversation_ref, "basic") == [
        {"role": "user", "content": "hello-postgres"}
    ]


def test_http_adapter_contract_survives_postgres_backend(postgres_settings: Settings, postgres_repo) -> None:
    unique_id = int(f"8{int(time.time()) % 100000}{uuid.uuid4().int % 10000:04d}")
    user_ref = UserRef(str(unique_id))
    now_ts = int(time.time())
    session = postgres_repo.create_session(user_ref, issued_at=now_ts, expires_at=now_ts + 900)
    conversation = postgres_repo.ensure_default_conversation(user_ref)
    job = postgres_repo.create_job(
        DeferredJob(
            job_id=f"job-{uuid.uuid4().hex}",
            user_ref=user_ref,
            conversation_ref=conversation.conversation_ref,
            mode="basic",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=40,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )
    client = TestClient(
        create_app(
            AppDependencies(
                settings=postgres_settings,
                repositories=postgres_repo,
                readiness=ReadinessState(is_ready=True),
            )
        )
    )

    headers = {"Authorization": f"Bearer {session.session_token}"}
    me = client.get("/api/me", headers=headers)
    job_response = client.get(f"/api/jobs/{job.job_id}", headers=headers)

    assert me.status_code == 200
    assert me.json()["user_id"] == user_ref.value
    assert job_response.status_code == 200
    assert job_response.json()["job_id"] == job.job_id


def test_sqlite_fixture_cutover_rehearsal_imports_into_postgres(tmp_path: Path, postgres_repo) -> None:
    source_db = tmp_path / "sqlite-cutover-source.db"
    migrate_database(str(source_db), include_relationship_state=True)
    source = SQLiteRepositories(str(source_db), include_relationship_state=True, history_limit=10)
    unique_id = int(f"7{int(time.time()) % 100000}{uuid.uuid4().int % 10000:04d}")
    user_ref = UserRef(str(unique_id))
    now_ts = int(time.time())
    conversation = source.ensure_default_conversation(user_ref, active_mode="chef")
    source.append_history(user_ref, conversation.conversation_ref, "chef", "user", "cutover hello", created_at=now_ts)
    source.save_mode_state(user_ref, conversation.conversation_ref, "chef", {"rehearsal": True})
    source.create_session(user_ref, issued_at=now_ts, expires_at=now_ts + 900, session_token=f"session-{uuid.uuid4().hex}")
    source.create_job(
        DeferredJob(
            job_id=f"job-{uuid.uuid4().hex}",
            user_ref=user_ref,
            conversation_ref=conversation.conversation_ref,
            mode="chef",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=15,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )

    snapshot = export_sqlite_snapshot(str(source_db))
    result = import_snapshot_to_repositories(snapshot, postgres_repo)

    assert result.imported_counts["users"] == 1
    assert postgres_repo.load_history(user_ref, conversation.conversation_ref, "chef") == [
        {"role": "user", "content": "cutover hello"}
    ]
    assert postgres_repo.load_mode_state(user_ref, conversation.conversation_ref, "chef") == {"rehearsal": True}
