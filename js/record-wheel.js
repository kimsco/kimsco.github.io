/* Optional long-press wheel; short taps still use the existing input/keyboard path. */
(()=>{
 'use strict';
 const configs=[['recordWeight',5,0,500,'무게','kg'],['recordReps',1,1,60,'횟수','회'],['acc-weight',5,0,500,'무게','kg'],['acc-reps',1,1,60,'횟수','회'],['myRoutineRevealInputWeight',5,0,500,'무게','kg'],['myRoutineRevealInputReps',1,1,60,'횟수','회']];
 const style=document.createElement('style');style.textContent=`
 .record-wheel-overlay{position:fixed;inset:0;z-index:300000;background:transparent;overscroll-behavior:contain;}
 .record-wheel-overlay[hidden]{display:none;}
 .record-wheel-sheet{--record-wheel-row:44px;position:fixed;box-sizing:border-box;color:var(--c-text-primary,#fff);animation:record-wheel-unfold .18s cubic-bezier(.22,1,.36,1) both;}
 @keyframes record-wheel-unfold{from{clip-path:inset(33.33% 0);opacity:.3;}to{clip-path:inset(0);opacity:1;}}
 @media(prefers-reduced-motion:reduce){.record-wheel-sheet{animation:none;}}
 .record-wheel-header{position:absolute;top:var(--record-wheel-row);left:0;right:0;height:var(--record-wheel-row);z-index:3;pointer-events:none;}
 #recordWheelTitle{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);}
 .record-wheel-header button{appearance:none;position:absolute;top:50%;transform:translateY(-50%);width:24px;height:24px;padding:0;margin:0;border:0;border-radius:50%;background:rgba(128,128,128,.12);color:inherit;display:grid;place-items:center;pointer-events:auto;}
 .record-wheel-header [data-wheel-cancel]{left:4px;}.record-wheel-header [data-wheel-confirm]{right:4px;}
 .record-wheel-header svg{width:14px;height:14px;}
 .record-wheel-header button:focus-visible{outline:2px solid var(--c-text-secondary,#999);outline-offset:-2px;}
 .record-wheel-list:focus-visible{outline:none;}
 .record-wheel-list:focus-visible .record-wheel-option[aria-selected=true]{outline:1px solid var(--c-text-secondary,#999);outline-offset:-2px;border-radius:999px;}
 .record-wheel-window{height:calc(var(--record-wheel-row)*3);position:relative;width:100%;}
 .record-wheel-window::before{content:'';position:absolute;top:var(--record-wheel-row);left:0;right:0;height:var(--record-wheel-row);box-sizing:border-box;border:1px solid var(--c-border,#444);border-radius:999px;background:var(--c-bg-elevated,#181818);pointer-events:none;}
 .record-wheel-unit{display:none;}
 .record-wheel-list{position:relative;height:calc(var(--record-wheel-row)*3);box-sizing:border-box;overflow-y:auto;overscroll-behavior:contain;scroll-snap-type:y mandatory;scrollbar-width:none;padding:var(--record-wheel-row) 0;touch-action:pan-y;-webkit-mask-image:linear-gradient(transparent,#000 33.33%,#000 66.67%,transparent);mask-image:linear-gradient(transparent,#000 33.33%,#000 66.67%,transparent);}
 .record-wheel-list::-webkit-scrollbar{display:none;}
 .record-wheel-option{height:var(--record-wheel-row);line-height:var(--record-wheel-row);text-align:center;scroll-snap-align:center;font-size:21px;font-weight:400;color:inherit;opacity:.5;cursor:pointer;user-select:none;}
 .record-wheel-option[aria-selected=true]{font-weight:700;opacity:1;}
 .record-wheel-sheet.wheel-narrow .record-wheel-header button{width:18px;height:28px;}
 .record-wheel-sheet.wheel-narrow .record-wheel-header [data-wheel-cancel]{left:2px;}
 .record-wheel-sheet.wheel-narrow .record-wheel-header [data-wheel-confirm]{right:2px;}
 .record-wheel-sheet.wheel-narrow .record-wheel-option{font-size:18px;}
 .record-wheel-sheet.wheel-narrow .record-wheel-header svg{width:12px;height:12px;}
 `;document.head.append(style);
 const overlay=document.createElement('div');overlay.className='record-wheel-overlay';overlay.hidden=true;
 overlay.innerHTML='<section class="record-wheel-sheet" role="dialog" aria-modal="true" aria-labelledby="recordWheelTitle"><div class="record-wheel-header"><button type="button" data-wheel-cancel aria-label="취소"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m6 6 12 12M18 6 6 18"/></svg></button><span id="recordWheelTitle"></span><button type="button" data-wheel-confirm aria-label="선택한 값 적용"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 4 4L19 6"/></svg></button></div><div class="record-wheel-window"><div class="record-wheel-list" role="listbox" tabindex="0"></div><span class="record-wheel-unit"></span></div></section>';
 document.body.append(overlay);
 const list=overlay.querySelector('.record-wheel-list'),confirm=overlay.querySelector('[data-wheel-confirm]');
 let source=null,sourceVisibility='',values=[],selected=0,paintFrame=0,anchorFrame=0,rowSize=44,background=[];
 const sheet=overlay.querySelector('.record-wheel-sheet');
 function position(){
  if(!source || overlay.hidden)return;
  const r=source.getBoundingClientRect();
  const nextSize=r.height||44;
  if(Math.abs(nextSize-rowSize)>.1){rowSize=nextSize;sheet.style.setProperty('--record-wheel-row',rowSize+'px');list.scrollTop=selected*rowSize;}
  sheet.classList.toggle('wheel-narrow',r.width<100);sheet.style.width=r.width+'px';sheet.style.left=Math.max(0,Math.min(innerWidth-r.width,r.left))+'px';
  sheet.style.top=Math.max(4,Math.min(innerHeight-rowSize*3-4,r.top+r.height/2-rowSize*1.5))+'px';
 }
 window.addEventListener('resize',position);window.visualViewport?.addEventListener('resize',position);
 function paint(){
  selected=Math.max(0,Math.min(values.length-1,Math.round(list.scrollTop/rowSize)));
  [...list.children].forEach((row,i)=>{row.setAttribute('aria-selected',String(i===selected));const distance=Math.max(-3,Math.min(3,i-list.scrollTop/rowSize));row.style.transform=`perspective(300px) rotateX(${distance*-15}deg) scale(${1-Math.abs(distance)*.055})`;});
  list.setAttribute('aria-activedescendant','record-wheel-option-'+selected);
 }
 function close(apply){
  if(overlay.hidden)return;
  paint();const input=source;if(input)input.style.visibility=sourceVisibility;source=null;overlay.hidden=true;cancelAnimationFrame(paintFrame);cancelAnimationFrame(anchorFrame);
  background.forEach(([el,inert])=>{el.inert=inert;});background=[];
  if(apply && input?.isConnected){input.value=String(values[selected]);input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));}
  if(input?.isConnected){const bar=input.closest('.recordFloatBar');if(bar){bar.tabIndex=-1;bar.focus({preventScroll:true});}}
 }
 function open(input,config){
  if(!overlay.hidden)close(false);
  document.activeElement?.blur();source=input;sourceVisibility=input.style.visibility;input.style.opacity='';input.style.visibility='hidden';
  const [,step,min,max,title,unit]=config;values=Array.from({length:(max-min)/step+1},(_,i)=>min+i*step);
  const current=Number.parseFloat(input.value);selected=Number.isFinite(current)?Math.max(0,Math.min(values.length-1,Math.round((current-min)/step))):0;
  overlay.querySelector('#recordWheelTitle').textContent=title;overlay.querySelector('.record-wheel-unit').textContent=unit;list.setAttribute('aria-label',title);
  list.replaceChildren(...values.map((value,i)=>{const row=document.createElement('div');row.className='record-wheel-option';row.id='record-wheel-option-'+i;row.setAttribute('role','option');row.textContent=value;row.addEventListener('click',()=>{list.scrollTop=i*rowSize;paint();});return row;}));
  overlay.hidden=false;position();list.scrollTop=selected*rowSize;paint();
  const until=performance.now()+400;
  const follow=now=>{position();if(now<until && source)anchorFrame=requestAnimationFrame(follow);};anchorFrame=requestAnimationFrame(follow);
  background=[...document.body.children].filter(el=>el!==overlay && !['SCRIPT','STYLE'].includes(el.tagName)).map(el=>[el,el.inert]);background.forEach(([el])=>{el.inert=true;});
  confirm.focus({preventScroll:true});
 }
 list.addEventListener('scroll',()=>{cancelAnimationFrame(paintFrame);paintFrame=requestAnimationFrame(paint);},{passive:true});
 list.addEventListener('keydown',event=>{
  let index=selected;
  if(event.key==='ArrowDown')index++;else if(event.key==='ArrowUp')index--;else if(event.key==='Home')index=0;else if(event.key==='End')index=values.length-1;else return;
  event.preventDefault();list.scrollTop=Math.max(0,Math.min(values.length-1,index))*rowSize;paint();
 });
 confirm.addEventListener('click',()=>close(true));overlay.querySelector('[data-wheel-cancel]').addEventListener('click',()=>close(false));
 overlay.addEventListener('click',event=>{if(event.target===overlay)close(false);});
 overlay.addEventListener('touchmove',event=>{if(!event.target.closest('.record-wheel-list') && event.cancelable)event.preventDefault();},{passive:false});
 overlay.addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close(false);}
  if(event.key==='Tab'){event.stopPropagation();const controls=[overlay.querySelector('[data-wheel-cancel]'),confirm,list],index=controls.indexOf(document.activeElement);event.preventDefault();controls[(index+(event.shiftKey?-1:1)+controls.length)%controls.length].focus();}
 });
 let gesture=null,timer=0;
 function cancelGesture(){clearTimeout(timer);gesture=null;}
 function begin(input,config,x,y,kind){
  cancelGesture();gesture={input,config,x,y,kind,fired:false,cancelled:false};
  timer=setTimeout(()=>{if(gesture && !gesture.cancelled){gesture.fired=true;open(input,config);}},450);
 }
 function move(x,y){if(gesture && Math.hypot(x-gesture.x,y-gesture.y)>10){clearTimeout(timer);gesture.cancelled=true;}}
 function end(){
  if(!gesture)return;const g=gesture;cancelGesture();
  if(!g.fired && !g.cancelled){g.input.dispatchEvent(new Event('mf-short-tap'));if(document.activeElement!==g.input)g.input.focus({preventScroll:true});}
 }
 for(const config of configs){
  const input=document.getElementById(config[0]);if(!input)continue;
  input.addEventListener('touchstart',event=>{if(event.touches.length!==1){cancelGesture();return;}event.preventDefault();event.stopImmediatePropagation();const t=event.touches[0];begin(input,config,t.clientX,t.clientY,'touch');},{capture:true,passive:false});
  input.addEventListener('touchmove',event=>{if(!gesture)return;event.stopImmediatePropagation();if(event.touches.length!==1){cancelGesture();return;}move(event.touches[0].clientX,event.touches[0].clientY);},{capture:true,passive:false});
  input.addEventListener('touchend',event=>{if(!gesture)return;event.preventDefault();event.stopImmediatePropagation();if(!event.touches.length)end();},{capture:true,passive:false});
  input.addEventListener('touchcancel',cancelGesture,{capture:true});
  input.addEventListener('pointerdown',event=>{if(event.pointerType!=='mouse' || event.button!==0)return;event.preventDefault();begin(input,config,event.clientX,event.clientY,'mouse');});
  input.addEventListener('click',event=>{if(event.detail>0){event.preventDefault();event.stopImmediatePropagation();}},{capture:true});
  input.addEventListener('contextmenu',event=>event.preventDefault());
 }
 document.addEventListener('pointermove',event=>{if(gesture?.kind==='mouse')move(event.clientX,event.clientY);});
 document.addEventListener('pointerup',event=>{if(gesture?.kind==='mouse' && event.button===0)end();});
 document.addEventListener('pointercancel',cancelGesture);
 window.addEventListener('blur',()=>{cancelGesture();if(!overlay.hidden)close(false);});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelGesture();close(false);}});
})();
