import {appendFile} from 'node:fs/promises';
import {createSender, firestoreStore, PROJECT_ID} from './sender.mjs';

async function main() {
  // Only explicitly dispatched main-branch runs by the repository owner may send.
  if (process.env.GITHUB_EVENT_NAME !== 'workflow_dispatch' || process.env.GITHUB_REF !== 'refs/heads/main' ||
      process.env.GITHUB_REPOSITORY !== 'kimsco/kimsco.github.io' || process.env.GITHUB_ACTOR !== 'kimsco') {
    throw Error('저장소 소유자의 main 수동 실행에서만 발송할 수 있습니다.');
  }
  const testUid = process.env.PUSH_TEST_UID;
  if (!testUid || /[\s/]/.test(testUid)) throw Error('GitHub Variables에 PUSH_TEST_UID를 먼저 설정해주세요.');
  let credentials;
  try { credentials = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_JSON || ''); }
  catch { throw Error('GitHub Secrets에 FIREBASE_SERVICE_ACCOUNT_JSON을 등록해주세요.'); }
  delete process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (credentials.project_id !== PROJECT_ID || !credentials.private_key || !credentials.client_email) {
    throw Error('rmpj-7ca13 프로젝트의 발송 서비스 계정이 필요합니다.');
  }
  const {initializeApp, cert, deleteApp} = await import('firebase-admin/app');
  const {getFirestore, FieldPath} = await import('firebase-admin/firestore');
  const {getMessaging} = await import('firebase-admin/messaging');
  const app = initializeApp({credential: cert(credentials), projectId: PROJECT_ID});
  try {
    const sender = createSender({store: firestoreStore(getFirestore(app), () => FieldPath.documentId()), send: message => getMessaging(app).send(message)});
    const mode = process.env.PUSH_MODE;
    let result;
    if (mode === 'test') result = await sender.test({runId: process.env.GITHUB_RUN_ID, title: process.env.PUSH_TITLE, body: process.env.PUSH_BODY, testUid});
    else if (mode === 'approved-broadcast') result = await sender.broadcast({testRunId: process.env.PUSH_TEST_RUN_ID, approval: process.env.PUSH_APPROVAL, runId: process.env.GITHUB_RUN_ID, testUid});
    else throw Error('지원하지 않는 발송 모드입니다.');
    const summary = `알림 ${mode}\n\n캠페인: ${result.campaignId}\n\nFCM 접수 ${result.accepted}건 / 무효 ${result.invalid}건 / 실패 ${result.failed}건 / 제외 ${result.skipped}건\n\n접수 성공은 실제 기기 표시를 보장하지 않습니다.${mode === 'test' ? '\n\n폰에서 수신과 내용을 확인한 뒤, 이 실행 번호로 별도의 전체 발송을 승인하세요.' : ''}\n`;
    if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, summary);
    console.log(summary);
    if (result.failed) process.exitCode = 1;
  } finally {
    await deleteApp(app);
  }
}

main().catch(error => {
  // SDK error messages may contain tokens or request bodies. Do not print them.
  const code = typeof error?.code === 'string' || typeof error?.code === 'number' ? String(error.code) : '';
  const known = /^(GitHub|저장소|rmpj|지원하지|유효한|제목은|PUSH_TEST_UID|이미 실행|테스트 발송|폰에서|테스트 실행|이 계정|테스트 내용|단일 발송)/.test(error?.message || '');
  console.error(known ? error.message : `발송 실패${/^[a-zA-Z0-9_/-]+$/.test(code) ? ' (' + code + ')' : ''}. 연결 권한과 Firestore 색인을 확인해주세요. 원문 오류는 토큰 보호를 위해 출력하지 않습니다.`);
  process.exitCode = 1;
});
