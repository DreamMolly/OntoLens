"""Request identity propagated to the workspace's transactional audit events."""
from contextvars import ContextVar


audit_actor: ContextVar[dict | None] = ContextVar("peiwu_audit_actor", default=None)
