# GLOBAL CODEX ENGINEERING STACK

## Global tools
- OpenAI Codex CLI
- Codebase Memory MCP
- Skylos
- Git
- Node/npm
- Python

## Project-specific tools when needed
- Playwright Test
- Supabase CLI
- psql
- Wrangler
- Docker
- framework-specific CLIs

## Optional external toolbox capabilities
These capabilities are advisory and non-authoritative. Repository/project
authority, RepoGuard, existing contracts, tests, and verification remain
superior.

- SkillCorpus — `OPTIONAL_EXTERNAL_SKILL_RETRIEVAL`; on-demand retrieval only; installation none.
- unlazy — `OPTIONAL_COMPLETION_AND_ACCEPTANCE_GATE_TOOLING`; substantial tasks only; derive gates from existing project authority; cannot grant RepoGuard admission, mutation authorization, verification authority, receipts, or completion status; no hooks or project activation by default.
- Oxc — `OPTIONAL_JS_TS_TOOLCHAIN_ACCELERATOR`; project-evaluation option only; complement existing JS/TS tools first and migrate only with evidence; no global package or project dependency installation by default.
- Replica Skill — `PARKED`; category `OPTIONAL_REPLICA_ANALYSIS_AND_UI_PARITY_TOOLBOX`; source: https://github.com/Jakeschincariol/replica-skill. Optional clean-room application analysis, design guidance, flow testing, feature parity, visual comparison, and rebranding checks. Prefer `replica-recon`, `replica-design`, `replica-test`, `replica-diff`, and `replica-brand`. Project-local and individually selected only; require a pinned, reviewed upstream revision before use. Advisory and never authoritative; Bootstrap, Loop, RepoGuard, and project authority remain superior. No global installation, automatic registration, automatic upstream instruction execution, mutation outside an approved task, proprietary source/assets/data copying, unauthorized external-service access, automatic deployment, or new mandatory dependency. Claude-specific instructions require Codex adaptation.

### Evaluated and parked toolbox entries

- OpenViking — `OPENVIKING_NORTH_STAR_PARKED`; evaluated at the immutable pin
  `1f4f7039fc394c5d04637828166f4e4e74e249e0` from
  `https://github.com/volcengine/OpenViking`. The objective was an optional,
  advisory, non-semantic, read-only Codex context capability. The official
  `openviking-sdk` is an HTTP client for a running OpenViking server, and the
  pinned Agent Plugins MCP proxy forwards to that server's `/mcp` endpoint.
  Runtime qualification showed that fresh server bootstrap creates internal
  metadata and 14 queue messages, then enters embedding processing. No model
  successfully executed, but the supported server path did not satisfy the
  approved no-model boundary. Lower-level RAGFS capabilities were not adopted
  as a private or unsupported Codex integration. Outcome:
  `BLOCKED_PRECONDITION`.

  Parked with OpenViking: local embedding, GGUF, `llama-cpp-python`, Ollama,
  CUDA/GPU, remote embedding, remote VLM, semantic search, memory writes,
  lifecycle hooks, automatic recall/capture, source patching, server
  workarounds, and private/internal RAGFS integration. These are not
  prerequisites and do not create scope.

  Reconsider OpenViking only if the human explicitly changes the objective or
  boundaries, or a future release provides a documented supported serverless,
  model-free, read-only integration surface that materially changes this
  architectural finding. A new release by itself is insufficient; do not poll
  for updates.

## Default engineering skills
Project-local where applicable:
- diagnosing-bugs
- tdd
- code-review
- codebase-design
- research
- wizard

## UI/frontend skills
Add when useful:
- redesign-existing-projects / Taste
- agentic-design-system
- design-review
- ux-baseline-check
- ui-polish-pass

## Do not auto-install
- handoff
- setup-matt-pocock-skills
- Context Mode
- broad agent frameworks
- hooks
- unrelated MCP servers
- unnecessary dependencies

## Default testing model
Use the smallest stack that proves behavior:
- existing unit/component tests
- static/type checks
- build
- Playwright + Chromium for rendered/E2E validation where appropriate
- staging verification when applicable

Tools are advisory. Project governance and source truth win.
