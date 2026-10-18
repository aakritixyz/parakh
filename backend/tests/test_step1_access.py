from argparse import Namespace
from datetime import UTC, datetime, timedelta

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.database import get_db
from app.core.migrations import migrate_database
from app.core.security import decode_access_token, hash_password
from app.models.audit import AuditLog, Lead
from app.models.case import CaseMembership
from app.models.session import AuthSession
from app.models.user import User
from app.services.audit_service import AuditService

PASSWORD = "synthetic-step1-password"
CASE = {"title": "Riya: investment scam complaint", "case_number": "SYN-RIYA-001", "jurisdiction": "Synthetic demo jurisdiction",
        "offence_type": "UPI investment fraud", "description": "Synthetic Riya pack only", "lead_investigator": "demo-investigator",
        "team_members": [{"username": "demo-prosecutor", "role": "prosecutor"}]}


@pytest.fixture()
def api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'step1.sqlite'}", connect_args={"check_same_thread": False})
    migrate_database(engine)
    sessions = sessionmaker(bind=engine)
    settings = Settings(_env_file=None, secret_key="synthetic-step1-test-secret", storage_root=tmp_path/'vault')
    import app.api.v2.auth as auth
    import app.core.security as security
    import app.main as main
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    with sessions() as db:
        for name, role in [("demo-admin", "admin"), ("demo-investigator", "investigator"), ("demo-prosecutor", "prosecutor"), ("demo-analyst", "analyst"), ("demo-outsider", "investigator")]:
            db.add(User(username=name, role=role, hashed_password=hash_password(PASSWORD)))
        db.commit()
    app = main.create_app()
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, sessions
    engine.dispose()


