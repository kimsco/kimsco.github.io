import {createRemoteJWKSet, jwtVerify} from 'jose';
import {buildPushPayload} from '@block65/webcrypto-web-push';
import {createStore, runReminder, koreaDay, koreaMinute, timestamp} from './core.mjs';

const PROJECT = 'rmpj-7ca13', ORIGIN = 'https://kimsco.github.io';
const jwks = createRemoteJWKSet(new URL('https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com'));
const json = (body, status = 200) => new Response(JSON.stringify(body), {status, headers: {
  'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ORIGIN, 'Vary': 'Origin',
  'Access-Control-Allow-Methods': 'GET,PUT,POST,DELETE,OPTIONS', 'Access-Control-Allow-Headers': 'Authorization,Content-Type', 'Cache-Control': 'no-store'
}});
export async function verifyUser(request) {
  const token = /^Bearer (\S+)$/.exec(request.headers.get('Authorization') || '')?.[1];
  if (!token) throw Error('unauthorized');
  const {payload} = await jwtVerify(token, jwks, {issuer: 'https://securetoken.google.com/' + PROJECT, audience: PROJECT, algorithms: ['RS256'], clockTolerance: 30});
  if (!payload.sub || payload.sub.length > 128) throw Error('unauthorized');
  return payload.sub;
}
function bytes(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]+$/.test(value)) throw Error('invalid-subscription');
  return Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
}
async function keysReady(env) {
  if(!env.DB||!env.VAPID_PUBLIC_KEY||!env.VAPID_PRIVATE_KEY)return false;
  try{
    const raw=bytes(env.VAPID_PUBLIC_KEY),encode=value=>btoa(String.fromCharCode(...value)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');
    if(raw.length!==65||raw[0]!==4||bytes(env.VAPID_PRIVATE_KEY).length!==32)return false;
    const jwk={kty:'EC',crv:'P-256',x:encode(raw.slice(1,33)),y:encode(raw.slice(33,65))};
    const privateKey=await crypto.subtle.importKey('jwk',{...jwk,d:env.VAPID_PRIVATE_KEY},{name:'ECDSA',namedCurve:'P-256'},false,['sign']);
    const publicKey=await crypto.subtle.importKey('jwk',jwk,{name:'ECDSA',namedCurve:'P-256'},false,['verify']);
    const algorithm={name:'ECDSA',hash:'SHA-256'},probe=new TextEncoder().encode('TTT VAPID setup');
    return crypto.subtle.verify(algorithm,publicKey,await crypto.subtle.sign(algorithm,privateKey,probe),probe);
  }catch(_){return false;}
}
export function validSubscription(value) {
  const url = new URL(value?.endpoint);
  // iOS-only. Never fetch a user-supplied arbitrary host or redirect (SSRF).
  if (url.protocol !== 'https:' || url.hostname !== 'web.push.apple.com' || url.port || url.username || url.password || url.hash || url.href.length > 4096) throw Error('invalid-subscription');
  const publicKey = bytes(value?.keys?.p256dh), auth = bytes(value?.keys?.auth);
  if (publicKey.length !== 65 || publicKey[0] !== 4 || auth.length !== 16) throw Error('invalid-subscription');
  return {endpoint: url.href, keys: {p256dh: value.keys.p256dh, auth: value.keys.auth}, expirationTime: null};
}
export async function push(env, subscription, payload, {build = buildPushPayload, send = globalThis.fetch} = {}) {
  let stage = 'prepare';
  try {
    const request = await build({data: JSON.stringify(payload), options: {ttl: 3600, urgency: 'high'}}, subscription,
      {subject: ORIGIN, publicKey: env.VAPID_PUBLIC_KEY, privateKey: env.VAPID_PRIVATE_KEY});
    stage = 'fetch';
    return await send(subscription.endpoint, {...request, redirect: 'manual', signal: AbortSignal.timeout(10000)});
  } catch (error) {
    // Never log messages/stacks: they can contain subscription URLs or key material.
    const name = ['TypeError', 'OperationError', 'DataError', 'NotSupportedError', 'InvalidAccessError', 'TimeoutError', 'AbortError'].includes(error?.name) ? error.name : 'Error';
    console.error(JSON.stringify({event: 'reminder-send-failed', stage, name}));
    const failure = new Error('reminder-send-failed');
    failure.reminderFailure = 'failed-' + stage + '-' + name;
    throw failure;
  }
}

export function createHandler({verify = verifyUser, now = Date.now} = {}) {
  return async (request, env) => {
    if (request.headers.get('Origin') !== ORIGIN) return json({error: 'origin'}, 403);
    if (request.method === 'OPTIONS') return json({ok: true});
    const path = new URL(request.url).pathname;
    if (path === '/config' && request.method === 'GET') return json({schema: 1, publicKey: env.VAPID_PUBLIC_KEY || '', ready: await keysReady(env)});
    let uid;
    try { uid = await verify(request); } catch (_) { return json({error: 'unauthorized'}, 401); }
    if (!env.DB) return json({error: 'not-configured'}, 503);
    const store = createStore(env.DB);
    try {
      if(path==='/preferences'&&request.method==='GET')return json(await store.preference(uid));
      if (path === '/account' && request.method === 'DELETE') { await store.forget(uid); return json({ok: true}); }
      // Limit JSON bodies before buffering. No weight, reps, exercise names or history accepted.
      const text = await request.text(); if (text.length > 8192) return json({error: 'too-large'}, 413);
      const body = JSON.parse(text);
      if(path==='/preferences'&&request.method==='PUT'){
        if(Object.keys(body).some(k=>k!=='minuteOfDay')||!Number.isInteger(body.minuteOfDay)||body.minuteOfDay<0||body.minuteOfDay>=1440)throw Error('invalid-time');
        await store.savePreference(uid,body.minuteOfDay,koreaDay(now()+(body.minuteOfDay<koreaMinute(now())?86400000:0)));return json({ok:true,minuteOfDay:body.minuteOfDay});
      }
      if (path === '/activity' && request.method === 'POST') {
        if (Object.keys(body).some(k => !['day', 'hasRecord', 'hasLocalRecord', 'deviceId', 'basis'].includes(k)) || body.day !== koreaDay(now()) || typeof body.hasRecord !== 'boolean') throw Error('invalid-activity');
        const basis = timestamp(body.basis), ms = Date.parse(basis);
        if (ms > now() + 30000 || ms < now() - 15 * 60000) throw Error('stale-activity');
        if(body.deviceId!==undefined&&!/^[A-Za-z0-9_-]{1,128}$/.test(body.deviceId))throw Error('invalid-device');
        if(body.hasLocalRecord!==undefined&&typeof body.hasLocalRecord!=='boolean')throw Error('invalid-activity');
        await store.activity(uid, body.day, body.hasRecord, basis, body.deviceId, body.hasLocalRecord); return json({ok: true});
      }
      if (path === '/device' && ['PUT', 'DELETE'].includes(request.method)) {
        if (typeof body.id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(body.id)) throw Error('invalid-device');
        if (request.method === 'DELETE') await store.remove(uid, body.id);
        else {
          const result = await store.register(uid, body.id, validSubscription(body.subscription));
          if (!result.meta.changes) return json({error: 'device-limit'}, 409);
        }
        return json({ok: true});
      }
      return json({error: 'not-found'}, 404);
    } catch (_) { return json({error: 'request-failed'}, 400); }
  };
}
export default {
  fetch: createHandler(),
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(runReminder({store: createStore(env.DB), time: controller.scheduledTime,
      enabled: env.REMINDERS_ENABLED === 'true', send: (subscription, message) => push(env, subscription, message)
    }).then(counts => console.log(JSON.stringify(counts))).catch(() => console.error('reminder-job-failed')));
  }
};
