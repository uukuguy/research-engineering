"""Start a new interactive client; never resume/fork a chat implicitly."""
import json
from pathlib import Path
import sys
import tomllib
from re_workflow_policy import config_override
from re_terminal_guard import run as guarded_run

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    "start": "$research-resume",
    "status": "$research-status",
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PROMPTS:
        raise SystemExit("usage: re_codex.py start|status")
    config = tomllib.loads((ROOT / ".codex/config.toml").read_text())
    model = config.get("model")
    if not isinstance(model, str) or not model:
        raise SystemExit("Set a model in project .codex/config.toml")
    # Explicit overrides also work before project trust is established. Provider
    # configuration is not accepted in the project layer of current Codex.
    args = ["codex", "-C", str(ROOT), "-m", model,
            "-c", 'model_provider="openai"',
            "-c", 'forced_login_method="chatgpt"',
            "-c", config_override(ROOT),
            "-c", "model_reasoning_effort=" + json.dumps(config.get("model_reasoning_effort", "high")),
            "-s", config.get("sandbox_mode", "workspace-write"),
            "-a", config.get("approval_policy", "on-request"),
            PROMPTS[sys.argv[1]]]
    print(f"Starting NEW Codex session; model={model}; ChatGPT login required; terminal charset guard=ON.", flush=True)
    return guarded_run(args, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
