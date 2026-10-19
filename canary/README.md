# canary

Prove a test can fail. A test that passes on your change *and* on the code before it doesn't prove your change.

```
canary tests/test_parser.py                  # run from the repo root: your change must pass, the last commit must fail
canary tests/test_a.py tests/test_b.py       # several tests, each judged on its own
canary --base HEAD~1 tests/test_parser.py    # after committing: compare against the commit before
canary --python .venv/bin/python tests/x.py  # pick the interpreter (default: the repo's venv*/bin/python)
```

Each test gets one verdict:

- **good canary**: passes on your change, fails on the old code
- **passes on the old code too**: the test doesn't prove your change
- **fails on your change**: fix that first

The old code runs in a temporary `git worktree` at the base commit, with your current test files copied in.
Your checkout is never touched, and the worktree is removed afterwards.

Requirements: Python 3.9+, git. No dependencies. Install: put `canary.py` on your PATH as `canary`.
Test: `python3 test_canary.py` (builds a throwaway repo; exits 1 on any failure).