def login(client, name="demo-investigator"):
    response = client.post('/api/v2/auth/login', data={"username": name, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()['access_token']}


def create(client, headers):
    response = client.post('/api/v2/cases', headers=headers, json=CASE)
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_done_when_create_case_prosecutor_cannot_edit_and_three_audit_actions(api):
    client, sessions = api
    owner = login(client)
    case_id = create(client, owner)
    listed = client.get('/api/v2/cases', headers=owner).json()[0]
    assert listed['title'] == CASE['title'] and listed['case_number'] == CASE['case_number']
    assert listed['evidence_count'] == 0 and listed['status'] == 'open' and listed['last_activity']
    assert listed['lead_investigator'] == 'demo-investigator'
    for key in ["jurisdiction", "offence_type", "description"]:
        assert listed[key] == CASE[key]
    prosecutor = login(client, 'demo-prosecutor')
    detail = client.get(f'/api/v2/cases/{case_id}', headers=prosecutor).json()
    assert detail['can_edit'] is False and detail['can_manage'] is False
    assert client.patch(f'/api/v2/cases/{case_id}', json={**CASE, 'team_members': []}, headers=prosecutor).status_code == 403
    assert client.post(f'/api/v2/cases/{case_id}/members', json={'username':'demo-analyst','role':'analyst'}, headers=prosecutor).status_code == 403
    audit = client.get(f'/api/v2/cases/{case_id}/audit', headers=owner).json()
    assert audit['chain_verified']
    assert {'auth.signed_in', 'case.created', 'case.member_added'} <= {row['action'] for row in audit['entries']}
    with sessions() as db:
        assert AuditService(db).verify_chain()['valid']
        assert db.scalar(select(User).where(User.username == 'demo-investigator')).hashed_password.startswith('$argon2id$')


@pytest.mark.parametrize('method,path,kwargs', [
    ('post', '/api/v1/cases', {'json':{'title':'Denied'}}),
    ('post', '/api/v2/cases', {'json':CASE}),
    ('post', '/api/v1/cases/{id}/evidence', {'files':{'file':('source.txt',b'synthetic')}}),
    ('post', '/api/v1/cases/{id}/entities/extract', {}),
    ('post', '/api/v1/cases/{id}/comments?target_type=case&target_id=1&body=denied', {}),
    ('post', '/api/v1/cases/{id}/reports/items?kind=case&ref=1', {}),
    ('post', '/api/v1/cases/{id}/reports', {}),
    ('post', '/api/v1/cases/{id}/export-bundle', {}),
    ('post', '/api/v1/auth/bootstrap', {'json':{'username':'escalation','password':PASSWORD,'role':'admin'}}),
])
def test_prosecutor_denied_all_writes_in_both_api_versions(api, method, path, kwargs):
    client, _ = api
    case_id = create(client, login(client))
    response = getattr(client, method)(path.format(id=case_id), headers=login(client, 'demo-prosecutor'), **kwargs)
    assert response.status_code == 403, response.text


def test_cross_case_and_object_authorization_and_role_ceiling(api):
    client, sessions = api
    owner = login(client)
    case_id = create(client, owner)
    outsider = login(client, 'demo-outsider')
    assert client.get('/api/v2/cases', headers=outsider).json() == []
    assert client.get(f'/api/v1/cases/{case_id}/evidence', headers=outsider).status_code == 403
    with sessions() as db:
        lead = Lead(case_id=case_id, title='Synthetic Riya lead', rationale='test', citations=[])
        db.add(lead)
        db.commit()
        lead_id = lead.id
    assert client.patch(f'/api/v1/leads/{lead_id}?status=accepted', headers=outsider).status_code == 403
    assert client.post(f'/api/v2/cases/{case_id}/members', headers=owner, json={'username':'demo-prosecutor','role':'investigator'}).status_code == 403
    prosecutor = login(client, 'demo-prosecutor')
    for path in ['/api/v1/jobs','/api/v1/identifiers','/api/v1/cases/stats','/api/v1/audit/verify']:
        assert client.get(path, headers=prosecutor).status_code == 403
    with sessions() as db:
        user = db.scalar(select(User).where(User.username == 'demo-prosecutor'))
        membership = db.scalar(select(CaseMembership).where(CaseMembership.user_id == user.id))
        membership.role = 'investigator'  # System role remains a read-only ceiling.
        db.commit()
    assert client.post(f'/api/v1/cases/{case_id}/entities/extract', headers=prosecutor).status_code == 403


def test_member_revocation_is_immediate_for_existing_access_token(api):
    client, sessions = api
    owner = login(client)
    case_id = create(client, owner)
    prosecutor = login(client, 'demo-prosecutor')
    with sessions() as db:
        user_id = db.scalar(select(User.id).where(User.username == 'demo-prosecutor'))
    assert client.delete(f'/api/v2/cases/{case_id}/members/{user_id}', headers=owner).status_code == 200
    assert client.get(f'/api/v1/cases/{case_id}/evidence', headers=prosecutor).status_code == 403
    assert client.get(f'/api/v2/cases/{case_id}', headers=prosecutor).status_code == 403


def test_rotating_refresh_is_http_only_and_replay_revokes_session(api):
    client, _ = api
    first = client.post('/api/v2/auth/login', data={'username':'demo-investigator','password':PASSWORD})
    old = client.cookies.get('parakh_refresh')
    assert 'HttpOnly' in first.headers['set-cookie'] and 'SameSite=strict' in first.headers['set-cookie']
    assert 'refresh_token' not in first.json()
    assert client.get('/api/v2/auth/me', headers={'Authorization':'Bearer '+old}).status_code == 401
    refreshed = client.post('/api/v2/auth/refresh')
    assert refreshed.status_code == 200
    new_access = refreshed.json()['access_token']
    assert client.cookies.get('parakh_refresh') != old
    assert client.post('/api/v2/auth/refresh', headers={'Cookie':'parakh_refresh='+old}).status_code == 401
    assert client.get('/api/v2/auth/me', headers={'Authorization':'Bearer '+new_access}).status_code == 401


def test_logout_and_expired_session_invalidate_access(api):
    client, sessions = api
    headers = login(client)
    assert client.post('/api/v2/auth/logout').status_code == 200
    assert client.get('/api/v2/auth/me', headers=headers).status_code == 401
    headers = login(client)
    sid = decode_access_token(headers['Authorization'][7:])['sid']
    with sessions() as db:
        db.get(AuthSession, sid).expires_at = datetime.now(UTC)-timedelta(seconds=1)
        db.commit()
    assert client.get('/api/v2/auth/me', headers=headers).status_code == 401
    assert client.post('/api/v2/auth/refresh').status_code == 401


def test_bcrypt_upgrade_first_admin_and_anonymous_account_creation_blocked(api, monkeypatch):
    client, sessions = api
    assert client.post('/api/v1/auth/bootstrap', json={'username':'bad','password':PASSWORD,'role':'admin'}).status_code == 401
    with sessions() as db:
        user = db.scalar(select(User).where(User.username == 'demo-investigator'))
        user.hashed_password = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
        db.commit()
    login(client)
    with sessions() as db:
        assert db.scalar(select(User).where(User.username == 'demo-investigator')).hashed_password.startswith('$argon2id$')
    from app import cli
    monkeypatch.setattr(cli, 'SessionLocal', sessions)
    monkeypatch.setattr(cli, 'require_current_schema', lambda _: None)
    with pytest.raises(SystemExit, match='first-run'):
        cli.create_admin(Namespace(username='second-admin', password=PASSWORD))
    with sessions() as db:
        assert all(PASSWORD not in str(row.payload) for row in db.scalars(select(AuditLog)))


def test_legacy_login_is_revocable_and_refresh_rejects_untrusted_origin(api):
    client, _ = api
    response = client.post('/api/v1/auth/token', data={'username':'demo-investigator','password':PASSWORD})
    assert response.status_code == 200
    headers = {'Authorization': 'Bearer '+response.json()['access_token']}
    assert client.get('/api/v2/auth/me', headers=headers).status_code == 200
    assert client.post('/api/v2/auth/refresh', headers={'Origin':'https://untrusted.example'}).status_code == 403
    assert client.post('/api/v2/auth/logout').status_code == 200
    assert client.get('/api/v2/auth/me', headers=headers).status_code == 401


def test_first_admin_creation_is_explicit_and_not_hardcoded(api, monkeypatch):
    client, sessions = api
    from app import cli
    monkeypatch.setattr(cli, 'SessionLocal', sessions)
    monkeypatch.setattr(cli, 'require_current_schema', lambda _: None)
    with sessions() as db:
        db.delete(db.scalar(select(User).where(User.role=='admin')))
        db.commit()
    cli.create_admin(Namespace(username='synthetic-first-admin', password=PASSWORD))
    with sessions() as db:
        user=db.scalar(select(User).where(User.username=='synthetic-first-admin'))
        assert user.role=='admin' and user.hashed_password.startswith('$argon2id$')
    assert client.post('/api/v2/auth/login',data={'username':'synthetic-first-admin','password':PASSWORD}).status_code==200


def test_analysts_cannot_manage_case_access_or_create_cases(api):
    client, _ = api
    owner = login(client)
    case_id = create(client, owner)
    assert client.post(f'/api/v2/cases/{case_id}/members',headers=owner,json={'username':'demo-analyst','role':'analyst'}).status_code==201
    analyst=login(client,'demo-analyst')
    assert client.get(f'/api/v2/cases/{case_id}',headers=analyst).status_code==200
    assert client.post('/api/v2/cases',headers=analyst,json=CASE).status_code==403
    assert client.post(f'/api/v2/cases/{case_id}/members',headers=analyst,json={'username':'demo-outsider','role':'investigator'}).status_code==403
    assert client.patch(f'/api/v2/cases/{case_id}',headers=analyst,json={**CASE,'team_members':[]}).status_code==403


def test_unknown_or_revoked_token_is_rejected_by_all_case_surfaces(api):
    client,_=api
    for path in ['/api/v2/cases','/api/v2/users','/api/v1/cases','/api/v1/jobs','/api/v1/parsers/capabilities']:
        assert client.get(path).status_code==401
        assert client.get(path,headers={'Authorization':'Bearer invalid'}).status_code==401
