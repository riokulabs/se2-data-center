<!-- managed by riokulabs/.github - edit there (templates/), not here -->
## What this changes

<!-- What and why, in a few sentences. Link the issue: "Fixes #123". -->

## How you checked it

<!-- Commands you ran, what you saw. -->

## Checklist

- [ ] Offline tests pass: `scripts/test.sh` (same as `python3 -m pytest -q Tests -m "not build"` minus the SDK build)
- [ ] If a definition, model or script changed: the SDK build passes (`pgrep -x Modern.bin` prints nothing, then `python3 ../../tools/scripts/se2mod.py build DataCenter` exits 0 with no DataCenter warnings)
- [ ] Files under `Assets/` come from the generator (`Source/Model/`), not hand edits; GUIDs are untouched
- [ ] No preview renders, decompiled code, Keen DLLs, or tokens are committed (`python3 scripts/check_repo_guard.py`)
- [ ] Built from the main checkout, not a git worktree, and nothing was published
- [ ] `CHANGELOG.md` has a line under `[Unreleased]` for anything players will notice
- [ ] Any Keen asset reused is covered by the documented vanilla reuse; any new third-party content has a compatible license noted in the PR
- [ ] Commits are signed off (`git commit -s`, see CONTRIBUTING.md)
- [ ] I have signed the Rioku Labs CLA (the bot asks on your first pull request; see CONTRIBUTING.md)
