# Agent packages in the monorepo

Root `apm.yml` is the compile entry for the whole tree. Module packages stay next to their
code (`<module>/agent-packages/`) and are listed as local `./…` dependencies from the root
manifest. After edits:

```bash
apm install --target cursor,claude --legacy-skill-paths --force
apm compile --target cursor,claude
```

Generic packages still come from
[qubership-apihub-ci/agent-packages](https://github.com/Netcracker/qubership-apihub-ci/tree/main/agent-packages)
and
[qubership-ai-packages](https://github.com/Netcracker/qubership-ai-packages/tree/main/agent-packages).

## Root packages

| Package | Path | Scope |
|---------|------|-------|
| `apihub-deployment-authoring` | `apihub-deployment-authoring/` | Helm, Compose, `docs/` |
| `apihub-deployment-followup` | `apihub-deployment-followup/` | Reminders when backend changes need deploy follow-up |

`applyTo` globs are rooted at the monorepo root (for example
`qubership-apihub-backend/qubership-apihub-service/**/*.go`).

Sources under `agent-packages/` and deployed `.cursor/` / `.claude/` harness trees are
**committed**. Gitignore: `apm_modules/`, `agent-packages/**/build/`.
