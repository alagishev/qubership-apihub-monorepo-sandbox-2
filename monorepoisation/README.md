# Monorepoisation

Sandbox log of folding APIHUB polyrepos into one git repository. Replay these steps in the
production monorepo. The operator supplies the source-repo list each time; do not treat any
single run's roster as canonical.

## How to use this log

1. Copy the prompt from the step you need.
2. Replace placeholders (`<GITHUB_ORG>`, `<ROOT_REPO>`, `<MODULE_REPOS>`, `<CI_REPO>`,
   `<CI_REF>`, and the rest).
3. After you finish a new step in this sandbox, append the next numbered section here.
   Neighbouring agents must do that without being asked (see `.cursor/rules/monorepoisation.mdc`).

This document is the draft of a reusable skill. Do not turn it into a skill until the sandbox
run is complete.

## Steps

### 1. Import git history, tags, and GitHub releases

**Summary:** Import the umbrella (root) repository 1:1 at the destination root, then `git subtree add`
(no squash) each module into a top-level folder named after that GitHub repo. Keep `main` and
`develop` only. Rename tags to `<repo>/<version>` (slash; git forbids `:` in ref names). Recreate
GitHub releases with original notes, matching titles, prerelease/draft flags, and assets.

**Agent time (sandbox run):** about 45 minutes after the approach was settled. Git import and push
took ~7 minutes. GitHub releases (create, retries, asset copy, notes rewrite for Windows newlines)
took ~37 minutes and dominate. Scale with module count for subtree add (typically under a minute
each once fetched) and with release count for the API (~10–15 seconds each, plus retries).

**Prompt:**

````markdown
Migrate several GitHub polyrepos into this repository as a monorepo. This checkout is the
destination. Do not hard-code a fixed module list: use the operator-supplied lists below (or
ask once for them if they are missing).

## Inputs

- GitHub org: `<GITHUB_ORG>`
- Destination: this repo (already cloned; `origin` points at it)
- Root (umbrella) repo name: `<ROOT_REPO>`
  Content stays at the destination root (Helm, Compose, docs, and similar). Not a subfolder.
- Module repo names: `<MODULE_REPOS>` — one GitHub repo name per line. Each name is the
  destination top-level folder. Do not assume a nine-repo list.

## Branches

- Import only `main` and `develop` from each source, plus **all tags** (and the commits those
  tags point at). Do not import other branches (`gh-pages`, `broadcast-*`, feature branches).
- Root `main` → destination `main`.
- If `<ROOT_REPO>` has no `develop`, create destination `develop` from the imported root `main`
  **before** adding modules.
- If `<ROOT_REPO>` has `develop`, import it onto destination `develop` the same way as `main`.
- Then for each module: `git subtree add --prefix=<repo-name>` that module's `main` onto
  destination `main`, and its `develop` onto destination `develop`. No `--squash` (old SHAs
  stay as merge parents so historical tags still resolve).

## Tags

- Git ref names cannot contain `:`. Use `<repo-name>/<original-tag>` (slash).
- Fetch tags with `--no-tags` on branch fetches, then
  `git fetch --no-tags <remote> "refs/tags/*:refs/tags/<repo-name>/*"`.
- Delete any unprefixed tags that slipped in via tag-following. Unprefixed `1.0.0` collides
  across modules.
- Keep original suffixes as-is (`alpha`, `beta`, `v0.0.1`, `0.0.1-test`).
- Old module tags are historical: `git checkout <repo>/<version>` shows that repo's old layout
  (files at the old root, not under the prefix). New tags after the monorepo exists will
  snapshot the combined tree.

## GitHub releases

- After `git push -u origin main develop` and `git push origin --tags`, copy every GitHub
  release from each source repo onto the destination.
- Destination tag = `<repo-name>/<original-tag>`.
- Destination **title must equal that prefixed tag** (the Releases list shows `name`, not
  `tagName`).
