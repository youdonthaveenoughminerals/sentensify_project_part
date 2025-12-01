import { useState } from "react";

export default function OptionPanel({
  selectedText,
  category,
  setCategory,
  language,
  setLanguage,
  strength,
  setStrength,
  userPrompt,
  setUserPrompt,
  optEnabled,
  setOptEnabled,
  onRun,
  candidates,
  onApplyCandidate,
}) {
  const [showStrengthInfo, setShowStrengthInfo] = useState(false);     // ? 아이콘에 마우스 올렸을 때
  const [showStrengthTooltip, setShowStrengthTooltip] = useState(false); // 슬라이더 위 작은 말풍선
  const [isRunning, setIsRunning] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const isBusy = isRunning || isRefreshing;


  const strengthLabelMap = {
    0: '1단계 : 맞춤법 교정',
    1: '2단계 : 문장 구조 개선',
    2: '3단계 : 표현 방식 변경',
  };

  const toggleOption = (key) => {
    setOptEnabled((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const renderOnOffLabel = (isOn) => (
    <div className="flex items-center gap-1 text-xs">
      <span
        className={
          isOn
            ? 'font-semibold text-purple-600'
            : 'text-gray-400'
        }
      >
        ON
      </span>
      <span className="text-gray-300">/</span>
      <span
        className={
          !isOn
            ? 'font-semibold text-purple-600'
            : 'text-gray-400'
        }
      >
        OFF
      </span>
    </div>
  );

  // 실행 버튼 클릭 핸들러
  const handleClickRun = async () => {
    if (!selectedText || isRunning) return;

    setIsRunning(true);
    try {
      // App.jsx에서 내려준 handleRunCorrection 호출
      await onRun();
    } catch (e) {
      console.error('교정 실행 중 오류:', e);
      alert('교정 실행 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleClickRefresh = async () => {
    if (!selectedText || isBusy) return;

    setIsRefreshing(true);
    try {
      // isRerun = true
      await onRun(true);
    } catch (e) {
      console.error('후보 다시 생성 중 오류:', e);
      alert('후보 문장을 다시 생성하는 중 오류가 발생했습니다.');
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <aside className="h-full flex flex-col gap-4">
      {/* 교정 대상 문장 미리보기 영역 */}
      <div className="border rounded-md mt-4 p-3 text-sm text-gray-700 bg-gray-50">
        <div className="font-semibold mb-1 text-gray-600">선택된 문장</div>
        <div className="max-h-24 overflow-auto whitespace-pre-wrap">
          {selectedText ? (
            selectedText
          ) : (
            <span className="text-gray-400">
              드래그한 문장이 여기에 표시됩니다.
            </span>
          )}
        </div>
      </div>

      {/* 카테고리 */}
      <div className="option-group">
        <div className="flex items-center justify-between">
          <label className="font-medium">카테고리</label>
          <div className="flex items-center gap-2">
            {renderOnOffLabel(optEnabled.category)}
            <input
              type="checkbox"
              checked={optEnabled.category}
              onChange={() => toggleOption('category')}
            />
          </div>

        </div>

        {/* ✅ ON/OFF와 상관없이 항상 select 표시 */}
        <select
          className={`mt-2 border rounded p-2 w-full ${
            !optEnabled.category ? 'opacity-60' : ''
          }`}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="none">없음</option>
          <option value="thesis">논문</option>
          <option value="report">보고서</option>
          <option value="article">기사</option>
          <option value="marketing">마케팅</option>
          <option value="customer_service">고객 상담</option>
        </select>

      </div>

      {/* 언어 */}
      <div className="option-group">
        <div className="flex items-center justify-between">
          <label className="font-medium">언어</label>
          <div className="flex items-center gap-2">
            {renderOnOffLabel(optEnabled.language)}
            <input
              type="checkbox"
              checked={optEnabled.language}
              onChange={() => toggleOption('language')}
            />
          </div>

        </div>

        {/* ✅ ON/OFF와 상관없이 항상 select 표시 */}
        <select
          className={`mt-2 border rounded p-2 w-full ${
            !optEnabled.language ? 'opacity-60' : ''
          }`}
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="ko">한국어</option>
          <option value="en">영어</option>
          <option value="ja">일본어</option>
          <option value="zh">중국어</option>
        </select>

      </div>

      {/* 교정 강도 */}
      <div className="option-group">
        <div className="flex items-center justify-between">

          {/* ⬅️ 왼쪽 그룹 : ? 아이콘 + 라벨 */}
          <div className="flex items-center gap-2 relative">
            {/* ? 아이콘 */}
            <button
              type="button"
              className="w-5 h-5 flex items-center justify-center rounded-full border border-gray-400 text-xs text-gray-500 bg-white"
              onMouseEnter={() => setShowStrengthInfo(true)}
              onMouseLeave={() => setShowStrengthInfo(false)}
            >
              ?
            </button>

            <label className="font-medium">교정 강도</label>

            {/* ? 아이콘 큰 말풍선 */}
            {showStrengthInfo && (
              <div className="absolute left-0 top-6 w-60 bg-gray-800 text-white text-xs rounded-md shadow-lg p-2 z-20">
                <div className="font-semibold mb-1">문장 교정 강도</div>
                <p>1단계 : 맞춤법 교정</p>
                <p>2단계 : 문장 구조 개선</p>
                <p>3단계 : 표현 방식 변경</p>
                <div className="w-3 h-3 bg-gray-800 rotate-45 absolute left-4 -top-1" />
              </div>
            )}
          </div>

          {/* ➡️ 오른쪽 그룹 : ON/OFF + 체크박스 */}
          <div className="flex items-center gap-2">
            {renderOnOffLabel(optEnabled.strength)}
            <input
              type="checkbox"
              checked={optEnabled.strength}
              onChange={() => toggleOption('strength')}
              className="w-4 h-4"
            />
          </div>

        </div>

        {/* 슬라이더는 아래 그대로 유지 */}
        <div
          className="relative mt-2"
          onMouseEnter={() => setShowStrengthTooltip(true)}
          onMouseLeave={() => setShowStrengthTooltip(false)}
        >
          <input
            className={`w-full ${!optEnabled.strength ? 'opacity-60' : ''}`}
            type="range"
            min="0"
            max="2"
            step="1"
            value={strength}
            onChange={(e) => setStrength(parseInt(e.target.value))}
          />

          {showStrengthTooltip && (
            <div className="absolute -top-9 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded shadow z-10">
              {strengthLabelMap[strength]}
              <div className="w-2 h-2 bg-gray-800 rotate-45 absolute left-1/2 -translate-x-1/2 top-full -mt-1" />
            </div>
          )}
        </div>
      </div>

      {/* 서술형 요청 */}
      <div className="request-form mt-2">
        <label className="font-medium">서술형 요청사항</label>
        <textarea
          className="flex w-full mt-2 border rounded p-2 text-sm"
          placeholder="예) 더 간결하고 자연스럽게 바꿔줘"
          value={userPrompt}
          onChange={(e) => setUserPrompt(e.target.value)}
        />
      </div>

      {/* 실행 버튼 + 로딩 상태 */}
      <div className="mt-2">
        <button
          onClick={handleClickRun}
          disabled={isRunning || !selectedText}
          className={`
            h-10 w-full rounded-md bg-purple-600 text-white text-sm font-medium
            flex items-center justify-center gap-2
            transition
            ${isRunning || !selectedText
              ? 'opacity-60 cursor-not-allowed'
              : 'hover:bg-purple-700'
            }
          `}
        >
          {isRunning ? (
            <>
              <span>교정 중...</span>
              {/* Tailwind 스피너 */}
              <span className="w-4 h-4 border-2 border-white/60 border-t-transparent rounded-full animate-spin" />
            </>
          ) : (
            '실행 (교정 후보 생성)'
          )}
        </button>

        {/* 버튼 아래 안내 문구 (선택) */}
        {isRunning && (
          <p className="mt-2 text-xs text-gray-500">
            모델이 교정 후보 문장을 생성하는 중입니다...
          </p>
        )}
      </div>

      {/* 후보 리스트 + 다시 생성 버튼 */}
      {Array.isArray(candidates) && candidates.length > 0 && (
        <div className="mt-3 border rounded-md p-3 bg-purple-50 text-sm text-gray-800">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-gray-700">
              교정된 문장 후보
            </span>

            {/* ⬇️ 다시 생성 버튼 */}
            <button
              type="button"
              onClick={handleClickRefresh}
              disabled={isBusy}
              className={`
                flex items-center gap-1 text-xs px-2 py-1 rounded-md
                border border-purple-300 text-purple-700 bg-white
                ${isBusy
                  ? 'opacity-50 cursor-not-allowed'
                  : 'hover:bg-purple-100'
                }
              `}
            >
              {isRefreshing ? (
                <>
                  <span>다시 생성 중…</span>
                  <span className="w-3 h-3 border-2 border-purple-500/60 border-t-transparent rounded-full animate-spin" />
                </>
              ) : (
                <>
                  <span>다시 생성</span>
                  <span className="text-xs">⟳</span>
                </>
              )}
            </button>
          </div>

          <ul className="space-y-2 max-h-40 overflow-auto">
            {candidates.map((c, idx) => (
              <li key={idx}>
                <button
                  type="button"
                  className="w-full text-left border rounded-md px-2 py-1 bg-white hover:bg-purple-100"
                  onClick={() => onApplyCandidate(c, idx)}
                >
                  {c}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-gray-500">
            원하는 문장을 클릭하면 본문에 반영됩니다.
          </p>
        </div>
      )}
      
      <div className="mt-auto text-xs text-gray-500 pt-3 border-t">
        히스토리 / 설정
      </div>
    </aside>
  );
}
