
// Weibull Analysis Core Logic
// Implements Median Ranks (Benard's) and Rank Regression (RRX)
// Supports 3-Parameter Weibull (gamma location parameter)

/**
 * Represents a single data point input
 */
export type DataPoint = {
  id: number
  value: number // Time to failure
  status: 'F' | 'S' // Failure or Suspension
}

/**
 * Represents a point on the Weibull Probability Plot
 */
export type PlotPoint = {
  x: number // ln(t - gamma)
  y: number // ln(-ln(1-MedianRank))
  originalValue: number
  medianRank: number
}

/**
 * Analysis Result
 */
export type WeibullResult = {
  beta: number | null // Shape parameter (slope)
  eta: number | null  // Scale parameter (characteristic life)
  gamma: number // Location parameter
  rSquared: number | null // Coefficient of determination
  points: PlotPoint[] // The calculated points for plotting
  converged?: boolean | string // Whether the calculation converged, or "unbounded" for Smith (1985) problem
}

/**
 * Calculates Median Ranks using Benard's approximation: (i - 0.3) / (N + 0.4)
 * Applies Weibull transformation with Gamma parameter.
 * X = ln(t - gamma)
 * Y = ln(-ln(1 - F(t)))
 * 
 * @param data Raw data points
 * @param gamma Location parameter (default 0). Points where value <= gamma are excluded.
 */
export function calculateMedianRanks(data: DataPoint[], gamma: number = 0): PlotPoint[] {
  // Filter for failures only
  // Also filter out invalid points where t <= gamma
  const failures = data
    .filter(d => d.status === 'F' && d.value > gamma)
    .sort((a, b) => a.value - b.value)
  
  const N = data.length 
  
  return failures.map((point, index) => {
    const rank = index + 1
    // Benard's approximation
    const medianRank = (rank - 0.3) / (N + 0.4)
    
    // Weibull Transformation (3-Parameter)
    const t_adjusted = point.value - gamma
    const x = Math.log(t_adjusted)
    const y = Math.log(-Math.log(1 - medianRank))

    return {
      x,
      y,
      originalValue: point.value,
      medianRank
    }
  })
}

/**
 * Performs Rank Regression on X (RRX) using Least Squares
 * Fits Y = beta * X + C
 * where X = ln(t - gamma)
 * C = -beta * ln(eta)
 */
export function calculateWeibullParameters(points: PlotPoint[], fixedGamma: number = 0): WeibullResult {
  const n = points.length
  if (n < 2) {
    return { beta: 0, eta: 0, gamma: fixedGamma, rSquared: 0, points }
  }

  let sumX = 0
  let sumY = 0
  let sumXY = 0
  let sumXX = 0
  let sumYY = 0

  points.forEach(p => {
    sumX += p.x
    sumY += p.y
    sumXY += p.x * p.y
    sumXX += p.x * p.x
    sumYY += p.y * p.y
  })

  // Calculate slope (Beta) and intercept
  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX)
  const intercept = (sumY - slope * sumX) / n

  const beta = slope
  const eta = Math.exp(-intercept / slope)

  // Calculate R-squared
  const numerator = n * sumXY - sumX * sumY
  const denom = Math.sqrt((n * sumXX - sumX * sumX) * (n * sumYY - sumY * sumY))
  const rSquared = denom === 0 ? 0 : Math.pow(numerator / denom, 2)

  return {
    beta,
    eta,
    gamma: fixedGamma,
    rSquared,
    points
  }
}

/**
 * Generates points for the fitted line (for visualization)
 * Returns 2 points: [start, end] covering the range of data
 * Line Equation: Y = beta * X - beta * ln(eta)
 * where X is already transformed ln(t - gamma)
 */
export function generateLinePoints(beta: number, eta: number, minX: number, maxX: number) {
  const y1 = beta * minX - beta * Math.log(eta)
  const y2 = beta * maxX - beta * Math.log(eta)

  return [
    { x: minX, y: y1 },
    { x: maxX, y: y2 }
  ]
}

/**
 * Generates points for the Probability Density Function (PDF) curve
 * f(t) = (beta/eta) * ((t-gamma)/eta)^(beta-1) * exp(-((t-gamma)/eta)^beta)
 */
export function generatePDFPoints(beta: number, eta: number, gamma: number, minT: number, maxT: number, steps: number = 100) {
  const points = []
  const stepSize = (maxT - minT) / steps
  
  for (let i = 0; i <= steps; i++) {
    const t = minT + i * stepSize
    if (t <= gamma) continue // PDF is 0 or undefined for t <= gamma
    
    const z = (t - gamma) / eta
    const y = (beta / eta) * Math.pow(z, beta - 1) * Math.exp(-Math.pow(z, beta))
    points.push({ x: t, y })
  }
  return points
}

/**
 * Generates points for the Cumulative Distribution Function (CDF) curve
 * F(t) = 1 - exp(-((t-gamma)/eta)^beta)
 */
export function generateCDFPoints(beta: number, eta: number, gamma: number, minT: number, maxT: number, steps: number = 100) {
  const points = []
  const stepSize = (maxT - minT) / steps
  
  for (let i = 0; i <= steps; i++) {
    const t = minT + i * stepSize
    if (t <= gamma) {
       points.push({ x: t, y: 0 })
       continue
    }
    
    const z = (t - gamma) / eta
    const y = 1 - Math.exp(-Math.pow(z, beta))
    points.push({ x: t, y })
  }
  return points
}
