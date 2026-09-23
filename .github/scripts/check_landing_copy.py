"""Keep the landing copy current with the capabilities a pull request changes."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pull_number import pull_number  # noqa: E402

CAPABILITY_ROOTS = ('bin/', 'lib/', 'adapters/', 'primitives/', 'policy/')
PRODUCT = 'product.json'
ESCAPE = re.compile(r'^\s*Landing copy:\s*(.+?)\s*$', re.MULTILINE)
MINIMUM_REASON = 20

FAILURE = (
    'A pull request that adds or changes a user-visible capability updates {product} in the same '
    'pull request. Touched: {touched}. Satisfy this either by updating {product}, or by adding a '
    'line to the pull request body that begins "Landing copy:" and says in at least {minimum} '
    'characters why the landing copy needs no change.')


def touched_capability_paths(files):
    return sorted(path for path in files if path.startswith(CAPABILITY_ROOTS))


def reason(body):
    match = ESCAPE.search(body or '')
    return match.group(1) if match else None


def validate(files, body):
    """Return the sentence to print, or raise ValueError naming both ways to satisfy the rule."""
    touched = touched_capability_paths(files)
    if not touched:
        return 'Landing copy check does not apply: no capability-bearing path changed.'
    if PRODUCT in files:
        return 'Landing copy verified: {} changed alongside {}.'.format(PRODUCT, touched[0])
    explained = reason(body)
    if explained is not None and len(explained) >= MINIMUM_REASON:
        return 'Landing copy waived by the pull request body: {}'.format(explained)
    raise ValueError(FAILURE.format(product=PRODUCT, touched=', '.join(touched),
                                    minimum=MINIMUM_REASON))


def pull_request(runner=None):
    runner = runner or subprocess.run
    repository, number = os.environ['GITHUB_REPOSITORY'], pull_number()
    files = runner([
        'gh', 'api', '--paginate', '-H', 'Accept: application/vnd.github+json',
        'repos/{}/pulls/{}/files'.format(repository, number), '--jq', '.[].filename'],
        check=True, capture_output=True, text=True)
    body = runner([
        'gh', 'api', '-H', 'Accept: application/vnd.github+json',
        'repos/{}/pulls/{}'.format(repository, number), '--jq', '.body'],
        check=True, capture_output=True, text=True)
    return [line for line in files.stdout.splitlines() if line.strip()], body.stdout


def main(runner=None):
    files, body = pull_request(runner)
    print(validate(files, body))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print('Landing copy check failed: {}'.format(error), file=sys.stderr)
        sys.exit(1)
