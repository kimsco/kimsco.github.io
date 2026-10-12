/* Bounded, single-flight profile reads. Late results cannot apply to another account. */
(function(root){
  'use strict';
  function create({read,apply,currentOwner,onState=()=>{},online=()=>true,timeoutMs=12000,retryMs=1500,attempts=2}){
    const pending=new Map();
    function load(owner){
      if(pending.has(owner))return pending.get(owner);
      const task=(async()=>{
        onState('pending',owner);
        for(let attempt=0;attempt<attempts;attempt++){
          if(currentOwner()!==owner) return false;
          let timer;
          try{
            if(!online())throw Error('offline');
            const value=await Promise.race([Promise.resolve().then(()=>read(owner)),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('profile timeout')),timeoutMs);})]);
            clearTimeout(timer);
            if(currentOwner()!==owner)return false;
            apply(value,owner);onState('ready',owner);return true;
          }catch(e){
            clearTimeout(timer);
            if(currentOwner()!==owner)return false;
            if(attempt+1<attempts && online()){
              onState('retry',owner);
              await new Promise(resolve=>setTimeout(resolve,retryMs));
            }else{onState('error',owner);return false;}
          }
        }
        return false;
      })();
      pending.set(owner,task);task.finally(()=>{if(pending.get(owner)===task)pending.delete(owner);});return task;
    }
    return {load};
  }
  const api={create};if(typeof module!=='undefined')module.exports=api;root.MFProfileLoader=api;
})(typeof window==='undefined'?globalThis:window);
