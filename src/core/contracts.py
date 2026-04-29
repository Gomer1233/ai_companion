from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ResetScope(str, Enum):
    CONVERSATION = "reset_conversation"
    MODE_IN_CONVERSATION = "reset_mode_in_conversation"
    USER_ALL = "reset_user_all"


class InboundEventType(str, Enum):
    USER_TEXT = "user_text"
    SWITCH_MODE = "switch_mode"
    RESET_CONVERSATION = "reset_conversation"
    RESET_MODE_IN_CONVERSATION = "reset_mode_in_conversation"
    RESET_USER_ALL = "reset_user_all"
    REQUEST_IMAGE = "request_image"
    REQUEST_AUDIO = "request_audio"
    CANCEL_JOB = "cancel_job"
    REQUEST_CONTEXT_REMINDER = "request_context_reminder"


class OutboundItemType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    ACTION = "action"
    PROGRESS = "progress"
    DEFERRED_RESULT = "deferred_result"


class JobType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalyticsEventType(str, Enum):
    CONVERSATION_CREATED = "conversation_created"
    CONVERSATION_ARCHIVED = "conversation_archived"
    MODE_SWITCHED = "mode_switched"
    USER_MESSAGE_RECEIVED = "user_message_received"
    ASSISTANT_REPLY_SENT = "assistant_reply_sent"
    IMAGE_REQUESTED = "image_requested"
    IMAGE_COMPLETED = "image_completed"
    AUDIO_REQUESTED = "audio_requested"
    AUDIO_COMPLETED = "audio_completed"
    JOB_CANCELLED = "job_cancelled"
    RESET_CONVERSATION = "reset_conversation"
    RESET_MODE_IN_CONVERSATION = "reset_mode_in_conversation"
    RESET_USER_ALL = "reset_user_all"


TERMINAL_JOB_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class UserRef:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("UserRef.value must be non-empty")


@dataclass(frozen=True, slots=True)
class ConversationRef:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("ConversationRef.value must be non-empty")


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    user_ref: UserRef
    conversation_ref: ConversationRef
    active_mode: str
    status: ConversationStatus = ConversationStatus.ACTIVE
    is_default: bool = False

    def __post_init__(self) -> None:
        if not self.active_mode or not self.active_mode.strip():
            raise ValueError("ConversationRecord.active_mode must be non-empty")

    @property
    def accepts_events(self) -> bool:
        return self.status == ConversationStatus.ACTIVE


def validate_default_conversations(conversations: list[ConversationRecord]) -> None:
    default_count = sum(1 for conversation in conversations if conversation.is_default)
    if default_count > 1:
        raise ValueError("A user cannot have more than one default conversation")


def resolve_current_conversation(conversations: list[ConversationRecord]) -> ConversationRecord | None:
    validate_default_conversations(conversations)

    active = [conversation for conversation in conversations if conversation.status == ConversationStatus.ACTIVE]
    if active:
        return active[-1]

    defaults = [conversation for conversation in conversations if conversation.is_default]
    if defaults:
        return defaults[0]

    return None


@dataclass(frozen=True, slots=True)
class InboundEvent:
    event_type: InboundEventType
    user_ref: UserRef
    conversation_ref: ConversationRef | None = None
    mode: str | None = None
    text: str | None = None
    job_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_type in {
            InboundEventType.USER_TEXT,
            InboundEventType.SWITCH_MODE,
            InboundEventType.RESET_CONVERSATION,
            InboundEventType.RESET_MODE_IN_CONVERSATION,
            InboundEventType.REQUEST_IMAGE,
            InboundEventType.REQUEST_AUDIO,
            InboundEventType.REQUEST_CONTEXT_REMINDER,
        } and self.conversation_ref is None:
            raise ValueError(f"{self.event_type.value} requires conversation_ref")

        if self.event_type == InboundEventType.USER_TEXT and not self.text:
            raise ValueError("user_text event requires text")

        if self.event_type == InboundEventType.SWITCH_MODE and not self.mode:
            raise ValueError("switch_mode event requires mode")

        if self.event_type == InboundEventType.RESET_MODE_IN_CONVERSATION and not self.mode:
            raise ValueError("reset_mode_in_conversation event requires mode")

        if self.event_type == InboundEventType.CANCEL_JOB and not self.job_id:
            raise ValueError("cancel_job event requires job_id")


@dataclass(frozen=True, slots=True)
class OutboundItem:
    item_type: OutboundItemType
    text: str | None = None
    media_ref: str | None = None
    action: str | None = None
    job_id: str | None = None
    progress: int | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CoreResponse:
    items: list[OutboundItem] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DeferredJob:
    job_id: str
    user_ref: UserRef
    conversation_ref: ConversationRef
    mode: str
    job_type: JobType
    status: JobStatus
    progress: int = 0
    error_code: str | None = None
    result_ref: str | None = None
    created_at: int = 0
    updated_at: int = 0

    def __post_init__(self) -> None:
        if not self.job_id or not self.job_id.strip():
            raise ValueError("DeferredJob.job_id must be non-empty")
        if not self.mode or not self.mode.strip():
            raise ValueError("DeferredJob.mode must be non-empty")
        if not 0 <= self.progress <= 100:
            raise ValueError("DeferredJob.progress must be between 0 and 100")

    def can_transition_to(self, next_status: JobStatus) -> bool:
        if self.status == JobStatus.CANCELLED and next_status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return False
        if self.status in TERMINAL_JOB_STATUSES and next_status != self.status:
            return False
        return True

    def with_status(
        self,
        next_status: JobStatus,
        *,
        progress: int | None = None,
        error_code: str | None = None,
        result_ref: str | None = None,
        updated_at: int | None = None,
    ) -> "DeferredJob":
        if not self.can_transition_to(next_status):
            raise ValueError(f"Invalid job status transition: {self.status.value} -> {next_status.value}")

        return DeferredJob(
            job_id=self.job_id,
            user_ref=self.user_ref,
            conversation_ref=self.conversation_ref,
            mode=self.mode,
            job_type=self.job_type,
            status=next_status,
            progress=self.progress if progress is None else progress,
            error_code=self.error_code if error_code is None else error_code,
            result_ref=self.result_ref if result_ref is None else result_ref,
            created_at=self.created_at,
            updated_at=self.updated_at if updated_at is None else updated_at,
        )


@dataclass(frozen=True, slots=True)
class AnalyticsEvent:
    event_type: AnalyticsEventType
    user_ref: UserRef
    ts: int
    ok: bool
    conversation_ref: ConversationRef | None = None
    mode: str | None = None
    job_id: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_token: str
    user_ref: UserRef
    issued_at: int
    expires_at: int
    last_seen_at: int

    def __post_init__(self) -> None:
        if not self.session_token or not self.session_token.strip():
            raise ValueError("SessionRecord.session_token must be non-empty")
        if self.expires_at <= self.issued_at:
            raise ValueError("SessionRecord.expires_at must be greater than issued_at")
        if self.last_seen_at < self.issued_at:
            raise ValueError("SessionRecord.last_seen_at must be >= issued_at")
