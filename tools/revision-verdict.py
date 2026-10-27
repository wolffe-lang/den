"""Do not mistake conform-run's process status for the checked-machine verdict."""
import json,sys
rows=[json.loads(line) for line in open(sys.argv[1]) if line.startswith('{')]
assert len(rows)==1 and rows[0]['verdict']=='exit(0)',rows
print('revision checked: exit(0)')
