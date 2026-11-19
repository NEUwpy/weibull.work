export const libraryRecommendationLabels = {
  principle: '原理依据',
  'direct-improvement': '直接改进',
  'method-transfer': '方法借鉴',
  'comparison-validation': '对照与验证',
} as const

export type LibraryRecommendationRelation = keyof typeof libraryRecommendationLabels
export type LibraryRecommendationRelations = Partial<Record<string, LibraryRecommendationRelation>>

export function isLibraryRecommendationRelation(value: unknown): value is LibraryRecommendationRelation {
  return typeof value === 'string' && Object.hasOwn(libraryRecommendationLabels, value)
}
