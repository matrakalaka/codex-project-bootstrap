# Shared Stack Contracts v0

This directory defines the read/write-neutral contract formats for the ChatGPT/Codex stack. These files do not authorize mutation, select a repository, approve work, launch Codex, or replace project authority.

## Contracts

- task_packet.v0.schema.json  bounded task request and optional playbook reference.
- bootstrap_assessment.v0.schema.json  read-only project assessment.
- human_approval.v0.schema.json  explicit human authorization binding.
- result_packet.v0.schema.json  RepoGuard result and evidence projection.

The validator is dependency-free and provides structural/semantic checks plus canonical SHA-256 hashing.

## Canonicalization

Canonical JSON uses UTF-8, sorted object keys, and no insignificant whitespace. Arrays preserve order unless the contract identifies them as unordered path/capability/reference sets. Hashes are SHA-256 strings prefixed with sha256:. Absolute paths and shell syntax are not part of the contract.

## Playbook boundary

The optional playbook field in Task Packet v0 is a fingerprinted reference only. It grants no permission, does not imply approval, and does not trigger resolution, composition, execution, or another task. A future effective playbook must be fully resolved and fingerprinted before human approval.

## Authority boundary

Existing project authority remains superior. Bootstrap observations are advisory inputs to RepoGuard; RepoGuard independently re-verifies security-relevant repository, authority, Git, scope, capability, and approval facts.