- Copy body 1:1 in UTF-8. Keep emoji. Do not rewrite links to old PRs/issues (those still live
  on the source repos).
- Preserve `prerelease` and `draft`. Copy release assets when present.
- Create oldest-first. Mark `<ROOT_REPO>/<latest-root-version>` as GitHub Latest, not a module
  tag GitHub might pick by semver.
- Write notes files with UTF-8 and `newline='\n'`. On Windows, `Path.write_text` with default
  newlines turns source CRLF into CRCRLF and inflates the body. After create, compare
  normalised bodies; if they differ only by CR, rewrite with `gh release edit --notes-file`.
- `gh api repos/.../releases/tags/<name>/<version>` breaks on the slash. Use
  `gh release view "<name>/<version>"` instead.

## Order of work

1. Import root `main` (and `develop` if it exists) and prefixed root tags; create destination
   `develop` if needed.
2. For each module in the given list: fetch `main`/`develop`/tags, subtree-add onto both
   destination branches, keep only prefixed tags.
3. Verify: `git diff --stat src-<name>/main HEAD:<name>` is empty on `main`, and the same for
   `develop`. Confirm zero unprefixed tags.
4. Push `main`, `develop`, and tags.
5. Recreate GitHub releases; verify titles equal prefixed tags and emoji still render.

Do not start CI, APM, CODEOWNERS, or workflow adaptation in this step.
````

### 2. Write the monorepo CI module map

**Summary:** GitHub Actions only runs workflows from the repository-root `.github/workflows`. Nested
`*/.github/workflows` imported from the polyrepos are inert. Capture the module graph in
`ci/modules.yaml` (image modules, path filters, Go workspace roots, E2E paths, tag prefixes) so later
reusable workflows in `<CI_REPO>` can read it from the caller checkout. Do not invent a second copy of
this map inside YAML workflows.

**Agent time (sandbox run):** about 15 minutes. Dominated by reading existing polyrepo CI wrappers and
the `docker-ci` / `calculate-effective-tag` contracts.

**Prompt:**

````markdown
Create `ci/modules.yaml` at the destination root. It is the only module map later CI reads from the
caller checkout. Do not duplicate it inside workflow files.

## Inputs

- GitHub org: `<GITHUB_ORG>`
- Destination: this repo
- Root (umbrella) repo name: `<ROOT_REPO>`
- Module repo names: `<MODULE_REPOS>` — one GitHub repo name per line (top-level folders)
- CI store repo: `<CI_REPO>` (reusable workflow sources; default `qubership-apihub-ci`)

## Requirements

- GitHub Actions does not run nested `*/.github/workflows`. Treat those files as dead until a later
  hygiene step deletes them.
- List every image-producing module with `image_name`, `dockerfile`, `context`, and whether it needs
  frontend-ci (npm pack) first.
- Go services that import `qubership-apihub-commons-go` must list that folder in `extra_paths` /
  `detect_paths` so a commons-go change rebuilds those images.
- Record E2E paths (`compose_folder`, `helm_chart`, `postman_path`, `playwright_path`).
- Fallback image is `ghcr.io/netcracker/<image_name>:dev` when this branch never published a tag.
- Module git tags stay `<module>/<semver>`. Application tags stay `<ROOT_REPO>/<semver>`.
- Reusable workflow *sources* live in `<CI_REPO>`. This repo only grows thin wrappers later.
- Do not rewrite workflows, APM, CODEOWNERS, or Dockerfiles in this step.

## Verify

- `ci/modules.yaml` lists every folder in `<MODULE_REPOS>` that produces an image, a Go library, or
  E2E assets.
- Path filters for each Go image include `qubership-apihub-commons-go/**` when that service imports
  the library.
````

### 3. Hoist GitHub hygiene, CODEOWNERS, and Dependabot

