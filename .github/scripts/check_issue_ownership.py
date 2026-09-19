"""Validate GitHub's closing-issue relationships using read-only API calls."""

import json
import os
import subprocess
import sys


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
    print('Issue ownership verified: #{}'.format(issue))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print('Issue ownership check failed: {}'.format(error), file=sys.stderr)
        sys.exit(1)
