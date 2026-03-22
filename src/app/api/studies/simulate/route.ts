import { NextResponse } from 'next/server'
import { getApiBaseUrl } from '@/lib/config'

/**
 * 蒙特卡洛模拟 API
 *
 * POST /api/studies/simulate
 *
 * 调用 Python 后端运行蒙特卡洛模拟，返回与预计算chunk相同格式的数据
 */

interface MonteCarloRequest {
  methodId: string
  params: {
    beta: number
    eta: number
    n: number
    rep?: number
    seed?: number
    gamma?: number
    offset?: number
  }
}

interface SimulationRow {
  beta_true: number
  eta_true: number
  gamma: number
  sample_size: number
  offset_value?: number
  sim_id: number
  est_beta: number | null
  est_eta: number | null
  est_gamma: number | null
  bias_beta: number | null
  bias_eta: number | null
  bias_gamma: number | null
  r_squared: number | null
}

export async function POST(request: Request) {
  try {
    const body: MonteCarloRequest = await request.json()
    const { methodId, params } = body

    // 调用 Python 后端
    const response = await fetch(`${getApiBaseUrl()}/monte_carlo_simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        method: methodId,
        beta: params.beta,
        eta: params.eta,
        n: params.n,
        rep: params.rep || 100,
        seed: params.seed || 42,
        gamma: params.gamma || 0,
        offset: params.offset
      })
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || 'Monte Carlo simulation failed' },
        { status: response.status }
      )
    }

    const data = await response.json()

    return NextResponse.json({
      rows: data.rows as SimulationRow[],
      count: data.count,
      methodId,
      params
    })

  } catch (error) {
    console.error('Monte Carlo simulation API error:', error)
    return NextResponse.json(
      { error: 'Failed to run Monte Carlo simulation' },
      { status: 500 }
    )
  }
}
