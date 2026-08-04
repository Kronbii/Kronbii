# How this README works

The neofetch-style card at the top of [README.md](README.md) is two SVG files —
`dark_mode.svg` and `light_mode.svg`. GitHub picks one based on the viewer's
theme via the `<picture>`/`prefers-color-scheme` block in the README, so the
card matches light and dark mode automatically.

`today.py` queries the GitHub GraphQL API for live stats and rewrites the
numbers inside both SVGs. `.github/workflows/build.yaml` runs it daily at
04:00 UTC (and on every push to `main`), then commits the updated SVGs.

Adapted from [Andrew6rant/Andrew6rant](https://github.com/Andrew6rant/Andrew6rant)
by Andrew Grant.

## What updates automatically

| Field | Source |
| --- | --- |
| Uptime | Age of the GitHub account, or your date of birth — see below |
| Repos / Contributed | Repository counts (owner vs. all affiliations) |
| Stars | Sum of stargazers across owned repos |
| Commits | Your commits across every repo in the cache |
| Followers | Follower count |
| Lines of Code | Additions/deletions from commits authored by you |

Everything else (job title, languages, hobbies, contact) is static text —
edit it directly in both SVG files.

## Optional: show your real age instead of the account age

`today.py` has a `BIRTHDAY` constant near the top. Leave it as `None` to show
how long the GitHub account has existed, or set it to show your real age:

```python
BIRTHDAY = datetime.datetime(1999, 5, 17)
```

## Optional: count private repositories

By default the workflow uses the built-in `GITHUB_TOKEN`, which only sees
public data. To include private repos, add a repository secret named
`ACCESS_TOKEN` containing a **fine-grained personal access token**:

1. GitHub → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token.
2. Repository access: **All repositories**.
3. Permissions:
   - Account: `Followers: read`, `Starring: read`, `Watching: read`
   - Repository: `Commit statuses: read`, `Contents: read`, `Metadata: read`
4. Copy the token, then add it under this repo's
   Settings → Secrets and variables → Actions → New repository secret,
   named `ACCESS_TOKEN`.

The workflow uses it if present and falls back to `GITHUB_TOKEN` otherwise.

## Running it locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r cache/requirements.txt
ACCESS_TOKEN=$(gh auth token) USER_NAME=Kronbii python today.py
```

The first run is slow — it walks the commit history of every repository. After
that, `cache/<sha256-of-username>.txt` stores per-repo commit counts, and only
repositories whose commit count changed are re-scanned.

If the cached numbers ever look wrong, delete that cache file and re-run to
rebuild it from scratch.
