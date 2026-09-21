"""Validate GitHub's closing-issue relationships using read-only API calls."""

import json
import os
import subprocess
import sys
from pathlib import Path

ISSUE_MAP = Path(__file__).resolve().parents[2] / '_bmad-output' / 'issue-map.json'


QUERY = """
query($owner:String!, $name:String!, $endCursor:String) {
  repository(owner:$owner, name:$name) {
    pullRequests(first:100, after:$endCursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number state merged
        closingIssuesReferences(first:100) {
          totalCount
          nodes { number repository { nameWithOwner } }
        }
      }
    }
  }
}
"""


def validate(pulls, number, repository):
    current = next((pr for pr in pulls if pr['number'] == number), None)
    if current is None:
        raise ValueError('Current PR was not returned by GitHub.')
    refs = current['closingIssuesReferences']
    if refs['totalCount'] != 1 or len(refs['nodes']) != 1:
        raise ValueError('Link exactly one delivery issue using Closes #N.')
    issue = refs['nodes'][0]
    if issue['repository']['nameWithOwner'].lower() != repository.lower():
        raise ValueError('The delivery issue must belong to this repository.')
    for other in pulls:
        if other['number'] == number:
            continue
        links = other['closingIssuesReferences']
        if links['totalCount'] != len(links['nodes']):
            raise ValueError('Issue references were truncated; ownership is unknown.')
        for candidate in links['nodes']:
            if (candidate['number'] == issue['number']
                    and candidate['repository']['nameWithOwner'].lower() == repository.lower()
                    and (other['state'] == 'OPEN' or other['merged'])):
                raise ValueError('Delivery issue is already owned by PR #{}.'.format(other['number']))
    return issue['number']


def require_mapping(issue, map_path):
    """The delivery issue must carry a BMad ID in the map this PR would leave on the base branch."""
    try:
        items = json.loads(map_path.read_text(encoding='utf-8'))['items']
        mapped = {entry['github_number']: entry['bmad_id'] for entry in items}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError('The BMad issue map at {} is missing or malformed: {!r}'.format(map_path, error))
    item = {'bmad_id': mapped[issue]} if issue in mapped else None
    if item is None:
        raise ValueError(
            'Delivery issue #{0} has no BMad ID. Run python3 scripts/bmad_issue_sync.py reserve '
            '--issue {0} --kind KIND and commit the result in this PR.'.format(issue))
    return item['bmad_id']


def main():
    repository = os.environ['GITHUB_REPOSITORY']
    owner, name = repository.split('/')
    result = subprocess.run([
        'gh', 'api', 'graphql', '--paginate', '--slurp',
        '-f', 'query=' + QUERY, '-f', 'owner=' + owner, '-f', 'name=' + name,
    ], check=True, capture_output=True, text=True)
    pulls = []
    for page in json.loads(result.stdout):
        if page.get('errors'):
            raise ValueError('GitHub returned errors; ownership is unknown.')
        pulls.extend(page['data']['repository']['pullRequests']['nodes'])
    issue = validate(pulls, int(os.environ['PR_NUMBER']), repository)
    bmad_id = require_mapping(issue, ISSUE_MAP)
    print('Issue ownership verified: #{} ({})'.format(issue, bmad_id))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print('Issue ownership check failed: {}'.format(error), file=sys.stderr)
        sys.exit(1)