**Summary:** GitHub only honours root `.github/CODEOWNERS` and `.github/dependabot.yml`. Merge
per-module owners into path rules, list every `go.mod` / npm / Docker directory in Dependabot, hoist
one copy of security-scan, delete-dist-tag, and the Playwright manual workflow, then delete nested
`*/.github/workflows`, nested CODEOWNERS, and nested Dependabot files. Keep root CLA, labeler,
conventional-commits, super-linter, and link-checker. Do not invent per-module CI wrappers yet.

**Agent time (sandbox run):** about 20 minutes. Dominated by deleting nested workflow trees.

**Prompt:**

````markdown
Adapt `.github` for a monorepo. Reusable workflow *sources* stay in `<CI_REPO>`. This repo only keeps
thin wrappers and GitHub-native config that must live at the destination root.

## Inputs

- GitHub org: `<GITHUB_ORG>`
- Destination: this repo
- Root (umbrella) repo name: `<ROOT_REPO>`
- Module repo names: `<MODULE_REPOS>`
- CI store repo: `<CI_REPO>`

## CODEOWNERS

- Keep a default `* <default-owners>` rule from `<ROOT_REPO>`.
- Add one path rule per module folder, copying owners from that module's old CODEOWNERS (root or
  `.github/CODEOWNERS`).
- Cover `/helm-templates/`, `/docker-compose/`, `/docs/`, `/ci/`, and `/.github/` with the umbrella
  owners.

## Dependabot

- One `.github/dependabot.yml` at the destination root. Nested Dependabot files do nothing.
- Add `gomod` entries for every `go.mod` directory, `npm` for every package-lock / shrinkwrap
  directory, `docker` for every image-module Dockerfile directory, and `github-actions` at `/`.
- Keep the existing commit-message prefix `chore: deps:` and the `dependencies` label.

## Workflows

- GitHub Actions only runs `.github/workflows` at the destination root. Delete every
  `<module>/.github/workflows/**` file.
- Keep the existing root hygiene wrappers (CLA, PR title, conventional commits, assigner, labeler,
  super-linter, link-checker).
- Hoist one `security-scan-apihub.yml` (discover GHCR packages for this repo).
- Hoist `delete-dist-tag.yaml` as a thin `uses: <CI_REPO>/.../delete-dist-tag.yaml@main` wrapper.
- Hoist the Playwright manual workflow with `defaults.run.working-directory` set to the ui-tests
  module folder.
- Leave smart Docker CI, E2E compose/kind orchestration, and Storybook CD for later steps (Storybook
  needs a `working-directory` input on the reusable workflow first).

## Do not

- Call `docker-ci` from the monorepo yet.
- Edit APM packages, Go Dockerfiles, or `go.work`.
- Leave nested CODEOWNERS or Dependabot files behind.

## Verify

- `git ls-files '*/.github/workflows/*'` is empty.
- `.github/CODEOWNERS` has a path rule for every folder in `<MODULE_REPOS>`.
- `.github/dependabot.yml` directories match real `go.mod` / lockfile / Dockerfile paths.
````

### 4. Point APM at the monorepo root

**Summary:** Root `apm.yml` now depends on every local `agent-packages/` tree plus the shared CI/AI
store packages. Instruction `applyTo` globs are rooted at the destination root so a single
`apm install` / `apm compile` covers backend, agents-backend, UI, Postman, and deployment.
Module `apm.yml` files keep working for a checkout of one folder by using sibling `../`
paths instead of old GitHub repo URLs.

**Agent time (sandbox run):** about 25 minutes, dominated by `apm compile` scanning the tree.

**Prompt:**

````markdown
Adapt APM for a monorepo. Compile from the destination root. Do not create new skills for this
migration itself.

## Inputs

- Destination: this repo
- Module repo names: `<MODULE_REPOS>`

## Root manifest

- Edit root `apm.yml` so `dependencies.apm` lists:
  - shared store packages already used by the modules (english-developer-style,
    markdown-line-length-120, development-conventions, go-conventions, apihub-go-developer,
    apihub-go-self-review, github-ticket-implementation-planner)
  - `./agent-packages/<name>` for umbrella packages
  - `./<module>/agent-packages/<name>` for every module-local package
