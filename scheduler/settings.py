"""Portable configuration. Only the offline demonstration provider is shipped."""
import os
from pathlib import Path

DB_PATH = os.getenv('SCHEDULER_DB', '/data/scheduler.db')
AUTH_PATH = Path(os.getenv('SCHEDULER_AUTH', '/data/auth.json'))
LATE_TOLERANCE = int(os.getenv('LATE_TOLERANCE_SECONDS', '900'))
HOUR_LIMIT = int(os.getenv('MAX_SENDS_PER_HOUR', '30'))
if LATE_TOLERANCE < 1 or not 1 <= HOUR_LIMIT <= 1000:
    raise ValueError('Invalid scheduling safety limits')
