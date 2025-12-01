// Sidebar.jsx

// docs: [{ id, title, updatedAt }, ...]
// currentId: 현재 에디터에서 열려 있는 문서 id
// onNew: "새 글" 버튼 클릭 시 호출
// onSelect: 특정 문서 클릭 시 호출 (id를 인자로 넘겨줌)
export default function Sidebar({ docs = [], currentId, onNew, onSelect, onDelete }) {
  // "오늘 / 어제 / N일 전" 간단 포맷터
  const formatDate = (isoString) => {
    if (!isoString) return '';

    const date = new Date(isoString);
    const today = new Date();

    // 시/분/초를 버리고 날짜만 비교
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const diffMs = t - d;
    const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return '오늘';
    if (diffDays === 1) return '어제';
    if (diffDays < 7) return `${diffDays}일 전`;

    // 일주일 이상이면 YYYY.MM.DD 형식으로
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const da = String(date.getDate()).padStart(2, '0');
    return `${y}.${m}.${da}`;
  };

  return (
    <div className="h-full flex flex-col">
      {/* 상단 헤더 + 새 글 버튼 */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">문서</h3>
        <button
          onClick={onNew}
          className="text-xs h-7 px-2 rounded bg-purple-600 text-white hover:bg-purple-700"
        >
          새 글
        </button>
      </div>

      {/* 문서 리스트 */}
      {docs.length === 0 ? (
        <div className="text-xs text-gray-400">
          아직 저장된 문서가 없습니다.
          <br />
          &quot;새 글&quot;을 눌러 첫 문서를 만들어 보세요.
        </div>
      ) : (
        <ul className="text-sm text-gray-600 space-y-1">
          {docs.map((doc) => {
            const isActive = doc.id === currentId;

            return (
              <li key={doc.id} className="flex items-center">
                {/* 문서 선택 버튼 */}
                <button
                  type="button"
                  onClick={() => onSelect && onSelect(doc.id)}
                  className={`flex-1 flex flex-col items-start px-2 py-1 rounded
                    text-left hover:bg-purple-50
                    ${
                      isActive
                        ? 'bg-purple-50 border border-purple-300'
                        : 'border border-transparent'
                    }`}
                >
                  <span
                    className={`truncate w-full ${
                      isActive ? 'font-semibold text-purple-700' : ''
                    }`}
                  >
                    {doc.title || '제목 없는 문서'}
                  </span>
                  <span className="text-xs text-gray-400">
                    {formatDate(doc.updatedAt)}
                  </span>
                </button>

                {/* 삭제 버튼 */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation(); // 문서 선택 이벤트 막기
                    onDelete && onDelete(doc.id);
                  }}
                  className="ml-1 text-xs text-gray-400 hover:text-red-500"
                  title="문서 삭제"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>

      )}
    </div>
  );
}
