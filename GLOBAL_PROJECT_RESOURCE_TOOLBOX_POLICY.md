# GLOBAL PROJECT RESOURCE & EXTERNAL TOOLBOX POLICY

Public GitHub repositories, tools, examples, APIs, MCP servers, design systems, agent patterns, and frameworks are an EXTRA TOOLBOX.

They are NOT:
- mandatory dependencies
- an installation checklist
- replacements for existing architecture
- replacements for project governance
- permission to restructure working systems

## Authority
Existing project resources always take priority:
- AGENTS.md
- KNOWN_GOOD_CONTRACTS.md
- CONTINUE_TOMORROW.md
- architecture/workflow/UI docs
- tests
- security boundaries
- installed skills/MCPs
- dependencies
- established patterns
- known-good implementation

## Before adopting an external tool
1. Identify the exact problem it solves.
2. Check whether the project already solves it.
3. Check overlap/conflicts.
4. Inspect security and persistence behavior.
5. Prefer project-local installation.
6. Avoid governance replacement.
7. Define validation and rollback.
8. Obtain approval where required.

If an external tool conflicts with project authority, project authority wins.
