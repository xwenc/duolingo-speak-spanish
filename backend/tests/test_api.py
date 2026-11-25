import os
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['COOKIE_SECURE'] = 'false'
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db, Exercise, User, Attempt
from app.main import app
from app.scoring import evaluate
from uuid import uuid4

@pytest.fixture
def client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with factory.begin() as db:
        db.add(Exercise(id='one', data={'id':'one', 'spanish':'Hola amigo'}))
    with TestClient(app, headers={'Origin': 'http://localhost:3000'}) as c:
        yield c, factory
    app.dependency_overrides.clear()

def register(c, email='test@example.com'):
    return c.post('/api/auth/register', json={'email': email, 'password': 'long-test-password'})

def test_auth_and_origin(client):
    c, _ = client
    assert c.get('/api/me').status_code == 401
    assert register(c).status_code == 200
    assert c.cookies.get('session')
    assert c.get('/api/me').json()['xp'] == 0
    assert c.post('/api/logout', headers={'Origin':'https://evil.example'}).status_code == 403
    assert c.post('/api/logout').status_code == 200
    assert c.get('/api/me').status_code == 401
    assert c.post('/api/auth/login', json={'email':'test@example.com', 'password':'wrong-password'}).status_code == 401

def test_attempt_idempotency_rewards_and_hearts(client):
    c, factory = client
    register(c)
    body = {'requestId':str(uuid4()), 'exerciseId':'one', 'transcript':'Hola amigo'}
    first = c.post('/api/attempts', json=body)
    assert first.status_code == 200
    assert first.json()['stats']['xp'] == 15
    assert c.post('/api/attempts', json=body).json()['stats']['xp'] == 15
    assert c.post('/api/attempts', json={**body, 'transcript':'otra'}).status_code == 409
    assert c.post('/api/attempts', json={**body, 'requestId':str(uuid4())}).json()['stats']['xp'] == 15
    for _ in range(5):
        r = c.post('/api/attempts', json={**body, 'requestId':str(uuid4()), 'transcript':''})
        assert r.status_code == 200
    assert r.json()['stats']['hearts'] == 5
    with factory.begin() as db:
        db.scalar(select(User)).hearts = 0
    assert c.post('/api/attempts', json={**body, 'requestId':str(uuid4())}).status_code == 200
    refilled = c.post('/api/hearts/refill')
    assert refilled.status_code == 200
    assert refilled.json()['hearts'] == 5
    assert refilled.json()['gems'] == 2
    with factory() as db:
        assert len(list(db.scalars(select(Attempt)))) == 8

def test_stars_isolated_and_persisted(client):
    c, _ = client
    register(c)
    assert c.put('/api/stars/one?enabled=true').json()['starredIds'] == ['one']
    assert c.put('/api/stars/missing?enabled=true').status_code == 404
    c.post('/api/logout')
    register(c, 'other@example.com')
    assert c.get('/api/me').json()['starredIds'] == []

def test_speech_validation(client):
    c, _ = client
    register(c)
    assert c.post('/api/speech', files={'audio':('a.txt',b'x','text/plain')}).status_code == 415
    with patch('app.main.speech.transcribe', return_value='Hola amigo'):
        assert c.post('/api/speech', files={'audio':('a.webm',b'x','audio/webm')}).json()['transcript'] == 'Hola amigo'

def test_scoring():
    assert evaluate('¡Hola, amigo!', 'hola amigo')['score'] == 100
    assert evaluate('año', 'ano')['score'] == 0
    assert evaluate('Hola amigo', '')['score'] == 0
    assert evaluate('Hola amigo', 'hola amigo extra extra extra')['score'] == 40

def test_free_refill_after_wait_and_expired_session(client):
    from datetime import datetime, timedelta
    from app.db import LoginSession
    c, factory = client
    r = register(c)
    assert 'httponly' in r.headers['set-cookie'].lower()
    assert 'samesite=lax' in r.headers['set-cookie'].lower()
    c.post('/api/attempts', json={'requestId': str(uuid4()), 'exerciseId':'one', 'transcript':''})
    with factory.begin() as db:
        latest = db.scalar(select(Attempt))
        latest.created_at = datetime.utcnow() - timedelta(minutes=31)
        user = db.scalar(select(User))
        user.hearts = 0
    result = c.post('/api/hearts/refill')
    assert result.status_code == 200
    assert result.json()['hearts'] == 5
    assert result.json()['gems'] == 0
    with factory.begin() as db:
        db.scalar(select(LoginSession)).expires = datetime.utcnow() - timedelta(seconds=1)
    assert c.get('/api/me').status_code == 401

