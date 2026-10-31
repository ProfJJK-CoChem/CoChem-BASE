"""Data-only single-request admission and exact run ownership, without science imports.

Hosted storage is composed separately. Records never grant source or scientific
permission; workflows supply independently authenticated execution context.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import threading
import uuid


def _request_contract():
    if __package__:
        from . import student_request
        return student_request
    path = Path(__file__).with_name("student_request.py")
    spec = importlib.util.spec_from_file_location("cochem_admission_request", path)
    if spec is None or spec.loader is None:
        raise ImportError("Source-local request contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

request_contract = _request_contract()
PROTOCOL = "cochem.student-actions-admission/1"
LEDGER_REF = "refs/heads/cochem-student-admission-v1"
DESCRIPTOR_PATH = ".cochem/student-actions-admission.json"
CAPABILITY_SCHEMA = "cochem.student-actions-capability/1"
REQUIRED_PATHS = frozenset({
    ".github/workflows/student_research.yml", ".github/workflows/student_project_setup.yml",
    "scripts/run_student_research.py", "scripts/check_student_project_setup.py",
    "src/cochem_base/interfaces/student_actions_admission.py",
    "src/cochem_base/interfaces/student_actions_admission_git.py",
    "src/cochem_base/interfaces/student_actions_admission_git_readonly.py",
    "src/cochem_base/interfaces/student_request.py",
    "src/cochem_base/interfaces/course_access.py",
    "src/cochem_base/interfaces/actions_jobs.py",
    "src/cochem_base/interfaces/student_research.py",
})
MAX_HISTORY = 256
MAX_TRANSPORT = request_contract.MAX_PAYLOAD_BASE64_BYTES
HEX40 = request_contract.COMMIT_PATTERN
HEX64 = request_contract.SHA_PATTERN
REPO = request_contract.REPOSITORY_PATTERN
FIELDS = {"schema_version", "request_id", "repository", "source_sha", "worker_source_sha", "submitted_at",
          "resources", "calculation", "provider", "capability_probe", "scientific_inputs", "data_inputs", "t9_request", "files"}
INTENT_FIELDS={'schema_version','protocol','generation','repository_id','repository','branch','workflow_id','workflow_path','request_id','payload_sha256','request_blob_sha','source_sha','worker_source_sha'}
STATE_FIELDS={'schema_version','generation','intent_sha256','phase','previous','actor','anchor','binding_sha256','stop_requested','terminal'}
BINDING_FIELDS={'schema_version','generation','intent_sha256','anchor','request_id','payload_sha256','repository_id','repository','workflow_id','branch','source_sha','worker_source_sha','run_id','run_attempt'}
CONCLUSIONS={'success','failure','neutral','cancelled','skipped','timed_out','action_required','stale','startup_failure'}

class AdmissionError(RuntimeError):
    """Fail-closed transport, ownership, record or admission refusal."""

class Conflict(AdmissionError):
    """An actual expected-parent Git update lost; no permission to POST."""

class TransportError(AdmissionError):
    """Actual HTTP failure; uncertain POSTs must never be automatically retried."""
    def __init__(self,message,uncertain=False):super().__init__(message);self.uncertain=uncertain

canonical = request_contract.canonical_json

def digest(raw): return hashlib.sha256(raw).hexdigest()
def blob_id(raw): return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
def positive(value): return type(value) is int and value > 0
def uid(value):
    try: return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError): return False

def strict(raw, maximum=65536):
    if not isinstance(raw, bytes) or len(raw) > maximum:
        raise AdmissionError("Record exceeds its byte bound")
    try:
        value = request_contract.strict_json(raw)
        if canonical(value) != raw:
            raise ValueError("Noncanonical record")
        return value
    except (ValueError, UnicodeError, TypeError) as error:
        raise AdmissionError("Invalid canonical data record") from error

def validate_request(raw):
    try:
        r = request_contract.decode_transport_request(base64.b64encode(raw).decode(), digest(raw))
        if set(r) != FIELDS or r["capability_probe"] is not None:
            raise ValueError("A research request with the exact transport fields is required")
        if sum(isinstance(r[k], dict) for k in ("calculation", "provider")) != 1:
            raise ValueError("Exactly one research operation is required")
        return r
    except (ValueError, TypeError, KeyError) as error:
        raise AdmissionError("The saved research transport is invalid") from error

def validate_intent(i,r,raw):
    if set(i)!=INTENT_FIELDS or i['schema_version']!='cochem.student-actions-intent/1' or i['protocol']!=PROTOCOL or not uid(i['generation']):raise AdmissionError('Unsupported intent')
    if not positive(i['repository_id']) or not positive(i['workflow_id']) or i['workflow_path']!='.github/workflows/student_research.yml' or not isinstance(i['branch'],str) or not i['branch'] or len(i['branch'])>255:raise AdmissionError('Invalid project/workflow identity')
    for k in ['request_id','repository','source_sha','worker_source_sha']:
        if i[k]!=r[k]:raise AdmissionError('Intent changed immutable request')
    if i['payload_sha256']!=digest(raw) or i['request_blob_sha']!=blob_id(raw):raise AdmissionError('Intent request hash differs')

def validate_run(run,i,terminal=False):
    if not isinstance(run,dict) or not positive(run.get('id')) or type(run.get('run_attempt')) is not int or run['run_attempt']!=1:raise AdmissionError('Only a real positive run ID and attempt1 are supported')
    if not isinstance(run.get('repository'),dict):raise AdmissionError('Missing real run project metadata')
    if (run.get('repository',{}).get('id')!=i['repository_id'] or type(run.get('repository',{}).get('id')) is not int or run.get('repository',{}).get('full_name')!=i['repository'] or run.get('workflow_id')!=i['workflow_id'] or type(run.get('workflow_id')) is not int or run.get('head_sha')!=i['source_sha'] or run.get('head_branch')!=i['branch'] or run.get('event')!='workflow_dispatch' or run.get('display_title')!='CoChem student '+i['request_id']):raise AdmissionError('Observed run identity differs')
    if terminal:
        if run.get('status')!='completed' or not isinstance(run.get('conclusion'),str) or run.get('conclusion') not in CONCLUSIONS:raise AdmissionError('Exact terminal status is not confirmed')
    elif not isinstance(run.get('status'),str) or run.get('status') not in {'queued','in_progress','waiting','requested','pending'}:raise AdmissionError('Do not bind a terminal/unknown run')

@dataclass(frozen=True)
class Snapshot:
    tip:str
    request:dict
    raw:bytes
    intent:dict
    state:dict
    binding:dict|None
    anchor:str|None


def identity(snapshot):
    """Captured immutable request scope; not a reusable dispatch permission."""
    if snapshot is None:
        raise AdmissionError("The captured request is unavailable")
    return {"generation": snapshot.intent["generation"], "intent_sha256": snapshot.state["intent_sha256"],
            **{key: snapshot.intent[key] for key in ("request_id", "payload_sha256", "repository_id", "repository",
                "branch", "workflow_id", "workflow_path", "source_sha", "worker_source_sha")}}


def require_expected(snapshot, expected):
    if not isinstance(expected, dict) or canonical(expected) != canonical(identity(snapshot)):
        raise AdmissionError("The captured project request changed; no operation was performed")


class AdmissionStore:
    """Validated state machine over the concrete Git-data backend."""
    def __init__(self, backend): self.backend = backend
    def tip(self): return self.backend.tip()
    def files(self, commit): return self.backend.files(commit)
    def commit(self, files, parent): return self.backend.commit(files, parent)
    def advance(self, commit, parent): return self.backend.advance(commit, parent)
    def read(self,commit=None):
        tip=commit if commit is not None else self.tip()
        if tip is None:return None
        chain=[];current=tip
        while current:
            if len(chain)>=MAX_HISTORY:raise AdmissionError('Finite ledger history bound reached; retain for review')
            files,parent=self.files(current);r=validate_request(files['request.json']);i=strict(files['intent.json'],16384);s=strict(files['state.json'],16384);b=strict(files['binding.json'],16384) if 'binding.json' in files else None
            validate_intent(i,r,files['request.json'])
            if set(s)!=STATE_FIELDS or s['schema_version']!='cochem.student-actions-state/1' or s['generation']!=i['generation'] or s['intent_sha256']!=digest(files['intent.json']) or s['previous']!=parent or type(s['stop_requested']) is not bool:raise AdmissionError('Invalid state/parent/intent schema')
            if not isinstance(s['phase'],str) or s['phase'] not in {'prepared','dispatch_intent','bound','terminal'} or s['actor'] is not None and not uid(s['actor']) or s['anchor'] is not None and (not isinstance(s['anchor'],str) or not HEX40.fullmatch(s['anchor'])):raise AdmissionError('Invalid state fields')
            if b is None and s['binding_sha256'] is not None or b is not None and (set(b)!=BINDING_FIELDS or b['schema_version']!='cochem.student-actions-binding/1' or s['binding_sha256']!=digest(files['binding.json'])):raise AdmissionError('Binding schema/hash differs')
            chain.append((current,files,r,i,s,b));current=parent
        previous=None;anchor=None;used=set();generations=set()
        for commit,files,r,i,s,b in reversed(chain):
            old=previous[4] if previous else None
            new_generation=previous is None or previous[3]['generation']!=i['generation']
            if new_generation:
                if previous and any(i[k]!=previous[3][k] for k in ['repository_id','repository','branch','workflow_id','workflow_path','protocol']):raise AdmissionError('A project ledger cannot change project/workflow identity')
                if previous and old['phase']!='terminal' or s['phase']!='prepared' or s['actor'] is not None or s['anchor'] is not None or b is not None or s['terminal'] is not None or s['stop_requested'] or r['request_id'] in used or i['generation'] in generations:raise AdmissionError('Only a new unique prepared request follows terminal')
                used.add(r['request_id']);generations.add(i['generation']);anchor=None
            else:
                if files['request.json']!=previous[1]['request.json'] or files['intent.json']!=previous[1]['intent.json'] or old['phase']=='terminal' or old['stop_requested'] and not s['stop_requested']:raise AdmissionError('Immutable request/intent/Stop changed')
                old_b=previous[5]
                if old_b is not None and canonical(b)!=canonical(old_b):raise AdmissionError('Run binding cannot change')
                allowed={'prepared':{'dispatch_intent','terminal'},'dispatch_intent':{'dispatch_intent','bound'},'bound':{'bound','terminal'}}
                if s['phase'] not in allowed[old['phase']]:raise AdmissionError('Illegal admission transition')
                if old['phase']=='prepared' and s['phase']=='dispatch_intent':
                    if not uid(s['actor']) or s['anchor'] is not None or b is not None or old['stop_requested']:raise AdmissionError('Invalid dispatch-intent transition')
                    anchor=commit
                elif old['phase']=='prepared':
                    if s['terminal']!={'kind':'withdrawn_before_dispatch'} or not s['stop_requested'] or s['actor'] is not None or b is not None:raise AdmissionError('Invalid before-dispatch terminal')
                else:
                    if s['actor']!=old['actor'] or s['anchor']!=anchor:raise AdmissionError('Dispatch actor/anchor changed')
                    if s['phase']=='dispatch_intent' and (not s['stop_requested'] or old['stop_requested']):raise AdmissionError('Only one Stop transition may retain unbound intent')
                    if s['phase']=='bound' and old['phase']=='bound' and (not s['stop_requested'] or old['stop_requested']):raise AdmissionError('Only one Stop transition may retain binding')
            if s['phase'] in {'prepared','dispatch_intent'} and b is not None:raise AdmissionError('Binding is premature')
            if b is not None:
                expected={'schema_version':'cochem.student-actions-binding/1','generation':i['generation'],'intent_sha256':s['intent_sha256'],'anchor':anchor,**{k:i[k] for k in ['request_id','payload_sha256','repository_id','repository','workflow_id','branch','source_sha','worker_source_sha']},'run_id':b.get('run_id'),'run_attempt':1}
                if canonical(b)!=canonical(expected) or not positive(b['repository_id']) or not positive(b['workflow_id']) or not positive(b['run_id']) or type(b['run_attempt']) is not int:raise AdmissionError('Binding identity differs')
            if s['phase']=='bound' and (b is None or s['terminal'] is not None):raise AdmissionError('Bound state lacks exact target')
            if s['phase']=='terminal' and b is not None:
                t=s['terminal']
                if not isinstance(t,dict) or set(t)!={'kind','run_id','run_attempt','conclusion'} or t!={'kind':'confirmed_run_terminal','run_id':b['run_id'],'run_attempt':1,'conclusion':t['conclusion']} or not isinstance(t['conclusion'],str) or t['conclusion'] not in CONCLUSIONS or type(t['run_id']) is not int or type(t['run_attempt']) is not int:raise AdmissionError('Terminal identity differs')
            if s['phase']!='terminal' and s['terminal'] is not None:raise AdmissionError('Unexpected terminal field')
            previous=(commit,files,r,i,s,b)
        return Snapshot(tip,previous[2],previous[1]['request.json'],previous[3],previous[4],previous[5],anchor)
    def publish(self,old,request,intent,state,binding=None):
        files={'request.json':request,'intent.json':canonical(intent),'state.json':canonical(state)}
        if binding is not None:files['binding.json']=canonical(binding)
        commit=self.commit(files,old.tip if old else None);self.read(commit);self.advance(commit,old.tip if old else None)
        result=self.read()
        if result.tip!=commit:raise Conflict('Publication moved after readback')
        return result
    def prepare(self,raw,*,repository_id,branch,workflow_id):
        r=validate_request(raw);old=self.read()
        if old is not None and old.state['phase']!='terminal':raise AdmissionError('Another request is active or unknown')
        i={'schema_version':'cochem.student-actions-intent/1','protocol':PROTOCOL,'generation':str(uuid.uuid4()),'repository_id':repository_id,'repository':r['repository'],'branch':branch,'workflow_id':workflow_id,'workflow_path':'.github/workflows/student_research.yml','request_id':r['request_id'],'payload_sha256':digest(raw),'request_blob_sha':blob_id(raw),'source_sha':r['source_sha'],'worker_source_sha':r['worker_source_sha']};validate_intent(i,r,raw)
        s={'schema_version':'cochem.student-actions-state/1','generation':i['generation'],'intent_sha256':digest(canonical(i)),'phase':'prepared','previous':old.tip if old else None,'actor':None,'anchor':None,'binding_sha256':None,'stop_requested':False,'terminal':None}
        return self.publish(old,raw,i,s)
    def resume(self, expected):
        snap=self.read();require_expected(snap,expected)
        if snap is None or snap.state['phase']!='prepared':raise AdmissionError('Existing dispatch intent is discovery-only')
        return _Publication(self,snap)
    def transition(self,snap,*,phase=None,binding=None,terminal=None,stop=False):
        if self.tip()!=snap.tip:raise Conflict('State changed; reread without dispatch')
        s={**snap.state,'previous':snap.tip,'anchor':snap.anchor,'phase':phase or snap.state['phase'],'stop_requested':snap.state['stop_requested'] or stop,'terminal':terminal}
        if binding is not None:s['binding_sha256']=digest(canonical(binding))
        return self.publish(snap,snap.raw,snap.intent,s,binding if binding is not None else snap.binding)
    def stop(self,expected):
        snap=self.read();require_expected(snap,expected)
        if snap is None or snap.state['phase']=='terminal':raise AdmissionError('No active request to stop')
        if snap.state['stop_requested']:return snap
        if snap.state['phase']=='prepared':return self.transition(snap,phase='terminal',terminal={'kind':'withdrawn_before_dispatch'},stop=True)
        return self.transition(snap,stop=True)
    def bind(self,transport,expected):
        snap=self.read();require_expected(snap,expected)
        if snap is None or snap.state['phase']!='dispatch_intent':raise AdmissionError('Only unbound dispatch intent may bind')
        runs,complete=transport.discover(snap.intent)
        if not complete or len(runs)!=1:raise AdmissionError('Run discovery ambiguous, missing or truncated; held')
        run=runs[0];validate_run(run,snap.intent)
        b={'schema_version':'cochem.student-actions-binding/1','generation':snap.intent['generation'],'intent_sha256':snap.state['intent_sha256'],'anchor':snap.anchor,**{k:snap.intent[k] for k in ['request_id','payload_sha256','repository_id','repository','workflow_id','branch','source_sha','worker_source_sha']},'run_id':run['id'],'run_attempt':1}
        return self.transition(snap,phase='bound',binding=b)
    def finish(self,transport,expected):
        snap=self.read();require_expected(snap,expected)
        if snap is None or snap.state['phase']!='bound':raise AdmissionError('Unbound/unknown state cannot be automatically released')
        run=transport.observe(snap.intent,snap.binding['run_id']);validate_run(run,snap.intent,terminal=True)
        if run['id']!=snap.binding['run_id']:raise AdmissionError('Terminal run changed')
        return self.transition(snap,phase='terminal',terminal={'kind':'confirmed_run_terminal','run_id':run['id'],'run_attempt':1,'conclusion':run['conclusion']})
    def cancel_bound(self,transport,expected):
        snap=self.read();require_expected(snap,expected)
        if snap is None or not snap.state['stop_requested'] or snap.state['phase']!='bound':raise AdmissionError('Stop waits for its exact bound run')
        run=transport.observe(snap.intent,snap.binding['run_id'])
        if not isinstance(run,dict):raise AdmissionError('Invalid cancellation status response; exact request remains held')
        validate_run(run,snap.intent,terminal=run.get('status')=='completed')
        if run['id']!=snap.binding['run_id']:raise AdmissionError('Cancel run changed')
        if run['status']!='completed':transport.cancel(snap.intent,run['id'])
        return snap

def verify_for_science(snap,*,anchor,request_sha256,run_id,run_attempt,repository_id,repository,workflow_id,branch,source_sha,worker_source_sha,request_id):
    context={'repository_id':repository_id,'repository':repository,'workflow_id':workflow_id,'branch':branch,'source_sha':source_sha,'worker_source_sha':worker_source_sha,'request_id':request_id}
    if not positive(repository_id) or not positive(workflow_id) or snap is None or any(snap.intent[k]!=v for k,v in context.items()):raise AdmissionError('Execution context differs from this project/source/request')
    if snap is None or snap.state['phase']!='bound' or snap.state['stop_requested'] or not positive(run_id) or type(run_attempt) is not int or run_attempt!=1 or anchor!=snap.anchor or request_sha256!=snap.intent['payload_sha256'] or snap.binding['run_id']!=run_id or snap.binding['run_attempt']!=run_attempt:raise AdmissionError('No exact active run/attempt binding; no protected operation')
    return {'request_id':snap.intent['request_id'],'run_id':run_id,'run_attempt':1,'anchor':anchor}

class _Publication:
    def __init__(self,store,snapshot):self.store=store;self.snapshot=snapshot;self.actor=str(uuid.uuid4());self.pid=os.getpid();self._confirmed=False;self._taken=False;self._lock=threading.Lock();self.commit=None
    def propose(self):
        if os.getpid()!=self.pid:raise AdmissionError('Publication owner cannot cross processes')
        if self.commit is None:
            s={**self.snapshot.state,'phase':'dispatch_intent','previous':self.snapshot.tip,'actor':self.actor}
            self.commit=self.store.commit({'request.json':self.snapshot.raw,'intent.json':canonical(self.snapshot.intent),'state.json':canonical(s)},self.snapshot.tip)
        self.store.read(self.commit)
        return self.commit
    def publish(self):
        commit=self.propose();
        try:
            self.store.advance(commit, self.snapshot.tip)
        except TransportError as error:
            if not error.uncertain:
                raise
            # Only this same live operation can resolve its own pre-POST write.
            return self.resolve_own_publication()
        return self.resolve_own_publication()
    def resolve_own_publication(self):
        if os.getpid()!=self.pid or self._taken or self.commit is None:raise AdmissionError('Not a live pre-POST publication owner')
        snap=self.store.read()
        if snap.tip!=self.commit or snap.anchor!=self.commit or snap.state['actor']!=self.actor or snap.state['phase']!='dispatch_intent' or snap.state['stop_requested']:raise AdmissionError('Only the live winning publisher may POST')
        self._confirmed=True;return self
    def post(self,transport):
        with self._lock:
            if os.getpid()!=self.pid or not self._confirmed or self._taken:raise AdmissionError('One-shot POST ownership unavailable')
            snap=self.store.read()
            if snap.tip!=self.commit or snap.state['phase']!='dispatch_intent' or snap.state['actor']!=self.actor or snap.state['stop_requested']:raise AdmissionError('Claim changed before POST')
            self._taken=True
        return transport.dispatch(snap)



def parse_descriptor(raw):
    value = strict(raw)
    if (set(value) != {"schema_version", "protocol", "ledger_ref", "workflow_path", "required_files"}
            or value["schema_version"] != CAPABILITY_SCHEMA or value["protocol"] != PROTOCOL
            or value["ledger_ref"] != LEDGER_REF
            or value["workflow_path"] != ".github/workflows/student_research.yml"
            or not isinstance(value["required_files"], dict)
            or set(value["required_files"]) != REQUIRED_PATHS
            or any(not isinstance(v, str) or not HEX64.fullmatch(v) for v in value["required_files"].values())):
        raise AdmissionError("Unsupported reviewed research admission capability")
    return value
