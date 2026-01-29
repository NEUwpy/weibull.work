"use client"

import React, { useState, useMemo, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Settings2, 
  FileText, 
  BarChart3, 
  Plus, 
  Copy, 
  MousePointer2,
  Layers,
  Check,
  ArrowRight,
  Loader2,
  Edit3,
  Sliders,
  Trash2,
  Eraser,
  BookOpen,
  RefreshCw,
  Play,
  LineChart as LineChartIcon,
  Calculator,
  AreaChart as AreaChartIcon,
  FilePlus2
} from 'lucide-react'
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
} from 'recharts'
import {
  DataPoint,
  WeibullResult,
  generatePDFPoints,
  generateCDFPoints
} from '@/lib/weibull'
import { getMethodInfo } from '@/lib/methods'

const cn = (...classes: (string | undefined | null | false)[]) => classes.filter(Boolean).join(' ')

export interface LayerInfo {
  id: string
  name: string
  color: string
  result: WeibullResult
}

interface AnalysisCardProps {
  id: string
  index: number
  data?: DataPoint[]
  result?: WeibullResult
  methodId?: string
  color: string
  fitMode: 'fit' | 'manual'
  is3P: boolean
  availableLayers: LayerInfo[]
  onAdd: (type: 'method' | 'data' | 'params' | 'chart' | 'blank', sourceId: string, currentData?: DataPoint[]) => void
  onMethodClick?: () => void
  onToggle3P?: () => void
  onDataClick?: () => void 
  onDataChange?: (newData: DataPoint[]) => void 
  onParamsUpdate?: (updates: Partial<WeibullResult>, mode?: 'fit' | 'manual') => void
  onCalculate?: () => Promise<void>
  onDelete?: () => void
}