- Keep `targets: [cursor, claude]`.

## applyTo globs

- Prefix every module-local `applyTo` with that module's top-level folder. Example:
  `qubership-apihub-service/**/*.go` becomes
  `qubership-apihub-backend/qubership-apihub-service/**/*.go`.
- Do not leave a glob that matches another module's files (in particular `docs/api/**` and
  `**/*.{ts,tsx}`).

## Sibling dependencies

- Replace GitHub URLs that pointed at another polyrepo's `agent-packages/` with relative paths
  (`../agent-packages/…`, `../<module>/agent-packages/…`).

## Compile

From the destination root:

```bash
apm install --target cursor,claude --legacy-skill-paths --force
apm compile --target cursor,claude
```

Commit the deployed `.cursor/`, `.claude/`, `AGENTS.md`, and `apm.lock.yaml` trees.

## Do not

- Change Dockerfiles, `go.work`, or GitHub Actions in this step.
````

### 5. Wire Go workspaces and Docker build context

**Summary:** Add a root `go.work` that lists every Go module. Each service `go.mod` gets a
`replace` that points at `qubership-apihub-commons-go` on the same branch. Dockerfiles for backend,
agents-backend, and the linter copy commons-go from the monorepo root (`GOWORK=off` so the image
build uses `replace`, not the workspace file). Image build context for those services is `.`.

**Agent time (sandbox run):** about 20 minutes, dominated by `go work sync` / `go mod tidy`.

**Prompt:**

````markdown
Use Go workspaces so services compile `qubership-apihub-commons-go` from this branch, and keep an
independent publish life cycle for the library.

## Requirements

- Create `go.work` at the destination root with `use (` every Go module directory `)`.
- In each service `go.mod` add
  `replace github.com/Netcracker/qubership-apihub-commons-go => ../../qubership-apihub-commons-go`
  (adjust `../` so it resolves from that `go.mod`).
- Do not drop the `require` line; `replace` overrides it for in-repo builds.
- Dockerfiles that build those services must `COPY` both the library and the service, set
  `ENV GOWORK=off`, and use a build context of the destination root.
- Leave npm-based Dockerfiles (UI, build-task-consumer) unchanged.
- A later module tag `<commons-module>/<semver>` still publishes the library; services do not
  `go get` that release for in-repo builds.

## Verify

- `go work sync` succeeds.
- Each service `go.mod` contains the `replace` directive.
- Backend / linter / agents-backend Dockerfiles copy `qubership-apihub-commons-go`.
````

### 6. Smart Docker CI in the CI store, thin wrapper in the monorepo

**Summary:** Reusable workflow sources stay in `<CI_REPO>`. Added optional `image-tag`,
`image-repository` on `docker-ci.yml` and `working-directory` on `frontend-ci.yaml`. New
`monorepo-ci.yml` detects changed modules from `ci/modules.yaml`, builds only those images, and
computes the branch/PR/tag image tag (module tags `module/1.2.3` publish as `1.2.3`). The destination
root keeps a thin `.github/workflows/ci.yml` that `uses` that reusable.

**Agent time (sandbox run):** about 40 minutes. Dominated by reusable workflow wiring.

**Prompt:**

````markdown
Add smart Docker CI. Put reusable workflow *sources* in `<CI_REPO>`. The destination repo only gets
a thin wrapper.

## CI store (`<CI_REPO>`)

- Keep existing `docker-ci.yml` behaviour. Add optional `image-tag` and `image-repository` inputs
  (empty `image-repository` still publishes `ghcr.io/netcracker/<name>`).
- Add optional `working-directory` to `frontend-ci.yaml` (default `.`).
- Add `monorepo-ci.yml` that:
  - checks out the caller and reads `<modules-file>` (default `ci/modules.yaml`)
  - diffs against the PR base / previous push SHA / `develop`
  - rebuilds only changed image modules
  - rebuilds every Go image that lists `qubership-apihub-commons-go` when that library changes
  - runs frontend-ci in the module folder before Docker for npm-pack images
  - uses context `.` for Dockerfiles that copy commons-go
