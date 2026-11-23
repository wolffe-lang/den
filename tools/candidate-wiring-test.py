"""The candidate is an executed gate, not merely a documented compiler pin."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
workflow = (ROOT / '.github/workflows/ci.yml').read_text()
stage = ("      - name: stage the immutable compiler candidate\n"
         "        env:\n"
         "          GH_TOKEN: ${{ github.token }}\n"
         "        run: tools/fetch-candidate-wolf\n")
rows = {
    'candidate-wolf-main-gate': 'tools/check-candidate-wolf' in (ROOT / 'tools/gate').read_text().splitlines(),
    'candidate-wolf-record-gate': 'leaf candidate-wolf --input target/candidate-wolf -- tools/check-candidate-wolf'
                                  in (ROOT / 'tools/gate-record').read_text().splitlines(),
    'candidate-wolf-hosted-staging': workflow.count(stage) == 1
        and workflow.index(stage) < workflow.index('        run: tools/in-container tools/gate'),
    'candidate-wolf-pin-triggers-ci': "      - 'candidate-wolf.toml'" in workflow,
}
for name, ok in rows.items():
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
sys.exit(not all(rows.values()))
