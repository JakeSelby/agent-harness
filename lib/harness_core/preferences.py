"""Resolve user preferences once for instructions, native policy and measurement."""
import copy
from contextvars import ContextVar
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from . import catalog

ACTIVE = ContextVar("harness_effective_preferences", default=None)
ROOT = Path(__file__).resolve().parents[2]
# These settings cannot grant native authority. No project or environment setting overrides.
SCHEMA = {
    'budgets.gather_words': (int, 1, 100000), 'budgets.digest_words': (int, 1, 100000),
    'budgets.search_calls': (int, 1, 10000), 'budgets.fan_out': (int, 1, 32),
    'budgets.review_rounds': (int, 1, 10),
    'delegation_controls.writes': ('serial', 'isolated-worktrees'),
    'delegation_controls.max_depth': (int, 1, 8),
    'observability.enabled': (bool,), 'observability.retention_days': (int, 0, 36500),
    'observability.include_repo': (bool,), 'observability.include_branch': (bool,),
    'gates.mode': ('blocking', 'advisory'), 'gates.max_blocks': (int, 1, 100),
    'gates.timeout_seconds': (int, 1, 3600),
}
DEFAULT_SETTINGS = {
    'budgets': {'gather_words': 400, 'digest_words': 600, 'search_calls': 200,
                'fan_out': 6, 'review_rounds': 3},
    'delegation_controls': {'writes': 'serial', 'max_depth': 1},
    'observability': {'enabled': True, 'retention_days': 0, 'include_repo': True, 'include_branch': True},
    'gates': {'mode': 'blocking', 'max_blocks': 8, 'timeout_seconds': 240},
}
OPERATIONAL = {'autonomy', 'delegation', 'cost', 'voice', 'context', 'plan-ceremony',
               'verification', 'external-actions', 'review', 'review-independence'}


