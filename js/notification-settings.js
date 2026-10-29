(function(root){
 'use strict';
 const DEFAULT_MINUTE=22*60;
 const valid=value=>Number.isInteger(value)&&value>=0&&value<1440;
 function createPreferences({storage,currentUid,revision=()=>root.crypto.randomUUID()}){
  const key=()=>currentUid()?`mf_account_v2:${currentUid()}:notification_time_v1`:'mf_notification_time_guest_v1';
  function read(){try{const value=JSON.parse(storage.getItem(key())||'null');if(valid(value?.minuteOfDay))return value;}catch(_){}return {minuteOfDay:DEFAULT_MINUTE,dirty:false,revision:null};}
  function save(minuteOfDay){if(!valid(minuteOfDay))throw Error('시간을 다시 선택해주세요.');const value={minuteOfDay,dirty:true,revision:revision()};storage.setItem(key(),JSON.stringify(value));return value;}
  function acknowledge(savedRevision){const value=read();if(value.revision===savedRevision)storage.setItem(key(),JSON.stringify({...value,dirty:false}));}
  function fromServer(minuteOfDay){if(!valid(minuteOfDay))throw Error('올바르지 않은 알림 시간입니다.');const value=read();if(!value.dirty)storage.setItem(key(),JSON.stringify({minuteOfDay,dirty:false,revision:revision()}));return read();}
  return {read,save,acknowledge,fromServer};
 }
 function install({preferences,onOpen,onSave,onPermission,onSaved}){
  const doc=root.document,screen=doc.getElementById('notificationSettingsOverlay'),parent=doc.getElementById('settingsOverlay');
  doc.body.append(screen);
  const save=doc.getElementById('notificationSaveBtn'),status=doc.getElementById('notificationSaveStatus'),back=doc.getElementById('notificationSettingsBack');
  let dirty=false,saving=false,session=0,returnFocus;
  const wheels=[];
  function wheel(id,labels,firstValue=0){
   const el=doc.getElementById(id),rowHeight=48;let index=0;
   labels.forEach((text,i)=>{const row=doc.createElement('div');row.className='notification-wheel-option';row.textContent=text;row.setAttribute('aria-hidden','true');row.addEventListener('click',()=>set(i,true));el.append(row);});
   function render(){el.setAttribute('aria-valuenow',String(index+firstValue));el.setAttribute('aria-valuetext',labels[index]);for(let i=0;i<el.children.length;i++)el.children[i].classList.toggle('selected',i===index);}
   function set(value,changed=false){index=Math.max(0,Math.min(labels.length-1,value));el.scrollTo({top:index*rowHeight,behavior:'auto'});render();if(changed){dirty=true;status.textContent='';}}
   el.setAttribute('aria-valuemin',String(firstValue));el.setAttribute('aria-valuemax',String(labels.length-1+firstValue));
   el.addEventListener('scroll',()=>{const next=Math.max(0,Math.min(labels.length-1,Math.round(el.scrollTop/rowHeight)));if(next!==index){index=next;render();dirty=true;status.textContent='';}},{passive:true});
   el.addEventListener('keydown',event=>{const delta={ArrowUp:-1,ArrowDown:1,PageUp:-5,PageDown:5}[event.key];if(delta!==undefined){event.preventDefault();set(index+delta,true);}else if(event.key==='Home'||event.key==='End'){event.preventDefault();set(event.key==='Home'?0:labels.length-1,true);}});
   const result={set,value:()=>index,element:el};wheels.push(result);return result;
  }
  const period=wheel('notificationPeriodWheel',['오전','오후']),hour=wheel('notificationHourWheel',Array.from({length:12},(_,i)=>String(i+1)),1),minute=wheel('notificationMinuteWheel',Array.from({length:60},(_,i)=>String(i).padStart(2,'0')));
  function showTime(){const value=preferences.read().minuteOfDay,h=Math.floor(value/60);period.set(h>=12?1:0);hour.set((h%12||12)-1);minute.set(value%60);dirty=false;}
  let swipeTimer,swipeTracking=false,swipeDragging=false,swipeX=0,swipeY=0,swipeDistance=0,suppressClickUntil=0;
  function resetSwipe(){
   clearTimeout(swipeTimer);swipeTimer=null;swipeTracking=false;swipeDragging=false;swipeDistance=0;
   screen.style.transition='';screen.style.transform='';
  }
  screen.addEventListener('touchstart',event=>{
   if(event.touches.length!==1 || swipeTimer || screen.classList.contains('hidden'))return;
   const point=event.touches[0];
   swipeTracking=point.clientX<=30;swipeDragging=false;swipeDistance=0;
   swipeX=point.clientX;swipeY=point.clientY;
  },{passive:true});
  screen.addEventListener('touchmove',event=>{
   if(!swipeTracking)return;
   if(event.touches.length!==1){resetSwipe();return;}
   const dx=event.touches[0].clientX-swipeX,dy=event.touches[0].clientY-swipeY;
   if(!swipeDragging){
    if(Math.abs(dy)>8 && Math.abs(dy)>dx || dx< -8){swipeTracking=false;return;}
    if(dx<=8 || dx<=Math.abs(dy))return;
    swipeDragging=true;screen.style.transition='none';
   }
   event.preventDefault();swipeDistance=Math.max(0,Math.min(root.innerWidth,dx));
   screen.style.transform=`translateX(${swipeDistance}px)`;
  },{passive:false});
  function finishSwipe(cancelled){
   if(!swipeTracking)return;
   swipeTracking=false;
   if(!swipeDragging)return;
   swipeDragging=false;suppressClickUntil=Date.now()+400;
   const dismiss=!cancelled && swipeDistance>root.innerWidth*.3;
   const reduced=root.matchMedia('(prefers-reduced-motion: reduce)').matches;
   screen.style.transition=reduced?'none':'transform .22s ease';
   screen.style.transform=dismiss?'translateX(100%)':'translateX(0)';
   swipeTimer=setTimeout(()=>{swipeTimer=null;if(dismiss)close();else resetSwipe();},reduced?0:230);
  }
  screen.addEventListener('touchend',()=>finishSwipe(false),{passive:true});
  screen.addEventListener('touchcancel',()=>finishSwipe(true),{passive:true});
  screen.addEventListener('click',event=>{if(Date.now()<suppressClickUntil){event.preventDefault();event.stopImmediatePropagation();}},true);
  function close(){session++;screen.classList.add('hidden');resetSwipe();parent.inert=false;returnFocus?.focus({preventScroll:true});}

  async function open(){resetSwipe();suppressClickUntil=0;session++;const current=session;returnFocus=doc.activeElement;screen.classList.remove('hidden');parent.inert=true;status.textContent='';showTime();back.focus({preventScroll:true});try{await onOpen();if(session===current&&!dirty)showTime();}catch(_){} }
  back.addEventListener('click',close);
  doc.addEventListener('keydown',event=>{
   if(screen.classList.contains('hidden'))return;
   if(event.key==='Escape'){event.preventDefault();close();return;}
   if(event.key==='Tab'){const nodes=[...screen.querySelectorAll('button:not(:disabled),[tabindex="0"]')];const first=nodes[0],last=nodes.at(-1);if(!screen.contains(doc.activeElement)){event.preventDefault();first.focus();return;}if(event.shiftKey&&doc.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&doc.activeElement===last){event.preventDefault();first.focus();}}
  });
  doc.getElementById('notificationAllowBtn').addEventListener('click',onPermission);
  save.addEventListener('click',async()=>{
   if(saving)return;const current=session;for(const wheel of wheels)wheel.set(wheel.value());
   const total=((hour.value()+1)%12+period.value()*12)*60+minute.value();
   saving=true;save.disabled=true;save.textContent='저장 중…';
   for(const wheel of wheels)wheel.element.inert=true;
   try{const message=await onSave(total);if(current===session){dirty=false;if(onSaved){status.textContent=message&&message!=='저장했어요.'?message:'';onSaved(message);}else status.textContent=message||'저장했어요.';}}
   catch(error){if(current===session)status.textContent=error.message||'저장하지 못했어요. 다시 시도해주세요.';}
   finally{saving=false;save.disabled=false;save.textContent='저장하기';for(const wheel of wheels)wheel.element.inert=false;}
  });
  return {open,close,accountChanged:()=>{if(!screen.classList.contains('hidden'))close();},refresh:()=>{if(!screen.classList.contains('hidden')&&!dirty&&!saving)showTime();}};
 }
 const api={DEFAULT_MINUTE,valid,createPreferences,install};if(typeof module!=='undefined')module.exports=api;root.MFNotificationSettings=api;
})(typeof window==='undefined'?globalThis:window);
