export default function NotFound() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-slate-50 text-slate-600">
      <div className="text-center space-y-6">
        <h2 className="text-6xl font-black text-slate-200">404</h2>
        <div className="space-y-2">
          <p className="text-xl font-bold text-slate-800">页面未找到</p>
          <p className="text-slate-500">您访问的页面不存在或已被移除。</p>
        </div>
      </div>
    </div>
  )
}
