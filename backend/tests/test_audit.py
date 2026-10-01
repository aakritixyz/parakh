from app.services.audit_service import AuditService


def test_hash_chain_detects_tamper(db):
    svc = AuditService(db)
    first = svc.log(action="case.created", actor="tester", payload={"a": 1})
    svc.log(action="evidence.uploaded", actor="tester", payload={"b": 2})
    db.commit()
    assert svc.verify_chain()["valid"] is True
    first.payload = {"a": 9}
    db.commit()
    assert svc.verify_chain()["valid"] is False
