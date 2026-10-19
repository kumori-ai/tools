#!/usr/bin/env python3
"""canary: prove a test can fail. Runs it on your change (must pass), then on the last commit with your
current test files copied in (must fail). A test that passes on both doesn't prove your change.

    canary tests/test_parser.py                  # run from the repo root
    canary tests/test_a.py tests/test_b.py       # several, each judged on its own
    canary --python .venv/bin/python tests/x.py  # pick the interpreter (default: the repo's venv*)
    canary --base HEAD~1 tests/test_parser.py    # after committing: the old code is the commit before

Why: a green check you have never seen go red is not evidence. A test written alongside a fix often passes
on the old code too, so it proves nothing about the fix. canary runs the test twice, once on your change
and once on the code before it, and says so when a test cannot fail. The old-code run happens in a
temporary git worktree, never by swapping files in your checkout, so other work in progress is untouched.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

TIMEOUT_S = 900


def _git(root, *args):
    return subprocess.run(['git', '-C', root, *args], capture_output=True, text=True)


def _run(python, test, cwd):
    try:
        p = subprocess.run([python, test], cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_S)
        return p.returncode, (p.stdout + p.stderr).strip().splitlines()
    except subprocess.TimeoutExpired:
        return 'timeout', [f'timed out after {TIMEOUT_S}s']


def _python(root, given):
    if given:
        return os.path.abspath(given)
    found = sorted(glob.glob(os.path.join(root, 'venv*', 'bin', 'python')))
    return found[0] if found else sys.executable


def judge(new, old):
    """(verdict, ok) for one test from its two exit codes."""
    if new != 0:
        return 'fails on your change: fix that first, the canary means nothing yet', False
    if old == 0:
        return 'PASSES on the old code too: this test does not prove your change', False
    return 'good canary: passes on your change, fails on the old code', True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('tests', nargs='+', help='test files, relative to the repo root')
    ap.add_argument('--python', help='interpreter (default: the repo venv*/bin/python)')
    ap.add_argument('--base', default='HEAD', help='the old code to compare against (default HEAD; HEAD~1 after committing)')
    a = ap.parse_args()
    root = _git(os.getcwd(), 'rev-parse', '--show-toplevel').stdout.strip()
    if not root:
        sys.exit('canary: not inside a git repo')
    python = _python(root, a.python)
    tests = [os.path.relpath(os.path.abspath(t), root) for t in a.tests]
    missing = [t for t in tests if not os.path.isfile(os.path.join(root, t))]
    if missing:
        sys.exit(f'canary: no such test file: {", ".join(missing)}')
    changed = [f for f in _git(root, 'diff', '--name-only', a.base).stdout.split() if f not in tests]
    changed += [f for f in _git(root, 'ls-files', '--others', '--exclude-standard').stdout.split() if f not in tests]
    if not changed:
        sys.exit(f'canary: nothing to prove: no change outside the tests since {a.base} (after a commit, try --base HEAD~1)')
    tmp = tempfile.mkdtemp(prefix='canary-')
    wt = os.path.join(tmp, 'head')
    add = _git(root, 'worktree', 'add', '--detach', wt, a.base)
    if add.returncode:
        sys.exit(f'canary: could not make a worktree at {a.base}: {add.stderr.strip()}')
    all_ok = True
    try:
        for t in tests:
            os.makedirs(os.path.dirname(os.path.join(wt, t)) or wt, exist_ok=True)
            shutil.copy2(os.path.join(root, t), os.path.join(wt, t))     # the new test, against the old code
            new, new_out = _run(python, t, root)
            old, old_out = _run(python, t, wt)
            verdict, ok = judge(new, old)
            all_ok &= ok
            print(f"{'✅' if ok else '❌'} {t}: {verdict}  (your change: exit {new}; old code: exit {old})")
            if not ok:
                tail = new_out if new != 0 else old_out
                for line in tail[-6:]:
                    print(f'     {line[:160]}')
    finally:
        _git(root, 'worktree', 'remove', '--force', wt)
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
