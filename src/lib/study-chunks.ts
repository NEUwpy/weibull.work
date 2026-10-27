/** Expand every selected value, including method-specific process parameters. */
export function expandChunkParameters(dimensions: Record<string, number[]>): Record<string, number>[] {
  return Object.entries(dimensions).reduce<Record<string, number>[]>(
    (combinations, [key, values]) => combinations.flatMap(parameters =>
      Array.from(new Set(values)).map(value => ({ ...parameters, [key]: value })),
    ),
    [{}],
  )
}
