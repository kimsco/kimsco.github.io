const test=require('node:test');const assert=require('node:assert/strict');const {create}=require('../js/login-diagnostic.js');
function storage(){const map=new Map();return {getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k),map};}
test('OFF stores no events; ON preserves first attempt across an app restart',()=>{
 const s=storage(),d=create({storage:s,version:'test'});d.mark('popup_start');assert.equal(s.map.size,0);
 d.toggle();d.mark('login_click',{hasUser:false});d.mark('popup_start');d.mark('popup_wait_timeout');
 const next=create({storage:s,version:'test'});next.mark('auth_state',{hasUser:true});
 const report=next.report();assert.match(report,/popup_wait_timeout/);assert.match(report,/실행 2.*boot/);assert.match(report,/auth_state.*true/);
 next.toggle();assert.equal(s.getItem('mf_login_diagnostic_v1'),null);
});
test('only safe flags and error codes enter the bounded local trace',()=>{
 const s=storage(),d=create({storage:s,version:'test'});d.toggle();
 d.mark('popup_error',{code:'auth/popup-closed-by-user',email:'secret@example.test',token:'secret-token',message:'private',uid:'secret-uid',hasUser:false});
 const report=d.report();assert.match(report,/auth\/popup-closed-by-user/);assert.doesNotMatch(report,/secret|private/);
 for(let i=0;i<200;i++)d.mark('app_return');assert.equal(JSON.parse(s.getItem('mf_login_diagnostic_v1')).events.length,120);
});
