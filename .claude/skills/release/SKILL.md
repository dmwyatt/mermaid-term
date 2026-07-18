---
name: release
description: Cut and publish a release of mermaid-term to PyPI. Use when asked to release, cut a release, ship a new version, or bump and publish.
---

# Release

Releases are published by CI via PyPI trusted publishing: pushing a `v*` tag
runs `.github/workflows/publish.yml`, which tests, builds, and publishes.
Never run `uv publish` locally; it would need a stored token and would skip
the test gate.

Two GitHub-side guards apply: a ruleset restricts `v*` tag creation and
deletion to the repo admin (pushes as dmwyatt bypass it), and the `pypi`
environment requires dmwyatt to approve the deployment before the publish
job runs.

## Preconditions

Abort and report if any of these fail:

1. On `main` with a clean working tree (`git status --porcelain` is empty).
2. In sync with the remote: `git fetch origin` then confirm `main` is not
   behind `origin/main`.
3. Lock file current: `uv lock --check`.
4. Tests pass: `uv run python -m pytest` (use `python -m`; bare
   `uv run pytest` fails on some Windows setups).

## Steps

1. Decide the bump. If the user didn't specify, look at what changed since
   the last tag (`git log $(git describe --tags --abbrev=0)..HEAD --oneline`)
   and ask: patch for fixes, minor for features, major for breaking changes.
2. `uv version --bump <patch|minor|major>`
3. Commit `pyproject.toml` and `uv.lock` with message `Release v<version>`.
4. Tag with the exact version: `git tag v$(uv version --short)`. The
   workflow rejects tags that don't match the package version.
5. `git push origin main v<version>`
6. The publish job pauses as "Waiting" until the `pypi` environment
   deployment is approved. Have the user approve it:
   `gh run list --workflow=publish.yml` for the run id, then
   `gh run view <id> --web` and click "Review deployments". Do not try to
   approve it yourself via the API; the human approval is the point.
7. Watch the run: `gh run watch` (or `gh run list --workflow=publish.yml`).
   Do not report success until the workflow succeeds.
8. Confirm the new version is live: `https://pypi.org/pypi/mermaid-term/json`
   should list it.
9. Create a GitHub release: `gh release create v<version> --generate-notes`.

## If the workflow fails

- Failure before the publish step (tests, version-mismatch guard): fix the
  problem on `main`, delete the tag locally and remotely
  (`git tag -d v<version>` and `git push origin :refs/tags/v<version>`),
  and re-tag once fixed.
- Failure during or after publish: check whether the version reached PyPI.
  A published version can never be re-uploaded, so if it's live (even
  partially), fix forward with a new patch release instead of re-tagging.
