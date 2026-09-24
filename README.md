# GLOBAL CODEX PROJECT KIT

Reusable files for starting future Codex software projects.

## Use
1. Keep this folder as your master template library.
2. For a new project, give Codex `GLOBAL_PROJECT_BOOTSTRAP.md`.
3. Start with `prompts/NEW_PROJECT_START.md`.
4. The bootstrap resolves the canonical global `PROJECT_NORTH_STAR.md`
   automatically; project-specific North Stars remain optional extensions.
5. Let Codex inspect the project read-only before creating project-local governance.
6. Once created, the project's own files become authoritative.

## Canonical routing

Canonical repository: https://github.com/matrakalaka/codex-project-bootstrap

Canonical bootstrap entry point: `GLOBAL_PROJECT_BOOTSTRAP.md`

When Codex is given this repository URL for use against another project:

1. Use this GitHub repository as the canonical bootstrap source of truth and read `GLOBAL_PROJECT_BOOTSTRAP.md` first.
2. Treat local copies as non-authoritative unless explicitly verified against the canonical repository/revision; report material divergence and never overwrite or delete them automatically.
3. Resolve the intended target repository identity and authoritative root before broad discovery.
4. Follow the bounded READ-ONLY discovery workflow inside that root.
5. Discover and respect the target project's existing authority.
6. Keep the global bootstrap rules subordinate to established project authority.
7. Stop at the human-approval gate before modifying the target project.

Recommended short launcher instruction:

> Initialize this project using the canonical bootstrap repository: https://github.com/matrakalaka/codex-project-bootstrap. Read and follow its `GLOBAL_PROJECT_BOOTSTRAP.md` as the canonical entry point. Resolve the target repository/root before broad discovery, start read-only, make no changes, and stop at the human-approval gate with the `PROJECT BOOTSTRAP ASSESSMENT`.

## Read-only authority resolution

The repository-provided resolver at `scripts/bootstrap_authority.py` verifies
the canonical Git revision and the required bootstrap files before authority
is used. A local Git copy is accepted only when its `origin` is the canonical
repository, the required commit object exists, and the committed file hashes
match the canonical revision. Pass a specific candidate with `--cache`; the
resolver never scans for or selects arbitrary local copies and never modifies
the candidate or target project.

Examples:

```sh
python3 scripts/bootstrap_authority.py --cache /path/to/explicit/bootstrap-cache
py -3 scripts/bootstrap_authority.py --cache C:\\path\\to\\explicit\\bootstrap-cache
```

Exit code `0` reports verified authority. Exit code `2` reports
`BLOCKED_PRECONDITION` and `stop: true` when canonical authority cannot be
established safely.

## Core project-local files
Usually:
- AGENTS.md
- KNOWN_GOOD_CONTRACTS.md
- CONTINUE_TOMORROW.md

Add when justified:
- ARCHITECTURE.md
- WORKFLOW_RULES.md
- UI_STANDARDS.md

The global kit is a template, not authority over an already-established project.