def read(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('configuration must be an object: ' + str(path))
    return data


def load(root=ROOT, env=None, config_path=None):
    env = os.environ if env is None else env
    home = Path(env.get('HARNESS_HOME', env.get('HOME', str(Path.home()))))
    cfg = read(root / 'config.example.json')
    user = read(Path(config_path) if config_path is not None else home / '.config/agent-harness/config.json')
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    if not isinstance(cfg.get("stances"), dict):
        raise ValueError("stances must be an object")
    project_file = env.get('HARNESS_PROJECT_CONFIG')
    if project_file:
        project = read(Path(project_file).expanduser())
        if set(project) - {'stances'} or not isinstance(project.get('stances', {}), dict):
            raise ValueError('project config may select stances only')
        cfg['stances'].update(project.get('stances', {}))
    for key, value in env.items():
        if key.startswith('HARNESS_STANCE_'):
            cfg['stances'][key[15:].lower().replace('_', '-')] = value
        elif key.startswith('HARNESS_IDENTITY_'):
            cfg['identity'][key[17:].lower()] = value
        elif key == 'HARNESS_PERMISSIONS':
            cfg['permissions'] = value
        elif key in ('HARNESS_MANAGE_VSCODE', 'HARNESS_MANAGE_CODEX'):
            cfg[key[15:].lower()]['manage'] = value not in ('0', 'false', 'no')
    settings(cfg)
    return cfg


def validate_setting(key, value):
    spec = SCHEMA.get(key)
    if spec is None:
        raise ValueError('unknown operational setting: ' + key)
    if spec[0] is bool:
        valid = type(value) is bool
    elif spec[0] is int:
        valid = type(value) is int and spec[1] <= value <= spec[2]
    else:
        valid = isinstance(value, str) and value in spec
    if not valid:
        raise ValueError('invalid setting ' + key + ': expected ' + str(spec))
    return value


def settings(config):
    result = copy.deepcopy(DEFAULT_SETTINGS)
    cost = config.get('stances', {}).get('cost', 'balanced')
    result['budgets']['fan_out'] = {'frugal': 3, 'balanced': 6, 'max': 16}.get(cost, 6)
    for group in result:
        supplied = config.get(group, {})
        if not isinstance(supplied, dict):
            raise ValueError(group + ' must be an object')
        for key, value in supplied.items():
            result[group][key] = validate_setting(group + '.' + key, value)
    return result


def resolve(config, root=ROOT):
    choices = catalog.resolve_stances(root, config)
    operational = {}
    bindings = config.get('policy_bindings', {})
    if not isinstance(bindings, dict):
        raise ValueError('policy_bindings must be an object')
    for key, target in bindings.items():
        parts = key.split('/')
        if len(parts) != 2 or parts[0] not in OPERATIONAL:
            raise ValueError('invalid operational binding: ' + key)
        name, variant = parts
        catalog.identifier(variant)
        catalog.identifier(target)
        if (root / 'primitives/stances' / name / (variant + '.md')).is_file():
            raise ValueError('built-in policy cannot be rebound: ' + key)
        if not (root / 'primitives/stances' / name / (target + '.md')).is_file():
            raise ValueError('policy binding must name a built-in variant: ' + key)
    for name, path in choices.items():
        builtin = root / 'primitives/stances' / name / (path.stem + '.md')
        operational[name] = path.stem if builtin.is_file() else bindings.get(name + '/' + path.stem)
    budget_config = copy.deepcopy(config)
    if operational.get('cost'):
        budget_config['stances']['cost'] = operational['cost']
    families = config.get('model_families', {})
    if not isinstance(families, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in families.items()):
        raise ValueError('model_families must map model identifiers to nonempty family names')
    return {'stances': dict(config['stances']), 'execution': operational, 'model_families': dict(families),
            'settings': settings(budget_config), 'sources': {k: str(v) for k, v in choices.items()}}


def current(env=None, config_path=None):
    active = ACTIVE.get()
    if active is not None:
        return active
    return resolve(load(env=env, config_path=config_path))


def choice(name, fallback=None, policy=None):
    policy = current() if policy is None else policy
    value = policy['execution'].get(name, fallback)
    if value is None and name in OPERATIONAL:
        raise ValueError('custom ' + name + ' is guidance-only; select an explicit policy_bindings mapping before execution')
    return value


def review_plan(policy, risk='logic', author_model=None, reviewer_model=None):
    if risk not in ('presentation', 'logic', 'sensitive'):
        raise ValueError('review risk must be presentation, logic or sensitive')
    depth = choice('review', 'scope-and-quality', policy)
    if depth == 'risk-adaptive':
        depth = {'presentation': 'self-check', 'logic': 'independent', 'sensitive': 'scope-and-quality'}[risk]
    roles = {'self-check': [], 'independent': ['reviewer'],
             'scope-and-quality': ['spec-reviewer', 'reviewer']}[depth]
    unresolved = []
    if roles and choice('delegation', 'tiered', policy) == 'off':
        unresolved.append('delegation is off; independent review remains unperformed')
    families = policy.get('model_families', {})
    author_family, reviewer_family = families.get(author_model), families.get(reviewer_model)
    different = bool(author_family and reviewer_family and author_family != reviewer_family)
    if roles and choice('review-independence', 'fresh-context', policy) == 'different-family' and not different:
        unresolved.append('a different model family is required; supply author/reviewer models and user model_families bindings')
    return {'depth': depth, 'roles': roles, 'unresolved': unresolved,
            'model_binding': {'author': author_model, 'reviewer': reviewer_model,
                              'author_family': author_family, 'reviewer_family': reviewer_family,
                              'source': 'user-configured; worker must use the selected reviewer model'}}


def external_scope(config, action, destination, now=None):
    """Match explicit user-configured authority, never tool-supplied approval flags."""
    now = datetime.now(timezone.utc) if now is None else now
    scopes = config.get('external_scopes', [])
    if not isinstance(scopes, list):
        raise ValueError('external_scopes must be a list')
    matched = False
    for scope in scopes:
        if not isinstance(scope, dict) or set(scope) != {'action', 'destination', 'expires_at'}:
            raise ValueError('external scope needs action, destination and expires_at')
        if any(not isinstance(scope[k], str) or not scope[k].strip() for k in scope):
            raise ValueError('external scope fields must be nonempty strings')
        expiry = datetime.fromisoformat(scope['expires_at'].replace('Z', '+00:00'))
        if expiry.tzinfo is None:
            raise ValueError('external scope expiry requires an explicit timezone')
        matched |= scope['action'] == action and scope['destination'] == destination and expiry > now
    return matched


def guidance(policy):
    return 'Effective operational settings (user-owned; native limits still apply):\n' + json.dumps(policy['settings'], sort_keys=True)


def delegation_check(policy, workspace, active=(), depth=1, constrained=False):
    """Check declared scheduling inputs; this does not attest to native worker isolation."""
    import subprocess
    if type(depth) is not int or depth < 1:
        raise ValueError('delegation depth must be a positive integer')
    controls = policy['settings']['delegation_controls']
    if choice('delegation', 'tiered', policy) == 'off':
        raise ValueError('delegation is off')
    if depth > controls['max_depth'] or (constrained and depth > 1):
        raise ValueError('delegation depth exceeds role or user policy')
    if not active:
        return {'eligible': True, 'coverage': 'declared scheduling inputs only; native confinement is separate'}
    if controls['writes'] == 'serial':
        raise ValueError('serial writes: another declared writer is active')
    roots = []
    for directory in [workspace] + list(active):
        path = Path(directory).resolve()
        out = subprocess.run(['git', '-C', str(path), 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True, timeout=5)
        if out.returncode or Path(out.stdout.strip()).resolve() != path:
            raise ValueError('writers must declare distinct Git worktree roots')
        # A linked worktree has a .git file; the shared checkout may not host a parallel writer.
        if not (path / '.git').is_file():
            raise ValueError('parallel writers require isolated linked worktrees')
        if any(path == other or path in other.parents or other in path.parents for other in roots):
            raise ValueError('writer worktrees overlap')
        roots.append(path)
    return {'eligible': True, 'coverage': 'declared scheduling inputs only; native confinement is separate'}
