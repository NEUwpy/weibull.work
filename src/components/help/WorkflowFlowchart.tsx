import { cn } from '@/lib/utils'

export interface FlowStep {
  label: string
  desc?: string
  status?: 'done' | 'partial' | 'todo'
}

interface WorkflowFlowchartProps {
  steps: FlowStep[]
  title?: string
}

export default function WorkflowFlowchart({ steps, title }: WorkflowFlowchartProps) {
  return (
    <div>
      {title && (
        <h3 className="text-lg font-bold text-slate-900 mb-6">{title}</h3>
      )}
      <div className="flex flex-wrap items-center justify-center gap-0">
        {steps.map((step, i) => (
          <div key={step.label} className="flex items-center">
            {/* Step node */}
            <div
              className={cn(
                'flex flex-col items-center text-center px-4 py-3 rounded-xl min-w-[120px] max-w-[160px] border transition-all',
                step.status === 'done' && 'bg-blue-50 border-blue-200',
                step.status === 'partial' && 'bg-amber-50 border-amber-200',
                step.status === 'todo' && 'bg-slate-50 border-slate-200',
                !step.status && 'bg-blue-50 border-blue-200',
              )}
            >
              <span
                className={cn(
                  'text-sm font-bold leading-tight',
                  step.status === 'todo' ? 'text-slate-400' : 'text-slate-900',
                )}
              >
                {step.label}
              </span>
              {step.desc && (
                <span className={cn(
                  'text-[11px] mt-1 leading-tight',
                  step.status === 'todo' ? 'text-slate-300' : 'text-slate-500',
                )}>
                  {step.desc}
                </span>
              )}
              {step.status === 'todo' && (
                <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded mt-1.5">
                  待完成
                </span>
              )}
            </div>

            {/* Arrow connector */}
            {i < steps.length - 1 && (
              <div className="flex items-center px-1 shrink-0">
                <div className="w-6 h-0.5 bg-slate-300" />
                <div className="w-0 h-0 border-t-[5px] border-t-transparent border-b-[5px] border-b-transparent border-l-[6px] border-l-slate-300" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
