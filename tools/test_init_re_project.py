"""Bounded deployment checks; no model requests and no real research state writes."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import init_re_project as installer
import upgrade_re_skills as migration

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "templates/project-install/tools"))
import re_workflow_policy


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="re-install-test-")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.target)], check=True)

    def install(self):
        with contextlib.redirect_stdout(io.StringIO()):
            installer.install(SOURCE, self.target)

    def test_install_idempotent_and_no_research_state(self):
        self.install()
        lock = (self.target / installer.LOCK).read_bytes()
        self.install()
        self.assertEqual(lock, (self.target / installer.LOCK).read_bytes())
        self.assertFalse((self.target / ".research").exists())
        self.assertTrue((self.target / ".agents/skills/research-pause/SKILL.md").is_file())
        self.assertTrue((self.target / ".agents/skills/research-resume/SKILL.md").is_file())
        self.assertTrue((self.target / ".agents/skills/research-routes/SKILL.md").is_file())
        for name in ('research-resume', 'research-status', 'research-routes', 'research-engineering'):
            self.assertEqual((self.target / f'.agents/skills/{name}/SKILL.md').read_bytes(),
                             (self.target / f'.claude/skills/{name}/SKILL.md').read_bytes())
        self.assertIn('@AGENTS.md', (self.target / 'CLAUDE.md').read_text())
        settings = json.loads((self.target / '.claude/settings.json').read_text())
        self.assertIn('Skill(brainstorming)', settings['permissions']['deny'])
        self.assertNotIn('model', settings)
        self.assertNotIn('env', settings)
        self.assertEqual(len(list((self.target / ".agents/skills").glob("*/SKILL.md"))),
                         len(list((SOURCE / "skills").glob("*/SKILL.md"))))
        result = subprocess.run([sys.executable, "tools/re", "init"], cwd=self.target, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        result = subprocess.run([sys.executable, "tools/re", "validate", "--json"], cwd=self.target, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout.decode())
        result = subprocess.run([sys.executable, 'tools/re', 'routes', 'list', '--json'],
                                cwd=self.target, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(json.loads(result.stdout)['payload']['registered'])
        state = (self.target / ".research/ACTIVE.json").read_bytes()
        self.install()
        self.assertEqual(state, (self.target / ".research/ACTIVE.json").read_bytes())

    def test_conflicting_makefile_preserved_before_any_writes(self):
        (self.target / "Makefile").write_text("# user-owned\n")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual((self.target / "Makefile").read_text(), "# user-owned\n")
        self.assertFalse((self.target / "tools").exists())

    def test_skill_upgrade_preserves_state_and_runtime_and_archives_old_bytes(self):
        self.install()
        skill = self.target / ".agents/skills/research-status/SKILL.md"
        skill.write_text("old frozen skill\n")
        lock_path = self.target / installer.LOCK
        lock = json.loads(lock_path.read_text())
        lock["files"][skill.relative_to(self.target).as_posix()] = installer.digest(skill.read_bytes())
        lock_path.write_text(json.dumps(lock))
        old_lock = lock_path.read_bytes()
        state = self.target / ".research/ACTIVE.json"
        state.parent.mkdir()
        state.write_text('{"sentinel": "do not modify"}')
        runtime = (self.target / "tools/re").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            migration.upgrade(SOURCE, self.target)
            self.assertEqual(skill.read_text(), "old frozen skill\n")
            migration.upgrade(SOURCE, self.target, apply=True)
        self.assertEqual(state.read_text(), '{"sentinel": "do not modify"}')
        self.assertEqual((self.target / "tools/re").read_bytes(), runtime)
        backup = self.target / ".re-install-history" / installer.digest(old_lock)
        self.assertEqual((backup / installer.LOCK).read_bytes(), old_lock)
        self.assertEqual((backup / skill.relative_to(self.target)).read_text(), "old frozen skill\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(migration.upgrade(SOURCE, self.target, apply=True), [])

    def test_skill_upgrade_refuses_drift_without_writes(self):
        self.install()
        path = self.target / ".agents/skills/research-status/SKILL.md"
        path.write_text("user change")
        before = (self.target / installer.LOCK).read_bytes()
        with self.assertRaises(ValueError):
            migration.upgrade(SOURCE, self.target, apply=True)
        self.assertEqual(path.read_text(), "user change")
        self.assertEqual((self.target / installer.LOCK).read_bytes(), before)
        self.assertFalse((self.target / ".re-install-history").exists())

    def test_skill_upgrade_adds_new_skill_to_owned_snapshot(self):
        self.install()
        path = self.target / ".agents/skills/research-pause/SKILL.md"
        path.unlink()
        lock_path = self.target / installer.LOCK
        lock = json.loads(lock_path.read_text())
        del lock["files"][path.relative_to(self.target).as_posix()]
        lock["owned_directories"].remove(".agents/skills/research-pause")
        lock_path.write_text(json.dumps(lock))
        with contextlib.redirect_stdout(io.StringIO()):
            migration.upgrade(SOURCE, self.target, apply=True)
            installer.check(self.target)
        self.assertEqual(path.read_bytes(), (SOURCE / "skills/research-pause/SKILL.md").read_bytes())
        self.assertIn(".agents/skills/research-pause", json.loads(lock_path.read_text())["owned_directories"])

    def test_existing_research_refused(self):
        (self.target / ".research").mkdir()
        with self.assertRaises(ValueError):
            self.install()

    def test_modified_snapshot_and_extra_code_refused(self):
        self.install()
        path = self.target / "tools/re"
        original = path.read_bytes()
        path.write_bytes(original + b"\n# drift\n")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(path.read_bytes(), original + b"\n# drift\n")
        path.write_bytes(original)
        (self.target / "tools/researchlog/unexpected.py").write_text("# drift\n")
        with self.assertRaises(ValueError):
            self.install()

    def test_launcher_uses_project_model_and_new_chat(self):
        self.install()
        spec = importlib.util.spec_from_file_location("test_launcher", self.target / "tools/re_codex.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(sys, "argv", ["re_codex.py", "start"]), patch.object(module, "guarded_run", return_value=0) as call:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 0)
        args = call.call_args.args[0]
        self.assertEqual(args[args.index("-m") + 1], "gpt-5.6-sol")
        self.assertIn('forced_login_method="chatgpt"', args)
        self.assertIn('model_reasoning_effort="high"', args)
        self.assertEqual(args[args.index("-s") + 1], "danger-full-access")
        self.assertEqual(args[args.index("-a") + 1], "never")
        self.assertNotIn("resume", args)
        self.assertNotIn("fork", args)
        self.assertEqual(args[-1], '$research-resume')
        self.assertNotIn("Independently select useful research", args[-1])
        policy = next(arg for arg in args if arg.startswith("skills.config="))
        rules = tomllib.loads(policy)["skills"]["config"]
        blocked_names = {r["name"] for r in rules if not r["enabled"]}
        self.assertIn("brainstorming", blocked_names)
        self.assertIn("superpowers:brainstorming", blocked_names)
        self.assertNotIn("research-engineering", blocked_names)
        self.assertNotIn("systematic-debugging", blocked_names)

    def test_claude_launcher_preserves_auth_model_and_permissions(self):
        self.install()
        spec = importlib.util.spec_from_file_location('test_claude_launcher', self.target / 'tools/re_claude.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(sys, 'argv', ['re_claude.py', 'start']), patch.object(module, 'guarded_run', return_value=0) as call:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 0)
        self.assertEqual(call.call_args.args[0], ['claude', '/research-resume'])
        self.assertEqual(call.call_args.kwargs['cwd'], self.target.resolve())
        self.assertFalse((self.target / '.research').exists())

    def test_claude_policy_exact_names_and_diagnostics(self):
        home = self.target / 'home'
        for name in ('gsd-example', 'research-resume', 'systematic-debugging'):
            path = home / '.claude/skills' / name / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text(f'---\nname: {name}\n---\n')
        path = home / '.claude/plugins/cache/community/superpowers/1/skills/brainstorming/SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text('---\nname: brainstorming\n---\n')
        denies = re_workflow_policy.claude_policy(self.target, home)['permissions']['deny']
        self.assertIn('Skill(gsd-example)', denies)
        self.assertIn('Skill(superpowers:brainstorming)', denies)
        self.assertNotIn('Skill(research-resume)', denies)
        self.assertNotIn('Skill(systematic-debugging)', denies)

    def test_existing_claude_settings_preserved(self):
        path = self.target / '.claude/settings.json'
        path.parent.mkdir()
        path.write_text('{"model":"user-choice"}')
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(path.read_text(), '{"model":"user-choice"}')
        self.assertFalse((self.target / 'tools').exists())

    def test_workflow_policy_discovers_gsd_and_preserves_diagnostics(self):
        home = self.target / "fake-home"
        for name in ("gsd-future-command", "research-engineering", "systematic-debugging"):
            directory = home / ".agents/skills" / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
        rules = re_workflow_policy.rules(self.target, home)
        names = {rule["name"] for rule in rules}
        self.assertIn("gsd-future-command", names)
        self.assertNotIn("research-engineering", names)
        self.assertNotIn("systematic-debugging", names)

    def test_launcher_respects_project_permission_override(self):
        self.install()
        config = self.target / ".codex/config.toml"
        config.write_text('model = "gpt-5.6-sol"\nmodel_reasoning_effort = "medium"\nsandbox_mode = "read-only"\napproval_policy = "on-request"\n')
        spec = importlib.util.spec_from_file_location("test_launcher_override", self.target / "tools/re_codex.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(sys, "argv", ["re_codex.py", "start"]), patch.object(module, "guarded_run", return_value=0) as call:
            with contextlib.redirect_stdout(io.StringIO()):
                module.main()
        args = call.call_args.args[0]
        self.assertIn('model_reasoning_effort="medium"', args)
        self.assertEqual(args[args.index("-s") + 1], "read-only")
        self.assertEqual(args[args.index("-a") + 1], "on-request")


if __name__ == "__main__":
    unittest.main()
