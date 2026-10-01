import pytest
from fastapi import HTTPException

from app.core.rbac import can_access_case, require_case_access
from app.models.case import Case, CaseMembership
from app.models.user import User
from app.services.case_service import CaseService


def test_case_creator_gets_membership(db):
    user = User(username="investigator", hashed_password="x", role="investigator")
    db.add(user)
    db.flush()

    case = CaseService(db).create_case("Case A", "Demo", "investigator")
    db.commit()

    membership = db.query(CaseMembership).filter_by(case_id=case.id, user_id=user.id).one()
    assert membership.role == "investigator"
    assert can_access_case(db, user, case.id)
    assert can_access_case(db, user, case.id, write=True)


def test_prosecutor_membership_is_read_only(db):
    case = Case(title="Case A")
    user = User(username="pros", hashed_password="x", role="prosecutor")
    db.add_all([case, user])
    db.flush()
    db.add(CaseMembership(case_id=case.id, user_id=user.id, role="prosecutor"))
    db.commit()

    assert can_access_case(db, user, case.id)
    assert not can_access_case(db, user, case.id, write=True)


def test_case_access_denied_without_membership(db):
    case = Case(title="Case A")
    user = User(username="outsider", hashed_password="x", role="analyst")
    db.add_all([case, user])
    db.commit()

    with pytest.raises(HTTPException) as exc:
        require_case_access(db, user, case.id)
    assert exc.value.status_code == 403
