from __future__ import annotations

import uuid


def test_new_job_id_is_non_enumerable_uuid4() -> None:
    from src.core.jobs import new_job_id

    job_id = new_job_id()

    parsed = uuid.UUID(job_id)
    assert parsed.version == 4
    assert str(parsed) == job_id
