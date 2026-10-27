import type { AtomicStatus } from '@/lib/method-status'

export interface MethodBuildStatusProps {
  label: string
  status: AtomicStatus
  reason?: string
  evidence?: string[]
}

const STATUS_DISPLAY: Record<
  AtomicStatus,
  { text: string; dotColor: string; bgColor: string; textColor: string }
> = {
  todo: {
    text: '未开始',
    dotColor: 'bg-slate-300',
    bgColor: 'bg-slate-50 border-slate-200',
    textColor: 'text-slate-400',
  },
  in_progress: {
    text: '进行中',
    dotColor: 'bg-amber-400',
    bgColor: 'bg-amber-50 border-amber-200',
    textColor: 'text-amber-700',
  },
  done: {
    text: '已完成',
    dotColor: 'bg-emerald-400',
    bgColor: 'bg-emerald-50 border-emerald-200',
    textColor: 'text-emerald-700',
  },
  blocked: {
    text: '受阻',
    dotColor: 'bg-red-400',
    bgColor: 'bg-red-50 border-red-200',
    textColor: 'text-red-700',
  },
  not_applicable: {
    text: '不适用',
    dotColor: 'bg-blue-300',
    bgColor: 'bg-blue-50 border-blue-200',
    textColor: 'text-blue-600',
  },
}

export default function MethodBuildStatus({
  label,
  status,
  reason,
}: MethodBuildStatusProps) {
  const display = STATUS_DISPLAY[status] ?? STATUS_DISPLAY.todo

  return (
    <div
      className={`flex flex-col items-center justify-center py-16 px-6 rounded-3xl border ${display.bgColor}`}
    >
      <span
        className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold ${display.textColor} bg-white/60 border border-white/30 shadow-sm`}
      >
        <span className={`w-2 h-2 rounded-full ${display.dotColor}`} />
        {display.text}
      </span>
      <p className="mt-3 text-sm font-bold text-slate-500">{label}</p>
      {reason && (
        <p className="mt-2 max-w-md text-center text-xs text-slate-400 leading-relaxed">
          {reason}
        </p>
      )}
    </div>
  )
}
