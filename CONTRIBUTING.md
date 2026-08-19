# Contributing

## Commit authorship

Commits in this repository should be attributed to **you**, not to Cursor or any agent identity.

Before committing (including commits made while pair-programming with an agent):

```bash
git config user.name "Your Name"
git config user.email "your@email.com"
```

Verify:

```bash
git var GIT_AUTHOR_IDENT
git log -1 --format='%an <%ae>'
```

If a commit was created with the wrong author, amend it **before pushing**, or ask to rewrite history on unpushed commits:

```bash
git commit --amend --author="Your Name <your@email.com>" --no-edit
```

For agent-assisted sessions, prefer having the agent stage changes and **you** run `git commit`, or ensure your local `user.name` / `user.email` are set so all commits use your identity.

## Docs

Architecture diagrams live in [docs/architecture.md](./docs/architecture.md). When behavior changes, update diagrams in the same PR as code.

## Tests

```bash
cd packages/protocol
PYTHONPATH=src python3 -m pytest tests/ -q
```
