const test=require('node:test');const assert=require('node:assert/strict');
const {create}=require('../js/google-login.js');
function fixture(){
 let resolve,reject,callback,calls=0;const states=[],users=[],auth={currentUser:null,signInWithPopup(){calls++;return new Promise((a,b)=>{resolve=a;reject=b;});}};
 const flow=create({auth,provider:()=>({}),onState:s=>states.push(s),onSignedIn:u=>users.push(u),schedule:fn=>{callback=fn;return 1;},cancel:()=>{}});
 return {auth,flow,states,users,get calls(){return calls;},resolve:v=>resolve(v),reject:e=>reject(e),slow:()=>callback()};
}
test('duplicate taps share one popup and success clears busy',async()=>{
 const f=fixture(),a=f.flow.request(),b=f.flow.request();assert.equal(a,b);assert.equal(f.calls,1);
 f.auth.currentUser={uid:'alice'};f.resolve({user:f.auth.currentUser});await a;
 assert.equal(f.flow.busy,false);assert.equal(f.users.length,1);assert.equal(f.states.at(-1).status,'success');
 await f.flow.request();assert.equal(f.calls,1);
});
test('auth observer settles a stalled popup and late errors cannot undo success',async()=>{
 const f=fixture(),a=f.flow.request();f.auth.currentUser={uid:'alice'};f.flow.observe(f.auth.currentUser);
 assert.equal(f.flow.busy,false);f.reject({code:'auth/cancelled-popup-request'});await a;
 assert.equal(f.states.at(-1).status,'success');
});
test('slow login stays single-flight; transient null auth state does not release it',async()=>{
 const f=fixture(),a=f.flow.request();f.slow();assert.equal(f.states.at(-1).status,'slow');f.flow.observe(null);
 assert.equal(f.flow.request(),a);assert.equal(f.calls,1);f.reject({code:'auth/popup-closed-by-user'});await a;
 assert.equal(f.flow.busy,false);assert.equal(f.states.at(-1).message,'로그인이 취소되었습니다.');
});
test('failure releases the guard so a later genuine attempt can succeed',async()=>{
 const f=fixture(),a=f.flow.request();f.reject({code:'auth/network-request-failed'});await a;
 const b=f.flow.request();assert.equal(f.calls,2);f.auth.currentUser={uid:'bob'};f.resolve({user:f.auth.currentUser});await b;
 assert.equal(f.users.at(-1).uid,'bob');assert.equal(f.states.at(-1).status,'success');
});
