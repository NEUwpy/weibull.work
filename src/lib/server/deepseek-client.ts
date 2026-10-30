import OpenAI from 'openai'
import config from '../../app/api/chat/config.json'

export function hasDeepSeekKey(): boolean {
  return Boolean(process.env.DEEPSEEK_API_KEY?.trim())
}

export function getDeepSeekSettings() {
  return {
    baseURL: process.env.DEEPSEEK_BASE_URL?.trim() || config.deepseek.baseURL,
    model: process.env.DEEPSEEK_MODEL?.trim() || config.deepseek.model,
    label: config.deepseek.label,
  }
}

export function getDeepSeekClient(): OpenAI {
  const apiKey = process.env.DEEPSEEK_API_KEY?.trim()
  if (!apiKey) throw new Error('DeepSeek API is not configured')
  return new OpenAI({ apiKey, baseURL: getDeepSeekSettings().baseURL, timeout: 90_000, maxRetries: 0 })
}
