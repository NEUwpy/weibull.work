"use client"

import type { ComponentProps } from 'react'
import { CalculationStepContent, CalculationSteps, ProcessDetails } from './CalculationSteps'
import { PowerScaleCalculation } from './PowerScaleCalculation'
import { LikelihoodProcessViewer } from './LikelihoodProcessViewer'
import { RegressionProcessViewer } from './RegressionProcessViewer'
import { MomentProcessViewer } from './MomentProcessViewer'
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { type CalculationChart, type CalculationTrace, formatCalculationNumber as number, readPowerScaleCalculation } from '@/lib/calculation-trace'

const math = (value: unknown) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

function Curve({ chart, title, ...reading }: Pick<ComponentProps<typeof CalculationStepContent>, 'calculation' | 'criterion' | 'symbols'> & {
  chart?: CalculationChart
  title: string
}) {
  return <CalculationStepContent title={title} axes={chart && { x: chart.x.label, y: chart.y.label }}
    figure={chart ? <ProcessChart chart={chart} figureOnly /> : <p className="text-base text-slate-600">本次记录没有该步骤的有限曲线。</p>}
    {...reading} />
}

export function MethodCalculationSteps({ trace }: { trace: CalculationTrace }) {
  if (trace.selection.status !== 'ok') return null
  const method = trace.method
  const chart = (id: string) => trace.charts.find(item => item.id === id)
  const details = trace.details as Record<string, any> | undefined
  const selection = trace.selection

  if (method === 'mle' || method === 'wmle') {
    const weighted = method === 'wmle'
    const shape = details?.reading_frames?.find((frame: { final: boolean }) => frame.final)?.shape_chart
      ?? chart('conditional-shape-equation')
    const shapeScore = weighted ? 'T₁' : 'Sβ'
    const shapeScoreMath = weighted ? 'T_1' : String.raw`S_\beta`
    const shapeAtLowerBound = !weighted && Number(selection.beta) === 1
    const shapeStep = <div key="shape" className="space-y-4">
      <Curve chart={shape} title="固定位置，求形状 β"
        calculation={<>
          <ProcessFormula expression={String.raw`\begin{aligned}d_i&=t_i-\gamma\\${shapeScoreMath}(\beta,\gamma)&=\frac{${weighted ? 'J_2' : '1'}}{\beta}+\frac1n\sum_i\ln d_i\\&\quad-\frac{\sum_i d_i^\beta\ln d_i}{\sum_i d_i^\beta}\end{aligned}`} />
          <p className="text-base text-slate-700">本图固定 γ = {number(selection.gamma)}。</p>
        </>}
        criterion={<>
          <ProcessFormula expression={weighted && selection.approximate === true ? String.raw`\gamma=0,\qquad T_1^2+T_2^2\le 10^{-8}`
            : shapeAtLowerBound ? String.raw`S_\beta(1,\gamma)\le0\ \Longrightarrow\ \beta^*(\gamma)=1`
              : String.raw`${shapeScoreMath}(\beta^*(\gamma),\gamma)=0`} />
          <p className="text-base text-slate-700">{weighted && selection.approximate === true ? '按边界残差容差采纳' : '该位置对应的形状'}为 β = {number(selection.beta)}。</p>
        </>}
        symbols={[
          ['γ', '本图固定的位置参数'], ['tᵢ', '第 i 个观测值'], ['dᵢ', '平移后的样本距离'], ['n', '样本量'],
          [shapeScore, '图中的方程值，水平虚线标记零值'], ['β*(γ)', '固定 γ 后求得的形状'],
          ...(weighted ? [['J₂', '按样本量查表的形状方程权重'], ['T₂', '下一步使用的位置方程残差']] as const : []),
        ]} />
      <ProcessDetails title={weighted ? '查看加权方程及权重细节' : '查看形状方程的代入细节'}><LikelihoodProcessViewer trace={trace} /></ProcessDetails>
    </div>
    const position = chart(weighted ? 'weighted-location-equation' : 'profile-likelihood')
    const positionStep = <div key="position" className="space-y-4">
      <Curve chart={position} title={weighted ? '联立加权方程，确定位置 γ' : '比较有限极大候选，确定位置 γ'}
        calculation={<>
          <ProcessFormula expression={weighted
            ? String.raw`T_2(\beta,\gamma)=\frac1n\sum_i\frac1{d_i}\cdot\frac{\sum_i d_i^\beta}{\sum_i d_i^{\beta-1}}-J_3`
            : String.raw`\begin{aligned}\ell(\beta,\eta,\gamma)&=n\ln\beta-n\beta\ln\eta\\&\quad+(\beta-1)\sum_i\ln d_i\\&\quad-\sum_i(d_i/\eta)^\beta\\\ell_p(\gamma)&=\ell\{\beta^*(\gamma),\eta^*(\gamma),\gamma\}\end{aligned}`} />
          <p className="text-base text-slate-700">{weighted ? '位置曲线把各 γ 下由 T₁ = 0 求得的 β 代入 T₂。' : '各 γ 先求条件形状与尺度，再代入对数似然。'}</p>
        </>}
        criterion={<>
          <ProcessFormula expression={weighted ? selection.approximate === true
            ? String.raw`\hat\gamma=0,\qquad T_1^2+T_2^2\le 10^{-8}`
            : String.raw`T_1(\hat\beta,\hat\gamma)=T_2(\hat\beta,\hat\gamma)=0`
            : String.raw`\hat\gamma=\arg\max_{\gamma\in\mathcal C}\ell_p(\gamma)`} />
          {weighted && selection.approximate !== true && <p className="text-base text-slate-700">数值接受条件为 T₁² + T₂² ≤ 10⁻⁸。{Number(details?.candidate_count) > 1 ? '残差近似相同的候选按与启发式初值的距离选取。' : ''}</p>}
          <p className="text-base text-slate-700">γ̂ = {number(selection.gamma)}{weighted ? `，T₂ = ${number(selection.t2)}` : `，ℓₚ = ${number(selection.log_likelihood)}`}。</p>
        </>}
        symbols={[
          ['dᵢ', '平移距离 tᵢ − γ'], ['tᵢ', '第 i 个观测值'], ['n', '样本量'],
          ...(weighted ? [['β', '候选位置对应的形状'], ['T₁、T₂', '加权形状与位置方程的残差'], ['J₃', '按样本量与形状查表的位置方程权重']] as const
            : [['β、η', '形状和尺度参数'], ['β*(γ)、η*(γ)', '固定 γ 后求得的形状和尺度'], ['ℓ', '原始对数似然'], ['ℓₚ', '把条件参数代入后的剖面对数似然'], ['𝒞', '通过内点或边界检查的有限极大候选位置']] as const),
          ['γ̂', '最终采纳的位置'],
        ]} />
      <ProcessDetails title="查看候选与判据细节"><LikelihoodProcessViewer trace={trace} /></ProcessDetails>
    </div>
    return <CalculationSteps method={method}>{weighted
      ? [shapeStep, positionStep, <PowerScaleCalculation key="scale" trace={trace} />]
      : [shapeStep, <PowerScaleCalculation key="scale" trace={trace} />, positionStep]}</CalculationSteps>
  }

  if (method === 'mmle') {
    const scale = readPowerScaleCalculation(trace)
    const profile = chart('modified-profile-likelihood')
    return <CalculationSteps method={method}>{[
      <CalculationStepContent key="location" title="取最小观测值，确定位置 γ"
        calculation={<ProcessFormula expression={String.raw`y_i=t_{(i)}-\hat\gamma\ (i=2,\ldots,n),\quad q=n-1`} />}
        criterion={<>
          <ProcessFormula expression={String.raw`\hat\gamma=\min_i t_i=t_{(1)}\approx${math(selection.gamma)}`} />
          <p className="text-base text-slate-700">用该最小观测确定位置，然后删去它，保留 {scale?.count ?? '—'} 个样本。</p>
        </>}
        symbols={[
          ['t₍ᵢ₎', '由小到大排列的第 i 个观测值'], ['γ̂', '采纳的位置参数'],
          ['yᵢ', '保留样本减去位置后的距离'], ['n、q', '原样本量与保留样本量'],
        ]} />,
      <div key="shape" className="space-y-4">
        <Curve chart={profile} title="由不动点迭代求形状 β"
          calculation={<>
            <ProcessFormula expression={String.raw`\begin{aligned}A(\beta)&=\frac1q\sum_i y_i^\beta\\\ell_p(\beta)&=q\ln\beta-q\ln A(\beta)\\&\quad+(\beta-1)\sum_i\ln y_i-q\end{aligned}`} />
            <ProcessFormula expression={String.raw`\begin{aligned}w_i(\beta_k)&=\frac{y_i^{\beta_k}}{\sum_j y_j^{\beta_k}}\\\beta_{k+1}&=\frac{q+\beta_k\sum_i\ln y_i}{q\sum_i w_i(\beta_k)\ln y_i}\end{aligned}`} />
          </>}
          criterion={<>
            <ProcessFormula expression={String.raw`|\beta_{k+1}-\beta_k|\le\varepsilon\ \Longrightarrow\ \hat\beta=\beta_{k+1}`} />
            <p className="text-base text-slate-700">本次步长为 {number(details?.final_shape_step)}，容差为 {number(details?.shape_absolute_step_tolerance)}，得到 β̂ = {number(selection.beta)}。</p>
          </>}
          symbols={[
            ['yᵢ、q', '保留样本的平移距离与样本量'], ['A(β)', '平移距离的幂次平均值'],
            ['βₖ', '第 k 步的形状'], ['wᵢ(βₖ)', '第 i 个样本的归一化幂次权重'],
            ['ε', '相邻两步形状绝对差的停止容差'], ['β̂', '满足停止条件时的形状估计'],
          ]} />
        <ProcessDetails title="查看真实迭代与停止判据"><LikelihoodProcessViewer trace={trace} /></ProcessDetails>
      </div>,
      <PowerScaleCalculation key="scale" trace={trace} />,
    ]}</CalculationSteps>
  }

  if (method === 'lse' || method === 'lre') {
    const lse = method === 'lse'
    const coordinates = lse
      ? String.raw`X_i=\mathbb{E}[W_{(i:n)}],\qquad Y_i(\gamma)=\ln(t_{(i)}-\gamma)`
      : String.raw`X_i(\gamma)=\ln(t_{(i)}-\gamma),\qquad Y_i=\ln[-\ln(1-p_i)]`
    const coordinateSymbols = lse ? [
      ['Xᵢ', '标准对数威布尔分布第 i 阶顺序统计量的期望'], ['Yᵢ', '样本平移距离的对数'],
      ['W₍ᵢ:ₙ₎', 'n 个标准对数威布尔变量中的第 i 个顺序统计量'],
    ] as const : [
      ['Xᵢ', '样本平移距离的对数'], ['Yᵢ', '由经验概率变换得到的威布尔分数'], ['pᵢ', 'Park 绘图位置给出的经验累计概率'],
    ] as const
    const regression = details?.regression_views?.find((view: { selected: boolean }) => view.selected)
    const regressionPlot = regression ? {
      id: 'selected-regression', title: '最终位置下的回归直线',
      x: { key: 'x', label: lse ? 'White 顺序统计量期望 Xᵢ' : '对数距离 Xᵢ = ln(tᵢ − γ̂)' },
      y: { key: 'y', label: lse ? '对数距离 Yᵢ = ln(tᵢ − γ̂)' : 'Weibull 分数 Yᵢ = ln[−ln(1−pᵢ)]' },
      series: [{ id: 'sample', label: '变换后的样本点', kind: 'scatter', role: 'diagnostic', points: regression.points.map((p: { x: number; y: number }) => ({ x: p.x, y: p.y })) },
        { id: 'fit', label: '最小二乘直线', kind: 'line', role: 'diagnostic', points: regression.points.map((p: { x: number; fit: number }) => ({ x: p.x, y: p.fit })) }],
    } satisfies CalculationChart : chart(lse ? 'white-regression' : 'park-probability-regression')
    return <CalculationSteps method={method}>{[
      <div key="location" className="space-y-4"><Curve chart={trace.charts[0]} title={lse ? '比较 F 比，确定位置 γ' : '比较相关系数，确定位置 γ'}
        calculation={<>
          <ProcessFormula expression={coordinates} />
          <ProcessFormula expression={lse
            ? String.raw`\begin{aligned}F(\gamma)&=S_Y^2/S_{\mathrm{res}}^2\\S_Y^2&=\frac{\sum_i(Y_i-\bar Y)^2}{n-1}\\S_{\mathrm{res}}^2&=\frac{\sum_i(Y_i-a-bX_i)^2}{n-2}\end{aligned}`
            : String.raw`\rho(\gamma)=\operatorname{corr}\{X_i(\gamma),Y_i\}`} />
          {!lse && <ProcessFormula expression={String.raw`p_i=\begin{cases}(i-3/8)/(n+1/4),&n\le10\\(i-1/2)/n,&n\ge11\end{cases}`} />}
        </>}
        criterion={<>
          <ProcessFormula expression={String.raw`\hat\gamma=\arg\max_{\gamma\in\mathcal G}${lse ? 'F' : String.raw`\rho`}(\gamma)`} />
          <p className="text-base text-slate-700">本次采纳 γ̂ = {number(selection.gamma)}。</p>
        </>}
        symbols={[
          ...coordinateSymbols, ['t₍ᵢ₎', '排序后的第 i 个样本'], ['n', '样本量'], ['𝒢', '本次搜索中用于比较的候选位置'],
          ...(lse ? [['S²Y', '对数距离的样本方差'], ['S²res', 'White 直线拟合的残差方差'], ['a、b', '固定 γ 时回归直线的截距和斜率'], ['Ȳ', '对数距离的平均值']] as const
            : [['corr', 'Pearson 相关系数']] as const),
          ['γ̂', '取值判据给出的最终位置'],
        ]} />
        <ProcessDetails title="查看不同位置下的回归比较"><RegressionProcessViewer trace={trace} /></ProcessDetails></div>,
      <div key="regression" className="space-y-4"><Curve chart={regressionPlot} title="由回归直线求形状 β 和尺度 η"
        calculation={<>
          <ProcessFormula expression={coordinates} />
          <ProcessFormula expression={String.raw`\hat Y_i=a+bX_i,\qquad (a,b)=\arg\min_{u,v}\sum_i(Y_i-u-vX_i)^2`} />
          <p className="text-base text-slate-700">固定 γ = γ̂ = {number(selection.gamma)}，本次截距 a = {number(details?.intercept)}，斜率 b = {number(details?.slope)}。</p>
        </>}
        criterion={<ProcessFormula expression={lse
          ? String.raw`\begin{aligned}\hat\beta&=1/b\approx${math(selection.beta)}\\\hat\eta&=e^a\approx${math(selection.eta)}\end{aligned}`
          : String.raw`\begin{aligned}\hat\beta&=b\approx${math(selection.beta)}\\\hat\eta&=e^{-a/b}\approx${math(selection.eta)}\end{aligned}`} />}
        symbols={[
          ...coordinateSymbols, ['t₍ᵢ₎', '排序后的第 i 个样本'], ['γ̂', '前一步采纳的位置'],
          ['Ŷᵢ', '图上回归直线在 Xᵢ 处的拟合值'], ['a、b', '拟合直线的截距和斜率'], ['u、v', '最小二乘比较的截距和斜率'],
          ['β̂、η̂', '由回归系数得到的形状与尺度'],
        ]} />
        <ProcessDetails title="查看样本变换和回归计算"><RegressionProcessViewer trace={trace} /></ProcessDetails></div>,
    ]}</CalculationSteps>
  }

  if (method === 'mm') return <CalculationSteps method={method}>{[0, 1, 2].map(step =>
    <MomentProcessViewer key={step} trace={trace} step={step} />
  )}</CalculationSteps>

  return <div className="space-y-4">{trace.charts.map(item => <ProcessChart key={item.id} chart={item} />)}</div>
}
