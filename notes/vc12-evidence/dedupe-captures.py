"""Deduplicate byte-identical retained captures and drop the one stale input.

retain-components.py gzips every target/*.json; final-counts.py gzips the same
stash captures under their own names. The pairs below are verified identical
before the component copy is removed; additional-captures.json is left as
generated and this record maps its entries to the retained copy. The stale
target/stash-measure.json predates the gauntlet (an oracle-only --measure run)
and is not gauntlet evidence, so its component copy is removed and named here.
"""
import hashlib,json,pathlib
O=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=dict(deduplicated={},stale_removed={})
for tier in ('native','release'):
 dup=O/f'component-stash-{tier}.json.gz';kept=O/f'stash-{tier}.json.gz'
 assert dup.exists() and kept.exists() and sha(dup)==sha(kept),(dup,kept)
 record['deduplicated'][dup.name]=dict(retained_as=kept.name,sha256=sha(kept))
 dup.unlink()
stale=O/'component-stash-measure.json.gz'
index=json.loads((O/'additional-captures.json').read_text())['components']
entry=index['target/stash-measure.json']
assert entry['capture']==stale.name
record['stale_removed'][stale.name]=dict(source='target/stash-measure.json',raw_sha256=entry['sha256'],reason='pre-gauntlet oracle-only --measure output (2026-10-27 23:22 local), not produced by the final gauntlet')
stale.unlink()
(O/'deduplicated-captures.json').write_text(json.dumps(record,indent=2)+'\n')
print('deduplicated',len(record['deduplicated']),'captures; removed',len(record['stale_removed']),'stale capture')
