"""The candidate runs where it can be fetched: the local record, not hosted CI.

The candidate is another repository's workflow artifact until wolf releases it. A workflow's own token
can download only its own repository's artifacts (GitHub's documentation of the GITHUB_TOKEN and of
actions/download-artifact), so the hosted gate cannot stage it: tools/gate-record runs the leaf, and
tools/gate (which hosted CI runs) runs only the leaf's self-tests, which need no compiler. The workflow
stages nothing for it.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
workflow = (ROOT / '.github/workflows/ci.yml').read_text()
gate = (ROOT / 'tools/gate').read_text().splitlines()
rows = {
    'candidate-wolf-record-gate': 'leaf candidate-wolf --input target/candidate-wolf -- tools/check-candidate-wolf'
                                  in (ROOT / 'tools/gate-record').read_text().splitlines(),
    'candidate-wolf-not-in-hosted-gate': 'tools/check-candidate-wolf' not in gate,
    'candidate-wolf-self-tests-in-hosted-gate': all(
        f'python3 -I tools/{t}.py' in gate for t in ('candidate-wolf-test', 'candidate-fetch-test', 'candidate-wiring-test')),
    'candidate-wolf-no-hosted-staging': 'candidate' not in workflow,
}
for name, ok in rows.items():
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
sys.exit(not all(rows.values()))
