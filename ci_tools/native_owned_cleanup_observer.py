"""Observe genuine unchanged lifetime controls without changing cleanup decisions."""
from __future__ import annotations
import ast
import datetime
import hashlib
import json
import pathlib
import sys
import time
import textwrap

for diagnostic_stream in (sys.stdout, sys.stderr):
    if hasattr(diagnostic_stream, 'reconfigure'):
        diagnostic_stream.reconfigure(encoding='utf-8')

SOURCE = pathlib.Path(sys.argv[1]).resolve()
OUTPUT = pathlib.Path(sys.argv[2]).resolve()
OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=False)
sys.path.insert(0, str(SOURCE))
from ci_tools.source_quarantine import activate_from_environment, loaded_origins
state = activate_from_environment()
if state is None or state['copied'] != SOURCE:
    raise RuntimeError('Source-bound diagnostic requires actual quarantine authority')
import runpy
RUNNER = SOURCE / 'ci_tools/zero_trust_runner.py'
ADMISSION = SOURCE / 'ci_tools/posix_admission.py'
TEST = SOURCE / 'tests/ci_tools/test_quarantine_owned_processes.py'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(RUNNER) == '3ed284ff44fb8b472364ce70fcb2dc9745f2ae010332785725bd13a03d2a19e5'
assert sha(ADMISSION) == 'ac275a9be93955d5caab29dddda25ec9c83a1782632ee1059a2f4f2aa76a1792'
source_hashes = {str(p.relative_to(SOURCE)): sha(p) for p in (RUNNER, ADMISSION, TEST)}
namespace = runpy.run_path(str(TEST))
node = next(n for n in ast.parse(TEST.read_text()).body if isinstance(n, ast.FunctionDef)
            and n.name == 'test_exited_launcher_cleans_workers_and_preserves_unrelated_owners')
body_node = next(n for n in ast.walk(node) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == '_run_control').args[1]
for value in ast.walk(body_node):
    if isinstance(value,ast.FormattedValue):
        assert isinstance(value.value,ast.Name) and value.value.id in {'exit_code','inherit_pipes'}
        assert value.format_spec is None
def render_original_body(exit_code, inherit_pipes):
    assert isinstance(body_node, ast.JoinedStr)
    parameters = {'exit_code': exit_code, 'inherit_pipes': inherit_pipes}
    parts = []
    for value in body_node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            assert isinstance(value.value, ast.Name) and value.value.id in parameters
            assert value.format_spec is None
            parameter = parameters[value.value.id]
            if value.conversion == 114:
                parts.append(repr(parameter))
            elif value.conversion == 97:
                parts.append(ascii(parameter))
            else:
                assert value.conversion in (-1, 115)
                parts.append(str(parameter))
        else:
            raise ValueError('Original native body contains unapproved interpolation')
    return ''.join(parts)

