/** Shared estimation stages. The first program reference is the main one. */
export const calculationSteps: Record<string, { label: string; programSteps: number[] }[]> = {
  wmle: [
    { label: '形状方程求 β', programSteps: [2, 1] },
    { label: '位置方程定 γ', programSteps: [4, 3, 5] },
    { label: '回代求 η', programSteps: [3, 6] },
  ],
  lse: [
    { label: '比较 F 比定 γ', programSteps: [3, 1, 2] },
    { label: '由回归求 β、η', programSteps: [4, 5] },
  ],
  lre: [
    { label: '比较相关系数定 γ', programSteps: [3, 1, 2] },
    { label: '由回归求 β、η', programSteps: [4, 5] },
  ],
  mm: [
    { label: '由面积求矩', programSteps: [2, 1] },
    { label: '代入求参数', programSteps: [3] },
    { label: '检查位置', programSteps: [4, 5, 6] },
  ],
  mmle: [
    { label: '最小值定 γ', programSteps: [2, 1] },
    { label: '迭代求 β', programSteps: [3] },
    { label: '回代求 η', programSteps: [4, 5] },
  ],
}
