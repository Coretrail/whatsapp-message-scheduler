#!/usr/bin/env python3
"""Create a private environment file once; never overwrite an existing installation."""
import os
from pathlib import Path
import secrets


def main():
    target = Path(__file__).resolve().parents[1] / '.env'
    example = target.with_name('.env.example').read_text()
    content = example.replace('SCHEDULER_ADMIN_PASSWORD=\n', 'SCHEDULER_ADMIN_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
    try:
        with open(target, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            stream.write(content)
    except FileExistsError:
        raise SystemExit('.env already exists; refusing to overwrite it')
    print('Created .env with a generated password. Read it privately; do not commit or share it.')

if __name__ == '__main__':
    main()
