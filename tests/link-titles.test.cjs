const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function fixture(fetch){
 const root={fetch,URL,AbortController,setTimeout,clearTimeout};
 vm.runInNewContext(fs.readFileSync('js/link-titles.js','utf8'),root);
 return root.MFLinkTitles;
}
test('link titles normalize web URLs and reject executable or credentialed URLs',()=>{
 const api=fixture(()=>{});
 assert.equal(api.normalizeUrl('youtu.be/abc'),'https://youtu.be/abc');
 for(const value of ['javascript:alert(1)','data:text/html,bad','https://user:pass@example.com','']) assert.equal(api.normalizeUrl(value),'');
 assert.equal(api.cleanTitle('  제목\n 두번째  '),'제목 두번째');
});
test('YouTube oEmbed title wins and duplicate in-flight requests coalesce',async()=>{
 let calls=0;const api=fixture(async()=>{calls++;return {ok:true,json:async()=>({title:'운동 영상'})};});
 const titles=await Promise.all([api.getTitle('https://youtu.be/abc'),api.getTitle('https://youtu.be/abc')]);
 assert.deepEqual(titles,['운동 영상','운동 영상']);assert.equal(calls,1);
});
test('page metadata works for other pages and YouTube failures fall back',async()=>{
 const calls=[];const api=fixture(async url=>{calls.push(url);return {ok:!url.includes('oembed'),json:async()=>({status:'success',data:{title:'페이지 제목'}})};});
 assert.equal(await api.getTitle('https://youtube.com/shorts/abc'),'페이지 제목');
 assert.ok(calls[1].startsWith('https://api.microlink.io/'));
 assert.equal(await api.getTitle('https://example.com/guide'),'페이지 제목');
});
test('blocked, invalid and generic metadata leaves the original address usable',async()=>{
 let calls=0;const api=fixture(async()=>{calls++;throw Error('offline');});
 assert.equal(await api.getTitle('https://example.com'), '');
 for(const url of ['http://localhost/page','http://192.168.1.1','https://foo.local/a','https://example.test/a']) assert.equal(await api.getTitle(url),'');
 assert.equal(calls,1);
 const generic=fixture(async()=>({ok:true,json:async()=>({status:'success',data:{title:'Instagram'}})}));
 assert.equal(await generic.getTitle('https://instagram.com/reel/abc'),'');
});
test('metadata queue limits concurrent requests to three',async()=>{
 let active=0,peak=0;const api=fixture(async()=>{active++;peak=Math.max(peak,active);await new Promise(r=>setTimeout(r,5));active--;return {ok:true,json:async()=>({status:'success',data:{title:'제목'}})};});
 await Promise.all(Array.from({length:9},(_,i)=>api.getTitle('https://example.com/'+i)));
 assert.equal(peak,3);
});
