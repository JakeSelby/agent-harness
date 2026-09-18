"""Cross-surface behavior for explicit preferences and bounded operational settings."""
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from test_harness import harness, CFG, TEMPLATE, REPO
from harness_core import preferences, lifecycle, workers, reconcile


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.config = self.base / '.config/agent-harness/config.json'
        self.config.parent.mkdir(parents=True)
        self.cfg = copy.deepcopy(CFG)
        self.environment = patch.dict(os.environ, {'HOME': str(self.base), 'PATH': os.environ['PATH']}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def save(self):
        self.config.write_text(json.dumps(self.cfg))

    def policy(self, **stances):
        self.cfg['stances'].update(stances)
        return preferences.resolve(self.cfg, REPO)

    def test_project_selection_reaches_cli_coordinator_legacy_hooks_and_telemetry(self):
        self.save()
        project = self.base / 'project.json'
        project.write_text(json.dumps({'stances': {'delegation': 'session-model', 'voice': 'off', 'autonomy': 'ask'}}))
        with patch.dict(os.environ, {'HARNESS_PROJECT_CONFIG': str(project)}):
            self.assertEqual(harness.load_config()['stances']['delegation'], 'session-model')
            self.assertEqual(lifecycle.selected('delegation', 'tiered'), 'session-model')
            self.assertEqual(lifecycle.load('tier-agent-spawns').stance(), 'session-model')
            self.assertEqual(lifecycle.load('brief-guard').stance(), 'session-model')
            self.assertEqual(lifecycle.load('grade-bash').stance(), 'ask')
            self.assertEqual(lifecycle.load('usage-log').stances()['voice'], 'off')
            with patch.dict(os.environ, {'HARNESS_STANCE_DELEGATION': 'off'}):
                self.assertEqual(lifecycle.load('tier-agent-spawns').stance(), 'off')
        project.write_text(json.dumps({'gates': {'mode': 'advisory'}}))
        with patch.dict(os.environ, {'HARNESS_PROJECT_CONFIG': str(project)}), self.assertRaises(ValueError):
            preferences.current()

    def test_old_configuration_gets_defaults_without_changing_its_explicit_choices(self):
        self.config.write_text(json.dumps({'stances': {'voice': 'off'}}))
        resolved = preferences.current()
        self.assertEqual(resolved['stances']['voice'], 'off')
        self.assertEqual(resolved['settings']['gates']['max_blocks'], 8)
        self.assertEqual(resolved['stances']['review'], 'scope-and-quality')

    def test_custom_guidance_has_no_implicit_operational_power(self):
        root = self.base / 'custom'
        for dimension, variant in [('feedback', 'direct'), ('autonomy', 'careful')]:
            folder = root / 'stances' / dimension
            folder.mkdir(parents=True)
            (folder / (variant + '.md')).write_text('Use the selected custom policy.\n')
        self.cfg['primitive_roots'] = [str(root)]
        policy = self.policy(feedback='direct', autonomy='careful')
        self.assertIsNone(policy['execution']['feedback'])
        with self.assertRaisesRegex(ValueError, 'guidance-only'):
            preferences.choice('autonomy', policy=policy)
        self.cfg['policy_bindings'] = {'autonomy/careful': 'ask'}
        self.assertEqual(preferences.choice('autonomy', policy=self.policy()), 'ask')
        self.cfg['policy_bindings'] = {'autonomy/execute': 'ask'}
        with self.assertRaisesRegex(ValueError, 'cannot be rebound'):
            self.policy()

    def test_invalid_settings_are_rejected_before_sync_mutates_home(self):
        for key, value in [('gates.max_blocks', True), ('gates.timeout_seconds', 0),
                           ('budgets.search_calls', -1), ('observability.enabled', 'false'),
                           ('delegation_controls.writes', 'shared-checkout')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                preferences.validate_setting(key, value)
        self.cfg['gates']['unknown'] = 10
        self.save()
        with self.assertRaises(SystemExit):
            harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=False, adopt_codex=False, print_only=False))
        self.assertFalse((self.base / '.claude').exists())

    def test_operational_schema_accepts_boundaries_and_rejects_wrong_types(self):
        for key, spec in preferences.SCHEMA.items():
            with self.subTest(key=key):
                if spec[0] is int:
                    valid, invalid = [spec[1], spec[2]], [spec[1] - 1, spec[2] + 1, True, str(spec[1])]
                elif spec[0] is bool:
                    valid, invalid = [True, False], [0, 1, 'true']
                else:
                    valid, invalid = list(spec), ['unknown', None, True]
                for value in valid:
                    self.assertEqual(preferences.validate_setting(key, value), value)
                for value in invalid:
                    with self.assertRaises(ValueError):
                        preferences.validate_setting(key, value)
        with self.assertRaises(ValueError):
            preferences.validate_setting('gates.unknown', 1)

    def test_cost_defaults_explicit_budgets_and_compaction_are_independent(self):
        self.assertEqual(self.policy(cost='frugal')['settings']['budgets']['fan_out'], 3)
        self.cfg['budgets'] = {'fan_out': 9}
        self.assertEqual(self.policy(cost='frugal')['settings']['budgets']['fan_out'], 9)
        detectors = lifecycle.load('rule-detectors')
        event = [{'kind': 'compact', 'turn': 1}]
        self.assertNotIn('cache-hygiene/compact', detectors.run(event, {'cost': 'max'}))
        self.assertIn('cache-hygiene/compact', detectors.run(event, {'cost': 'max', 'context': 'preserve-cache'}))
        self.assertNotIn('cache-hygiene/compact', detectors.run(event, {'cost': 'frugal', 'context': 'adaptive'}))
        events = [{'kind': 'tool_use', 'name': 'WebSearch', 'turn': i} for i in range(3)]
        self.assertIn('research/search-over-cap', detectors.run(events, settings={'budgets': {'search_calls': 2}}))
        self.assertNotIn('research/search-over-cap', detectors.run(events, settings={'budgets': {'search_calls': 3}}))

    def test_brief_guard_uses_effective_word_budget(self):
        self.cfg['budgets'] = {'gather_words': 123}
        self.save()
        result = lifecycle.invoke('brief-guard', {'tool_name': 'Agent', 'tool_input': {'prompt': 'Inspect source.'}})
        self.assertIn('123', result['hookSpecificOutput']['updatedInput']['prompt'])

    def test_off_does_not_install_a_style_and_transitions_restore_original(self):
        self.cfg['stances']['voice'] = 'off'
        self.assertNotIn('outputStyle', harness.merge_claude_settings({}, TEMPLATE, self.cfg))
        settings_file = self.base / '.claude/settings.json'
        settings_file.parent.mkdir()
        settings_file.write_text(json.dumps({'outputStyle': 'Personal', 'other': 1}))
        store = reconcile.Store(self.base / 'state')
        for _ in range(2):
            store.json(settings_file, {'outputStyle': 'Scannable'}, [['outputStyle']])
            self.assertEqual(json.loads(settings_file.read_text())['outputStyle'], 'Scannable')
            store.release_json(settings_file, ['outputStyle'])
            self.assertEqual(json.loads(settings_file.read_text()), {'outputStyle': 'Personal', 'other': 1})
        store.json(settings_file, {'outputStyle': 'Scannable'}, [['outputStyle']])
        settings_file.write_text(json.dumps({'outputStyle': 'Changed by user'}))
        store.release_json(settings_file, ['outputStyle'])
        self.assertEqual(json.loads(settings_file.read_text())['outputStyle'], 'Changed by user')
        self.assertTrue(store.conflicts)

    def test_absent_original_style_is_removed_on_release(self):
        path = self.base / 'settings.json'
        store = reconcile.Store(self.base / 'state')
        store.json(path, {'outputStyle': 'Scannable'}, [['outputStyle']])
        store.release_json(path, ['outputStyle'])
        self.assertNotIn('outputStyle', json.loads(path.read_text()))

    def test_review_depth_and_unavailable_independence(self):
        self.assertEqual(preferences.review_plan(self.policy(review='self-check'))['roles'], [])
        self.assertEqual(preferences.review_plan(self.policy(review='independent'))['roles'], ['reviewer'])
        for risk, roles in [('presentation', []), ('logic', ['reviewer']), ('sensitive', ['spec-reviewer', 'reviewer'])]:
            self.assertEqual(preferences.review_plan(self.policy(review='risk-adaptive'), risk)['roles'], roles)
        policy = self.policy(review='independent', delegation='off')
        self.assertTrue(preferences.review_plan(policy)['unresolved'])
        policy = self.policy(delegation='tiered', **{'review-independence': 'different-family'})
        self.assertTrue(preferences.review_plan(policy)['unresolved'])
        self.cfg['model_families'] = {'author-model': 'family-a', 'review-model': 'family-b'}
        policy = self.policy()
        self.assertFalse(preferences.review_plan(policy, author_model='author-model', reviewer_model='review-model')['unresolved'])
        self.assertTrue(preferences.review_plan(policy, author_model='author-model', reviewer_model='author-model')['unresolved'])
        with self.assertRaises(ValueError):
            preferences.review_plan(policy, 'unknown')

    def test_explicit_external_scope_is_exact_expiring_and_user_owned(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.cfg['external_scopes'] = [{'action': 'post', 'destination': 'project/discussion', 'expires_at': '2026-01-02T00:00:00Z'}]
        self.assertTrue(preferences.external_scope(self.cfg, 'post', 'project/discussion', now))
        self.assertFalse(preferences.external_scope(self.cfg, 'delete', 'project/discussion', now))
        self.assertFalse(preferences.external_scope(self.cfg, 'post', 'other', now))
        self.assertFalse(preferences.external_scope(self.cfg, 'post', 'project/discussion', now + timedelta(days=1)))
        self.cfg['external_scopes'][0]['expires_at'] = '2026-01-02'
        with self.assertRaises(ValueError):
            preferences.external_scope(self.cfg, 'post', 'project/discussion', now)

    def test_disabled_collection_does_not_launch_read_or_write(self):
        self.cfg['observability']['enabled'] = False
        self.save()
        module = lifecycle.load('usage-log')
        with patch.object(module.subprocess, 'Popen') as launch, patch.object(module, 'scan') as scan:
            self.assertEqual(module.main(['--worker', '/missing']), 0)
            self.assertEqual(module.rescan(), 0)
            module.upsert({'session_id': 'one'})
            launch.assert_not_called()
            scan.assert_not_called()
        self.assertFalse(module.usage_path().exists())

    def test_telemetry_metadata_and_retention_do_not_erase_unknown_age(self):
        self.cfg['observability'].update(include_repo=False, include_branch=False, retention_days=1)
        self.save()
        module = lifecycle.load('usage-log')
        path = self.base / 'usage.jsonl'
        old = datetime.now(timezone.utc) - timedelta(days=2)
        recent = datetime.now(timezone.utc) - timedelta(hours=12)
        rows = [{'session_id': 'expired', 'ended': old.isoformat()},
                {'session_id': 'recent', 'ended': recent.isoformat()},
                {'session_id': 'unknown', 'ended': 'unavailable'}]
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        module.upsert({'session_id': 'new', 'repo': 'private', 'branch': 'private'}, path)
        records = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual({r['session_id'] for r in records}, {'recent', 'unknown', 'new'})
        self.assertNotIn('repo', records[-1])
        self.assertNotIn('branch', records[-1])
        self.assertIn('recorded_at', records[-1])

    def test_planner_light_contract_does_not_force_review_card(self):
        work = self.base / 'work'
        workers.validate_artifact(REPO, '# A small plan\n\n1. Check the result.', work, 'light')
        with self.assertRaisesRegex(ValueError, 'Review Card'):
            workers.validate_artifact(REPO, '# A small plan\n\n1. Check the result.', work, 'review-card')
        with self.assertRaises(ValueError):
            workers.validate_artifact(REPO, 'untitled', work, 'light')
        with self.assertRaises(ValueError):
            workers.validate_artifact(REPO, '', work, 'light')

    def test_every_builtin_variant_resolves_and_reaches_worker_instructions(self):
        for dimension in (REPO / 'primitives/stances').iterdir():
            for variant in dimension.glob('*.md'):
                cfg = copy.deepcopy(CFG)
                cfg['stances'][dimension.name] = variant.stem
                with self.subTest(dimension=dimension.name, variant=variant.stem):
                    policy = preferences.resolve(cfg, REPO)
                    self.assertEqual(policy['execution'][dimension.name], variant.stem)
                    if cfg['stances']['delegation'] != 'off':
                        for runtime in ('codex', 'claude-code'):
                            instructions = workers.resolve(REPO, cfg, runtime, 'reviewer', 'fixture-model')[2]
                            self.assertIn(variant.read_text(), instructions)
                            self.assertIn('Effective operational settings', instructions)

    def test_declared_parallel_writers_require_isolated_nonoverlapping_roots(self):
        policy = self.policy()
        with self.assertRaisesRegex(ValueError, 'serial'):
            preferences.delegation_check(policy, self.base, [self.base])
        self.cfg['delegation_controls']['writes'] = 'isolated-worktrees'
        policy = self.policy()
        with self.assertRaisesRegex(ValueError, 'Git worktree'):
            preferences.delegation_check(policy, self.base, [self.base])
        repo = self.base / 'repo'
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture' + '@' + 'example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        roots = [self.base / 'one', self.base / 'two']
        for path in roots:
            subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '--detach', str(path)], check=True, capture_output=True)
        self.assertTrue(preferences.delegation_check(policy, roots[0], [roots[1]])['eligible'])
        with self.assertRaisesRegex(ValueError, 'overlap'):
            preferences.delegation_check(policy, roots[0], [roots[0]])
        with self.assertRaisesRegex(ValueError, 'linked worktrees'):
            preferences.delegation_check(policy, repo, [roots[1]])
        self.cfg['delegation_controls']['max_depth'] = 3
        with self.assertRaisesRegex(ValueError, 'depth'):
            preferences.delegation_check(self.policy(), roots[0], depth=2, constrained=True)

    def test_policy_commands_never_execute_an_external_action(self):
        self.save()
        out = subprocess.run([sys.executable, str(REPO / 'bin/harness'), 'policy', 'external', '--action', 'post', '--destination', 'fixture'], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        result = json.loads(out.stdout)
        self.assertFalse(result['standing_scope_matches'])
        self.assertIn('no action executed', result['coverage'])
        self.cfg['stances'].update(review='independent', delegation='off')
        self.save()
        out = subprocess.run([sys.executable, str(REPO / 'bin/harness'), 'policy', 'review'], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertTrue(json.loads(out.stdout)['unresolved'])

    def test_rescan_cannot_revive_expired_records_or_refresh_their_collection_time(self):
        self.cfg['observability']['retention_days'] = 1
        self.save()
        module = lifecycle.load('usage-log')
        path = self.base / 'usage.jsonl'
        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        module.upsert({'session_id': 'expired', 'ended': old}, path)
        self.assertEqual(path.read_text(), '')
        module.upsert({'session_id': 'present'}, path)
        original = json.loads(path.read_text())['recorded_at']
        module.upsert({'session_id': 'present'}, path)
        self.assertEqual(json.loads(path.read_text())['recorded_at'], original)

    def test_review_cli_consumes_explicit_model_family_bindings(self):
        self.cfg['stances']['review-independence'] = 'different-family'
        self.cfg['model_families'] = {'author-model': 'family-a', 'review-model': 'family-b'}
        self.save()
        out = subprocess.run([sys.executable, str(REPO / 'bin/harness'), 'policy', 'review',
                              '--author-model', 'author-model', '--reviewer-model', 'review-model'],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(json.loads(out.stdout)['unresolved'])

    def test_releasing_a_user_edited_style_retires_ownership(self):
        path = self.base / 'settings.json'
        store = reconcile.Store(self.base / 'state')
        store.json(path, {'outputStyle': 'Scannable'}, [['outputStyle']])
        path.write_text(json.dumps({'outputStyle': 'User edit'}))
        store.release_json(path, ['outputStyle'])
        reloaded = reconcile.Store(self.base / 'state')
        reloaded.release_json(path, ['outputStyle'])
        self.assertFalse(reloaded.conflicts)
        self.assertFalse(reloaded.drift())
        self.assertEqual(json.loads(path.read_text())['outputStyle'], 'User edit')

    def test_hook_deadline_covers_configured_gate_deadline(self):
        self.cfg['gates']['timeout_seconds'] = 600
        self.save()
        for runtime in ('claude-code', 'codex'):
            timeout = lifecycle.registration(REPO, runtime)['hooks']['Stop'][0]['hooks'][0]['timeout']
            self.assertGreater(timeout, 600)


class GatePreferenceTests(unittest.TestCase):
    def setUp(self):
        from test_stop_gate import StopGateTests
        self.fixture = StopGateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tmp.cleanup)
        self.addCleanup(self.fixture.tearDown)

    def config(self, **values):
        path = self.fixture.home / '.config/agent-harness/config.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'gates': values}))

    def test_advisory_records_failure_and_blocking_uses_configured_limit(self):
        f = self.fixture
        f.write_gate('exit 1')
        self.config(mode='advisory')
        self.assertEqual(f.run_hook().stdout.strip(), '')
        self.assertEqual(f.state()['status'], 'failed')
        self.assertTrue(f.state()['released'])
        self.config(mode='blocking', max_blocks=2)
        self.assertEqual(json.loads(f.run_hook(session='new').stdout)['decision'], 'block')
        self.assertEqual(f.run_hook(session='new').stdout.strip(), '')
        self.assertIsNone(f.state()['green_hash'])
        self.assertEqual(f.state()['status'], 'unverified')

    def test_timeout_and_changed_gate_settings_never_reuse_green_evidence(self):
        f = self.fixture
        f.write_gate('exit 0')
        f.run_hook()
        original = f.state()['green_hash']
        self.config(timeout_seconds=1)
        f.run_hook()
        self.assertNotEqual(f.state()['green_hash'], original)
        f.write_gate('sleep 2')
        self.assertEqual(f.run_hook().stdout.strip(), '')
        self.assertIsNone(f.state()['green_hash'])
        self.assertIn('past 1s', f.state()['reason'])


class SyncPreferenceTests(unittest.TestCase):
    setUp = PreferenceTests.setUp
    save = PreferenceTests.save
    def test_sync_off_on_off_restores_style_and_preserves_session_scope(self):
        self.cfg['vscode']['manage'] = False
        self.cfg['codex']['manage'] = False
        self.cfg['stances']['voice'] = 'off'
        self.save()
        settings = self.base / '.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'outputStyle': 'My style'}))
        args = harness.argparse.Namespace(dry_run=False, adopt=True, adopt_codex=False, print_only=False)
        with patch.object(harness, 'ensure_gitignore_entries'), patch.object(harness, 'ensure_local_bin_on_path'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness.cmd_sync(args), 0)
            self.cfg['stances']['voice'] = 'scannable'
            self.save()
            with patch.dict(os.environ, {'HARNESS_STANCE_VOICE': 'off'}):
                self.assertEqual(harness.cmd_sync(args), 0)
            self.assertEqual(json.loads(settings.read_text())['outputStyle'], 'Scannable')
            self.cfg['stances']['voice'] = 'off'
            self.save()
            self.assertEqual(harness.cmd_sync(args), 0)
            self.assertEqual(json.loads(settings.read_text())['outputStyle'], 'My style')
            self.assertEqual(harness.cmd_sync(args), 0)
            settings.write_text(json.dumps(dict(json.loads(settings.read_text()), outputStyle='New personal style')))
            self.assertFalse(any('outputStyle' in line for line in harness._diff_lines()))
