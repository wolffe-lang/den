"""The candidate is an executed gate, not merely a documented compiler pin."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
rows = {
    'candidate-wolf-main-gate': 'tools/check-candidate-wolf' in (ROOT / 'tools/gate').read_text().splitlines(),
    'candidate-wolf-record-gate': 'leaf candidate-wolf --input target/candidate-wolf -- tools/check-candidate-wolf'
                                  in (ROOT / 'tools/gate-record').read_text().splitlines(),
    'candidate-wolf-hosted-staging': 'tools/fetch-candidate-wolf' in (ROOT / '.github/workflows/ci.yml').read_text(),
}
for name, ok in rows.items():
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
sys.exit(not all(rows.values()))
