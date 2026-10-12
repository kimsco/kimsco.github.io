const {test}=require('node:test');const assert=require('node:assert/strict');
const {configure,readProfile,isIOSStandalone}=require('../js/firestore-runtime.js');
test('iOS PWA bypasses multi-tab persistence and uses supported long polling settings',async()=>{
 let persistence=0,settings;const db={settings:value=>settings=value,enablePersistence:()=>{persistence++;return new Promise(()=>{});}};
 assert.equal(await configure({db,nav:{userAgent:'iPhone',standalone:true}}),'memory');assert.equal(persistence,0);
 assert.deepEqual(settings,{experimentalForceLongPolling:true,experimentalAutoDetectLongPolling:false,experimentalLongPollingOptions:{timeoutSeconds:5}});
 assert.equal(isIOSStandalone({platform:'MacIntel',maxTouchPoints:5,standalone:true}),true);
});
test('ordinary browsers retain persistence with a supported memory fallback',async()=>{
 let options;assert.equal(await configure({db:{enablePersistence:async x=>options=x},nav:{userAgent:'Chrome'}}),'persistent');assert.deepEqual(options,{synchronizeTabs:true});
 assert.equal(await configure({db:{enablePersistence:async()=>{throw Error('unsupported');}},nav:{userAgent:'Chrome'}}),'memory');
});
test('authenticated REST recovery decodes typed profile fields and reads only its own account',async()=>{
 const auth={currentUser:{uid:'a/b',getIdToken:async()=> 'isolated-token'}};let calls=0;
 const snap=await readProfile({auth,projectId:'demo-test',owner:'a/b',fetchFn:async(url,options)=>{
  calls++;assert.match(url,/projects\/demo-test\/databases\/\(default\)\/documents\/users\/a%2Fb\/profile\/spec$/);assert.equal(options.headers.Authorization,'Bearer isolated-token');assert.equal(options.cache,'no-store');
  return new Response(JSON.stringify({fields:{name:{stringValue:'Test'},height:{integerValue:'180'},weight:{doubleValue:72.5},enabled:{booleanValue:true},empty:{nullValue:null},nested:{mapValue:{fields:{a:{arrayValue:{values:[{integerValue:'2'}]}}}}}}}),{status:200});
 }});assert.equal(calls,1);assert.deepEqual(snap.data(),{name:'Test',height:180,weight:72.5,enabled:true,empty:null,nested:{a:[2]}});
 await assert.rejects(readProfile({auth,projectId:'demo-test',owner:'other',fetchFn:()=>{throw Error('must not run');}}),/Account changed/);
});
test('REST failure is not an empty profile; late token retrieval after timeout does not send a request',async()=>{
 const auth={currentUser:{uid:'a',getIdToken:async()=> 'isolated-token'}};
 await assert.rejects(readProfile({auth,projectId:'demo-test',owner:'a',fetchFn:async()=>new Response('',{status:403})}),/rejected/);
 let release,requests=0;auth.currentUser.getIdToken=()=>new Promise(r=>release=r);
 await assert.rejects(readProfile({auth,projectId:'demo-test',owner:'a',timeoutMs:5,fetchFn:async(_,options)=>{requests++;assert.equal(options.signal.aborted,true);throw Error('aborted');}}),/timeout/);
 release('late');await new Promise(r=>setTimeout(r,1));assert.equal(requests,0);
});
test('REST response cannot apply across an account change',async()=>{
 const auth={currentUser:{uid:'a',getIdToken:async()=> 'isolated-token'}};
 await assert.rejects(readProfile({auth,projectId:'demo-test',owner:'a',fetchFn:async()=>{auth.currentUser={uid:'b'};return new Response('{}');}}),/Account changed/);
});
