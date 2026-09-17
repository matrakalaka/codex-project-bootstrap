Initialize this project using my GLOBAL_PROJECT_BOOTSTRAP.md standard.

Start with READ-ONLY discovery.

Do not modify anything yet.

Inspect the existing project and determine which parts of my standard are already present, which are missing, and which would conflict with existing project authority.

Use Codebase Memory first where appropriate.

Before broad discovery, resolve the intended target repository identity and
authoritative root using bounded evidence: the explicit user target/current
working directory, current Git root, nested Git boundaries, origin/remotes,
existing project authority, and workspace layout. Do not automatically
prefer an outer repository, nested repository, current directory, or first
Git root found. Surface conflicting evidence or ambiguity and stop/request
clarification when necessary; do not scan multiple candidate roots broadly.

Use this order:

CANONICAL BOOTSTRAP SOURCE
→ TARGET REPOSITORY IDENTITY / ROOT
→ TARGET PROJECT AUTHORITY
→ BOUNDED PROJECT DISCOVERY
→ TOOL/MCP HEALTH
→ GAP ASSESSMENT
→ HUMAN APPROVAL GATE

Keep discovery inside the authoritative root unless specific evidence
requires otherwise. Do not use blanket exclusions for names such as `tmp*`.

Return:

PROJECT BOOTSTRAP ASSESSMENT

Existing Governance:
Existing Architecture Docs:
Existing Tests:
Existing Tooling:
Existing Deployment Model:
Existing Database Model:
Existing Known-Good Evidence:

Tool / MCP Health:

Tool:
Configured:
Available In Current Session:
Correctly Scoped To Current Project:
Operational:
Required By Existing Project Authority:
Bootstrap Blocker:
Observed Gap:
Recommended Action:

Recommended .md Files:
Recommended Skills:
Recommended Testing Stack:
Recommended Project-Specific Tools:

Conflicts With Global Standard:
<none or explain>

Files Proposed For Bootstrap:
<list>

Safe To Bootstrap:
YES / NO

Then STOP.
