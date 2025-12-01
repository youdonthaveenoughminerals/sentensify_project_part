export async function mockCorrect(payload) {
  console.log('[MockCorrect Input]', payload);

  // 네트워크 지연 유사 효과
  await new Promise((r) => setTimeout(r, 300 + Math.random() * 500));

  const { selected_text, strength, style_request } = payload;
  const original = (selected_text ?? '').trim();

  // 안전장치
  if (!original) {
    console.log('[MockCorrect Output] 빈 입력');
    return [];
  }

  // 기본 버전 (원문에 살짝 태그만)
  let base = original;

  // 강도에 따라 가벼운/중간/강한 교정 느낌만 다르게
  const light = `${original} (가벼운 교정)`;
  const medium = `[중간 교정] ${original.replace(/\s+/g, ' ')}`;
  const strong = `[강한 교정] ${original.toUpperCase()}`;

  // strength 값(0,1,2)에 따라 우선순위 다르게 정렬
  let candidates = [];
  switch (strength) {
    case 0:
      candidates = [light, medium, strong];
      break;
    case 2:
      candidates = [strong, medium, light];
      break;
    case 1:
    default:
      candidates = [medium, light, strong];
      break;
  }

  // 서술형 요청이 있으면 꼬리 태그로 전부에 반영
  if (style_request && style_request.trim().length > 0) {
    const tag = ` [요청사항 반영: ${style_request.trim()}]`;
    candidates = candidates.map((c) => c + tag);
  }

  console.log('[MockCorrect Output]', candidates);
  return candidates; // ✅ 문자열 배열 반환
}
