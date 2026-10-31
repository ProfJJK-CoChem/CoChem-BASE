"""Real local Git/OS/HTTP engineering; no hosted GitHub or scientific acceptance."""
from pathlib import Path
import base64
from copy import deepcopy
import hashlib
import http.server
import json
import os
import runpy
import socket
import subprocess
import sys
import tempfile
import tarfile
import threading
import time
import types
import unittest
import urllib.parse

ROOT=Path(__file__).resolve().parents[2]
from ci_tools.source_quarantine import source_paths
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    quarantine=sys.modules.get('ci_tools.source_quarantine')
    assert quarantine is not None and Path(quarantine.__file__).resolve()==ROOT/'ci_tools/source_quarantine.py'
    state=getattr(quarantine,'_active',None)
    assert state is not None and state['copied']==ROOT
    assert state['original']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_ORIGINAL']).resolve()
    assert state['evidence']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_EVIDENCE']).resolve()
    assert state['revision']==os.environ['COCHEM_SOURCE_QUARANTINE_REVISION']
    startup=sys.modules.get('sitecustomize')
    if startup is not None:
        assert Path(startup.__file__).resolve()==ROOT/'ci_tools/quarantine_startup/sitecustomize.py'
    else:
        # Canonical run_profile uses -I and explicitly activates the same guard.
        # Tests never activate/replace it or admit an unguarded application import.
        assert sys.flags.isolated==1 and sys.flags.ignore_environment==1
    assert not quarantine.loaded_origins(state)['escaped']
from cochem_base.interfaces import student_actions_admission as production
from cochem_base.interfaces import student_actions_admission_git as hosted
from cochem_base.interfaces.student_actions import StudentActionsClient
assert Path(production.__file__).resolve()==ROOT/'src/cochem_base/interfaces/student_actions_admission.py'
assert Path(hosted.__file__).resolve()==ROOT/'src/cochem_base/interfaces/student_actions_admission_git.py'
assert Path(sys.modules[StudentActionsClient.__module__].__file__).resolve()==ROOT/'src/cochem_base/interfaces/student_actions.py'
def child_env():
    return dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join(source_paths(ROOT)))
h=types.SimpleNamespace(**vars(production))
AdmissionError,Conflict,blob_id=h.AdmissionError,h.Conflict,h.blob_id
class LocalGitBackend:
    """Real LOCAL Git expected-parent CAS. Never equated with hosted ref semantics."""
    ref='refs/heads/cochem-student-admission-v1'
    def __init__(self,path):self.path=Path(path).resolve()
    def git(self,*args,data=None,allowed=(0,)):
        env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull,GIT_CONFIG_NOSYSTEM='1',GIT_NO_REPLACE_OBJECTS='1',GIT_NO_LAZY_FETCH='1',GIT_TERMINAL_PROMPT='0',GIT_AUTHOR_NAME='Engineering record',GIT_AUTHOR_EMAIL='record@example.invalid',GIT_COMMITTER_NAME='Engineering record',GIT_COMMITTER_EMAIL='record@example.invalid')
        p=subprocess.run(['git','--git-dir',str(self.path),'-c','core.hooksPath='+os.devnull,*args],input=data,capture_output=True,env=env,timeout=10)
        if p.returncode not in allowed:raise AdmissionError('Local Git refused '+args[0])
        return p.returncode,p.stdout
    @classmethod
    def create(cls,path):
        p=Path(path);p.mkdir();subprocess.run(['git','init','--bare',str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=10,env={**os.environ,'GIT_CONFIG_GLOBAL':os.devnull,'GIT_CONFIG_SYSTEM':os.devnull});return cls(p)
    def tip(self):
        code,raw=self.git('rev-parse','--verify',self.ref,allowed=(0,128))
        return raw.decode().strip() if code==0 else None
    def commit(self,files,parent):
        entries=[]
        for name,raw in sorted(files.items()):
            _,oid=self.git('hash-object','-w','--stdin',data=raw);oid=oid.strip().decode()
            if oid!=blob_id(raw):raise AdmissionError('Local Git changed a blob')
            entries.append(('100644 blob '+oid+'\t'+name+'\0').encode())
        _,tree=self.git('mktree','-z',data=b''.join(entries));args=['commit-tree',tree.strip().decode()]
        if parent is not None:args+=['-p',parent]
        _,commit=self.git(*args,data=b'Engineering admission data only\n');return commit.strip().decode()
    def advance(self,commit,parent):
        code,_=self.git('update-ref',self.ref,commit,parent or '0'*40,allowed=(0,128))
        if code:raise Conflict('Another append-only writer won; discovery only')
        if self.tip()!=commit:raise Conflict('Admission publication readback changed; discovery only')
    def files(self,commit):
        _,parents=self.git('rev-list','--parents','-n','1',commit);parents=parents.decode().split()[1:]
        if len(parents)>1:raise AdmissionError('Admission commits cannot merge')
        _,tree=self.git('ls-tree','-z',commit);files={}
        for entry in tree.split(b'\0'):
            if not entry:continue
            meta,name=entry.split(b'\t');mode,kind,oid=meta.decode().split();name=name.decode()
            if mode!='100644' or kind!='blob' or name not in {'request.json','intent.json','state.json','binding.json'}:raise AdmissionError('Unexpected ledger tree member')
            _,size=self.git('cat-file','-s',oid)
            if int(size)>65536:raise AdmissionError('Ledger member too large')
            _,files[name]=self.git('cat-file','blob',oid)
        if not {'request.json','intent.json','state.json'}<=set(files):raise AdmissionError('Incomplete ledger tree')
        return files,parents[0] if parents else None

class GitStore(production.AdmissionStore):
    """Fixture-only actual Git CAS, not a hosted guarantee."""
    def __init__(self,path):
        backend=LocalGitBackend(path)
        super().__init__(backend)
        self.path,self.ref=backend.path,backend.ref
    @classmethod
    def create(cls,path):
        LocalGitBackend.create(path)
        return cls(path)
    def git(self,*args,**kwargs):return self.backend.git(*args,**kwargs)

class ActionsTransport(hosted.ActionsAdmissionTransport):
    def __init__(self,url,*,allow_loopback=False):
        super().__init__(StudentActionsClient('engineering/private-project',token='engineering-only-token',
            api_url=url,allow_loopback=allow_loopback))
    def _request(self,path,*,method='GET',body=None):
        return hosted._call(self.client,path,method=method,body=body)

h.GitStore,h.ActionsTransport=GitStore,ActionsTransport

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):self.server.access.append(fmt%args)
    def reply(self,value,status=200):
        raw=h.canonical(value);self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def drop(self):
        self.connection.shutdown(socket.SHUT_RDWR);self.connection.close()
    def do_GET(self):
        peer=self.server;path=urllib.parse.urlsplit(self.path);peer.gets.append(self.path)
        if path.path == '/engineering/slow-metadata':
            raw=h.canonical({'engineering_metadata_only':True})
            self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            for offset in range(0,len(raw),2):
                self.wfile.write(raw[offset:offset+2]);self.wfile.flush();time.sleep(.025)
            return
        if '/workflows/' in path.path and path.path.endswith('/runs'):
            page=int(urllib.parse.parse_qs(path.query)['page'][0]);self.reply({'total_count':len(peer.runs)+(peer.listing_extra if page>=peer.listing_change_page else 0),'workflow_runs':peer.runs[(page-1)*100:page*100]});return
        if '/actions/runs/' in path.path:
            wanted=int(path.path.rsplit('/',1)[-1])
            if peer.observation_override is not None:self.reply(peer.observation_override);return
            matches=[r for r in peer.runs if r['id']==wanted]
            self.reply(matches[0] if len(matches)==1 else {},200 if len(matches)==1 else 404);return
        self.reply({'error':'engineering route not found'},404)
    def do_POST(self):
        peer=self.server;raw=self.rfile.read(int(self.headers.get('Content-Length','0')));body=json.loads(raw) if raw else {}
        if self.path=='/engineering/advance':
            try:peer.store.advance(body['commit'],body['parent'])
            except h.Conflict:self.reply({'error':'actual local Git sibling lost'},409);return
            peer.ref_updates.append(body)
            if peer.drop_ref_ack:self.drop();return
            self.reply({});return
        if self.path=='/engineering/protected':peer.protected.append(body);self.reply({});return
        if self.path.endswith('/cancel'):
            peer.cancels.append(int(self.path.split('/')[-2]));self.reply({},202);return
        if self.path.endswith('/dispatches'):
            inputs=body['inputs'];request=base64.b64decode(inputs['request_base64'],validate=True)
            if h.digest(request)!=inputs['request_sha256']:self.reply({'error':'bad hash'},422);return
            r=h.validate_request(request)
            with peer.lock:
                peer.posts.append(body);number=100+len(peer.posts)
                peer.runs.append({'id':number,'run_attempt':1,'repository':{'id':peer.repository_id,'full_name':r['repository']},'workflow_id':peer.workflow_id,'head_sha':r['source_sha'],'head_branch':body['ref'],'event':'workflow_dispatch','display_title':'CoChem student '+r['request_id'],'status':'queued','conclusion':None})
            if peer.drop_dispatch_ack:self.drop();return
            self.reply({});return
        self.reply({'error':'engineering route not found'},404)


