"""Wall-clock recurrence anchored in Lisbon. Skip invalid dates and DST gaps.
Repeated autumn hours select fold=0 once, never both instants.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY

LISBON=ZoneInfo('Europe/Lisbon')
UTC=timezone.utc

def local_instant(value):
    local=datetime.fromisoformat(value)
    if local.tzinfo is not None: raise ValueError('Use data/hora local sem fuso; Europe/Lisbon é aplicado pelo servidor.')
    aware=local.replace(tzinfo=LISBON,fold=0)
    result=aware.astimezone(UTC)
    if result.astimezone(LISBON).replace(tzinfo=None)!=local:
        raise ValueError('Esta hora não existe em Europe/Lisbon devido à mudança de hora.')
    return result

def next_occurrence(message, after):
    if message.recurrence=='once': return None
    start=datetime.fromisoformat(message.scheduled_local)
    freq={'daily':DAILY,'weekly':WEEKLY,'weekdays':WEEKLY,'monthly':MONTHLY,'yearly':YEARLY}[message.recurrence]
    params={'byweekday':message.weekdays} if message.recurrence=='weekdays' else {}
    rule=rrule(freq,dtstart=start,**params)
    wall=datetime.fromtimestamp(after,UTC).astimezone(LISBON).replace(tzinfo=None)
    candidate=rule.after(wall,inc=False)
    for _ in range(400):
        if candidate is None or (message.end_date and candidate.date().isoformat()>message.end_date): return None
        try:
            instant=local_instant(candidate.isoformat()).timestamp()
            if instant>after: return instant
        except ValueError: pass
        candidate=rule.after(candidate,inc=False)
    raise ValueError('Não foi possível calcular a recorrência.')


def first_occurrence(message):
    start=local_instant(message.scheduled_local).timestamp()
    if message.recurrence=='weekdays' and datetime.fromisoformat(message.scheduled_local).weekday() not in message.weekdays:
        result=next_occurrence(message,start-1)
        if result is None: raise ValueError('Não existe ocorrência nos dias selecionados antes da data final.')
        return result
    return start
