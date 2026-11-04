const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
test('status-bar test variants have distinct install identities and controlled metadata',()=>{
 const a=fs.readFileSync('statusbar-test/a/index.html','utf8'),b=fs.readFileSync('statusbar-test/b/index.html','utf8');
 assert.ok(!a.includes('name="apple-mobile-web-app-status-bar-style"'));
 assert.ok(b.includes('name="apple-mobile-web-app-status-bar-style" content="black-translucent"'));
 const ma=JSON.parse(fs.readFileSync('statusbar-test/a/manifest.webmanifest')),mb=JSON.parse(fs.readFileSync('statusbar-test/b/manifest.webmanifest'));
 assert.notEqual(ma.id,mb.id);assert.notEqual(ma.start_url,mb.start_url);
 for(const m of [ma,mb]){assert.equal(m.display,'standalone');assert.ok(m.start_url.startsWith(m.scope));assert.ok(m.start_url.includes('startup_check='));assert.notEqual(m.id,'/');}
 assert.match(fs.readFileSync('index.html','utf8'),/name="apple-mobile-web-app-status-bar-style" content="black-translucent"/);
});
test('diagnostic documents cannot connect accounts, subscribe to push or write user data',()=>{
 for(const name of ['index.html','a/index.html','b/index.html']){
  const html=fs.readFileSync('statusbar-test/'+name,'utf8');
  assert.doesNotMatch(html,/<script\b|<form\b|<input\b|<iframe\b/i);
  assert.doesNotMatch(html,/firebase|localStorage|sessionStorage|serviceWorker|pushManager|requestPermission/);
 }
});
function worker(){
 const listeners={},writes=[],requests=[],pending=[];
 const self={location:{origin:'https://example.test'},addEventListener:(name,listener)=>listeners[name]=listener};
 const caches={open:async()=>({put:async(key,response)=>writes.push([key,await response.text()])})};
 vm.runInNewContext(fs.readFileSync('sw.js','utf8'),{self,URL,Response,caches,fetch:async(request,options)=>{requests.push({request,options});return new Response('network content');}});
 const navigate=async path=>{
  let result;listeners.fetch({request:{url:'https://example.test'+path,mode:'navigate',method:'GET'},respondWith:p=>result=p,waitUntil:p=>pending.push(p)});
  const response=await result;await Promise.all(pending);return response;
 };
 return {navigate,writes,requests};
}
test('diagnostic navigation bypasses cache and never overwrites the production shell',async()=>{
 const w=worker();await w.navigate('/statusbar-test/a/');await w.navigate('/statusbar-test/b/?startup_check=statusbar-b-v1');
 assert.equal(w.writes.length,0);assert.equal(w.requests.length,2);
 assert.ok(w.requests.every(r=>r.options.cache==='no-store'));
});
test('production navigation continues to cache only the production app shell',async()=>{
 const w=worker();await w.navigate('/');assert.deepEqual(w.writes.map(x=>x[0]).sort(),['/','/index.html']);
});
