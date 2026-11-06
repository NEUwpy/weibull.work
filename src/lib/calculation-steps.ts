/** Statistical stages and their references to the existing program flow. */
export const calculationSteps: Record<string, { label: string; programSteps: number[] }[]> = {
  mdm: [
    { label: '求形状 β', programSteps: [2] },
    { label: '确定位置 γ', programSteps: [3] },
    { label: '求尺度 η', programSteps: [4] },
  ],
  mle: [
    { label: '固定位置求 β', programSteps: [2] },
    { label: '回代求 η', programSteps: [3] },
    { label: '比较似然定 γ', programSteps: [4, 5] },
  ],
  wmle: [
    { label: '形状方程求 β', programSteps: [2] },
    { label: '位置方程定 γ', programSteps: [3, 4, 5] },
    { label: '回代求 η', programSteps: [3] },
  ],
  lse: [
    { label: '比较 F 比定 γ', programSteps: [3] },
    { label: '由回归求 β、η', programSteps: [4] },
  ],
  lre: [
    { label: '比较相关系数定 γ', programSteps: [3] },
    { label: '由回归求 β、η', programSteps: [4] },
  ],
  mm: [
    { label: '由面积求矩', programSteps: [2] },
    { label: '代入求参数', programSteps: [3] },
    { label: '检查位置', programSteps: [4] },
  ],
  mmle: [
    { label: '最小值定 γ', programSteps: [2] },
    { label: '迭代求 β', programSteps: [3] },
    { label: '回代求 η', programSteps: [4] },
  ],
}
