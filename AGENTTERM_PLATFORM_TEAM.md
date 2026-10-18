# Local team authorization

`TeamService` models organizations and workspaces, binds principals to the
tenant, and enforces owner/editor/viewer permissions at each operation.
Invitations are random one-time tokens stored only as digests and are bound to
organization, workspace, and target user. Revocation removes membership and
immediately denies subsequent operations.

This proves local authorization behavior with synthetic users. It is not an
identity provider, SSO integration, hosted tenant service, or independent
server process.
