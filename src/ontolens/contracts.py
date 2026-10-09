from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CheckRequest(StrictModel):
    request_id: str = Field(min_length=1, max_length=80)
    requester_id: str = Field(min_length=1, max_length=80)
    lot_id: str = Field(min_length=1, max_length=80)
    destination_cabinet_id: str = Field(min_length=1, max_length=80)
    quantity: float = Field(gt=0, le=1e9, strict=True)
    unit: str = Field(min_length=1, max_length=20)
    as_of: date
    version_id: str | None = Field(default=None, max_length=80)


class ReviewEvidenceReference(StrictModel):
    """A source locator attached to a human follow-up audit record.

    ``quote`` is optional because a needs_review graph edge may intentionally
    be unresolved.  The source id, locator and source hash are always checked
    against the run's immutable evidence edges; a nullable quote is retained
    only to make unresolved references explicit in detached exports.
    """

    source_id: str = Field(min_length=1, max_length=80)
    locator: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    quote: str | None = Field(default=None, max_length=6000)
    unresolved: bool = Field(default=False, strict=True)


class ReviewRecordRequest(StrictModel):
    """Record human follow-up without allowing a business decision override."""

    reviewer: str = Field(min_length=1, max_length=120)
    review_status: Literal["queued", "in_review", "evidence_requested", "closed_no_decision"]
    note: str = Field(min_length=1, max_length=1000)
    # ``evidence_ids`` is retained for existing workbench clients.  New
    # clients may send a structured reference in the same list; the workspace
    # expands legacy source-only values to immutable source/locator/hash
    # references before appending the audit event.
    evidence_ids: list[str | ReviewEvidenceReference] = Field(default_factory=list, max_length=20)
    evidence_references: list[ReviewEvidenceReference] = Field(default_factory=list, max_length=20)


class CitationReference(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    locator: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=6000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class EvidenceRerankRequest(StrictModel):
    query: str = Field(min_length=1, max_length=300)
    version_id: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=12, ge=1, le=30, strict=True)
    citations: list[CitationReference] | None = Field(default=None, min_length=1, max_length=30)
    live: bool = Field(default=False, strict=True)


class CandidateRequest(StrictModel):
    parent_id: str = Field(min_length=1, max_length=80)
    requester_id: str = Field(min_length=1, max_length=80)
    classes: list[Literal["FLAMMABLE", "OXIDIZER", "ACID", "BASE", "WATER_REACTIVE", "TOXIC", "COMPRESSED_GAS", "GENERAL"]] = Field(max_length=8)
    source_id: str = Field(min_length=1, max_length=80)
    locator: str = Field(min_length=1, max_length=100)
    valid_from: date | None = None
    valid_until: date | None = None
    note: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def dates_and_classes(self):
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("生效起始日期晚于结束日期")
        if len(set(self.classes)) != len(self.classes):
            raise ValueError("授权类别不能重复")
        return self


class SwitchRequest(StrictModel):
    expected_active: str = Field(min_length=1, max_length=80)
    note: str = Field(min_length=1, max_length=600)
    confirm_demo: Literal[True] | None = None
    confirm_publish: Literal[True] | None = None

    @model_validator(mode="after")
    def explicit_confirmation(self):
        if self.confirm_demo is not True and self.confirm_publish is not True:
            raise ValueError("须显式确认发布或回滚")
        return self


class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)