def test_local_tts_auth_validation_and_audio(client):
    import httpx
    c, _ = client
    assert c.get('/api/tts', params={'text':'Hola'}).status_code == 401
    register(c)
    assert c.get('/api/tts', params={'text':'Hola', 'speed':0.1}).status_code == 422
    assert c.get('/api/tts', params={'text':'x'*501}).status_code == 422
    assert c.get('/api/tts', params={'text':'   '}).status_code == 422
    with patch('app.main.httpx.post', return_value=httpx.Response(200, content=b'RIFF-test-audio', request=httpx.Request('POST', 'http://127.0.0.1:8001/synthesize'))) as synth:
        response = c.get('/api/tts', params={'text':'Hola', 'speed':0.6})
        assert response.status_code == 200
        assert response.headers['content-type'] == 'audio/wav'
        assert response.content == b'RIFF-test-audio'
        assert synth.call_args.kwargs['json'] == {'text':'Hola', 'speed':0.6}
    with patch('app.main.httpx.post', side_effect=httpx.ConnectError('offline')):
        assert c.get('/api/tts', params={'text':'Hola'}).status_code == 503
    with patch('app.main.httpx.post', return_value=httpx.Response(503)), patch('app.main.asyncio.sleep'):
        assert c.get('/api/tts', params={'text':'Hola'}).headers['retry-after'] == '2'

def test_answers_only_preserve_manually_added_stars(client):
    from app.db import Star
    c, factory = client
    register(c)
    body = {'requestId':str(uuid4()), 'exerciseId':'one', 'transcript':'adiós'}
    failed = c.post('/api/attempts', json=body)
    assert failed.status_code == 200
    assert not failed.json()['evaluation']['isPassed']
    assert failed.json()['stats']['starredIds'] == []
    assert c.post('/api/attempts', json=body).json()['stats']['hearts'] == 5
    assert c.post('/api/attempts', json={**body, 'requestId':str(uuid4())}).json()['stats']['starredIds'] == []
    with factory() as db:
        assert len(list(db.scalars(select(Star)))) == 0
    assert c.get('/api/me').json()['starredIds'] == []
    assert c.put('/api/stars/one?enabled=true').json()['starredIds'] == ['one']
    failed_again = c.post('/api/attempts', json={**body, 'requestId':str(uuid4())})
    assert failed_again.json()['stats']['starredIds'] == ['one']
    passed = c.post('/api/attempts', json={**body, 'requestId':str(uuid4()), 'transcript':'Hola amigo'})
    assert passed.json()['stats']['starredIds'] == ['one']
    assert c.put('/api/stars/one?enabled=false').json()['starredIds'] == []

def test_global_reset_preserves_accounts_rebuilds_seed_and_revokes_other_sessions(client, monkeypatch):
    from app.db import Star, LoginSession
    from app.seed import load_book
    c, factory = client
    monkeypatch.setenv('ADMIN_EMAIL', 'test@example.com')
    register(c)
    admin_token = c.cookies.get('session')
    body = {'requestId':str(uuid4()), 'exerciseId':'one', 'transcript':'adiós'}
    assert c.post('/api/attempts', json=body).status_code == 200
    register(c, 'other@example.com')
    other_token = c.cookies.get('session')
    assert c.post('/api/attempts', json={**body, 'requestId':str(uuid4())}).status_code == 200
    assert c.post('/api/admin/reset-practice', json={'password':'long-test-password','confirmed':True}).status_code == 403
    c.cookies.set('session', admin_token, domain='testserver.local', path='/api')
    assert c.post('/api/admin/reset-practice', json={'password':'wrong-password','confirmed':True}).status_code == 401
    assert c.post('/api/admin/reset-practice', json={'password':'long-test-password','confirmed':False}).status_code == 422
    with factory() as db:
        credentials = {u.id:(u.email,u.password) for u in db.scalars(select(User))}
    response = c.post('/api/admin/reset-practice', json={'password':'long-test-password','confirmed':True})
    assert response.status_code == 200, response.text
    assert response.json()['stats']['hearts'] == 5
    assert response.json()['stats']['xp'] == 0
    assert response.json()['stats']['starredIds'] == []
    assert {row['id'] for row in response.json()['exercises']} == {sentence.id for chapter in load_book().book.chapters for sentence in chapter.sentences}
    with factory() as db:
        assert {u.id:(u.email,u.password) for u in db.scalars(select(User))} == credentials
        assert not list(db.scalars(select(Attempt)))
        assert not list(db.scalars(select(Star)))
        assert len(list(db.scalars(select(LoginSession)))) == 1
        assert db.get(Exercise, 'one') is None
        assert all((u.hearts,u.xp,u.gems,u.streak,u.last_practice)==(5,0,0,0,None) for u in db.scalars(select(User)))
    assert c.get('/api/me').status_code == 200
    c.cookies.set('session', other_token, domain='testserver.local', path='/api')
    assert c.get('/api/me').status_code == 401
    assert c.post('/api/auth/login', json={'email':'other@example.com','password':'long-test-password'}).status_code == 200

