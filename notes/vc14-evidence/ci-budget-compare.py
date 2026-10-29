"""Compare CI completion windows; these are not isolated checked-program runtimes."""
import collections,datetime,hashlib,json,pathlib,re,statistics
R=pathlib.Path('/work/den');P=R/'notes/vc14-evidence'
def instant(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
def read(label):
 path=P/f'ci-budget-{label}.log';meta=json.loads((P/f'ci-budget-{label}-job.json').read_text());step=next(s for s in meta['steps'] if s['name']=='every gate inside the pinned Ubuntu container')
 result=dict(job=meta,step=step,markers=[],events=[],timings=[],command_timings=[],log_sha256=hashlib.sha256(path.read_bytes()).hexdigest());seen=collections.Counter();group=0;command_previous=None;command_group=0
 for line in path.read_text().splitlines():
  match=re.search(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z',line)
  if not match:continue
  timestamp=instant(match.group());text=line[match.end():].lstrip();event=dict(time=match.group(),text=text);result['events'].append(event)
  if text.startswith('{'):
   try:value=json.loads(text)
   except ValueError:continue
   if isinstance(value,dict) and 'file' in value and 'verdict' in value:
    seen[value['file']]+=1;result['markers'].append(dict(file=value['file'],occurrence=seen[value['file']],time=match.group(),verdict=value['verdict']))
  if text.startswith('PACK TIMING '):
   value=json.loads(text[len('PACK TIMING '):]);value.update(tier=('native','release')[group],time=match.group());result['timings'].append(value)
  if text.startswith('PACK WRITE COMPLETE '):group+=1;command_previous=timestamp
  command=re.fullmatch(r'PACK COMMAND (\S+) (\d+)',text)
  if command:
   assert command_previous is not None
   result['command_timings'].append(dict(tier=('native','release')[command_group],fixture=command.group(1),commands=int(command.group(2)),seconds=(timestamp-command_previous).total_seconds()))
   command_previous=timestamp
  if text.startswith('PACK COMMAND COMPLETE '):command_group+=1;command_previous=None
 assert group==2
 return result
trunk=read('trunk');branch=read('vc14')
def key(r):return (r['file'],r['occurrence'])
def windows(run):
 out={};previous=instant(run['step']['startedAt']);anchor='container step start'
 for row in run['markers']:
  at=instant(row['time']);out[key(row)]=dict(**row,seconds=(at-previous).total_seconds(),previous=anchor);previous=at;anchor=row['file']
 return out
tw,bw=windows(trunk),windows(branch);rows=[]
order=list(tw)
for k in bw:
 if k not in tw:
  next_shared=next((key(r) for r in branch['markers'][branch['markers'].index(next(r for r in branch['markers'] if key(r)==k))+1:] if key(r) in tw),None)
  order.insert(order.index(next_shared) if next_shared else len(order),k)
controls=[]
for k in order:
 t,b=tw.get(k),bw.get(k);ratio=b['seconds']/t['seconds'] if t and b and t['previous']==b['previous'] and t['seconds']>0 else None
 row=dict(file=k[0],occurrence=k[1],trunk=t,vc14=b,ratio=ratio)
 if t and b and t['previous']==b['previous'] and t['seconds']>=5 and k[0]!='src/pack_write_test.lu':controls.append(row)
 rows.append(row)
# The added housekeeping gate starts after the initial two den builds.
house=next(r for r in branch['markers'] if r['file']=='src/housekeeping_test.lu');h_end=instant(house['time'])
builds=[e for e in branch['events'] if e['text']=='build: target/release/den' and instant(e['time'])<h_end]
assert builds;house_start=builds[0]['time'];house_seconds=(h_end-instant(house_start)).total_seconds()
# Unchanged fixture/mode writer timings control for extra fixtures.
old={(r['tier'],r['fixture'],r['mode']):r for r in trunk['timings']};new={(r['tier'],r['fixture'],r['mode']):r for r in branch['timings']};assert old.keys()<=new.keys()
writer={}
for tier in ('native','release'):
 shared=[k for k in old if k[0]==tier];added=[k for k in new if k[0]==tier and k not in old]
 t=sum(old[k]['row_seconds'] for k in shared);b=sum(new[k]['row_seconds'] for k in shared)
 writer[tier]=dict(shared_rows=len(shared),trunk_shared_seconds=t,vc14_shared_seconds=b,shared_ratio=b/t,added_rows=len(added),added_seconds=sum(new[k]['row_seconds'] for k in added),added_by_fixture={f:sum(new[k]['row_seconds'] for k in added if k[1]==f) for f in sorted({k[1] for k in added})})
old_commands={(r['tier'],r['fixture']):r for r in trunk['command_timings']};new_commands={(r['tier'],r['fixture']):r for r in branch['command_timings']};assert old_commands.keys()<=new_commands.keys()
commands={}
for tier in ('native','release'):
 shared=[k for k in old_commands if k[0]==tier];added=[k for k in new_commands if k[0]==tier and k not in old_commands]
 t=sum(old_commands[k]['seconds'] for k in shared);b=sum(new_commands[k]['seconds'] for k in shared)
 commands[tier]=dict(shared_fixtures=len(shared),shared_commands=sum(old_commands[k]['commands'] for k in shared),trunk_shared_seconds=t,vc14_shared_seconds=b,shared_ratio=b/t,added_fixtures=len(added),added_commands=sum(new_commands[k]['commands'] for k in added),added_seconds=sum(new_commands[k]['seconds'] for k in added))
# Whole writer/command/failure/adversarial phase boundaries printed by the gate.
def phases(run):
 out=[];start=None;tier=0;phase=None
 for e in run['events']:
  text=e['text'];at=instant(e['time'])
  if text.startswith('pack writer delta: 5 checks;'):
   start=at;phase='writer including client builds/setup/capture serialization'
  elif text.startswith('PACK WRITE COMPLETE ') and start is not None:
   out.append(dict(tier=('native','release')[tier],phase=phase,seconds=(at-start).total_seconds(),end=e['time']));start=at;phase='command matrix'
  elif text.startswith('PACK COMMAND COMPLETE ') and start is not None:
   out.append(dict(tier=('native','release')[tier],phase=phase,seconds=(at-start).total_seconds(),end=e['time']));start=at;phase='publication failures'
  elif text.startswith('PACK FAILURE COMPLETE ') and start is not None:
   out.append(dict(tier=('native','release')[tier],phase=phase,seconds=(at-start).total_seconds(),end=e['time']));start=at;phase='adversarial'
  elif text.startswith('PACK ADVERSARIAL COMPLETE ') and start is not None:
   out.append(dict(tier=('native','release')[tier],phase=phase,seconds=(at-start).total_seconds(),end=e['time']));start=None;tier+=1
 assert tier==2
 return out
ratios=[r['ratio'] for r in controls];median=statistics.median(ratios)
last=branch['markers'][-1];tk=tw[key(last)];tail=(instant(trunk['step']['completedAt'])-instant(tk['time'])).total_seconds();elapsed=(instant(last['time'])-instant(branch['step']['startedAt'])).total_seconds()
summary=dict(method='Each file row measures elapsed wall time since the previous recorded file verdict, initially the container-step start. Windows include intervening builds and matrices; they are not isolated file-test execution times. Missing branch rows were not reached before cancellation.',trunk_job_seconds=(instant(trunk['job']['completedAt'])-instant(trunk['job']['startedAt'])).total_seconds(),trunk_container_seconds=(instant(trunk['step']['completedAt'])-instant(trunk['step']['startedAt'])).total_seconds(),vc14_job_seconds=(instant(branch['job']['completedAt'])-instant(branch['job']['startedAt'])).total_seconds(),vc14_container_seconds=(instant(branch['step']['completedAt'])-instant(branch['step']['startedAt'])).total_seconds(),housekeeping=dict(start=house_start,end=house['time'],seconds=house_seconds),controls=dict(count=len(controls),median_ratio=median,min_ratio=min(ratios),max_ratio=max(ratios),files=[r['file'] for r in controls]),writer=writer,commands=commands,trunk_pack_phases=phases(trunk),vc14_pack_phases=phases(branch),last_completed_file=last['file'],last_file_elapsed_seconds=elapsed,trunk_remaining_seconds=tail,projected_finish_seconds=elapsed+tail*median,projected_finish_at_2x_tail_seconds=elapsed+tail*2,log_sha256=dict(trunk=trunk['log_sha256'],vc14=branch['log_sha256']))
output=dict(summary=summary,files=rows)
(P/'ci-budget-comparison.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
lines=['file\ttrunk_previous\ttrunk_end\ttrunk_seconds\tvc14_previous\tvc14_end\tvc14_seconds\tratio']
for r in rows:
 t,b=r['trunk'],r['vc14'];lines.append('\t'.join([r['file'],t['previous'] if t else '-',t['time'] if t else '-',f"{t['seconds']:.3f}" if t else '-',b['previous'] if b else '-',b['time'] if b else '-',f"{b['seconds']:.3f}" if b else '-',f"{r['ratio']:.3f}" if r['ratio'] is not None else '-']))
(P/'ci-budget-per-file.tsv').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,indent=2),flush=True)
print('\n'.join(lines),flush=True)
