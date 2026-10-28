/* Shared, cancellable return-to-top motion for the two record tabs. */
(()=>{
 'use strict';
 const read=()=>window.MFRecordScrollContext?.()||null;
 const same=(a,b)=>!!a&&!!b&&a.el===b.el&&a.key===b.key&&a.owner===b.owner;
 const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
 let frame=0,refreshFrame=0,moving=null;
 const button=document.createElement('button');
 button.id='recordScrollTop';button.type='button';button.className='record-scroll-top';
 button.setAttribute('aria-label','기록 목록 맨 위로 이동');button.setAttribute('aria-hidden','true');button.disabled=true;
 button.innerHTML='<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
 document.body.appendChild(button);
 function stop(){cancelAnimationFrame(frame);frame=0;moving=null;}
 function render(){
  refreshFrame=0;
  const context=read();
  if(moving&&!same(context,moving))stop();
  const visible=!!context&&context.el.scrollTop>100;
  button.classList.toggle('visible',visible);button.disabled=!visible;
  button.setAttribute('aria-hidden',String(!visible));
  if(!visible){if(document.activeElement===button)button.blur();return;}
  const rect=context.el.getBoundingClientRect(),anchor=context.anchor?.getBoundingClientRect();
  button.style.top=Math.round(Math.max(rect.top,anchor?.bottom||0)+10)+'px';
  button.style.left=Math.round((rect.left+rect.right)/2)+'px';
 }
 function refresh(){if(!refreshFrame)refreshFrame=requestAnimationFrame(render);}
 function top(context){
  stop();
  if(!same(context,read()))return;
  const el=context.el,from=Math.max(0,el.scrollTop);
  if(from<=0){refresh();return;}
  if(reduced()){el.scrollTop=0;refresh();return;}
  moving=context;
  const duration=Math.min(400,280+from*.035),start=performance.now();
  function step(now){
   if(!same(context,read())){stop();refresh();return;}
   const t=Math.min(1,(now-start)/duration);
   el.scrollTop=from*Math.pow(1-t,3);
   if(t<1){frame=requestAnimationFrame(step);}else{el.scrollTop=0;frame=0;moving=null;}
   refresh();
  }
  frame=requestAnimationFrame(step);
 }
 window.MFRecordScroll={
  capture(el){const context=read();return context?.el===el?context:null;},
  afterSave(context){if(context)top(context);},
  refresh
 };
 button.addEventListener('click',()=>top(read()));
 document.addEventListener('scroll',refresh,{capture:true,passive:true});
 for(const name of ['touchstart','wheel','pointerdown'])document.addEventListener(name,stop,{capture:true,passive:true});
 document.addEventListener('keydown',event=>{if(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(event.key))stop();},{capture:true});
 window.addEventListener('resize',refresh);
 window.visualViewport?.addEventListener('resize',refresh);
 const observer=new MutationObserver(refresh);
 const nodes=document.querySelectorAll('.tabContent, #exercise-screen, #exercise-detail-screen, [id$="Overlay"], [id$="Modal"], .exercise-ref-modal-overlay');
 nodes.forEach(el=>observer.observe(el,{attributes:true,attributeFilter:['class','style','hidden']}));
 observer.observe(document.documentElement,{attributes:true,attributeFilter:['class','style']});
 const resize=new ResizeObserver(refresh);
 ['tab2','tab4'].forEach(id=>{const el=document.getElementById(id);if(el)resize.observe(el);});
 render();
})();
