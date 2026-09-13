# Monorepoisation

Sandbox log of folding APIHUB polyrepos into one git repository. Replay these steps in the
production monorepo. The operator supplies the source-repo list each time; do not treat any
single run's roster as canonical.

## How to use this log

1. Copy the prompt from the step you need.
2. Replace placeholders (`<GITHUB_ORG>`, `<ROOT_REPO>`, `<MODULE_REPOS>`, and the rest).
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

