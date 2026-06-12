# Service Development Status: Model Registry

**Current Status:** 🟢 Completed (MVP)
**Progress:** 75%
**Last Updated:** 2026-06-12

---

## Technical Specifications
- **Service Name:** model-registry
- **Domain:** coordinator
- **Port:** 8004
- **Protocol:** REST

---

## Roadmap & Progress

| Task | Priority | Status | Progress |
|------|----------|--------|----------|
| Folder Structure | High | 🟢 Completed | 100% |
| API Definitions | High | 🟢 Completed | 100% |
| Versioning Logic | High | 🟢 Completed | 100% |
| PostgreSQL Integration | High | 🟢 Completed | 100% |
| Artifact Storage (Local Disk) | High | 🟢 Completed | 100% |
| MLflow Integration | Medium | 🔵 On Hold | - |
| Artifact Storage (MinIO) | Medium | 🔵 On Hold | - |
| Dockerization | Medium | 🟢 Completed | 100% |

---

## Notes & Blockers
- Model metadata is persisted in PostgreSQL.
- Model artifacts are stored on local disk via `ARTIFACT_DIR` (bytes uploaded via `/models/register`).
