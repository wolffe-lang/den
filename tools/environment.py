"""Pinned environment, scratch HOME, exact global config saved beside it."""
import os, pathlib, sys
R=pathlib.Path(__file__).resolve().parent.parent
base=pathlib.Path(os.environ.get('DEN_ENV_ROOT',R/'target/environment')).resolve()
for name in ('home','xdg','empty-hooks','empty-template'):
    (base/name).mkdir(parents=True,exist_ok=True)
config=(f'[user]\n\tname = Den Tester\n\temail = den@example.invalid\n'
        f'[color]\n\tui = never\n[core]\n\tpager = cat\n\thooksPath = {base}/empty-hooks\n'
        '[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n')
(base/'gitconfig').write_bytes(config.encode())
e={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
e.update(LC_ALL='C',TZ='UTC',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=str(base/'gitconfig'),
         GIT_AUTHOR_DATE='1700000000 +0000',GIT_COMMITTER_DATE='1700000000 +0000',
         GIT_EDITOR='false',PAGER='cat',HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'xdg'),
         GIT_TERMINAL_PROMPT='0',GIT_OPTIONAL_LOCKS='0',DEN_EMPTY_TEMPLATE=str(base/'empty-template'))
if os.environ.get('DEN_GIT'):
    git=pathlib.Path(os.environ['DEN_GIT']).resolve()
    e['GIT_EXEC_PATH']=str(git.parent.parent/'libexec/git-core')
    e['PATH']=str(git.parent)+os.pathsep+e.get('PATH','')
if len(sys.argv)==1: sys.exit('usage: tools/env COMMAND [ARG ...]')
os.execvpe(sys.argv[1],sys.argv[1:],e)
