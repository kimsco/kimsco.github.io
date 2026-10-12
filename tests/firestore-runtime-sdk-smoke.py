"""Real Firebase 13 configuration and memory reads; rejects production network traffic.
This validates SDK compatibility, not iPhone WebKit behavior or production Firestore.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import urllib.request
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
files={name:urllib.request.urlopen('https://www.gstatic.com/firebasejs/13.0.0/'+name,timeout=30).read() for name in ['firebase-app-compat.js','firebase-firestore-compat.js']}
runtime=(root/'js/firestore-runtime.js').read_text()
html='''<!doctype html><html><body><script src="https://www.gstatic.com/firebasejs/13.0.0/firebase-app-compat.js"></script><script src="https://www.gstatic.com/firebasejs/13.0.0/firebase-firestore-compat.js"></script><script src="/runtime.js"></script><script>
firebase.initializeApp({projectId:'demo-ttt-memory',apiKey:'demo-ttt-memory',appId:'1:123:web:test'});
window.db=firebase.firestore();window.indexedDbOpens=0;
const originalOpen=indexedDB.open.bind(indexedDB);indexedDB.open=function(...args){indexedDbOpens++;return originalOpen(...args);};
window.ready=MFFirestoreRuntime.configure({db,nav:{userAgent:'iPhone',standalone:true}}).then(mode=>db.disableNetwork().then(()=>mode));
</script></body></html>'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','application/javascript' if self.path=='/runtime.js' else 'text/html');self.end_headers();self.wfile.write((runtime if self.path=='/runtime.js' else html).encode())
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',8184),Handler);Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context();blocked=[]
  def route(r):
   name=r.request.url.rsplit('/',1)[-1]
   if name in files:r.fulfill(body=files[name],content_type='application/javascript')
   else:blocked.append(r.request.url);r.abort()
  c.route('https://**/*',route)
  page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8184/');assert page.evaluate('ready')=='memory'
  assert page.evaluate('firebase.SDK_VERSION')=='13.0.0'
  page.evaluate("""async()=>{const ref=db.doc('users/isolated/records/stable');ref.set({weight:60,createdAt:firebase.firestore.Timestamp.fromMillis(1234)}).catch(()=>{});for(let i=0;i<30;i++){try{const d=await ref.get({source:'cache'});if(d.exists&&d.data().weight===60&&d.data().createdAt.toMillis()===1234)return;}catch(e){}await new Promise(r=>setTimeout(r,20));}throw Error('Local memory write unavailable');}""")
  assert page.evaluate('indexedDbOpens')==0
  assert not blocked,blocked
  assert not errors,errors
  b.close();print('PASS: real Firebase 13 supports iOS runtime long-poll settings and memory cache without opening IndexedDB; no production request')
finally:server.shutdown();server.server_close()
