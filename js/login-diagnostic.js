/* Opt-in, bounded local trace. Never accepts credentials, identifiers or error messages. */
(function(root){
  'use strict';
  function create({storage,now=Date.now,version}){
    const flag='mf_login_diagnostic_enabled',key='mf_login_diagnostic_v1';
    let run=0;
    function enabled(){try{return storage.getItem(flag)==='1';}catch(e){return false;}}
    function read(){try{const data=JSON.parse(storage.getItem(key)||'null');if(Array.isArray(data?.events))return {run:Number(data.run)||0,events:data.events.slice(-120)};}catch(e){}return {run:0,events:[]};}
    function mark(stage,details={}){
      if(!enabled() || !/^[a-z_]+$/.test(stage))return;
      try{
        const data=read(),safe={};
        for(const name of ['hasUser','busy','hidden','standalone','repeated'])if(typeof details[name]==='boolean')safe[name]=details[name];
        if(typeof details.code==='string' && /^auth\/[a-z-]+$/.test(details.code))safe.code=details.code;
        data.run=Math.max(data.run,run);data.events.push({run,at:now(),stage,...safe});data.events=data.events.slice(-120);
        storage.setItem(key,JSON.stringify(data));
      }catch(e){}
    }
    function start(){if(enabled()){run=read().run+1;mark('boot',{standalone:root.navigator?.standalone===true});}}
    function toggle(){
      const on=!enabled();storage.setItem(flag,on?'1':'0');
      if(on){storage.removeItem(key);start();}else storage.removeItem(key);
      return on;
    }
    function report(){
      const data=read();return 'TTT 로그인 진단 '+version+'\n'+data.events.map(e=>{
        const {run,at,stage,...detail}=e;return '실행 '+run+' | '+new Date(at).toISOString()+' | '+stage+' | '+JSON.stringify(detail);
      }).join('\n');
    }
    start();return {enabled,mark,toggle,report};
  }
  const api={create};if(typeof module!=='undefined')module.exports=api;root.MFLoginDiagnostic=api;
})(typeof window==='undefined'?globalThis:window);