TRACE_PREFIX = r'''
import collections
import sys
import time
from ci_tools import zero_trust_runner as diagnostic_runner
diagnostic_events = collections.deque(maxlen=256)
diagnostic_all_exceptions = []
diagnostic_started = time.monotonic()
diagnostic_invocation = 0
def diagnostic_identity(value):
    if value is None:
        return None
    return {'pid':getattr(value,'pid',None),
            'captured_ident':getattr(value,'_ident',None),
            'cached_gone':getattr(value,'_gone',None),
            'cached_pid_reused':getattr(value,'_pid_reused',None)}
def observe_cleanup_frame(frame,event,argument):
    if frame.f_code is not diagnostic_runner._stop_owned_process.__code__:
        return None
    if event not in ('call','line','return','exception'):
        return observe_cleanup_frame
    global diagnostic_invocation
    if event=='call':
        diagnostic_invocation += 1
        diagnostic_events.clear()
    local = frame.f_locals
    entry = {'event':event,'line':frame.f_lineno,'elapsed_s':time.monotonic()-diagnostic_started}
    for key in ('leader_present','owns_group','uncertain','status','created','identity','deadline'):
        if key in local:
            value = local[key]
            if value is None or isinstance(value,(bool,int,float,str,tuple)):
                entry[key]=value
    for key in ('members','current_terminal'):
        if key in local:
            entry[key]=sorted(local[key])
    for key in ('descendants','same_generation','alive'):
        if key in local:
            entry[key]=[diagnostic_identity(p) for p in local[key]]
    for key in ('current','child','member'):
        if key in local:
            entry[key]=diagnostic_identity(local[key])
    process=local.get('process')
    if process is not None:
        entry['launcher']={'pid':process.pid,'cached_returncode':process.returncode}
    owner=local.get('owner')
    if owner is not None:
        entry['owner']={'owns_posix_group':owner.owns_posix_group,
                        'admission_pending':owner.admission_pending,
                        'admitted_before_exec':owner.admitted_before_exec,
                        'launcher_create_time':owner.launcher_create_time,
                        'leader':diagnostic_identity(owner.leader),
                        'external_reaping_pending':owner.external_reaping_pending}
    if event=='exception':
        kind,exception,_=argument
        entry['exception']={'type':kind.__name__,'errno':getattr(exception,'errno',None)}
        diagnostic_all_exceptions.append(entry.copy())
    if event=='return':
        entry['actual_return']=argument
    diagnostic_events.append(entry)
    if event=='return':
        receipt={'scope':'Observational trace of actual unchanged cleanup; no poll/wait/status calls from observer',
                 'runner_sha256':hashlib.sha256(Path(diagnostic_runner.__file__).read_bytes()).hexdigest(),
                 'actual_return':argument,'return_line':frame.f_lineno,
                 'events':list(diagnostic_events),'all_observed_exceptions':diagnostic_all_exceptions}
        (evidence_dir/('actual-cleanup-frame-trace-'+str(diagnostic_invocation)+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    return observe_cleanup_frame
import hashlib
diagnostic_previous_trace = sys.gettrace()
sys.settrace(observe_cleanup_frame)
'''

observations=[]
for inherit_pipes, exit_code in ((False,0),(False,7),(True,0),(True,7)):
    case=OUTPUT/f'{inherit_pipes}-{exit_code}'
    case.mkdir(mode=0o700)
    actual_body=render_original_body(exit_code, inherit_pipes)
    (case/'original-body.sha256').write_text(hashlib.sha256(actual_body.encode()).hexdigest()+'\n')
    started=time.monotonic()
    try:
        observed_body=TRACE_PREFIX+'try:\n'+textwrap.indent(textwrap.dedent(actual_body),'    ')+'\nfinally:\n    sys.settrace(diagnostic_previous_trace)\n'
        result=namespace['_run_control'](case, observed_body)
        record={'case':case.name,'original_assertions_passed':True,'observation':result}
    except Exception as error:
        record={'case':case.name,'original_assertions_passed':False,'exception_type':type(error).__name__}
    record['elapsed_s']=time.monotonic()-started
    observations.append(record)
    (case/'diagnostic-observation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'case':case.name,'original_assertions_passed':record['original_assertions_passed'],
                      'actual_trace_present':bool(list(case.glob('actual-cleanup-frame-trace-*.json')))}),flush=True)
final_origins=loaded_origins(state)
assert not final_origins['escaped']
assert source_hashes=={str(p.relative_to(SOURCE)):sha(p) for p in (RUNNER,ADMISSION,TEST)}
receipt={'schema_version':1,'scope':'Source-bound engineering cause observation; not release acceptance and not a retry to convert original failure to a pass',
         'source_revision':state['revision'],'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'source_hashes':source_hashes,'source_unchanged':True,'origins':final_origins,
         'source_refusal_or_deadline_relaxed':False,'actual_cases':observations}
(OUTPUT/'native-diagnostic-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

# Preserve diagnostic failures as nonzero execution outcomes after all raw cases are written.
raise SystemExit(0 if all(row["original_assertions_passed"] for row in observations) else 1)
