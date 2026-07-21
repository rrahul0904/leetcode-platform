# Runtime Compatibility Matrix

| Component | Development | CI | Production | State |
| --- | --- | --- | --- | --- |
| Node | 24.18.x required | 24.18.x | 24.18.x image by digest | local shell currently 26.4; use version manager |
| Python application | 3.13.5 | 3.13.x | 3.13.x image by digest | verified locally |
| Python challenges | 3.11–3.14 | image tests required | separate immutable images | not yet verified |
| PostgreSQL | 18.x container | 18.x testcontainer | RDS PostgreSQL 18.x | availability unverified |
| Browser | current evergreen | Playwright pinned browsers | evergreen support policy | pending |
| gVisor | optional local profile | isolated security suite | EKS sandbox nodes | pending infrastructure proof |

The application must fail startup with an actionable error when a required runtime or configuration is incompatible.