def test_reset_invalid_seed_keeps_existing_data(client, monkeypatch):
    c, factory = client
    monkeypatch.setenv('ADMIN_EMAIL','test@example.com')
    register(c)
    c.post('/api/attempts', json={'requestId':str(uuid4()),'exerciseId':'one','transcript':'adiós'})
    with patch('app.main.load_book', side_effect=ValueError('invalid')):
        assert c.post('/api/admin/reset-practice', json={'password':'long-test-password','confirmed':True}).status_code == 503
    assert c.get('/api/me').json()['hearts'] == 5
    with factory() as db:
        assert db.get(Exercise,'one') is not None
        assert len(list(db.scalars(select(Attempt)))) == 1


def test_chapter_progress_uses_latest_scores_and_is_account_scoped(client):
    from app.db import Book, Chapter
    from datetime import datetime
    c, factory = client
    register(c)
    with factory.begin() as db:
        user = db.scalar(select(User))
        db.add(Book(id='book', name='Book'))
        db.flush()
        db.add(Chapter(id='chapter', book_id='book', name='Chapter'))
        db.flush()
        db.get(Exercise, 'one').chapter_id = 'chapter'
        db.add(Exercise(id='two', chapter_id='chapter', data={'spanish': 'Hola'}))
        for exercise_id, score, day in [('one', 10, 1), ('one', 80, 2), ('two', 100, 3)]:
            db.add(Attempt(user_id=user.id, exercise_id=exercise_id, request_id=str(uuid4()),
                           result={'score': score}, created_at=datetime(2026, 1, day)))
    expected = {'chapter': {'averageScore': 90, 'practicedCount': 2, 'lastPracticedAt': '2026-01-03T00:00:00Z'}}
    assert c.get('/api/me').json()['chapterProgress'] == expected
    assert c.get('/api/me').json()['chapterProgress'] == expected
    c.post('/api/logout')
    register(c, 'other@example.com')
    assert c.get('/api/me').json()['chapterProgress'] == {}


def test_daily_report_timezone_gaps_accuracy_and_isolation(client):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    c, factory = client
    assert c.get('/api/report').status_code == 401
    register(c)
    today = datetime.now(ZoneInfo('Europe/Madrid')).date()
    with factory.begin() as db:
        user = db.scalar(select(User))
        other = User(email='report-other@example.com', password='unused')
        db.add(other)
        db.flush()
        # 23:30 UTC on the preceding day belongs to today in Madrid.
        from datetime import timedelta, time
        timestamp = datetime.combine(today - timedelta(days=1), time(23, 30))
        for owner, score in [(user.id, 100), (user.id, 50), (other.id, 0)]:
            db.add(Attempt(user_id=owner, exercise_id='one', request_id=str(uuid4()),
                           result={'score': score}, created_at=timestamp))
    response = c.get('/api/report?days=7&timezone=Europe%2FMadrid')
    assert response.status_code == 200
    report = response.json()
    assert len(report['daily']) == 7
    assert report['daily'][-1] == {'date': today.isoformat(), 'count': 2, 'accuracy': 75.0}
    assert report['daily'][0]['count'] == 0
    assert report['daily'][0]['accuracy'] is None
    assert report['total'] == 2
    assert report['accuracy'] == 75.0
    assert report['activeDays'] == 1
    for query in ['days=0', 'days=91', 'timezone=bad-zone']:
        assert c.get('/api/report?' + query).status_code == 422


def test_daily_report_empty_and_idempotent_submissions(client):
    c, _ = client
    register(c)
    empty = c.get('/api/report').json()
    assert empty['total'] == 0
    assert empty['accuracy'] is None
    body = {'requestId': str(uuid4()), 'exerciseId': 'one', 'transcript': 'Hola amigo'}
    assert c.post('/api/attempts', json=body).status_code == 200
    assert c.post('/api/attempts', json=body).status_code == 200
    assert c.get('/api/report').json()['total'] == 1
