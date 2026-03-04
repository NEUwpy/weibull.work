/**
 * MDM 方法图表组件
 *
 * 复用场景：
 * - 计算过程 (interactive=true): 单曲线 + 滑动条调整
 * - 案例展示 (interactive=false, overlayMode=true): 多曲线叠加 + 静态展示
 * - 方法示例 (noContainer=true): 纯图表，无外框
 *
 * 设计原则：交互组件 + 功能开关
 */
export { SigmaBetaChart } from './SigmaBetaChart'
export type { SigmaBetaCurvePoint, CurveData, ReferenceLineConfig } from './SigmaBetaChart'

export { GradientGammaChart } from './GradientGammaChart'
export type { GradientGammaPoint, GradientCurveData, GammaReferenceLine } from './GradientGammaChart'