class GitHandler(Handler):
    """Real local Git object store behind loopback API-shaped messages.

    This is engineering transport behavior, not a hosted nonforce acceptance.
    """
    def do_GET(self):
        prefix='/repos/'+self.server.repository+'/git/'
        if not self.path.startswith(prefix):return super().do_GET()
        self.server.gets.append(self.path)
        part=self.path[len(prefix):];git=self.server.store.backend
        if part=='ref/heads/cochem-student-admission-v1':
            tip=git.tip()
            if tip is None:self.reply({'error':'absent'},404);return
            self.reply({'ref':h.LEDGER_REF,'object':{'type':'commit','sha':tip}});return
        kind,sha=part.split('/',1)
        if kind=='commits':
            _,raw=git.git('cat-file','commit',sha);headers=raw.split(b'\n\n',1)[0].decode().splitlines()
            tree=next(x.split()[1] for x in headers if x.startswith('tree '))
            parents=[{'sha':x.split()[1]} for x in headers if x.startswith('parent ')]
            self.reply({'sha':sha,'tree':{'sha':tree},'parents':parents});return
        if kind=='trees':
            _,raw=git.git('ls-tree','-z',sha);entries=[]
            for item in raw.split(b'\0'):
                if not item:continue
                meta,name=item.split(b'\t');mode,kind,oid=meta.decode().split()
                entries.append({'path':name.decode(),'mode':mode,'type':kind,'sha':oid})
            self.reply({'sha':sha,'truncated':False,'tree':entries});return
        if kind=='blobs':
            _,raw=git.git('cat-file','blob',sha)
            self.reply({'sha':sha,'size':len(raw),'encoding':'base64','content':base64.b64encode(raw).decode()});return
        self.reply({'error':'unsupported engineering Git route'},404)
    def do_POST(self):
        prefix='/repos/'+self.server.repository+'/git/'
        if not self.path.startswith(prefix):return super().do_POST()
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')));body=json.loads(raw)
        part=self.path[len(prefix):];git=self.server.store.backend
        self.server.git_writes.append({'method':'POST','path':self.path,'body':body})
        if part=='blobs':
            assert set(body)=={'content','encoding'} and body['encoding']=='base64'
            _,sha=git.git('hash-object','-w','--stdin',data=base64.b64decode(body['content'],validate=True))
            self.reply({'sha':sha.strip().decode()});return
        if part=='trees':
            assert set(body)=={'tree'}
            entries=[(entry['mode']+' '+entry['type']+' '+entry['sha']+'\t'+entry['path']+'\0').encode() for entry in body['tree']]
            _,sha=git.git('mktree','-z',data=b''.join(entries));self.reply({'sha':sha.strip().decode()});return
        if part=='commits':
            assert set(body)=={'message','tree','parents'}
            args=['commit-tree',body['tree']]
            for parent in body['parents']:args+=['-p',parent]
            _,sha=git.git(*args,data=body['message'].encode());self.reply({'sha':sha.strip().decode()});return
        if part=='refs':
            assert body['ref']==h.LEDGER_REF and set(body)=={'ref','sha'}
            code,unused=git.git('update-ref',h.LEDGER_REF,body['sha'],'0'*40,allowed=(0,128))
            if code:self.reply({'error':'already exists'},422);return
            if self.server.drop_create_ack:self.drop();return
            self.reply({'ref':h.LEDGER_REF,'object':{'type':'commit','sha':body['sha']}});return
        self.reply({'error':'unsupported engineering Git write'},404)
    def do_PATCH(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')));body=json.loads(raw)
        return self._patch_body(body)
    def _patch_body(self,body):
        assert self.path=='/repos/'+self.server.repository+'/git/refs/heads/cochem-student-admission-v1'
        assert set(body)=={'sha','force'} and body['force'] is False
        self.server.git_writes.append({'method':'PATCH','path':self.path,'body':body})
        git=self.server.store.backend;old=git.tip()
        code,unused=git.git('merge-base','--is-ancestor',old,body['sha'],allowed=(0,1))
        if code:self.reply({'error':'nonfastforward'},422);return
        git.advance(body['sha'],old)
        if self.server.drop_patch_ack:self.drop();return
        self.reply({'ref':h.LEDGER_REF,'object':{'type':'commit','sha':body['sha']}})


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='admission-engineering-');self.root=Path(self.temp.name);self.store=h.GitStore.create(self.root/'ledger.git')
        self.source=self.store.commit({'engineering-source.txt':b'Identity fixture only, not program approval'},None)
        self.worker=self.store.commit({'engineering-worker.txt':b'Identity fixture only, no scientific routine'},None)
        self.request={'schema_version':'cochem.student-request/1','request_id':'6a1e38de-0c02-4727-824d-23d8978cfa39','repository':'engineering/private-project','source_sha':self.source,'worker_source_sha':self.worker,'submitted_at':'2026-10-31T00:00:00+00:00','resources':{'cores':1,'maxcore_mb':128},'calculation':{'unexecuted_engineering_payload':{'charge':0,'multiplicity':1,'method':'retained opaque request, not chemistry acceptance'}},'provider':None,'capability_probe':None,'scientific_inputs':None,'data_inputs':None,'t9_request':None,'files':{}}
        self.peer=http.server.ThreadingHTTPServer(('127.0.0.1',0),GitHandler);self.peer.daemon_threads=True
        self.peer.posts=[];self.peer.runs=[];self.peer.gets=[];self.peer.access=[];self.peer.protected=[];self.peer.cancels=[];self.peer.ref_updates=[];self.peer.lock=threading.Lock();self.peer.store=self.store;self.peer.repository='engineering/private-project';self.peer.repository_id=17;self.peer.workflow_id=37;self.peer.drop_ref_ack=False;self.peer.drop_dispatch_ack=False;self.peer.observation_override=None;self.peer.git_writes=[];self.peer.drop_create_ack=False;self.peer.drop_patch_ack=False;self.peer.listing_extra=0;self.peer.listing_change_page=1
        self.thread=threading.Thread(target=self.peer.serve_forever,daemon=True);self.thread.start();self.url=f'http://127.0.0.1:{self.peer.server_port}';self.transport=h.ActionsTransport(self.url,allow_loopback=True);self.children=[]
    def tearDown(self):
        for child in self.children:
            if child.poll() is None:child.terminate()
            child.communicate(timeout=10)
        self.peer.shutdown();self.peer.server_close();self.thread.join(timeout=3)
        evidence=os.environ.get('ADMISSION_ENGINEERING_EVIDENCE')
        if evidence:
            out=Path(evidence);out.mkdir(exist_ok=True,parents=True)
            record={'scope':'Actual loopback HTTP records and local Git fixture; all run/project IDs are engineering records, not GitHub service evidence','test':self._testMethodName,'dispatch_bodies':self.peer.posts,'runs':self.peer.runs,'gets':self.peer.gets,'access':self.peer.access,'engineering_protected_markers':self.peer.protected,'cancels':self.peer.cancels,'ref_updates':self.peer.ref_updates,'git_writes':self.peer.git_writes,'child_terminal_returncodes':[c.returncode for c in self.children],'source_sha256':hashlib.sha256(Path(production.__file__).read_bytes()).hexdigest(),'fixture_removed_after_capture':True}
            (out/(self._testMethodName+'.json')).write_text(json.dumps(record,indent=2)+'\n')
            if self._testMethodName in {'test_simultaneous_real_process_resumes_have_one_winner_one_post','test_terminal_exact_attempt_preserves_receipt_and_allows_new_UUID'}:
                with tarfile.open(out/(self._testMethodName+'.tar.gz'),'w:gz') as archive:archive.add(self.store.path,arcname='engineering-local-ledger.git')
        self.temp.cleanup()
    def prepare(self,request=None):return self.store.prepare(h.canonical(request or self.request),repository_id=17,branch='main',workflow_id=37)
    def dispatch(self):
        self.prepare();owner=self.store.resume(h.identity(self.store.read())).publish();owner.post(self.transport);return owner
    def bind(self):self.dispatch();return self.store.bind(self.transport,h.identity(self.store.read()))
    def protect(self,run_id,attempt=1,anchor=None):
        snap=self.store.read();receipt=h.verify_for_science(snap,anchor=anchor or snap.anchor,request_sha256=snap.intent['payload_sha256'],run_id=run_id,run_attempt=attempt,repository_id=17,repository=self.request['repository'],workflow_id=37,branch='main',source_sha=self.source,worker_source_sha=self.worker,request_id=self.request['request_id'])
        self.transport._request('/engineering/protected',method='POST',body=receipt)
    def corrupt(self,transform):
        old=self.store.read();files,parent=self.store.files(old.tip);transform(files)
        commit=self.store.commit(files,old.tip);self.store.advance(commit,old.tip)
    def hosted_store(self,read_only=False):
        return production.AdmissionStore(hosted.GitAdmissionBackend(self.transport.client,'engineering/private-project',read_only=read_only))
    def test_hosted_adapter_actual_git_objects_orphan_and_nonforce_transitions(self):
        store=self.hosted_store();prepared=store.prepare(h.canonical(self.request),repository_id=17,branch='main',workflow_id=37)
        files,parent=self.store.files(prepared.tip);self.assertIsNone(parent);self.assertEqual(files['request.json'],h.canonical(self.request))
        owner=store.resume(h.identity(store.read())).publish();owner.post(self.transport);bound=store.bind(self.transport,h.identity(store.read()))
        self.assertEqual(bound.binding['run_id'],101);self.assertEqual(len(self.peer.posts),1)
        self.assertTrue(any(row['method']=='PATCH' for row in self.peer.git_writes))
        self.assertTrue(all(row['body'].get('force') is False for row in self.peer.git_writes if row['method']=='PATCH'))
        self.assertFalse(any('base_tree' in row['body'] for row in self.peer.git_writes))
    def test_hosted_create_ref_lost_ack_holds_prepared_without_dispatch(self):
        self.peer.drop_create_ack=True;store=self.hosted_store()
        with self.assertRaises(h.TransportError) as error:store.prepare(h.canonical(self.request),repository_id=17,branch='main',workflow_id=37)
        self.assertTrue(error.exception.uncertain);self.assertEqual(store.read().state['phase'],'prepared');self.assertEqual(self.peer.posts,[])
        self.assertEqual(len([row for row in self.peer.git_writes if row['path'].endswith('/refs')]),1)
    def test_hosted_lost_patch_ack_only_live_owner_can_resolve_and_post_once(self):
        store=self.hosted_store();store.prepare(h.canonical(self.request),repository_id=17,branch='main',workflow_id=37)
        self.peer.drop_patch_ack=True;owner=store.resume(h.identity(store.read())).publish();owner.post(self.transport)
        self.assertEqual(len(self.peer.posts),1)
        with self.assertRaises(h.AdmissionError):store.resume(h.identity(store.read()))
        with self.assertRaises(h.AdmissionError):owner.post(self.transport)
    def test_workflow_backend_read_only_refuses_all_mutation_without_http(self):
        store=self.hosted_store(read_only=True)
        with self.assertRaises(h.AdmissionError):store.prepare(h.canonical(self.request),repository_id=17,branch='main',workflow_id=37)
        self.assertEqual(self.peer.git_writes,[]);self.assertEqual(self.peer.posts,[])
    def test_hosted_observed_ref_rewind_is_refused(self):
        store=self.hosted_store();prepared=store.prepare(h.canonical(self.request),repository_id=17,branch='main',workflow_id=37)
        store.resume(h.identity(store.read())).publish();self.store.git('update-ref',self.store.ref,prepared.tip)
        with self.assertRaisesRegex(h.AdmissionError,'replaced or rewound'):store.read()
        self.assertEqual(self.peer.posts,[])
    def test_stale_request_scope_cannot_resume_stop_bind_finish_or_cancel_new_request(self):
        first=self.prepare();expected=h.identity(first)
        self.store.stop(expected)
        other=deepcopy(self.request);other['request_id']='ac72d7ea-3c83-425e-9163-e5d5b15d0af2'
        second=self.prepare(other);before=second.tip
        for operation in (lambda:self.store.resume(expected),lambda:self.store.stop(expected),
                          lambda:self.store.bind(self.transport,expected),lambda:self.store.finish(self.transport,expected),
                          lambda:self.store.cancel_bound(self.transport,expected)):
            with self.assertRaisesRegex(h.AdmissionError,'captured project request changed'):operation()
            self.assertEqual(self.store.tip(),before)
        self.assertEqual(self.peer.posts,[]);self.assertEqual(self.peer.cancels,[])
    def test_reused_generation_uuid_in_real_git_history_is_refused(self):
        first=self.prepare();self.store.stop(h.identity(first))
        other=deepcopy(self.request);other['request_id']='ac72d7ea-3c83-425e-9163-e5d5b15d0af2'
        second=self.prepare(other);self.store.stop(h.identity(second))
        third_request=deepcopy(other);third_request['request_id']='deec352b-e947-405d-9a20-4bf31d895eba'
        third=self.prepare(third_request);files,parent=self.store.files(third.tip)
        intent=h.strict(files['intent.json']);intent['generation']=first.intent['generation'];files['intent.json']=h.canonical(intent)
        state=h.strict(files['state.json']);state['generation']=intent['generation'];state['intent_sha256']=h.digest(files['intent.json']);files['state.json']=h.canonical(state)
        corrupt=self.store.commit(files,parent);self.store.git('update-ref',self.store.ref,corrupt,third.tip)
        with self.assertRaises(h.AdmissionError):self.store.read()
        self.assertEqual(self.peer.posts,[])
    def test_short_page_total_count_inconsistent_is_not_unique_discovery(self):
        self.dispatch();self.peer.listing_extra=1
        with self.assertRaisesRegex(h.AdmissionError,'inconsistent'):self.store.bind(self.transport,h.identity(self.store.read()))
        self.assertEqual(self.store.read().state['phase'],'dispatch_intent');self.assertEqual(self.peer.protected,[])
    def test_moving_pagination_count_is_held(self):
        self.dispatch();base=deepcopy(self.peer.runs[0]);self.peer.runs += [{**base,'id':200+n,'display_title':'unrelated '+str(n)} for n in range(100)]
        self.peer.listing_extra=1;self.peer.listing_change_page=2
        with self.assertRaisesRegex(h.AdmissionError,'changed'):self.store.bind(self.transport,h.identity(self.store.read()))
        self.assertEqual(self.store.read().state['phase'],'dispatch_intent');self.assertEqual(self.peer.protected,[])
    def test_read_only_deadline_rejects_bool_nonfinite_and_write_without_http(self):
        for value in (True,False,float('nan'),float('inf'),-float('inf')):
            with self.subTest(value=value),self.assertRaises(h.AdmissionError):hosted.ReadOnlyAPI('engineering-token',deadline=value)
        api=hosted.ReadOnlyAPI('engineering-token',deadline=time.time()+5,api_url=self.url,allow_loopback=True)
        with self.assertRaises(h.AdmissionError):api._request('/engineering/protected',method='POST',body={})
        self.assertEqual(self.peer.protected,[]);self.assertEqual(self.peer.gets,[])
    def test_real_trickled_http_body_cannot_return_after_inherited_deadline(self):
        start=time.time();api=hosted.ReadOnlyAPI('engineering-token',deadline=start+.15,api_url=self.url,allow_loopback=True)
        with self.assertRaisesRegex(h.AdmissionError,'budget expired'):api._request('/engineering/slow-metadata')
        elapsed=time.time()-start
        self.assertGreater(elapsed,.15);self.assertLess(elapsed,3)
        self.assertEqual(self.peer.protected,[]);self.assertEqual(self.peer.posts,[])
    def test_exact_transport_original_bytes_and_noncircular_anchor(self):
        prepared=self.prepare();owner=self.store.resume(h.identity(self.store.read())).publish();snap=self.store.read()
        self.assertNotEqual(owner.commit,self.source);self.assertEqual(snap.raw,h.canonical(self.request));self.assertIsNone(snap.state['anchor']);self.assertEqual(snap.anchor,owner.commit)
        owner.post(self.transport);body=self.peer.posts[0];self.assertEqual(set(body['inputs']),{'request_id','request_sha256','request_base64','admission_anchor'});self.assertEqual(body['inputs']['admission_anchor'],owner.commit)
        self.assertEqual(base64.b64decode(body['inputs']['request_base64']),snap.raw);self.assertNotIn('admission_anchor',self.request);self.assertEqual(prepared.intent['request_blob_sha'],h.blob_id(snap.raw))
    def test_same_project_one_active_request_and_independent_project_stores(self):
        self.prepare();other=deepcopy(self.request);other['request_id']='ac72d7ea-3c83-425e-9163-e5d5b15d0af2'
        with self.assertRaises(h.AdmissionError):self.prepare(other)
        second=h.GitStore.create(self.root/'other-project.git');other['repository']='engineering/other-project';snap=second.prepare(h.canonical(other),repository_id=18,branch='main',workflow_id=38);self.assertEqual(snap.intent['repository_id'],18)
    def test_restarted_process_cannot_resume_any_existing_intent(self):
        owner=self.dispatch();snapshot=self.store.read();saved={'actor':snapshot.state['actor'],'anchor':snapshot.anchor,'request':snapshot.request};(self.root/'saved.json').write_bytes(h.canonical(saved))
        code="import runpy,types,sys; h=runpy.run_path(sys.argv[1],run_name='admission_fixture')['h']; s=h.GitStore(sys.argv[2]); s.resume(h.identity(s.read()))"
        p=subprocess.run([sys.executable,'-B','-c',code,str(Path(__file__)),str(self.store.path)],capture_output=True,timeout=10,env=child_env())
        self.assertNotEqual(p.returncode,0);self.assertIn(b'discovery-only',p.stderr);self.assertEqual(len(self.peer.posts),1)
        with self.assertRaises(h.AdmissionError):owner.post(self.transport)
    def test_real_lost_dispatch_ack_consumes_one_post_and_then_discovers(self):
        self.prepare();owner=self.store.resume(h.identity(self.store.read())).publish();self.peer.drop_dispatch_ack=True
        with self.assertRaises(h.TransportError) as caught:owner.post(self.transport)
        self.assertTrue(caught.exception.uncertain)
        with self.assertRaises(h.AdmissionError):owner.post(self.transport)
        snap=self.store.bind(self.transport,h.identity(self.store.read()));self.assertEqual(snap.binding['run_id'],101);self.assertEqual(len(self.peer.posts),1)
    def test_live_owner_resolves_real_lost_ref_ack_before_sole_post(self):
        self.prepare();owner=self.store.resume(h.identity(self.store.read()));commit=owner.propose();self.peer.drop_ref_ack=True
        with self.assertRaises(h.TransportError):self.transport._request('/engineering/advance',method='POST',body={'commit':commit,'parent':owner.snapshot.tip})
        self.assertEqual(len(self.peer.ref_updates),1);self.assertEqual(self.store.tip(),commit)
        owner.resolve_own_publication().post(self.transport)
        with self.assertRaises(h.AdmissionError):owner.post(self.transport)
        self.assertEqual(len(self.peer.posts),1)
    def test_simultaneous_real_process_resumes_have_one_winner_one_post(self):
        self.prepare();release=self.root/'release'
        program='''import pathlib,runpy,types,sys,time,json,os
source,repo,url,ready,release=sys.argv[1:];h=runpy.run_path(source,run_name='admission_fixture')['h'];s=h.GitStore(repo);p=s.resume(h.identity(s.read()));c=p.propose();pathlib.Path(ready).write_text(json.dumps({'actor':p.actor,'commit':c,'pid':os.getpid(),'source':h.GitStore.read.__code__.co_filename}));deadline=time.monotonic()+10
while not pathlib.Path(release).exists() and time.monotonic()<deadline:time.sleep(.01)
if not pathlib.Path(release).exists():raise RuntimeError('bounded OS barrier expired')
try:p.publish().post(h.ActionsTransport(url,allow_loopback=True))
except h.AdmissionError as e:print(e);raise SystemExit(2)
print('one local publication and HTTP dispatch');raise SystemExit(0)
'''
        for n in range(2):
            child=subprocess.Popen([sys.executable,'-B','-c',program,str(Path(__file__)),str(self.store.path),self.url,str(self.root/f'ready-{n}'),str(release)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=child_env());self.children.append(child)
        deadline=time.monotonic()+10
        while not all((self.root/f'ready-{n}').exists() for n in range(2)) and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(all((self.root/f'ready-{n}').exists() for n in range(2)))
        ready=[json.loads((self.root/f'ready-{n}').read_text()) for n in range(2)];self.assertNotEqual(ready[0]['actor'],ready[1]['actor']);self.assertNotEqual(ready[0]['commit'],ready[1]['commit']);release.touch()
        outputs=[]
        for n,child in enumerate(self.children):
            stdout,stderr=child.communicate(timeout=15);outputs.append(child.returncode);self.assertIn(child.returncode,[0,2],stdout+stderr)
        self.assertEqual(sorted(outputs),[0,2]);self.assertEqual(len(self.peer.posts),1);self.assertEqual(self.store.read().anchor,self.peer.posts[0]['inputs']['admission_anchor'])
    def test_one_live_owner_gate_is_thread_safe(self):
        self.prepare();owner=self.store.resume(h.identity(self.store.read())).publish();results=[]
        def consume():
            try:owner.post(self.transport);results.append('posted')
            except h.AdmissionError:results.append('refused')
        threads=[threading.Thread(target=consume) for _ in range(4)]
        for t in threads:t.start()
        for t in threads:t.join(timeout=10)
        self.assertEqual(results.count('posted'),1);self.assertEqual(results.count('refused'),3);self.assertEqual(len(self.peer.posts),1)
    def test_real_process_crash_after_C_before_POST_remains_held(self):
        self.prepare();witness=self.root/'pre-crash-source.json';child_evidence=self.root/'expected-crash-source-evidence'
        child_evidence.mkdir(mode=0o700)
        crash_environment=child_env();crash_environment['COCHEM_SOURCE_QUARANTINE_EVIDENCE']=str(child_evidence)
        self.assertNotEqual(child_evidence,Path(os.environ['COCHEM_SOURCE_QUARANTINE_EVIDENCE']))
        self.assertEqual(list(child_evidence.iterdir()),[])
        relative_sources=('tests/base/test_student_actions_admission.py','ci_tools/source_quarantine.py',
            'src/cochem_base/interfaces/student_actions_admission.py',
            'src/cochem_base/interfaces/student_actions_admission_git.py',
            'src/cochem_base/interfaces/student_actions.py')
        source_before={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in relative_sources}
        program='''import runpy,sys,os,json,hashlib
from pathlib import Path
fixture=runpy.run_path(sys.argv[1],run_name='admission_fixture');h=fixture['h'];root=fixture['ROOT']
guard=sys.modules['ci_tools.source_quarantine'];state=guard._active
assert state is not None and state['copied']==root
assert state['original']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_ORIGINAL']).resolve()
assert state['evidence']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_EVIDENCE']).resolve()
assert state['revision']==os.environ['COCHEM_SOURCE_QUARANTINE_REVISION']
assert Path(guard.__file__).resolve()==root/'ci_tools/source_quarantine.py'
s=h.GitStore(sys.argv[2]);s.resume(h.identity(s.read())).publish()
loaded=guard.loaded_origins(state);assert not loaded['escaped']
modules={name:sys.modules[name].__file__ for name in ('ci_tools.source_quarantine',
    'cochem_base.interfaces.student_actions_admission','cochem_base.interfaces.student_actions_admission_git',
    'cochem_base.interfaces.student_actions')}
sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in json.loads(sys.argv[4])}
record={'scope':'PRE-CRASH active source observation; NOT a finalizer receipt','pid':os.getpid(),'parent_pid':os.getppid(),
    'copied':str(state['copied']),'original':str(state['original']),'evidence':str(state['evidence']),
    'revision':state['revision'],'loaded_origins':loaded,'modules':modules,'source_sha256':sources}
fd=os.open(sys.argv[3],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as stream:json.dump(record,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
os._exit(77)
'''
        p=subprocess.Popen([sys.executable,'-B','-c',program,str(Path(__file__)),str(self.store.path),str(witness),json.dumps(relative_sources)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=crash_environment)
        self.children.append(p)
        try:stdout,stderr=p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill();p.communicate(timeout=10);raise
        self.assertEqual(p.returncode,77,stdout+stderr)
        raw=witness.read_bytes();observed=json.loads(raw)
        self.assertEqual(observed['scope'],'PRE-CRASH active source observation; NOT a finalizer receipt')
        self.assertEqual(observed['pid'],p.pid);self.assertEqual(observed['parent_pid'],os.getpid())
        self.assertEqual(observed['copied'],str(ROOT))
        for key,variable in (('original','COCHEM_SOURCE_QUARANTINE_ORIGINAL'),('revision','COCHEM_SOURCE_QUARANTINE_REVISION')):
            self.assertEqual(observed[key],os.environ[variable])
        self.assertEqual(observed['evidence'],str(child_evidence))
        initial_files=list(child_evidence.glob('*-initial.json'))
        self.assertEqual(len(initial_files),1);self.assertEqual(list(child_evidence.glob('*-final.json')),[])
        self.assertEqual({path.name for path in child_evidence.iterdir()},{initial_files[0].name})
        initial_raw=initial_files[0].read_bytes();initial=json.loads(initial_raw)
        self.assertEqual(initial['pid'],p.pid);self.assertEqual(initial['parent_pid'],os.getpid())
        self.assertIs(initial['passed'],True);self.assertEqual(initial['stage'],'initial')
        self.assertEqual(initial['source_root'],str(ROOT));self.assertEqual(initial['original_root'],observed['original'])
        self.assertEqual(initial['source_revision'],observed['revision'])
        self.assertEqual(initial['startup_source_sha256'],source_before['ci_tools/source_quarantine.py'])
        self.assertEqual(observed['loaded_origins']['escaped'],[])
        for module,relative in (('ci_tools.source_quarantine','ci_tools/source_quarantine.py'),
                ('cochem_base.interfaces.student_actions_admission',relative_sources[2]),
                ('cochem_base.interfaces.student_actions_admission_git',relative_sources[3]),
                ('cochem_base.interfaces.student_actions',relative_sources[4])):
            self.assertEqual(Path(observed['modules'][module]).resolve(),ROOT/relative)
            self.assertIn(observed['modules'][module],observed['loaded_origins']['origins'][module])
        self.assertEqual(observed['source_sha256'],source_before)
        self.assertEqual({name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in relative_sources},source_before)
        evidence=os.environ.get('ADMISSION_ENGINEERING_EVIDENCE')
        if evidence:
            out=Path(evidence);out.mkdir(exist_ok=True,parents=True)
            (out/(self._testMethodName+'-pre-crash-source.json')).write_bytes(raw)
            (out/(self._testMethodName+'-actual-initial.json')).write_bytes(initial_raw)
            (out/(self._testMethodName+'-parent-child-exit.json')).write_text(json.dumps({'scope':'Actual Popen child linkage; pre-crash witness is not finalizer evidence',
                'child_pid':p.pid,'returncode':p.returncode,'witness_sha256':hashlib.sha256(raw).hexdigest(),
                'initial_receipt_sha256':hashlib.sha256(initial_raw).hexdigest(),'child_evidence':str(child_evidence),
                'finalizer_receipt_observed':False,'source_sha256':source_before},indent=2)+'\n')
        self.assertEqual(p.returncode,77);self.assertEqual(self.store.read().state['phase'],'dispatch_intent');self.assertEqual(self.peer.posts,[])
        with self.assertRaises(h.AdmissionError):self.store.resume(h.identity(self.store.read()))
        with self.assertRaises(h.AdmissionError):self.store.bind(self.transport,h.identity(self.store.read()))
        with self.assertRaises(h.AdmissionError):self.store.finish(self.transport,h.identity(self.store.read()))
    def test_actual_fork_cannot_use_inherited_live_owner(self):
        self.prepare();owner=self.store.resume(h.identity(self.store.read())).publish();pid=os.fork()
        if pid==0:
            try:owner.post(self.transport)
            except h.AdmissionError:os._exit(0)
            os._exit(3)
        waited,status=os.waitpid(pid,0);self.assertEqual(waited,pid);self.assertEqual(os.waitstatus_to_exitcode(status),0);self.assertEqual(self.peer.posts,[]);owner.post(self.transport);self.assertEqual(len(self.peer.posts),1)
    def test_exact_bound_run_only_can_reach_engineering_marker(self):
        bound=self.bind();self.protect(101);self.assertEqual(len(self.peer.protected),1)
        for run,attempt,anchor in [(102,1,bound.anchor),(101,2,bound.anchor),(True,1,bound.anchor),(101,True,bound.anchor),(101,1,'f'*40)]:
            with self.subTest(run=run,attempt=attempt),self.assertRaises(h.AdmissionError):self.protect(run,attempt,anchor)
        self.assertEqual(len(self.peer.protected),1)
    def test_duplicate_matching_UUID_before_binding_is_ambiguous(self):
        self.dispatch();self.transport.dispatch(self.store.read());self.assertEqual(len(self.peer.posts),2)
        with self.assertRaisesRegex(h.AdmissionError,'ambiguous'):self.store.bind(self.transport,h.identity(self.store.read()))
        self.assertEqual(self.store.read().state['phase'],'dispatch_intent');self.assertEqual(self.peer.protected,[])
    def test_later_duplicate_same_UUID_cannot_take_bound_target(self):
        bound=self.bind();self.transport.dispatch(bound)
        with self.assertRaises(h.AdmissionError):self.protect(102)
        self.assertEqual(self.store.read().binding,bound.binding);self.protect(101);self.assertEqual([p['run_id'] for p in self.peer.protected],[101])
    def test_truncated_real_HTTP_listing_is_not_unique_discovery(self):
        self.dispatch();base=deepcopy(self.peer.runs[0]);self.peer.runs += [{**base,'id':200+n,'display_title':'unrelated engineering record '+str(n)} for n in range(500)]
        with self.assertRaisesRegex(h.AdmissionError,'truncated'):self.store.bind(self.transport,h.identity(self.store.read()))
        self.assertEqual(len([p for p in self.peer.gets if '/workflows/' in p]),5);self.assertIsNone(self.store.read().binding)
    def test_invalid_actual_HTTP_run_identity_never_binds(self):
        for field,value in [('id',True),('run_attempt',2),('head_sha','f'*40),('workflow_id',38),('repository',None),('status','completed')]:
            with self.subTest(field=field):
                if self.store.read() is None:self.dispatch()
                original=deepcopy(self.peer.runs[0]);self.peer.runs[0][field]=value
                with self.assertRaises(h.AdmissionError):self.store.bind(self.transport,h.identity(self.store.read()))
                self.peer.runs[0]=original
        self.assertIsNone(self.store.read().binding)
    def test_Stop_before_dispatch_is_terminal_without_HTTP(self):
        self.prepare();snap=self.store.stop(h.identity(self.store.read()));self.assertEqual(snap.state['phase'],'terminal');self.assertEqual(self.peer.posts,[])
        with self.assertRaises(h.AdmissionError):self.store.resume(h.identity(self.store.read()))
    def test_Stop_unbound_prevents_POST_and_waits_without_guessed_cancel(self):
        self.prepare();owner=self.store.resume(h.identity(self.store.read())).publish();snap=self.store.stop(h.identity(self.store.read()));self.assertTrue(snap.state['stop_requested'])
        with self.assertRaises(h.AdmissionError):owner.post(self.transport)
        with self.assertRaises(h.AdmissionError):self.store.cancel_bound(self.transport,h.identity(self.store.read()))
        self.assertEqual(self.peer.posts,[]);self.assertEqual(self.peer.cancels,[])
    def test_Stop_after_binding_targets_only_its_exact_run_and_stays_held(self):
        bound=self.bind();self.store.stop(h.identity(self.store.read()));self.store.cancel_bound(self.transport,h.identity(self.store.read()))
        self.assertEqual(self.peer.cancels,[101]);self.assertEqual(self.store.read().state['phase'],'bound')
        with self.assertRaises(h.AdmissionError):self.protect(101)
        with self.assertRaises(h.AdmissionError):self.store.finish(self.transport,h.identity(self.store.read()))
        self.peer.runs[0].update(status='completed',conclusion='cancelled');terminal=self.store.finish(self.transport,h.identity(self.store.read()));self.assertEqual(terminal.state['terminal']['conclusion'],'cancelled')
    def test_next_generation_cannot_change_project_identity_or_workflow(self):
        self.prepare();self.store.stop(h.identity(self.store.read()));tip=self.store.tip();new=deepcopy(self.request);new['request_id']='ac72d7ea-3c83-425e-9163-e5d5b15d0af2'
        for values in [dict(repository_id=18,branch='main',workflow_id=37),dict(repository_id=17,branch='other',workflow_id=37),dict(repository_id=17,branch='main',workflow_id=38)]:
            with self.subTest(values=values),self.assertRaises(h.AdmissionError):self.store.prepare(h.canonical(new),**values)
            self.assertEqual(self.store.tip(),tip)
    def test_complete_execution_context_is_checked_before_engineering_marker(self):
        snap=self.bind();base={'anchor':snap.anchor,'request_sha256':snap.intent['payload_sha256'],'run_id':101,'run_attempt':1,'repository_id':17,'repository':self.request['repository'],'workflow_id':37,'branch':'main','source_sha':self.source,'worker_source_sha':self.worker,'request_id':self.request['request_id']}
        for key,bad in [('repository_id',True),('repository_id',18),('repository','engineering/other'),('workflow_id',38),('branch','other'),('source_sha','f'*40),('worker_source_sha','f'*40),('request_id','ac72d7ea-3c83-425e-9163-e5d5b15d0af2'),('request_sha256','f'*64)]:
            with self.subTest(key=key),self.assertRaises(h.AdmissionError):h.verify_for_science(snap,**dict(base,**{key:bad}))
        self.assertEqual(self.peer.protected,[]);self.protect(101);self.assertEqual(len(self.peer.protected),1)
    def test_malformed_actual_HTTP_cancel_observation_keeps_Stop_held(self):
        self.bind();self.store.stop(h.identity(self.store.read()));self.peer.observation_override=[]
        stopped=self.store.read();posts_before=deepcopy(self.peer.posts);gets_before=list(self.peer.gets)
        with self.assertRaises(h.TransportError) as caught:self.store.cancel_bound(self.transport,h.identity(stopped))
        self.assertIs(type(caught.exception),h.TransportError)
        self.assertEqual(str(caught.exception),'GitHub admission metadata request failed')
        self.assertIs(type(caught.exception.__cause__),sys.modules[StudentActionsClient.__module__].StudentActionsError)
        self.assertEqual(str(caught.exception.__cause__),'GitHub returned an invalid acknowledgement. Check the original submission before retrying.')
        self.assertIs(caught.exception.uncertain,False)  # GET failed; no uncertain cancel POST was submitted.
        after=self.store.read()
        self.assertEqual(after.tip,stopped.tip);self.assertEqual(after.raw,stopped.raw)
        self.assertEqual(h.canonical(after.intent),h.canonical(stopped.intent))
        self.assertEqual(h.canonical(after.state),h.canonical(stopped.state))
        self.assertEqual(h.canonical(after.binding),h.canonical(stopped.binding))
        self.assertIsNone(after.state['terminal']);self.assertEqual(self.peer.posts,posts_before);self.assertEqual(len(self.peer.posts),1)
        self.assertEqual(self.peer.gets,gets_before+['/repos/engineering/private-project/actions/runs/101'])
        self.assertEqual(self.peer.cancels,[]);self.assertEqual(self.store.read().state['phase'],'bound');self.assertTrue(self.store.read().state['stop_requested'])
        with self.assertRaises(h.AdmissionError):self.protect(101)
        self.assertEqual(self.peer.protected,[]);self.assertEqual(self.peer.posts,posts_before)
        self.assertEqual(self.store.tip(),stopped.tip)
    def test_terminal_exact_attempt_preserves_receipt_and_allows_new_UUID(self):
        bound=self.bind();self.peer.runs[0].update(status='completed',conclusion='success');terminal=self.store.finish(self.transport,h.identity(self.store.read()));self.assertEqual(terminal.binding,bound.binding)
        before=self.store.tip()
        with self.assertRaises(h.AdmissionError):self.prepare()
        self.assertEqual(self.store.tip(),before)
        new=deepcopy(self.request);new['request_id']='ac72d7ea-3c83-425e-9163-e5d5b15d0af2';self.prepare(new);self.assertEqual(self.store.read().state['phase'],'prepared')
        self.assertEqual(self.store.read(bound.tip).binding['run_id'],101)
    def test_rerun_attempt_two_never_releases_or_executes(self):
        self.bind();self.peer.runs[0].update(status='completed',conclusion='success',run_attempt=2)
        with self.assertRaises(h.AdmissionError):self.store.finish(self.transport,h.identity(self.store.read()))
        with self.assertRaises(h.AdmissionError):self.protect(101,2)
        self.assertEqual(self.store.read().state['phase'],'bound')
    def test_strict_transport_rejects_duplicate_unknown_nonfinite_or_probes(self):
        self.assertRaises(h.AdmissionError,h.strict,b'{"x":1,"x":1}')
        self.assertRaises(h.AdmissionError,h.strict,b'{"x":1e999}')
        self.assertRaises(h.AdmissionError,h.strict,b'{"x":NaN}')
        for mutate in [lambda r:r.update(extra='not allowed'),lambda r:r.update(capability_probe={'engines':['orca']},calculation=None),lambda r:r.update(resources={'cores':True,'maxcore_mb':128}),lambda r:r.update(source_sha='main')]:
            r=deepcopy(self.request);mutate(r)
            with self.assertRaises(h.AdmissionError):h.validate_request(h.canonical(r))
        self.assertIsNone(self.store.tip())
    def test_first_binding_numeric_aliases_are_refused_in_real_Git(self):
        # A separate real Git clone creates the unmodified production binding.
        # Main store stays at C, then receives a genuinely malformed FIRST B.
        for field in ['repository_id','workflow_id']:
            for alias in [1.0,True]:
                with self.subTest(field=field,alias=alias),tempfile.TemporaryDirectory(prefix='B-alias-') as td:
                    store=h.GitStore.create(Path(td)/'ledger.git')
                    store.prepare(h.canonical(self.request),repository_id=1,branch='main',workflow_id=1)
                    owner=store.resume(h.identity(store.read())).publish();self.peer.repository_id=1;self.peer.workflow_id=1;self.peer.runs=[];owner.post(self.transport)
                    clone=h.GitStore.create(Path(td)/'valid-binding.git');clone.git('fetch','--no-tags',str(store.path),store.ref+':'+clone.ref)
                    valid=clone.bind(self.transport,h.identity(clone.read()));files,parent=clone.files(valid.tip)
                    binding=h.strict(files['binding.json']);binding[field]=alias;files['binding.json']=h.canonical(binding)
                    state=h.strict(files['state.json']);state['binding_sha256']=h.digest(files['binding.json']);files['state.json']=h.canonical(state)
                    corrupt=store.commit(files,parent);store.advance(corrupt,parent)
                    with self.assertRaises(h.AdmissionError):store.read()
    def test_immutable_binding_numeric_alias_cannot_hide_behind_dict_equality(self):
        for field in ['repository_id','workflow_id']:
            with self.subTest(field=field),tempfile.TemporaryDirectory(prefix='B-immutable-alias-') as td:
                store=h.GitStore.create(Path(td)/'ledger.git');store.prepare(h.canonical(self.request),repository_id=17,branch='main',workflow_id=37)
                self.peer.repository_id=17;self.peer.workflow_id=37;self.peer.runs=[];store.resume(h.identity(store.read())).publish().post(self.transport);bound=store.bind(self.transport,h.identity(store.read()))
                files,parent=store.files(bound.tip);binding=h.strict(files['binding.json']);binding[field]=float(binding[field]);files['binding.json']=h.canonical(binding)
                state=h.strict(files['state.json']);state.update(previous=bound.tip,stop_requested=True,binding_sha256=h.digest(files['binding.json']));files['state.json']=h.canonical(state)
                corrupt=store.commit(files,bound.tip);store.advance(corrupt,bound.tip)
                with self.assertRaisesRegex(h.AdmissionError,'Run binding cannot change'):store.read()
    def test_corrupt_state_and_changed_request_fail_closed(self):
        self.prepare()
        def change(files):
            state=h.strict(files['state.json']);state['unexpected']='not allowed';files['state.json']=h.canonical(state)
        self.corrupt(change)
        with self.assertRaises(h.AdmissionError):self.store.read()
        with self.assertRaises(h.AdmissionError):self.store.resume(h.identity(self.store.read()))
    def test_immutable_binding_and_Stop_cannot_be_cleared_by_new_commit(self):
        self.bind();self.store.stop(h.identity(self.store.read()))
        def change(files):
            state=h.strict(files['state.json']);binding=h.strict(files['binding.json']);binding['run_id']=102;files['binding.json']=h.canonical(binding);state['binding_sha256']=h.digest(files['binding.json']);state['stop_requested']=False;state['previous']=self.store.tip();files['state.json']=h.canonical(state)
        self.corrupt(change)
        with self.assertRaises(h.AdmissionError):self.store.read()
        self.assertEqual(self.peer.protected,[])

if __name__=='__main__':unittest.main(verbosity=2)
