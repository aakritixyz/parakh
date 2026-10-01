# RBAC Notes

Current implementation has a simple user role field:

- `admin`
- `investigator`
- `analyst`
- `prosecutor`

Target implementation will add per-case `CaseMembership` with role-specific permissions.

## Intended Role Matrix

| Action | Admin | Investigator | Analyst | Prosecutor |
| --- | --- | --- | --- | --- |
| Manage users | Yes | No | No | No |
| Create cases | Yes | Yes | No | No |
| Upload evidence | Yes | Yes | No | No |
| Parse/analyse evidence | Yes | Yes | Yes | No |
| Tag/comment/bookmark | Yes | Yes | Yes | Limited |
| Accept/dismiss leads | Yes | Yes | Yes | No |
| View approved exhibits | Yes | Yes | Yes | Yes |
| Generate reports | Yes | Yes | Limited | Read-only |
| Verify audit chain | Yes | Yes | Yes | Yes |

Until Phase 1 implements membership tables, endpoints rely on authenticated access and coarse role data only.
