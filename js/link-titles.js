/* Public link metadata only. Saved titles remain available offline. */
(function(root){
  'use strict';
  const pending = new Map(), queue = [];
  let active = 0;
  function normalizeUrl(value){
    try {
      const text = String(value || '').trim();
      if (!text) return '';
      const url = new URL(/^[a-z][a-z\d+.-]*:/i.test(text) ? text : 'https://' + text);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return '';
      return url.href;
    } catch (_) { return ''; }
  }
  function cleanTitle(value){
    return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 240) : '';
  }
  function publicUrl(value){
    const normalized = normalizeUrl(value);
    if (!normalized) return '';
    const url = new URL(normalized), host = url.hostname.toLowerCase();
    // Do not send local addresses or authenticated URLs to a metadata service.
    if (!host.includes('.') || /^[\d.]+$/.test(host) || host.includes(':') || /\.(localhost|local|internal|test|invalid)$/.test(host) || !['','80','443'].includes(url.port)) return '';
    url.hash = '';
    return url.href;
  }
  async function json(url){
    const controller = new AbortController();
    const timer = setTimeout(()=>controller.abort(), 8000);
    try {
      const response = await fetch(url, {signal:controller.signal, credentials:'omit', referrerPolicy:'no-referrer'});
      if (!response.ok) return null;
      return await response.json();
    } catch (_) { return null; }
    finally { clearTimeout(timer); }
  }
  async function lookup(url){
    const host = new URL(url).hostname;
    if (/(^|\.)youtube\.com$/.test(host) || host === 'youtu.be') {
      const data = await json('https://www.youtube.com/oembed?format=json&url=' + encodeURIComponent(url));
      const title = cleanTitle(data?.title);
      if (title) return title;
    }
    // Microlink exposes page/Open Graph titles with CORS, without a private API key.
    const data = await json('https://api.microlink.io/?url=' + encodeURIComponent(url) + '&audio=false&video=false');
    const title = data?.status === 'success' ? cleanTitle(data.data?.title) : '';
    return /^(instagram|youtube|login|log in|로그인)(\s*[|·•—-].*)?$/i.test(title) ? '' : title;
  }
  function drain(){
    while (active < 3 && queue.length) {
      const {url, resolve} = queue.shift();
      active++;
      lookup(url).then(resolve, ()=>resolve('')).finally(()=>{active--;pending.delete(url);drain();});
    }
  }
  function getTitle(value){
    const url = publicUrl(value);
    if (!url) return Promise.resolve('');
    if (pending.has(url)) return pending.get(url);
    const result = new Promise(resolve=>queue.push({url,resolve}));
    pending.set(url,result);
    drain();
    return result;
  }
  const api = {normalizeUrl, cleanTitle, getTitle};
  root.MFLinkTitles = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
