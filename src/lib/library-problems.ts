import taxonomy from '../data/library-problems.json'

export const libraryProblemSource = taxonomy.source
export const libraryProblemDirections = taxonomy.directions
export const libraryProblems = taxonomy.problems
const directions = new Set(libraryProblemDirections.map(direction => direction.key))
const problems = new Map(libraryProblems.map(problem => [problem.key, problem]))
export const libraryProblemTagPrefix = 'problem:'

type TaggedPaper = { tags?: string[] }

export function validLibraryProblemKey(key: string): boolean {
  return directions.has(key) || problems.has(key)
}

export function validateLibraryProblemTags(tags: string[]): string[] {
  for (const tag of tags) {
    if (tag.startsWith(libraryProblemTagPrefix) && !validLibraryProblemKey(tag.slice(libraryProblemTagPrefix.length))) {
      throw new Error(`未知科学问题标签：${tag}`)
    }
  }
  return tags
}

export function matchesLibraryProblem(paper: TaggedPaper, key: string): boolean {
  if (!validLibraryProblemKey(key)) return false
  return (paper.tags || []).some(tag => {
    if (!tag.startsWith(libraryProblemTagPrefix)) return false
    const value = tag.slice(libraryProblemTagPrefix.length)
    return value === key || (directions.has(key) && problems.get(value)?.direction === key)
  })
}

/** The paper tags are the only membership store; counts are derived, never maintained. */
export function libraryProblemGroups(papers: TaggedPaper[]) {
  return libraryProblemDirections.map(direction => ({
    ...direction,
    count: papers.filter(paper => matchesLibraryProblem(paper, direction.key)).length,
    problems: libraryProblems.filter(problem => problem.direction === direction.key).map(problem => ({
      ...problem, count: papers.filter(paper => matchesLibraryProblem(paper, problem.key)).length,
    })),
  }))
}
