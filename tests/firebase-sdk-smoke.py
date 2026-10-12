"""Requires isolated Auth emulator on 127.0.0.1:9199 (demo-ttt-sdk); rejects production requests.
Real SDK 8-to-13 Auth/Firestore persistence migration; does not test live Google OAuth.
"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import json,base64,urllib.request
SDK_FILES={}
for version,suffix in [('8.10.1',''),('13.0.0','-compat')]:
 for component in ['app','auth','firestore']:
  name='firebase-'+component+suffix+'.js'
  SDK_FILES[name]=urllib.request.urlopen('https://www.gstatic.com/firebasejs/'+version+'/'+name,timeout=30).read()
from playwright.sync_api import sync_playwright
html='''<!doctype html><html><body><script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js"></script><script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-auth.js"></script><script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-firestore.js"></script><script>
firebase.initializeApp({apiKey:'demo-ttt-sdk',authDomain:'demo-ttt-sdk.firebaseapp.com',projectId:'demo-ttt-sdk',appId:'1:123:web:test'});
window.auth=firebase.auth();auth.useEmulator('http://127.0.0.1:9199',{disableWarnings:true});window.db=firebase.firestore();
window.ready=db.enablePersistence({synchronizeTabs:true}).then(()=>db.disableNetwork());
window.authReady=new Promise(resolve=>{let off=auth.onAuthStateChanged(user=>{off();resolve(Boolean(user));});});
</script></body></html>'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(html.encode())
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',8155),Handler);Thread(target=server.serve_forever,daemon=True).start()
def encode(v):return base64.urlsafe_b64encode(json.dumps(v).encode()).decode().rstrip('=')
token=encode({'alg':'none','typ':'JWT'})+'.'+encode({'sub':'isolated-sdk-google','email':'isolated-sdk@example.invalid','email_verified':True,'name':'SDK Test','iss':'https://accounts.google.com','aud':'demo-ttt-sdk'})+'.'
try:
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context();blocked=[]
  def route(r):
   name=r.request.url.rsplit('/',1)[-1]
   if name in ['firebase-app.js','firebase-auth.js','firebase-firestore.js','firebase-app-compat.js','firebase-auth-compat.js','firebase-firestore-compat.js']:r.fulfill(body=SDK_FILES[name],content_type='application/javascript')
   else:blocked.append(r.request.url);r.abort()
  c.route('https://**/*',route);page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8155/');page.evaluate('ready');assert page.evaluate('authReady') is False
  assert page.evaluate('firebase.SDK_VERSION')=='8.10.1'
  assert page.evaluate('firebase.firestore.FieldValue.serverTimestamp() instanceof firebase.firestore.FieldValue')
  # Simulate pagehide before Google credential completion, using only the local Auth emulator.
  page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}))")
  result=page.evaluate("""async token=>{const result=await auth.signInWithCredential(firebase.auth.GoogleAuthProvider.credential(token));return {hasUser:Boolean(auth.currentUser),google:result.user.providerData.some(p=>p.providerId==='google.com')};}""",token)
  assert result=={'hasUser':True,'google':True},result
  page.evaluate("""async()=>{const ref=db.doc('users/isolated-sdk/records/stable');ref.set({weight:60,reps:5,createdAt:firebase.firestore.Timestamp.fromMillis(1234),updatedAt:firebase.firestore.FieldValue.serverTimestamp()}).catch(()=>{});for(let i=0;i<30;i++){try{const d=await ref.get({source:'cache'});if(d.exists)return;}catch(e){}await new Promise(r=>setTimeout(r,30));}throw Error('No local write');}""")
  html=html.replace('8.10.1/firebase-app.js','13.0.0/firebase-app-compat.js').replace('8.10.1/firebase-auth.js','13.0.0/firebase-auth-compat.js').replace('8.10.1/firebase-firestore.js','13.0.0/firebase-firestore-compat.js')
  page.reload();page.evaluate('ready');assert page.evaluate('firebase.SDK_VERSION')=='13.0.0';assert page.evaluate('authReady') is True
  assert page.evaluate("async()=>{let d=await db.doc('users/isolated-sdk/records/stable').get({source:'cache'});return d.data().weight===60 && d.data().createdAt.toMillis()===1234;}")
  page.evaluate('auth.signOut()');assert page.evaluate('auth.currentUser===null')
  page.reload();page.evaluate('ready');assert page.evaluate('authReady') is False
  assert not errors,errors
  assert not blocked,blocked
  print('PASS: native SDK 8.10.1 -> 13.0.0 upgrade preserves signed-in Google emulator user and offline Firestore records; sign-out persists; no production requests')
  b.close()
finally:server.shutdown()
