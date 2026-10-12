/* Single-flight popup login. No tokens or credentials are stored by this module. */
(function(root){
  'use strict';
  function create({auth,provider,onState=()=>{},onSignedIn=()=>{},onDiagnostic=()=>{},slowMs=15000,
    schedule=setTimeout,cancel=clearTimeout}){
    let pending=null, generation=0;
    const trace=(stage,details)=>{try{onDiagnostic(stage,details);}catch(e){}};
    function finish(op,status,message){
      if(pending!==op)return;
      cancel(op.timer);pending=null;
      trace('flow_'+status,{hasUser:Boolean(auth.currentUser)});
      onState({status,message});
    }
    function observe(user){
      trace('auth_observed',{hasUser:Boolean(user),busy:Boolean(pending)});
      if(user && pending)finish(pending,'success','로그인되었습니다.');
    }
    function request(){
      trace('login_click',{hasUser:Boolean(auth.currentUser),busy:Boolean(pending)});
      if(auth.currentUser){observe(auth.currentUser);onSignedIn(auth.currentUser);return Promise.resolve(auth.currentUser);}
      if(pending){trace('duplicate_blocked');return pending.promise;}
      const op={id:++generation};pending=op;
      onState({status:'pending',message:'Google 로그인 결과를 기다리고 있습니다.'});
      op.timer=schedule(()=>{
        if(pending===op)trace('popup_wait_timeout',{hasUser:Boolean(auth.currentUser)});
        if(pending===op)onState({status:'slow',message:'로그인 확인이 지연되고 있습니다. 결과를 기다리고 있습니다.'});
      },slowMs);
      let popup;
      try{trace('popup_start');popup=auth.signInWithPopup(provider());}catch(e){popup=Promise.reject(e);}
      op.promise=Promise.resolve(popup).then(result=>{
        trace('popup_result',{hasUser:Boolean(result?.user),repeated:pending!==op});
        if(pending!==op)return;
        const user=auth.currentUser || result?.user;
        if(!user)throw Error('로그인 결과를 확인하지 못했습니다.');
        finish(op,'success','로그인되었습니다.');onSignedIn(user);return user;
      }).catch(error=>{
        trace('popup_error',{code:error?.code,hasUser:Boolean(auth.currentUser),repeated:pending!==op});
        if(pending!==op)return;
        if(auth.currentUser){finish(op,'success','로그인되었습니다.');onSignedIn(auth.currentUser);return;}
        const code=error?.code;
        const message=code==='auth/popup-closed-by-user'?'로그인이 취소되었습니다.':
          code==='auth/cancelled-popup-request'?'다른 로그인 요청이 진행 중입니다. 잠시 후 다시 시도해주세요.':
          code==='auth/popup-blocked'?'로그인 창을 열지 못했습니다. 팝업 허용 설정을 확인해주세요.':
          '로그인을 완료하지 못했습니다. 연결 상태를 확인하고 다시 시도해주세요.';
        finish(op,'error',message);
      });
      return op.promise;
    }
    return {request,observe,get busy(){return Boolean(pending);}};
  }
  const api={create};if(typeof module!=='undefined')module.exports=api;root.MFGoogleLogin=api;
})(typeof window==='undefined'?globalThis:window);
