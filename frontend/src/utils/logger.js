export async function logEvent(eventData) {
  try {
    // 전역 버퍼 적재
    if (!window.__eventLog) window.__eventLog = [];
    window.__eventLog.push({
      ts: new Date().toISOString(),
      ...eventData,
    });

    console.log('[Event Log]', eventData);

    // HEAD 방식: 실제 서버로 로그 전송 (Vite proxy -> FastAPI)
    await fetch('/log', {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(eventData),
    });
  } catch (err) {
    console.error('Logging failed:', err);
  }
}