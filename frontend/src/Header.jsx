export default function Header({ onLogout }) {
  return (
    <header className="h-16 border-b px-4 flex items-center justify-between bg-white">
      <div className="flex items-center gap-2">
        <span className="text-xl font-bold text-purple-600">*</span>
        <span className="font-semibold">SENTENCIFY</span>
        <span className="ml-3 text-sm text-gray-500">Team Project – MVP</span>
      </div>

      <nav className="flex items-center gap-4 text-sm">
        <a
          className="text-gray-600 hover:text-black"
          href="http://localhost:8501"
          target="_blank"
          rel="noopener noreferrer"
        >
          관리자 대시보드
        </a>
        <a className="text-gray-600 hover:text-black" href="#">
          에디터
        </a>
        <a className="text-gray-600 hover:text-black" href="#">
          튜토리얼
        </a>
        <a className="text-gray-600 hover:text-black" href="#">
          FAQ
        </a>

        <button
          onClick={onLogout}
          className="ml-4 h-9 px-3 rounded-md bg-gray-800 text-white hover:bg-gray-900"
        >
          로그아웃
        </button>
      </nav>
    </header>
  );
}
