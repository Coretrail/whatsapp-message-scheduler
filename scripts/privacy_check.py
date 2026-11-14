#!/usr/bin/env python3
"""Inspect publishable files and every Git object without printing sensitive matches."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'private-network': rb'\b(?:192[.]168[.]\d{1,3}[.]\d{1,3}|10[.]\d{1,3}[.]\d{1,3}[.]\d{1,3}|172[.](?:1[6-9]|2\d|3[01])[.]\d{1,3}[.]\d{1,3})\b',
    'private-key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'operational-database': rb'^SQLite format 3\x00',
}


def inspect(label, data):
    findings = [name for name, rule in RULES.items() if re.search(rule, data)]
    # The only contiguous international number shipped in fixtures is reserved fiction.
    numbers = re.findall(rb'(?<![\w)])\+[1-9][0-9]{6,14}\b', data)
    if any(n != b'+12025550123' for n in numbers):
        findings.append('unapproved-phone-like-value')
    return [(label, finding) for finding in findings]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-objects', action='store_true')
    args = parser.parse_args()
    files = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0')
    findings = []
    for name in filter(None, files):
        path = ROOT / name
        if path.is_file():
            findings.extend(inspect(name, path.read_bytes()))
        if name == '.env' or name.startswith(('data/', 'secrets/', 'backups/', 'artifacts/')) or re.search(r'\.(?:db|sqlite|log|pem|key)(?:$|[.-])', name):
            findings.append((name, 'forbidden-publish-path'))
    if args.all_objects:
        objects = subprocess.check_output(['git', '-C', str(ROOT), 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)']).decode().splitlines()
        for row in objects:
            oid, kind = row.split()
            data = subprocess.check_output(['git', '-C', str(ROOT), 'cat-file', kind, oid])
            findings.extend(inspect('git-object:' + oid, data))
        print(f'Inspected {len(objects)} Git objects, including unreachable objects')
    for name, kind in findings:
        print(f'{kind}: {name}')
    print(f'Privacy indicators: {len(findings)}; tracked files: {len(list(filter(None, files)))}')
    raise SystemExit(bool(findings))

if __name__ == '__main__':
    main()