- Helper scripts live under `<CI_REPO>/.github/workflows/scripts/`. The reusable checks that repo
  out as `.ci-store` using inputs `ci-store-repository` and `ci-store-ref`.

## Destination wrapper

- `.github/workflows/ci.yml` calls
  `<CI_REPO>/.github/workflows/monorepo-ci.yml@<CI_REF>` with `secrets: inherit`.
- Pin `<CI_REF>` to the feature branch until the CI store PR merges, then switch to `main`.
- `permissions.packages: write` is required so GHCR push works.

## Verify

- A PR that only touches `<ui-module>` does not run backend `docker-ci`.
- A PR that touches commons-go rebuilds backend, linter, and agents-backend.
````

### 7. E2E compose and kind with image-tag fallback

**Summary:** `run-e2e-tests.yml` and `run-e2e-tests-kind.yaml` gained `source-layout: monorepo`
(checkout the caller once, symlink compose/helm/postman/playwright paths) and `image-refs-json`.
Resolve logic: image built in this run, else GHCR tag for the current ref, else
`ghcr.io/netcracker/<image>:dev`. Compose rewrites full image refs from that JSON. Kind writes a
Helm values overlay (`image.repository` + `image.tag`) so sandbox GHCR namespaces work. E2E runs
on pull requests when a runtime or test module changed.

**Agent time (sandbox run):** about 25 minutes.

**Prompt:**

````markdown
Keep compose and kind E2E. Take image tags from this branch; if a module was not built, fall back
to `ghcr.io/netcracker/<image>:dev`.

## CI store

- Add `source-layout` (`polyrepo` default, `monorepo` checkouts the caller) plus `postman-path` and
  `playwright-path` to both E2E reusables. Skip sibling-repo clones when `source-layout=monorepo`.
- Add `image-refs-json`. When set, rewrite `ghcr.io/netcracker/<image>:<anything>` in compose to the
  full ref from the JSON. For Kind, write a Helm values overlay with `image.repository` and
  `image.tag` (do not pass full refs as `--set tag=`). Keep the old `--set-string …image.tag=` path
  when `image-refs-json` is empty so polyrepo callers stay unchanged.
- `monorepo-ci.yml` resolve step: this-run tag, else GHCR `<registry-owner>/<image>:<current-tag>`,
  else `ghcr.io/netcracker/<image>:dev`.
- Run compose and kind E2E on `pull_request` when detect says `e2e_needed`.

## Destination

- Do not duplicate E2E job YAML. The root `ci.yml` wrapper already enables both flags.
- Keep the existing manual `run-e2e-tests.yml` / `run-e2e-tests-kind.yml` dispatch wrappers.

## Verify

- A UI-only PR builds the UI image and runs E2E with other services on `:dev` (or an existing
  branch tag in GHCR).
````

### 8. Module tag release notes

**Summary:** Pushing `<module>/<semver>` still runs smart Docker CI (step 6). A thin
`module-release.yml` wrapper calls `monorepo-module-release.yml`, which writes GitHub Release notes
from `git log` between the previous tag with that prefix and this one, scoped to the module path.
Commons-go tags publish a GitHub Release for the library; services keep using workspace sources.

**Agent time (sandbox run):** about 15 minutes.

**Prompt:**

````markdown
Preserve per-module releases. A git tag `<module>/<semver>` builds that module and publishes
release notes.

## Requirements

- Reusable `monorepo-module-release.yml` in `<CI_REPO>`: previous tag with the same prefix, `git log`
  on the module path, `gh release create` with title equal to the prefixed tag.
- Destination wrapper on `push.tags` for every image module and commons-go.
- Do not copy personal GitHub tokens into the tree. Use `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`.
- Commons-go keeps its own tag/release; in-repo services do not switch off `replace` / `go.work`.
````

