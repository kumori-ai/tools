"""canary's own checks, in a throwaway git repo. Run: python3 test_canary.py. Exit 1 on any failure."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CANARY = os.path.join(HERE, 'canary.py')
fails = []


def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  {detail}' if detail and not cond else ''))
    if not cond:
        fails.append(name)


def git(repo, *a):
    subprocess.run(['git', '-C', repo, *a], check=True, capture_output=True)


with tempfile.TemporaryDirectory() as repo:
    git(repo, 'init', '-q', '-b', 'main'); git(repo, 'config', 'user.email', 't@t'); git(repo, 'config', 'user.name', 't')
    with open(os.path.join(repo, 'src.py'), 'w') as f:
        f.write('def answer():\n    return 1\n')
    git(repo, 'add', '.'); git(repo, 'commit', '-qm', 'old code')
    with open(os.path.join(repo, 'src.py'), 'w') as f:                       # the change, uncommitted
        f.write('def answer():\n    return 2\n')
    os.makedirs(os.path.join(repo, 'tests'))
    tests = {
        'test_good.py': 'assert __import__("src").answer() == 2',            # proves the change
        'test_weak.py': 'assert callable(__import__("src").answer)',         # passes either way
        'test_broken.py': 'assert __import__("src").answer() == 3',          # fails on the change
    }
    for name, body in tests.items():
        with open(os.path.join(repo, 'tests', name), 'w') as f:
            f.write('import os, sys\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n'
                    + body + '\n')

    def canary(*t):
        p = subprocess.run([sys.executable, CANARY, '--python', sys.executable, *t], cwd=repo,
                           capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    rc, out = canary('tests/test_good.py')
    check('a test that proves the change is a good canary', rc == 0 and 'good canary' in out, out)
    rc, out = canary('tests/test_weak.py')
    check('a test that passes on the old code too is flagged', rc == 1 and 'PASSES on the old code too' in out, out)
    rc, out = canary('tests/test_broken.py')
    check('a test failing on the change is flagged first', rc == 1 and 'fails on your change' in out, out)
    with open(os.path.join(repo, 'src.py')) as f:
        check('the checkout is untouched', 'return 2' in f.read())
    wts = subprocess.run(['git', '-C', repo, 'worktree', 'list'], capture_output=True, text=True).stdout
    check('the temporary worktree is removed', len(wts.strip().splitlines()) == 1, wts)

sys.exit(1 if fails else 0)