export default function AnalysisCard({
  id, 
  index, 
  data, 
  result, 
  methodId, 
  color, 
  fitMode,
  is3P,
  availableLayers, 
  onAdd, 
  onMethodClick, 
  onToggle3P,
  onDataClick,
  onDataChange,
  onParamsUpdate,
  onCalculate,
  onDelete
}: AnalysisCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false)
  const [isOverlayMenuOpen, setIsOverlayMenuOpen] = useState(false)
  const [selectedOverlayIds, setSelectedOverlayIds] = useState<string[]>([])
  const [isCalculating, setIsCalculating] = useState(false)
  const [chartMode, setChartMode] = useState<'pdf' | 'cdf'>('pdf')
  
  const [sampleText, setSampleText] = useState("")
  const [simN, setSimN] = useState(20)

  const menuRef = useRef<HTMLDivElement>(null)
  const addMenuRef = useRef<HTMLDivElement>(null)
  const methodInfo = getMethodInfo(methodId)
  const router = useRouter()

  useEffect(() => {
    if (data) {
      const text = data.map(d => `${d.value}${d.status === 'S' ? ' S' : ''}`).join('\n')
      setSampleText(text)
      setSimN(data.length)
    }
  }, [data])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOverlayMenuOpen(false)
      }
      if (addMenuRef.current && !addMenuRef.current.contains(event.target as Node)) {
        setIsAddMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const chartData = useMemo(() => {
    if (!result) return []
    const minT = result.gamma
    // Fixed range based on parameters only, ensuring the curve is stable even if data changes
    const maxT = result.gamma + result.eta * 2.5
    
    if (chartMode === 'pdf') {
      return generatePDFPoints(result.beta, result.eta, result.gamma, minT, maxT, 100)
    } else {
      return generateCDFPoints(result.beta, result.eta, result.gamma, minT, maxT, 100)
    }
  }, [result, chartMode])

  const overlayCurves = useMemo(() => {
    return selectedOverlayIds.map(overlayId => {
      const layer = availableLayers.find(l => l.id === overlayId)
      if (!layer) return null
      const res = layer.result
      const minT = res.gamma
      const maxT = Math.max(res.eta * 2.5, ...(data?.map(d => d.value) || [])) * 1.2
      
      const points = chartMode === 'pdf' 
        ? generatePDFPoints(res.beta, res.eta, res.gamma, minT, maxT, 100)
        : generateCDFPoints(res.beta, res.eta, res.gamma, minT, maxT, 100)
        
      return { id: layer.id, name: layer.name, color: layer.color, points }
    }).filter(Boolean)
  }, [selectedOverlayIds, availableLayers, chartMode, data])

  const handleParamChange = (key: 'beta' | 'eta' | 'gamma', value: string) => {
    const val = parseFloat(value)
    if (!isNaN(val) && onParamsUpdate) {
      onParamsUpdate({ [key]: val }, 'manual')
    }
  }

  const handleSampleTextBlur = () => {
    if (!onDataChange) return
    const lines = sampleText.split('\n').filter(line => line.trim())
    const newData: DataPoint[] = []
    lines.forEach((line, idx) => {
      const parts = line.trim().split(/\s+/)
      const val = parseFloat(parts[0])
      if (!isNaN(val)) {
        const status = parts.length > 1 && parts[1].toUpperCase().startsWith('S') ? 'S' : 'F'
        newData.push({ id: idx, value: val, status })
      }
    })
    if (newData.length > 0) onDataChange(newData)
  }

  const handleGenerateSample = () => {
    if (!result || !onDataChange) return
    const newSample: DataPoint[] = Array.from({ length: simN }, (_, i) => {
      const u = Math.random()
      const t = result.gamma + result.eta * Math.pow(-Math.log(u), 1 / result.beta)
      return { id: i, value: t, status: 'F' }
    })
    onDataChange(newSample)
  }

  const handleEstimation = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!onCalculate) return
    setIsCalculating(true)
    try {
      await onCalculate()
    } finally {
      setIsCalculating(false)
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="w-full relative group/card pb-4 mb-4 mt-4"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Action Buttons (Moved Outside - Right Side) */}
      <div className="absolute top-0 -right-10 flex flex-col gap-2 z-30">
         <button onClick={onDelete} className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-full transition-all duration-200 opacity-0 group-hover/card:opacity-100">
            <Trash2 size={18} />
         </button>
         
         <div className="relative" ref={addMenuRef}>
           <button 
             onClick={() => setIsAddMenuOpen(!isAddMenuOpen)}
             className={cn(
               "p-2 rounded-full transition-all duration-200 opacity-0 group-hover/card:opacity-100",
               isAddMenuOpen ? "text-blue-600 bg-blue-50" : "text-slate-300 hover:text-blue-500 hover:bg-blue-50"
             )}
           >
              <Plus size={18} />
           </button>
           <AnimatePresence>
             {isAddMenuOpen && (
               <motion.div
                 initial={{ opacity: 0, x: 10, scale: 0.9 }}
                 animate={{ opacity: 1, x: 0, scale: 1 }}
                 exit={{ opacity: 0, x: 10, scale: 0.9 }}
                 className="absolute right-full top-0 mr-2 w-36 bg-white rounded-xl shadow-xl border border-slate-100 p-1.5 z-50 flex flex-col gap-1"
               >
                 <button onClick={() => { onAdd('method', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-blue-50 rounded-lg text-xs font-black text-slate-600 hover:text-blue-600 transition-colors text-left group">
                   <Copy size={12} className="text-blue-400 group-hover:text-blue-600" /> 
                   <span>继承方法</span>
                 </button>
                 <button onClick={() => { onAdd('data', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-indigo-50 rounded-lg text-xs font-black text-slate-600 hover:text-indigo-600 transition-colors text-left group">
                   <Copy size={12} className="text-indigo-400 group-hover:text-indigo-600" />
                   <span>继承样本</span>
                 </button>
                 <button onClick={() => { onAdd('params', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-indigo-50 rounded-lg text-xs font-black text-slate-600 hover:text-indigo-600 transition-colors text-left group">
                   <Copy size={12} className="text-indigo-400 group-hover:text-indigo-600" />
                   <span>继承参数</span>
                 </button>
                 <button onClick={() => { onAdd('chart', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-emerald-50 rounded-lg text-xs font-black text-slate-600 hover:text-emerald-600 transition-colors text-left group">
                   <MousePointer2 size={12} className="text-emerald-400 group-hover:text-emerald-600" />
                   <span>继承图表</span>
                 </button>
                 <div className="h-[1px] bg-slate-100 my-0.5"></div>
                 <button onClick={() => { onAdd('blank', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 rounded-lg text-xs font-black text-slate-600 hover:text-slate-800 transition-colors text-left group">
                   <FilePlus2 size={12} className="text-slate-400 group-hover:text-slate-600" />
                   <span>新建空白</span>
                 </button>
               </motion.div>
             )}
           </AnimatePresence>
         </div>
      </div>

      {/* Main Card Container */}
      <div className={cn(
        "relative bg-white rounded-xl border transition-all duration-300 overflow-hidden shadow-sm h-[340px]",
        isHovered ? "border-blue-400 shadow-md ring-1 ring-blue-100" : "border-slate-200"
      )}>

        <div className="flex h-full divide-x divide-slate-100 relative z-10 bg-white pt-2 pb-2">
          
          {/* Column 1: 方法栏 */}
          <div
            className="w-[12.5%] bg-slate-50/30 flex flex-col group/col cursor-pointer hover:bg-blue-50/30 transition-colors h-full"
            onClick={onMethodClick}
          >
            {/* 标题栏 */}
            <div className="h-12 flex items-center gap-2 px-3 text-slate-500 border-b border-slate-100/50">
              <Settings2 size={16} className="text-blue-600" />
              <span className="text-base font-black uppercase tracking-wider">方法</span>
            </div>
            {/* 内容栏 */}
            <div className="flex-1 flex flex-col items-center justify-center text-center px-3 gap-3">
              {methodId ? (
                 <div className="flex flex-col items-center gap-2">
                   <div className="font-black text-slate-700 text-sm sm:text-base leading-tight break-words max-w-full">
                     {methodInfo.name}
                   </div>
                   <div className="px-2 py-0.5 text-xs text-blue-600 bg-blue-50 rounded-full border border-blue-100 font-black tracking-tighter">
                     {methodInfo.short}
                   </div>
                 </div>
              ) : (
                <div className="w-full border-2 border-dashed border-slate-200 rounded-lg flex items-center justify-center text-slate-400 text-xs py-8">选择</div>
              )}
              
              {/* Process Button */}
              {methodId && data && data.length > 0 && (
                 <button 
                   onClick={(e) => {
                     e.stopPropagation(); // Prevent opening method selector
                     if (!methodId || !data) return;
                     const dataStr = data.map(d => d.value).join(',');
                     router.push(`/methods/${methodId}?data=${dataStr}`);
                   }}
                   className="flex items-center gap-1 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg text-[10px] font-bold transition-all opacity-0 group-hover/col:opacity-100"
                 >
                   <ArrowRight size={12} />
                   过程详解
                 </button>
              )}
            </div>
          </div>

          {/* Column 2: 样本 */}
          <div className="w-1/4 flex flex-col bg-white h-full">
            {/* 标题栏 */}
            <div className="h-12 flex items-center justify-between px-4 text-slate-500 border-b border-slate-100/50">
              <div className="flex items-center gap-2">
                 <div className="p-1 bg-emerald-50 text-emerald-600 rounded"><FileText size={16} /></div>
                 <span className="text-base font-black uppercase tracking-wider">样本</span>
              </div>
              <button onClick={onDataClick} className="h-7 px-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded transition-colors flex items-center gap-1 border border-transparent hover:border-emerald-100">
                <BookOpen size={14} />
                <span className="text-sm font-black">案例库</span>
              </button>
            </div>
            {/* 内容栏 */}
            <div className="flex-1 p-4 overflow-hidden">
              <div className="relative w-full h-full">
                <textarea
                  className="w-full h-full text-xs font-mono p-3 bg-slate-50 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400 transition-all text-slate-600 leading-relaxed"
                  placeholder="数据..."
                  value={sampleText}
                  onChange={(e) => setSampleText(e.target.value)}
                  onBlur={handleSampleTextBlur}
                />
                <div className="absolute bottom-2 right-2 text-xs font-black text-slate-400 bg-white/90 px-1.5 py-0.5 rounded shadow-sm border border-slate-100">N={data ? data.length : 0}</div>
              </div>
            </div>
            {/* 底栏 */}
            <div className="h-12 flex items-center gap-2 px-4">
               <button onClick={handleEstimation} disabled={isCalculating} className="flex-1 h-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-md flex items-center justify-center gap-1.5 text-sm font-black transition-all active:scale-95 shadow-sm disabled:opacity-50">
                 {isCalculating ? <Loader2 size={14} className="animate-spin" /> : <Calculator size={14} />}
                 <span>参数估计</span>
               </button>
               <button onClick={() => { setSampleText(""); onDataChange?.([]); }} className="flex-1 h-full bg-slate-50 hover:bg-red-50 text-slate-500 hover:text-red-600 border border-slate-200 hover:border-red-200 rounded-md flex items-center justify-center gap-1.5 text-sm font-black transition-all active:scale-95 shadow-sm group">
                 <Trash2 size={14} className="group-hover:rotate-12 transition-transform" />
                 <span>清除样本</span>
               </button>
            </div>
          </div>

                      {/* Column 3: 参数 */}
                    <div className="w-1/4 flex flex-col bg-white h-full">
                                              {/* 标题栏 */}
                                              <div className="h-12 flex items-center justify-between px-4 text-slate-500 border-b border-slate-100/50">
                                                 <div className="flex items-center gap-2">
                                                   <div className="p-1 bg-indigo-50 text-indigo-600 rounded"><Sliders size={16} /></div>
                                                   <span className="text-base font-black uppercase tracking-wider">参数</span>
                                                 </div>
                                                 <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200 h-8">
                                                    <button onClick={() => is3P && onToggle3P?.()} className={cn("px-2.5 h-full rounded-full text-sm font-black transition-all flex items-center", !is3P ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-500")}>2P</button>
                                                    <button onClick={() => !is3P && onToggle3P?.()} className={cn("px-2.5 h-full rounded-full text-sm font-black transition-all flex items-center", is3P ? "bg-white text-indigo-600 shadow-sm" : "text-slate-400 hover:text-slate-500")}>3P</button>
                                                 </div>
                                              </div>                                  {/* 内容栏 */}
                                  <div className="flex-1 p-4 flex flex-col overflow-y-auto">
                                    {result ? (
                                      <div className="space-y-3">
                                        <ParamInput label="β 形状" value={result.beta} onChange={(v) => handleParamChange('beta', v)} readOnly={false} color="text-indigo-600" decimals={3} />
                                        <ParamInput label="η 尺度" value={result.eta} onChange={(v) => handleParamChange('eta', v)} readOnly={false} color="text-indigo-600" decimals={3} />
                                        <ParamInput label="γ 位置" value={result.gamma} onChange={(v) => handleParamChange('gamma', v)} readOnly={!is3P} color={is3P ? "text-blue-600" : "text-slate-300"} decimals={3} />
                                        
                                        {/* N (Sample Count) moved here */}
                                        <div className="pt-2 border-t border-slate-100 mt-2">
                                           <ParamInput label="N 样本数" value={simN} onChange={(v) => setSimN(parseInt(v) || 0)} readOnly={false} color="text-slate-500" step={1} decimals={0} />
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="flex-1 flex items-center justify-center text-xs text-slate-300">无参数</div>
                                    )}
                                  </div>            {/* 底栏 */}
            <div className="h-12 flex items-center gap-2 px-4">
                <button onClick={handleGenerateSample} className="flex-1 h-full bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200 rounded-md flex items-center justify-center gap-1.5 text-sm font-black transition-all active:scale-95 shadow-sm">
                  <RefreshCw size={14} className="group-hover:rotate-180 transition-transform duration-500" />
                  <span>生成样本</span>
                </button>
                <button onClick={() => onParamsUpdate?.({ beta: 1.0, eta: 100.0, gamma: 0.0 }, 'manual')} className="flex-1 h-full bg-slate-50 hover:bg-red-50 text-slate-500 hover:text-red-600 border border-slate-200 hover:border-red-200 rounded-md flex items-center justify-center gap-1.5 text-sm font-black transition-all active:scale-95 shadow-sm group">
                  <Eraser size={14} className="group-hover:rotate-12 transition-transform" />
                  <span>清除参数</span>
                </button>
            </div>
                    </div>
          
                              {/* Column 4: 图像 */}
          
                              <div className="w-[37.5%] flex flex-col bg-white h-full relative group/chart">
          
                                 {/* 标题栏 */}
          
                                 <div className="h-12 flex items-center justify-between px-4 text-slate-500 border-b border-slate-100/50">
          
                                    <div className="flex items-center gap-2">
          
                                       <div className="p-1 bg-blue-50 text-blue-600 rounded"><BarChart3 size={16} /></div>
          
                                       <span className="text-base font-black uppercase tracking-wider">图像</span>
          
                                    </div>
          
                                    <div className="flex items-center gap-2">
          
                                      <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200 h-8">
          
                                        <button onClick={() => setChartMode('pdf')} className={cn("px-3 h-full rounded-full text-sm font-black transition-all flex items-center", chartMode === 'pdf' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-500")}>PDF</button>
          
                                        <button onClick={() => setChartMode('cdf')} className={cn("px-3 h-full rounded-full text-sm font-black transition-all flex items-center", chartMode === 'cdf' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-500")}>CDF</button>
          
                                      </div>
          
                                      <div ref={menuRef} className="relative h-8">
          
                                        <button onClick={() => setIsOverlayMenuOpen(!isOverlayMenuOpen)} className={cn("h-full aspect-square flex items-center justify-center rounded-md transition-colors border", isOverlayMenuOpen ? "bg-blue-100 text-blue-600 border-blue-200" : "text-slate-400 hover:text-blue-600 hover:bg-blue-50 border-slate-200 hover:border-blue-100")}>
          
                                          <Layers size={16} />
          
                                        </button>
                    <AnimatePresence>
                      {isOverlayMenuOpen && (
                        <motion.div initial={{ opacity: 0, scale: 0.95, y: 5 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 5 }} className="absolute right-0 top-full mt-2 w-48 bg-white rounded-lg shadow-xl border border-slate-100 p-2 z-30">
                          <div className="text-[10px] font-black text-slate-400 px-2 py-1 mb-1 uppercase tracking-widest">叠加对比</div>
                          {availableLayers.length > 0 ? availableLayers.map(layer => (
                            <div key={layer.id} onClick={() => setSelectedOverlayIds(prev => prev.includes(layer.id) ? prev.filter(id => id !== layer.id) : [...prev, layer.id])} className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50 rounded cursor-pointer text-xs text-slate-600">
                              <div className={cn("w-2 h-2 rounded-full", !selectedOverlayIds.includes(layer.id) && "opacity-30")} style={{ backgroundColor: layer.color }} />
                              <span className="flex-1 truncate font-bold">{layer.name}</span>
                              {selectedOverlayIds.includes(layer.id) && <Check size={12} className="text-blue-600" />}
                            </div>
                          )) : <div className="px-2 py-2 text-[10px] text-slate-400 italic text-center">无图层</div>}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
             </div>
             {/* 内容栏 */}
             <div className="flex-1 p-4">
               {result ? (
                 <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                      <defs>
                        <linearGradient id={`color-${id}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={color} stopOpacity={0.1}/>
                          <stop offset="95%" stopColor={color} stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="x" type="number" domain={['auto', 'auto']} tick={{ fontSize: 9, fill: '#94a3b8' }} tickFormatter={(v) => v.toFixed(0)} />
                      <YAxis tick={{ fontSize: 9, fill: '#94a3b8' }} width={30} />
                      <Tooltip content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            return (
                              <div className="bg-white/95 backdrop-blur border border-slate-200 p-2 rounded-lg shadow-xl text-[10px] z-50">
                                <p className="font-black text-slate-800">t: {payload[0].payload.x.toFixed(2)}</p>
                                <p className="font-black" style={{ color }}>{chartMode.toUpperCase()}: {(payload[0].value as number)?.toFixed(4)}</p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Area type="monotone" dataKey="y" stroke={color} strokeWidth={2} fillOpacity={1} fill={`url(#color-${id})`} isAnimationActive={false} />
                      {overlayCurves.map(layer => layer && (
                         <Area key={layer.id} type="monotone" data={layer.points} dataKey="y" stroke={layer.color} strokeWidth={1.5} strokeDasharray="4 4" fill="none" isAnimationActive={false} />
                      ))}
                    </AreaChart>
                 </ResponsiveContainer>
               ) : (
                 <div className="flex-1 h-full flex flex-col items-center justify-center text-slate-300">
                    <BarChart3 size={48} strokeWidth={1} />
                 </div>
               )}
             </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function ParamInput({ label, value, onChange, readOnly, color, step = 0.1, decimals = 2 }: { label: string, value: number, onChange: (v: string) => void, readOnly: boolean, color: string, step?: number, decimals?: number }) {
  // Define available magnitudes based on decimal precision
  const allSteps = [10, 1, 0.1, 0.01, 0.001]
  const availableSteps = allSteps.filter(s => {
    if (decimals === 0) return s >= 1
    const sDecimals = s.toString().includes('.') ? s.toString().split('.')[1].length : 0
    return sDecimals <= decimals
  })

  // Initialize or fallback to a valid step
  const [currentStep, setCurrentStep] = useState(() => {
    return availableSteps.includes(step) ? step : (availableSteps[availableSteps.length - 1] || 1)
  })

  const cycleStep = () => {
    if (readOnly) return
    const currentIndex = availableSteps.indexOf(currentStep)
    const nextIndex = (currentIndex + 1) % availableSteps.length
    setCurrentStep(availableSteps[nextIndex])
  }

  return (
    <div className="flex items-center justify-center gap-2 text-sm h-8">
      <span className={cn("font-black w-20 shrink-0 truncate text-left", color)}>{label}</span>
      
      {/* Step Toggle Badge - More professional look */}
      <button 
        onClick={cycleStep}
        disabled={readOnly}
        className={cn(
          "min-w-[42px] px-1.5 py-0.5 rounded-md text-[10px] font-mono font-black border transition-all active:scale-90 shadow-sm",
          readOnly 
            ? "bg-slate-50 border-slate-100 text-slate-300" 
            : "bg-white border-blue-200 text-blue-600 hover:border-blue-400 hover:bg-blue-50"
        )}
        title="点击切换步进位数"
      >
        <span className="opacity-50 mr-0.5">±</span>
        {currentStep >= 1 ? currentStep : currentStep.toString().replace('0.', '.')}
      </button>

      <div className="w-28 shrink-0">
        <StepperInput 
          value={value} 
          onChange={(v) => onChange(v.toString())} 
          step={currentStep} 
          readOnly={readOnly}
          color={color}
          decimals={decimals}
        />
      </div>
    </div>
  )
}

function StepperInput({ value, onChange, step = 1, readOnly, color, decimals = 0 }: { value: number, onChange: (val: number) => void, step?: number, readOnly?: boolean, color?: string, decimals?: number }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [inputValue, setInputValue] = useState(value.toFixed(decimals))

  // Sync with external value changes, but only if not currently focused (to avoid conflict)
  // Or better: only update if the numeric value is significantly different to avoid formatting loops
  useEffect(() => {
    // Check if the current input value parses to the same number
    const currentNum = parseFloat(inputValue)
    if (Math.abs(currentNum - value) > 1e-10 || isNaN(currentNum)) {
       setInputValue(value.toFixed(decimals))
    }
  }, [value, decimals])

  const handleIncrement = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (readOnly) return
    const newValue = parseFloat((value + step).toFixed(decimals))
    onChange(newValue)
    setInputValue(newValue.toFixed(decimals))
  }

  const handleDecrement = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (readOnly) return
    const newValue = parseFloat((value - step).toFixed(decimals))
    onChange(newValue)
    setInputValue(newValue.toFixed(decimals))
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawVal = e.target.value
    setInputValue(rawVal)
    
    // Attempt to parse and notify parent
    const val = parseFloat(rawVal)
    if (!isNaN(val)) {
      onChange(val)
    }
  }

  const handleBlur = () => {
    // On blur, force format to standard precision
    setInputValue(value.toFixed(decimals))
  }

  return (
    <div className={cn(
      "flex items-stretch border rounded-lg overflow-hidden h-8 transition-all",
      readOnly ? "bg-slate-50 border-slate-100" : "bg-white border-slate-200 hover:border-blue-300"
    )}>
      <input 
        ref={inputRef}
        type="text" 
        className={cn(
          "w-full bg-transparent text-left text-sm font-black focus:outline-none pl-3 pr-1",
          readOnly ? "text-slate-400 cursor-default" : "text-slate-700"
        )} 
        value={inputValue} 
        readOnly={readOnly}
        onChange={handleInputChange}
        onBlur={handleBlur}
        onClick={(e) => e.stopPropagation()}
      />
      {!readOnly && (
        <div className="flex flex-col border-l border-slate-100 w-5 bg-slate-50">
          <button 
            onClick={handleIncrement} 
            className="flex-1 flex items-center justify-center text-slate-400 hover:text-blue-600 hover:bg-blue-50 border-b border-slate-100 transition-colors"
          >
            <Plus size={10} strokeWidth={4} />
          </button>
          <button 
            onClick={handleDecrement} 
            className="flex-1 flex items-center justify-center text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          >
            <div className="w-1.5 h-[2px] bg-current rounded-full" />
          </button>
        </div>
      )}
    </div>
  )
}