### 9. Application release from a sprint name

**Summary:** Manual `workflow_dispatch` with `sprint-name` calls `monorepo-app-release.yml`. It takes
the latest `<ROOT_REPO>/<semver>` tag, bumps patch, creates an annotated tag, writes notes from
`git log`, and packages the Helm chart onto that GitHub Release.

**Agent time (sandbox run):** about 15 minutes.

**Prompt:**

````markdown
Add a manual application release.

## Requirements

- `workflow_dispatch` input `sprint-name`.
- Reusable in `<CI_REPO>` computes the next `<ROOT_REPO>/<semver>` (patch +1 on the previous
  prefixed app tag, or `0.1.0` if none).
- Create an annotated git tag, push it, create a GitHub Release, include the sprint name in the
  body, and attach a packaged Helm chart (see step 10).
- Do not store a GitHub token in the repository.
````

### 10. Publish the Helm chart to GHCR OCI

**Summary:** `helm package` + `helm push oci://ghcr.io/<owner>/charts`. The app-release reusable
does this on every application tag. A separate `publish-helm-chart.yml` wrapper allows a manual
chart-only publish.

**Agent time (sandbox run):** about 10 minutes.

**Prompt:**

````markdown
Publish the umbrella Helm chart instead of asking users to copy it from a git tag.

## Requirements

- Reusable `publish-helm-chart.yml` in `<CI_REPO>`: `helm package` `<chart-path>` with the given
  version, `helm push` to `oci://ghcr.io/<owner>/charts`, optional `gh release upload`.
- Call it from the application release (step 9) and from a destination `workflow_dispatch` wrapper.
- Chart path defaults to `helm-templates/qubership-apihub`.
- `permissions.packages: write` is required.
````

### 11. Remove polyrepo GitHub leftover files from module folders

**Summary:** GitHub Actions, Copilot custom instructions, super-linter, Dependabot, CODEOWNERS,
and the security/contributing pages only read the destination root. After step 3 hoisted workflows,
each module still carried `.github/linters`, `.github/instructions`, `super-linter.env`,
`auto-labeler-config.yaml`, and (in one module) `release-drafter-config.yml`, plus duplicate
`CONTRIBUTING.md`, `SECURITY.md`, and `CODE-OF-CONDUCT.md`. Those files do nothing in a monorepo,
so they were deleted. APM sources (`agent-packages/`, `apm.yml`), compiled `AGENTS.md` /
`.cursor` / `.claude`, licences, module readmes, and per-module `.editorconfig` stay.

**Agent time (sandbox run):** about 15 minutes. Dominated by inventory and `git rm`.

**Prompt:**

````markdown
Delete GitHub config that only worked in the old polyrepos. Keep product source, APM packages, and
root `.github`.

## Inputs

- Destination: this repo
- Module repo names: `<MODULE_REPOS>`

## Delete in every module folder

- The whole `<module>/.github/` tree (linters, Copilot `instructions/`, `super-linter.env`,
  `auto-labeler-config.yaml`, release-drafter, leftover workflow fragments). GitHub never reads
  nested `.github`.
- Duplicate `<module>/CONTRIBUTING.md`, `<module>/SECURITY.md`, and `<module>/CODE-OF-CONDUCT.md`.
  GitHub serves the copies at the destination root.

## Keep

- Root `.github/` (workflows, CODEOWNERS, Dependabot, linters, instructions).
- Root `CONTRIBUTING.md`, `SECURITY.md`, `CODE-OF-CONDUCT.md`.
- `<module>/agent-packages/`, `<module>/apm.yml`, compiled `AGENTS.md` / `.cursor` / `.claude`.
- Licences, module readmes, Dockerfiles, `.editorconfig`.

## Do not

- Delete `agent-packages/` or rewrite module readmes in this step.
- Touch reusable workflows in `<CI_REPO>`.

## Verify

