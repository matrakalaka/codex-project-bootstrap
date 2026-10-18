"""Built-in adapters (Codex CLI, Claude Code) and the configurable generic adapter.

Agent CLIs change quickly. Every adapter declares the flags it depends on and
``agentterm doctor`` re-checks them against the installed ``--help`` output, so
adapter drift shows up as a diagnostic instead of a confusing failure.
"""

from __future__ import annotations

from .base import Adapter


class CodexAdapter(Adapter):
    name = "codex"
    binary = "codex"
    required_flags = ("--sandbox", "--cd")
    help_args = ("exec", "--help")
    enforces_read_only = True

    def command(self, *, mutation_allowed, cwd, is_git, prompt):
        argv = [
            "codex", "exec",
            "--sandbox", "workspace-write" if mutation_allowed else "read-only",
            "--cd", cwd,
        ]
        if not is_git:
            argv.append("--skip-git-repo-check")
        argv.append("-")  # read the prompt from stdin (no argv size limit)
        return argv, prompt

    def interactive_command(self, prompt):
        return ["codex", prompt]


class ClaudeAdapter(Adapter):
    name = "claude"
    binary = "claude"
    required_flags = ("--print", "--permission-mode")
    enforces_read_only = True

    def command(self, *, mutation_allowed, cwd, is_git, prompt):
        mode = "acceptEdits" if mutation_allowed else "plan"
        return ["claude", "--print", "--permission-mode", mode, "--output-format", "text"], prompt

    def interactive_command(self, prompt):
        return ["claude", prompt]


class GenericAdapter(Adapter):
    """Any CLI, declared in ``agentterm.toml``::

        [agents.myagent]
        command = ["myagent", "--auto"]   # "{prompt}" is substituted when stdin = false
        stdin = true
        check = ["myagent", "--version"]
    """

    def __init__(self, name: str, command: list[str], *, stdin: bool = True,
                 check: list[str] | None = None, interactive: list[str] | None = None):
        self.name = name
        self.binary = command[0]
        self._command = list(command)
        self._stdin = stdin
        self._interactive = interactive
        if check:
            self.version_args = tuple(check[1:])

    def command(self, *, mutation_allowed, cwd, is_git, prompt):
        if self._stdin:
            return list(self._command), prompt
        return [prompt if part == "{prompt}" else part for part in self._command], None

    def interactive_command(self, prompt):
        if self._interactive:
            return [prompt if part == "{prompt}" else part for part in self._interactive]
        return [self.binary, prompt]


BUILTIN = {"codex": CodexAdapter, "claude": ClaudeAdapter}
