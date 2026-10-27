import OpenAI from 'openai'

export function hasMoonshotKey(): boolean {
  return Boolean(process.env.MOONSHOT_API_KEY?.trim())
}

// Construct only when a request needs it; missing deployment config must not break builds.
export function getMoonshotClient(baseURL: string): OpenAI {
  const apiKey = process.env.MOONSHOT_API_KEY?.trim()
  if (!apiKey) throw new Error('Moonshot API is not configured')
  return new OpenAI({ apiKey, baseURL })
}
