"""Daily learning history, grouped using the learner's local calendar."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from .auth import current_user
from .db import Attempt, get_db

router = APIRouter()


@router.get('/api/report')
def daily_report(days: int = Query(30, ge=1, le=90), timezone_name: str = Query('UTC', alias='timezone', max_length=100),
                 user=Depends(current_user), db=Depends(get_db)):
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, '无效的时区')
    today = datetime.now(zone).date()
    start = today - timedelta(days=days - 1)
    utc_start = datetime.combine(start, time.min, zone).astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = datetime.combine(today + timedelta(days=1), time.min, zone).astimezone(timezone.utc).replace(tzinfo=None)
    buckets = {(start + timedelta(days=i)).isoformat(): [] for i in range(days)}
    rows = db.execute(select(Attempt.created_at, Attempt.result).where(
        Attempt.user_id == user.id, Attempt.created_at >= utc_start, Attempt.created_at < utc_end))
    for created_at, result in rows:
        day = created_at.replace(tzinfo=timezone.utc).astimezone(zone).date().isoformat()
        buckets[day].append(result['score'])
    daily = [{'date': day, 'count': len(scores),
              'accuracy': round(sum(scores) / len(scores), 1) if scores else None}
             for day, scores in buckets.items()]
    scores = [score for values in buckets.values() for score in values]
    return {'timezone': timezone_name, 'daily': daily, 'total': len(scores),
            'accuracy': round(sum(scores) / len(scores), 1) if scores else None,
            'activeDays': sum(bool(values) for values in buckets.values())}
