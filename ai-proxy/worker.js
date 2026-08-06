// Cloudflare Worker: MuscleFlow(TTT) 앱의 AI 챗봇이 쓰는 Gemini API 프록시.
//
// 이 앱(index.html)은 서버 없는 정적 GitHub Pages 사이트라서, Gemini API 키를
// 코드에 직접 넣으면 페이지 소스로 누구나 볼 수 있다. 이 Worker를 대신 배포해서
// 키를 여기(Cloudflare 쪽 Secret)에만 두고, 앱은 이 Worker의 URL만 호출한다.
//
// 배포 방법은 ai-proxy/README.md 참고.

const MODEL = "gemini-2.5-flash-lite"; // 무료 티어: 하루 1,000회. 다른 모델로 바꾸려면 이 줄만 수정.

const SYSTEM_INSTRUCTION =
  "너는 'MuscleFlow'라는 운동/식단 기록 앱 안에 들어있는 보조 AI야. " +
  "사용자는 한국어로 질문하니 한국어로 답해. 특히 음식 영양성분(탄수화물/단백질/지방/칼로리), " +
  "식단 구성, 운동 관련 질문에 강점을 두고 답변해. " +
  "모바일 화면에서 읽는다는 걸 감안해서 너무 길게 늘어놓지 말고, 핵심 위주로 간결하게 답해. " +
  "표가 필요하면 마크다운 표 대신 '- 항목: 값' 같은 줄바꿈 목록으로 정리해줘(모바일에서 표는 깨져 보임). " +
  "확실하지 않은 수치는 '대략'이라고 표시하고, 의학적 진단이 필요한 질문에는 전문가 상담을 권해.";

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin");

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(origin) });
    }
    if (request.method !== "POST") {
      return json({ error: "POST만 지원합니다." }, 405, origin);
    }

    let body;
    try {
      body = await request.json();
    } catch (e) {
      return json({ error: "요청 본문이 올바른 JSON이 아닙니다." }, 400, origin);
    }

    const message = typeof body.message === "string" ? body.message.trim() : "";
    if (!message) {
      return json({ error: "message가 비어있습니다." }, 400, origin);
    }
    const history = Array.isArray(body.history) ? body.history : [];

    // 클라이언트 role("user"/"model")을 Gemini contents 포맷으로 변환
    const contents = history
      .filter((h) => h && typeof h.text === "string" && (h.role === "user" || h.role === "model"))
      .map((h) => ({ role: h.role, parts: [{ text: h.text }] }));
    contents.push({ role: "user", parts: [{ text: message }] });

    const geminiUrl =
      `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${env.GEMINI_API_KEY}`;

    let resp;
    try {
      resp = await fetch(geminiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents,
          systemInstruction: { parts: [{ text: SYSTEM_INSTRUCTION }] },
        }),
      });
    } catch (e) {
      return json({ error: "AI 서버에 연결할 수 없습니다." }, 502, origin);
    }

    if (!resp.ok) {
      const errText = await resp.text().catch(() => "");
      return json({ error: `AI 응답 오류 (${resp.status})`, detail: errText.slice(0, 300) }, 502, origin);
    }

    const data = await resp.json();
    const answer = data?.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("") || "";
    if (!answer) {
      return json({ error: "AI가 답변을 생성하지 못했습니다." }, 502, origin);
    }

    return json({ answer }, 200, origin);
  },
};
