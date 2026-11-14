#!/usr/bin/env python3
"""Read-only Docker artifact checks. Does not start Compose services or attach data volumes."""
import argparse
import os
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    env = os.environ | {'SCHEDULER_ADMIN_PASSWORD': 'synthetic-artifact-check-password'}
    image_sets = []
    for name in ('artifact-check-a', 'artifact-check-b'):
        output = subprocess.check_output(['docker', 'compose', '-p', name, 'config', '--images'], env=env, text=True)
        image_sets.append({image for image in output.splitlines() if not image.startswith('nginx:')})
    assert image_sets[0].isdisjoint(image_sets[1]), 'Independent projects must not share a mutable application image tag'
    print('PASS independent application image names per Compose project')
    code = 'from pathlib import Path; assert Path("/app/LICENSE").is_file(); assert Path("/app/THIRD_PARTY_NOTICES.md").is_file(); p=Path("/app/docs/licenses"); assert list(p.glob("npm-react-LICENSE*")); assert len(list(p.glob("*.txt")))>=10'
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', args.image, 'python', '-c', code], check=True)
    print('PASS project and dependency licence texts retained in runtime image')

if __name__ == '__main__':
    main()
