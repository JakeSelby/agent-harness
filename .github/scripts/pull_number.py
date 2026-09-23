"""The pull request a check is judging, on a pull request run or on a merge queue run.

A `merge_group` event carries no pull request object. GitHub names the queue's temporary branch
`gh-readonly-queue/<base>/pr-<number>-<sha>`, one branch per queued entry, so the entry's own
pull request is recoverable from that name.
"""

import os
import re

QUEUE_REF = re.compile(r'(?:^|/)gh-readonly-queue/.+/pr-([0-9]+)-[0-9a-f]+$')


def pull_number(env=None):
    """The pull request number, or KeyError when the run names neither a PR nor a queue entry."""
    env = os.environ if env is None else env
    if env.get('PR_NUMBER'):
        return int(env['PR_NUMBER'])
    match = QUEUE_REF.search(env.get('MERGE_GROUP_HEAD_REF', ''))
    if match:
        return int(match.group(1))
    raise KeyError('neither PR_NUMBER nor a merge queue MERGE_GROUP_HEAD_REF is set')
