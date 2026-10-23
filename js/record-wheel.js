/* Optional long-press wheel; short taps still use the existing input/keyboard path. */
(()=>{
 'use strict';
 const configs=[['recordWeight',5,0,500,'무게','kg'],['recordReps',1,1,60,'횟수','회'],['acc-weight',5,0,500,'무게','kg'],['acc-reps',1,1,60,'횟수','회'],['myRoutineRevealInputWeight',5,0,500,'무게','kg'],['myRoutineRevealInputReps',1,1,60,'횟수','회']];
 const style=document.createElement('style');style.textContent=`
 .record-wheel-overlay{position:fixed;inset:0;z-index:300000;background:transparent;overscroll-behavior:contain;}
 .record-wheel-overlay[hidden]{display:none;}
 .record-wheel-sheet{--record-wheel-row:44px;--wheel-safe-top:env(safe-area-inset-top,0px);--wheel-safe-bottom:env(safe-area-inset-bottom,0px);position:fixed;box-sizing:border-box;color:var(--c-text-primary,#fff);animation:record-wheel-unfold .18s cubic-bezier(.22,1,.36,1) both;}
 .record-wheel-sheet::before{content:'';position:absolute;inset:0;background:var(--wheel-fill,#202020);opacity:.5;pointer-events:none;-webkit-mask-image:linear-gradient(transparent,#000 25%,#000 calc(50% - var(--wheel-input-height)/2),transparent calc(50% - var(--wheel-input-height)/2),transparent calc(50% + var(--wheel-input-height)/2),#000 calc(50% + var(--wheel-input-height)/2),#000 75%,transparent);mask-image:linear-gradient(transparent,#000 25%,#000 calc(50% - var(--wheel-input-height)/2),transparent calc(50% - var(--wheel-input-height)/2),transparent calc(50% + var(--wheel-input-height)/2),#000 calc(50% + var(--wheel-input-height)/2),#000 75%,transparent);}
 @keyframes record-wheel-unfold{from{clip-path:inset(42.85% 0);opacity:.3;}to{clip-path:inset(0);opacity:1;}}
 @media(prefers-reduced-motion:reduce){.record-wheel-sheet{animation:none;}}
 #recordWheelTitle{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);}
 .record-wheel-source{color:transparent!important;caret-color:transparent!important;}
 .record-wheel-list:focus-visible{outline:none;}

 .record-wheel-window{height:calc(var(--record-wheel-row)*7);position:relative;width:100%;}
 .record-wheel-window::before{content:'';position:absolute;top:calc(var(--record-wheel-row)*3);left:0;right:0;height:var(--wheel-input-height,44px);transform:translateY(-50%);margin-top:calc(var(--record-wheel-row)/2);box-sizing:border-box;border:1px solid rgba(255,255,255,.65);border-radius:999px;background:transparent;pointer-events:none;}
 .record-wheel-unit{display:none;}
 .record-wheel-list{position:relative;height:calc(var(--record-wheel-row)*7);box-sizing:border-box;overflow-y:auto;overscroll-behavior:contain;scroll-snap-type:y mandatory;scrollbar-width:none;padding:calc(var(--record-wheel-row)*3) 0;touch-action:pan-y;-webkit-mask-image:linear-gradient(transparent,#000 42.85%,#000 57.15%,transparent);mask-image:linear-gradient(transparent,#000 42.85%,#000 57.15%,transparent);}
 .record-wheel-list.is-direct-drag{scroll-snap-type:none;}
 .record-wheel-list::-webkit-scrollbar{display:none;}
 .record-wheel-option{height:var(--record-wheel-row);line-height:var(--record-wheel-row);text-align:center;scroll-snap-align:center;font-size:20px;font-weight:400;color:inherit;opacity:.5;cursor:pointer;user-select:none;}
 .record-wheel-option[aria-selected=true]{font-weight:700;opacity:1;}
 .record-wheel-sheet.wheel-narrow .record-wheel-option{font-size:18px;}
 .record-wheel-sheet::before{display:none;}
 .record-wheel-list{opacity:0;mask-image:none;-webkit-mask-image:none;}
 .record-disc-face{position:fixed;inset:0;pointer-events:none;overflow:hidden;}
 .record-disc-plate{pointer-events:auto;touch-action:none;position:absolute;border-radius:50%;background:var(--wheel-fill,#202020);opacity:.5;border:1px solid rgba(160,160,160,.15);box-sizing:border-box;}
 .record-disc-number{pointer-events:auto;touch-action:none;position:absolute;text-align:center;font-size:20px;line-height:36px;height:36px;transform-origin:center;white-space:nowrap;color:var(--c-text-primary,#fff);}
 .record-disc-number.is-selected{font-weight:700;}
 `;document.head.append(style);
 const overlay=document.createElement('div');overlay.className='record-wheel-overlay';overlay.hidden=true;
 overlay.innerHTML='<div class="record-disc-face" aria-hidden="true"><div class="record-disc-plate"></div><div class="record-disc-numbers"></div></div><section class="record-wheel-sheet" role="dialog" aria-modal="true" aria-labelledby="recordWheelTitle"><span id="recordWheelTitle"></span><div class="record-wheel-window"><div class="record-wheel-list" role="listbox" tabindex="0"></div></div></section>';
 document.body.append(overlay);
 const list=overlay.querySelector('.record-wheel-list');
 let source=null,values=[],selected=0,paintFrame=0,anchorFrame=0,rowSize=44,background=[];
 const sheet=overlay.querySelector('.record-wheel-sheet');
 const face=overlay.querySelector('.record-disc-face'),plate=face.querySelector('.record-disc-plate'),numbers=face.querySelector('.record-disc-numbers');
 let discX=0,discY=0,discRadius=100;
 function position(){
  if(!source || overlay.hidden)return;
  const r=source.getBoundingClientRect();
  sheet.style.setProperty('--wheel-input-height',r.height+'px');
  discX=r.left+r.width/2;discY=r.top+r.height/2;discRadius=Math.max(65,Math.min(145,discX-10,innerWidth-discX-10));
  Object.assign(plate.style,{width:discRadius*2+'px',height:discRadius*2+'px',left:discX-discRadius+'px',top:discY-discRadius*2+'px'});
  paintDisc();
  const center=r.top+r.height/2,computed=getComputedStyle(sheet);
  const topEdge=4+(parseFloat(computed.getPropertyValue('--wheel-safe-top'))||0),bottomEdge=innerHeight-4-(parseFloat(computed.getPropertyValue('--wheel-safe-bottom'))||0);
  const nextSize=Math.max(44,Math.min((r.height||44)*1.5,66,(center-topEdge)/3.5))/2;
  if(Math.abs(nextSize-rowSize)>.1){rowSize=nextSize;sheet.style.setProperty('--record-wheel-row',rowSize+'px');list.scrollTop=selected*rowSize;}
  sheet.classList.toggle('wheel-narrow',r.width<100);sheet.style.width=r.width+'px';sheet.style.left=Math.max(0,Math.min(innerWidth-r.width,r.left))+'px';
  sheet.style.top=Math.max(topEdge,center-rowSize*3.5)+'px';
 }
 window.addEventListener('resize',position);window.visualViewport?.addEventListener('resize',position);
 function paintDisc(){
  const progress=list.scrollTop/rowSize;
  [...numbers.children].forEach((label,i)=>{
   const distance=i-progress,visible=Math.abs(distance)<=3.25;
   label.hidden=!visible;if(!visible)return;
   const angle=distance*.85,x=discX+Math.sin(angle)*discRadius,y=discY+(Math.cos(angle)-1)*discRadius;
   label.classList.toggle('is-selected',i===selected);
   Object.assign(label.style,{left:x-32+'px',top:y-18+'px',width:'64px',opacity:String(Math.max(0,1-Math.abs(distance)/3.5)),transform:`rotate(${-angle*28}deg) scale(${1-Math.abs(distance)*.07})`});
  });
 }
 function paint(){
  selected=Math.max(0,Math.min(values.length-1,Math.round(list.scrollTop/rowSize)));
  [...list.children].forEach((row,i)=>{row.setAttribute('aria-selected',String(i===selected));const distance=Math.max(-3,Math.min(3,i-list.scrollTop/rowSize));row.style.transform=`perspective(300px) rotateX(${distance*-10}deg) scale(${1-Math.abs(distance)*.055})`;});
  list.setAttribute('aria-activedescendant','record-wheel-option-'+selected);paintDisc();
 }
 function close(apply){
  if(overlay.hidden)return;
  paint();const input=source;if(input)input.classList.remove('record-wheel-source');source=null;overlay.hidden=true;cancelAnimationFrame(paintFrame);cancelAnimationFrame(anchorFrame);
  background.forEach(([el,inert])=>{el.inert=inert;});background=[];
  if(apply && input?.isConnected){input.value=String(values[selected]);input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));}
  if(input?.isConnected){const bar=input.closest('.recordFloatBar');if(bar){bar.tabIndex=-1;bar.focus({preventScroll:true});}}
 }
 function open(input,config){
  if(!overlay.hidden)close(false);
  document.activeElement?.blur();
  // Flatten the input and its ancestor backgrounds to the same opaque wheel tint.
  const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d');
  ctx.fillStyle=getComputedStyle(document.documentElement).getPropertyValue('--c-bg').trim()||'#000';ctx.fillRect(0,0,1,1);
  const layers=[];for(let el=input;el;el=el.parentElement)layers.push(getComputedStyle(el).backgroundColor);
  layers.reverse().forEach(color=>{ctx.fillStyle=color;ctx.fillRect(0,0,1,1);});
  const [red,green,blue]=ctx.getImageData(0,0,1,1).data;sheet.style.setProperty('--wheel-fill',`rgb(${red},${green},${blue})`);face.style.setProperty('--wheel-fill',`rgb(${red},${green},${blue})`);
  source=input;input.style.opacity='';input.classList.add('record-wheel-source');
  const [,step,min,max,title,unit]=config;values=Array.from({length:(max-min)/step+1},(_,i)=>max-i*step);
  const current=Number.parseFloat(input.value);selected=values.length-1-(Number.isFinite(current)?Math.max(0,Math.min(values.length-1,Math.round((current-min)/step))):0);
  overlay.querySelector('#recordWheelTitle').textContent=title+' ('+unit+')';list.setAttribute('aria-label',title);
  list.replaceChildren(...values.map((value,i)=>{const row=document.createElement('div');row.className='record-wheel-option';row.id='record-wheel-option-'+i;row.setAttribute('role','option');row.textContent=value;row.addEventListener('click',()=>{list.scrollTop=i*rowSize;paint();});return row;}));
  numbers.replaceChildren(...values.map(value=>{const label=document.createElement('span');label.className='record-disc-number';label.textContent=value;return label;}));
  overlay.hidden=false;list.classList.toggle('is-direct-drag',!!gesture?.fired);position();list.scrollTop=selected*rowSize;paint();
  const until=performance.now()+400;
  const follow=now=>{position();if(now<until && source)anchorFrame=requestAnimationFrame(follow);};anchorFrame=requestAnimationFrame(follow);
  background=[...document.body.children].filter(el=>el!==overlay && !['SCRIPT','STYLE'].includes(el.tagName)).map(el=>[el,el.inert]);background.forEach(([el])=>{if(!gesture?.fired || !el.contains(input))el.inert=true;});
  list.focus({preventScroll:true});
 }
 list.addEventListener('scroll',()=>{cancelAnimationFrame(paintFrame);paintFrame=requestAnimationFrame(paint);},{passive:true});
 list.addEventListener('keydown',event=>{
  let index=selected;
  if(event.key==='ArrowDown')index++;else if(event.key==='ArrowUp')index--;else if(event.key==='Home')index=0;else if(event.key==='End')index=values.length-1;else return;
  event.preventDefault();list.scrollTop=Math.max(0,Math.min(values.length-1,index))*rowSize;paint();
 });
 overlay.addEventListener('click',event=>{if(event.target===overlay)close(true);});
 overlay.addEventListener('touchmove',event=>{if(!event.target.closest('.record-wheel-list') && event.cancelable)event.preventDefault();},{passive:false});
 overlay.addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close(false);}
  if(event.key==='Enter'){event.preventDefault();event.stopPropagation();close(true);}
  if(event.key==='Tab'){event.preventDefault();event.stopPropagation();list.focus();}
 });
 let gesture=null,timer=0;
 function resumeDisc(x,y,kind){
  cancelGesture();gesture={fired:true,kind,originX:x,originY:y,lastX:x,lastY:y,wheelStartIndex:selected};list.classList.add('is-direct-drag');
 }
 face.addEventListener('touchstart',event=>{if(event.touches.length!==1)return;event.preventDefault();const t=event.touches[0];resumeDisc(t.clientX,t.clientY,'touch');},{passive:false});
 face.addEventListener('pointerdown',event=>{if(event.pointerType==='mouse' && event.button===0){event.preventDefault();resumeDisc(event.clientX,event.clientY,'mouse');}});

 function cancelGesture(){clearTimeout(timer);if(gesture?.fired && !overlay.hidden)background.forEach(([el])=>{el.inert=true;});gesture=null;}
 function begin(input,config,x,y,kind){
  cancelGesture();gesture={input,config,x,y,kind,lastY:y,lastX:x,fired:false,cancelled:false};
  timer=setTimeout(()=>{if(gesture && !gesture.cancelled){gesture.fired=true;open(input,config);gesture.originY=gesture.lastY;gesture.originX=gesture.lastX;gesture.wheelStartIndex=selected;}},200);
 }
 function move(x,y){
  if(!gesture)return;gesture.lastY=y;gesture.lastX=x;
  if(gesture.fired){list.scrollTop=Math.max(0,Math.min((values.length-1)*rowSize,gesture.wheelStartIndex*rowSize-(y-gesture.originY)-(x-gesture.originX)*.8));paint();return;}
  if(Math.hypot(x-gesture.x,y-gesture.y)>10){clearTimeout(timer);gesture.cancelled=true;}
 }
 function end(){
  if(!gesture)return;const g=gesture;cancelGesture();
  if(g.fired){paint();list.classList.remove('is-direct-drag');list.scrollTop=selected*rowSize;list.focus({preventScroll:true});}
  if(!g.fired && !g.cancelled){g.input.dispatchEvent(new Event('mf-short-tap'));if(document.activeElement!==g.input)g.input.focus({preventScroll:true});}
 }
 for(const config of configs){
  const input=document.getElementById(config[0]);if(!input)continue;
  input.addEventListener('touchstart',event=>{if(event.touches.length!==1){cancelGesture();return;}event.preventDefault();event.stopImmediatePropagation();const t=event.touches[0];begin(input,config,t.clientX,t.clientY,'touch');},{capture:true,passive:false});
  input.addEventListener('touchmove',event=>{if(!gesture)return;event.stopImmediatePropagation();if(event.touches.length!==1){cancelGesture();return;}move(event.touches[0].clientX,event.touches[0].clientY);},{capture:true,passive:false});
  input.addEventListener('touchend',event=>{if(!gesture)return;event.preventDefault();event.stopImmediatePropagation();if(!event.touches.length)end();},{capture:true,passive:false});
  input.addEventListener('touchcancel',cancelGesture,{capture:true});
  input.addEventListener('pointerdown',event=>{if(event.pointerType!=='mouse' || event.button!==0)return;event.preventDefault();input.setPointerCapture(event.pointerId);begin(input,config,event.clientX,event.clientY,'mouse');});
  input.addEventListener('click',event=>{if(event.detail>0){event.preventDefault();event.stopImmediatePropagation();}},{capture:true});
  input.addEventListener('contextmenu',event=>event.preventDefault());
 }
 // The first touch keeps targeting the original input after the wheel unfolds.
 document.addEventListener('touchmove',event=>{
  if(gesture?.kind!=='touch' || !gesture.fired)return;
  if(event.touches.length!==1){cancelGesture();return;}
  if(event.cancelable)event.preventDefault();event.stopImmediatePropagation();move(event.touches[0].clientX,event.touches[0].clientY);
 },{capture:true,passive:false});
 document.addEventListener('touchend',event=>{
  if(gesture?.kind!=='touch' || !gesture.fired || event.touches.length)return;
  if(event.cancelable)event.preventDefault();event.stopImmediatePropagation();end();
 },{capture:true,passive:false});
 document.addEventListener('pointermove',event=>{if(gesture?.kind==='mouse')move(event.clientX,event.clientY);});
 document.addEventListener('pointerup',event=>{if(gesture?.kind==='mouse' && event.button===0)end();});
 document.addEventListener('pointercancel',cancelGesture);
 window.addEventListener('blur',()=>{cancelGesture();if(!overlay.hidden)close(false);});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelGesture();close(false);}});
})();