- `git ls-files '*/.github/**'` is empty.
- `git ls-files '*/CONTRIBUTING.md' '*/SECURITY.md' '*/CODE-OF-CONDUCT.md'` is empty.
- Root `.github/workflows`, `.github/linters`, and `.github/CODEOWNERS` are unchanged.
````

### 12. Adapt hoisted linters, link checker, and CLA to the monorepo tree

**Summary:** After the polyrepos sit in one tree, super-linter Checkov treats every OpenAPI file as IaC
(portal specs, Postman fixtures, `docs/api`). Lychee follows GitHub-pages root paths (`/docs/img/…`)
and leftover polyrepo links (`CONTRIBUTING.md` inside a module, a missing backend overview). CLA
Assistant writes to `Netcracker/cla-storage` and fails when `CLA_ACCESS_TOKEN` is unset (personal
sandboxes). Skip OpenAPI Checkov paths, drop or retarget those links, skip CLA when the token is
missing.

**Agent time (sandbox run):** about 20 minutes. Dominated by CI log triage; local YAML and markdown
edits were small.

**Prompt:**

````markdown
After the modules land in one tree, the hoisted linters and CLA workflow still assume a single
polyrepo layout. Adjust them so a docs-only change does not fail CI on OpenAPI fixtures, dead
subtree links, or a missing org CLA token.

## Inputs

- GitHub org: `<GITHUB_ORG>`
- Destination: this repo
- Module repo names: `<MODULE_REPOS>`
- CLA org / storage repo: `<CLA_ORG>` / `<CLA_STORAGE_REPO>` (default `Netcracker` / `cla-storage`)

## Checkov

In the destination `.github/linters/.checkov.yaml` (local file wins over the org copy):

- Skip `CKV_OPENAPI_*` checks. API contracts are not Kubernetes/IaC.
- Add `skip-path` entries for `<module>/docs/api`, UI-test spec fixtures, and Postman
  `working-directory` sample APIs.

## Link checker

- Point module contributing links at the destination-root `CONTRIBUTING.md`.
- Remove or retarget markdown links that the subtree never imported (missing overview pages).
- Exclude GitHub-pages user guides that use root-relative `/docs/img/` paths, or add
  `--exclude '/docs/img/'`, until those screenshots live in the monorepo.

## CLA

- Keep the CLA job for destinations in `<CLA_ORG>` that have `CLA_ACCESS_TOKEN`.
- Skip the job when that secret is empty (`secrets.CLA_ACCESS_TOKEN != ''`). Personal forks and
  sandboxes must not fail the PR because they cannot write `<CLA_ORG>/<CLA_STORAGE_REPO>`.

## Do not

- Rewrite OpenAPI files to satisfy Checkov.
- Copy screenshot binaries into the monorepo in this step.
- Change the CLA document URL or signature path for org destinations that already work.

## Verify

- A PR that only touches a module readme does not fail Checkov on `docs/api` or test fixtures.
- `CLA Assistant` is skipped (or green) when `CLA_ACCESS_TOKEN` is unset.
- Link checker does not report the retargeted contributing/overview links.
````

### Pins in this sandbox

Destination wrappers currently call
`<CI_REPO>/.github/workflows/…@feat/monorepo-reusable-workflows` and pass
`ci-store-ref: feat/monorepo-reusable-workflows`. The CI-store change is
[PR #74](https://github.com/Netcracker/qubership-apihub-ci/pull/74). After it
merges, retarget every wrapper and `ci-store-ref` to `main`.

Images built in this fork publish to `ghcr.io/${{ github.repository_owner }}/…`.
E2E fallback images stay on `ghcr.io/netcracker/<image>:dev`. Compose and Kind
E2E need the same secrets the polyrepo workflows used (`JWT_PRIVATE_KEY`,
`APIHUB_ADMIN_EMAIL`, `APIHUB_ADMIN_PASSWORD`, `APIHUB_ACCESS_TOKEN`).

