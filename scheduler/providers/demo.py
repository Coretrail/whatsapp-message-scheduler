"""Offline simulation. This module intentionally has no network or filesystem access."""
from .base import Result

class DemoProvider:
    def send(self, job: dict) -> Result:
        if job['message'].get('consent') is not True:
            return Result('failed', error='consent_required')
        return Result('accepted', provider_id='demo:' + job['id'])

    def health(self) -> dict:
        return {'mode': 'demo', 'real_sending': False,
                'whatsapp': 'available', 'email': 'available',
                'contacts': {'state': 'disabled', 'count': 0, 'synced_at': None}}
