import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

/**
 * 方法级别的 Chunk 文件名解析 API
 *
 * GET /api/studies/{methodId}/chunks
 *
 * 返回指定方法的所有 chunk 文件列表和解析后的参数值
 * 所有示例共享同一套 chunk 数据
 */

interface ParsedParams {
  beta?: number[]
  eta?: number[]
  gamma?: number[]
  n?: number[]
  d?: number[]      // offset/process (MDM特有)
  rep?: number[]    // 仿真重复次数
  seed?: number[]   // 随机种子
  step?: number[]   // 计算步长 (MDM特有)
}

interface ChunkInfo {
  chunks: string[]
  parsedParams: ParsedParams
  total: number
}

// 解析 chunk 文件名
// 格式: b{beta}_e{eta}_g{gamma}_n{n}_d{d}_rep{rep}_seed{seed}_step{step}.csv
// 例如: b1.5_e1000_g1000_n10_d0.05_rep1000_seed42_step60.csv
function parseChunkFilename(filename: string): Record<string, number> | null {
  const name = filename.replace('.csv', '')
  const parts = name.split('_')

  const params: Record<string, number> = {}

  for (const part of parts) {
    if (part.match(/^b[\d.]+$/)) {
      params.beta = parseFloat(part.slice(1))
    }
    else if (part.match(/^e[\d.]+$/)) {
      params.eta = parseFloat(part.slice(1))
    }
    else if (part.match(/^g[\d.]+$/)) {
      params.gamma = parseFloat(part.slice(1))
    }
    else if (part.match(/^n\d+$/)) {
      params.n = parseInt(part.slice(1))
    }
    else if (part.match(/^d[\d.]+$/)) {
      params.d = parseFloat(part.slice(1))
    }
    else if (part.match(/^rep\d+$/)) {
      params.rep = parseInt(part.slice(3))
    }
    else if (part.match(/^seed\d+$/)) {
      params.seed = parseInt(part.slice(4))
    }
    else if (part.match(/^step\d+$/)) {
      params.step = parseInt(part.slice(4))
    }
  }

  return Object.keys(params).length > 0 ? params : null
}

// 收集唯一值
function collectUniqueValues(chunks: string[]): ParsedParams {
  const valueSets: Record<string, Set<number>> = {
    beta: new Set(),
    eta: new Set(),
    gamma: new Set(),
    n: new Set(),
    d: new Set(),
    rep: new Set(),
    seed: new Set(),
    step: new Set()
  }

  for (const chunk of chunks) {
    const params = parseChunkFilename(chunk)
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (valueSets[key] && typeof value === 'number') {
          valueSets[key].add(value)
        }
      }
    }
  }

  const result: ParsedParams = {}
  for (const [key, set] of Object.entries(valueSets)) {
    if (set.size > 0) {
      result[key as keyof ParsedParams] = Array.from(set).sort((a, b) => a - b)
    }
  }

  return result
}

export async function GET(
  request: Request,
  { params }: { params: { methodId: string } }
) {
  const { methodId } = params

  try {
    // 方法级别的 chunks 目录
    const chunksDir = path.join(
      process.cwd(),
      'public',
      'studies',
      methodId.toLowerCase(),
      'chunks'
    )

    if (!fs.existsSync(chunksDir)) {
      return NextResponse.json({
        chunks: [],
        parsedParams: {},
        total: 0,
        error: 'Chunks directory not found'
      })
    }

    const files = fs.readdirSync(chunksDir)
    const csvFiles = files.filter(f => f.endsWith('.csv'))

    const parsedParams = collectUniqueValues(csvFiles)

    const result: ChunkInfo = {
      chunks: csvFiles,
      parsedParams,
      total: csvFiles.length
    }

    console.log(`[Chunks API] ${methodId}: ${result.total} chunks found`)

    return NextResponse.json(result)
  } catch (error) {
    console.error('Error loading chunks:', error)
    return NextResponse.json({
      chunks: [],
      parsedParams: {},
      total: 0,
      error: 'Failed to load chunks'
    }, { status: 500 })
  }
}
