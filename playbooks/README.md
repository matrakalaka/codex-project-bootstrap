# Versioned Engineering Playbooks v0

An engineering playbook is reusable procedural guidance for a class of work. It is not authorization, a capability grant, a TaskDeclaration, a skill, project authority, a verification contract, or a RepoGuard execution engine.

Authority precedence is: project authority > human approval > canonical bootstrap policy > RepoGuard admission/execution policy > effective project-approved playbook > task parameters > skills/agent instructions > loop/launcher mechanics. A canonical playbook is default procedural guidance only. Project authority may accept, narrow, replace a step with a stricter step, add verification or human gates, or reject it. There is no automatic “newer canonical version wins” rule.

`schema.v0.json` defines `engineering_playbook.v0`. Fingerprints are `sha256:` plus SHA-256 of UTF-8 canonical JSON with `fingerprint` removed, sorted object keys, compact separators, and preserved array order. This is formatting-independent, path-independent, and changes when procedural content changes. Parameters use the same canonicalization.

Resolution is `canonical playbook + project-authority narrowing/stricter requirements + task parameters = effective playbook`. It is deterministic and procedural only; it cannot broaden Task Packet scope, human approval, RepoGuard admission, or capabilities. Approval binds canonical fingerprint, effective fingerprint, and effective-parameters hash. Changes to version/content, resolution, verification, gates, or parameters require a new binding. The optional Task Packet reference remains only `id`, `version`, `fingerprint`, `parameters`; it does not imply approval or resolution.

Future evidence must record canonical ID/version/fingerprint, effective fingerprint and parameters, expected/completed/skipped/blocked phases, required verification, and verification evidence. A playbook cannot claim its own phase completion; applicable completion requires external or RepoGuard-observed evidence.

Composition is unsupported. A future composed playbook must resolve into one deterministic effective playbook before approval, with all modules and parameters represented in its fingerprint. It cannot grant permission, broaden scope, create sessions, transfer approval, or change procedure without invalidating approval.

Skill = reusable agent capability/instruction behavior. Playbook = reusable engineering procedure. Task Packet = exact bounded task. Approval = authorization for that exact task. RepoGuard = admission, managed execution, verification, evidence, and outcome. These concepts are not interchangeable.
