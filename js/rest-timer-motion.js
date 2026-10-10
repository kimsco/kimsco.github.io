/* One visual layer moves the time, state icon and pill with the same progress. */
(function(root){
  'use strict';
  const rect = el => {
    const r=el.getBoundingClientRect();
    return {left:r.left,top:r.top,width:r.width,height:r.height};
  };
  const textRect = el => {
    const range=document.createRange();range.selectNodeContents(el);
    const r=range.getBoundingClientRect();
    return {left:r.left,top:r.top,width:r.width,height:r.height};
  };
  const mix = (a,b,t) => Object.fromEntries(['left','top','width','height'].map(k=>[k,a[k]+(b[k]-a[k])*t]));
  // The existing Material curve: cubic-bezier(0.4, 0, 0.2, 1).
  function ease(x){
    let lo=0,hi=1,t=x;
    for(let i=0;i<16;i++){
      const v=3*(1-t)*(1-t)*t*.4+3*(1-t)*t*t*.2+t*t*t;
      if(v<x) lo=t; else hi=t;
      t=(lo+hi)/2;
    }
    return 3*(1-t)*t*t+t*t*t;
  }
  function create({bar,bg,fullDisplay,fullValue,fullButton,mini,readIcon,readText}){
    let frameId=0,layer=null,state=null;
    function cancel(){
      cancelAnimationFrame(frameId);frameId=0;
      layer?.remove();layer=null;state=null;
      fullDisplay.style.visibility='';fullButton.style.visibility='';mini.style.visibility='';
      mini.style.transition='';mini.style.opacity='';
      for(const k of ['transition','left','top','width','height','right','bottom']) bg.style[k]='';
      bg.style.removeProperty('--rtimer-card-h');
    }
    function snapshot(){return state && JSON.parse(JSON.stringify(state));}
    function start({from,to,duration=260,onFinish}){
      cancel();
      layer=document.createElement('div');layer.className='mf-rest-motion';
      layer.style.cssText='position:absolute;inset:0;pointer-events:none;z-index:2';
      const time=document.createElement('div');time.className='mf-rest-motion-time';
      const style=getComputedStyle(fullValue);
      time.style.cssText='position:absolute;display:flex;align-items:center;justify-content:center;transform-origin:center;white-space:nowrap';
      for(const key of ['fontFamily','fontSize','fontWeight','letterSpacing','color','fontVariantNumeric']) time.style[key]=style[key];
      time.style.width=to.fullTime.width+'px';time.style.height=to.fullTime.height+'px';
      const icon=document.createElement('div');icon.className='mf-rest-motion-icon';
      icon.style.cssText='position:absolute;display:flex;align-items:center;justify-content:center;transform-origin:center;width:22px;height:22px';
      icon.style.color=getComputedStyle(fullButton).color;
      let iconSource;
      layer.append(time,icon);bar.appendChild(layer);
      fullDisplay.style.visibility='hidden';fullButton.style.visibility='hidden';mini.style.visibility='hidden';
      bg.style.transition='none';bg.style.right='auto';bg.style.bottom='auto';
      const startAt=performance.now();
      function draw(t){
        const b=rect(bar);
        state={pill:mix(from.pill,to.pill,t),time:mix(from.time,to.time,t),icon:mix(from.icon,to.icon,t),weight:from.weight+(to.weight-from.weight)*t};
        for(const key of ['left','top','width','height']){
          const origin=key==='left'?b.left:key==='top'?b.top:0;
          bg.style[key]=(state.pill[key]-origin)+'px';
        }
        bg.style.setProperty('--rtimer-card-h',state.pill.height+'px');
        time.textContent=readText();
        time.style.fontWeight=String(Math.round(from.weight+(to.weight-from.weight)*t));
        for(const [el,r,w,h] of [[time,state.time,to.fullTime.width,to.fullTime.height],[icon,state.icon,22,22]]){
          el.style.left=(r.left+r.width/2-b.left-w/2)+'px';
          el.style.top=(r.top+r.height/2-b.top-h/2)+'px';
          el.style.transform=`scale(${r.width/w},${r.height/h})`;
        }
        const source=readIcon();
        if(source!==iconSource){
          iconSource=source;const svg=source.cloneNode(true);svg.removeAttribute('id');svg.classList.remove('hidden');
          svg.setAttribute('width','22');svg.setAttribute('height','22');icon.replaceChildren(svg);
        }
      }
      draw(0); // Commit the exact previous frame before the first animation frame.
      function tick(now){
        const progress=Math.min(1,(now-startAt)/duration);
        draw(ease(progress));
        if(progress<1) frameId=requestAnimationFrame(tick);
        else {cancel();onFinish();}
      }
      frameId=requestAnimationFrame(tick);
    }
    return {start,cancel,snapshot};
  }
  root.MFRestMotion={create,rect,textRect};
})(window);
