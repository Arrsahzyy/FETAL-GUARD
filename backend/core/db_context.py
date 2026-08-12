from sqlalchemy import event, text
from sqlalchemy.orm import Session


_SESSION_CONTEXT_KEY = "fetal_guard_postgresql_request_context"


def _apply_postgresql_context(connection, context: dict[str, str]) -> None:
    connection.execute(
        text(
            "SELECT "
            "set_config('app.current_user_id', :user_id, true), "
            "set_config('app.current_membership_id', :membership_id, true), "
            "set_config('app.current_organization_id', :organization_id, true), "
            "set_config('app.current_membership_role', :membership_role, true)"
        ),
        context,
    )


@event.listens_for(Session, "after_begin")
def _restore_postgresql_request_context(session, _transaction, connection) -> None:
    """Reapply RLS identity whenever a route starts a new transaction.

    Several API routes intentionally commit an audit event and then refresh an
    ORM object. PostgreSQL clears transaction-local settings at that commit, so
    a pooled connection must never rely on the previous transaction retaining
    the identity.
    """

    if connection.dialect.name != "postgresql":
        return
    context = session.info.get(_SESSION_CONTEXT_KEY)
    if context:
        _apply_postgresql_context(connection, context)


def set_postgresql_request_context(
    db: Session,
    *,
    user_id: str,
    membership_id: str | None = None,
    organization_id: str | None = None,
    membership_role: str | None = None,
) -> None:
    """Set transaction-local identity for PostgreSQL RLS policies.

    Transaction-local settings are mandatory: ordinary ``SET`` would leak the
    previous request identity when a pooled connection is reused.
    """

    context = {
        "user_id": user_id,
        "membership_id": membership_id or "",
        "organization_id": organization_id or "",
        "membership_role": membership_role or "",
    }
    db.info[_SESSION_CONTEXT_KEY] = context

    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    _apply_postgresql_context(db.connection(), context)
