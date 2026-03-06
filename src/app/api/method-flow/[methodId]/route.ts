import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

// ========================================
// 类型定义
// ========================================

interface FormulaSymbol {
  symbol: string
  meaning: string
}

interface Formula {
  expression: string
  symbols: FormulaSymbol[]
  explanation: string
}

interface Variable {
  symbol: string    // 数学符号
  meaning: string   // 含义说明
  code: string      // 代码变量名
}

interface FlowStep {
  id: number
  name: string
  description: string
  codeLines: number[]
  formula: Formula
  inputs: Variable[]
  outputs: Variable[]
  isLoop?: boolean
  loopCount?: string
}

interface MethodFlow {
  methodId: string
  methodName: string
  description: string
  code: string[]
  steps: FlowStep[]
}

// ========================================
// 辅助函数
// ========================================

/**
 * 解析符号说明字符串
 * 新格式: code|symbol|meaning (三字段，用 | 分隔)
 * 旧格式兼容: symbol=meaning (两字段)
 */
function parseSymbols(symbolsStr: string): FormulaSymbol[] {
  if (!symbolsStr.trim()) return []

  return symbolsStr.split(',').map(s => {
    const trimmed = s.trim()

    // 新格式：code|symbol|meaning
    if (trimmed.includes('|')) {
      const parts = trimmed.split('|')
      if (parts.length >= 3) {
        return {
          symbol: parts[1].trim(),
          meaning: parts.slice(2).join('|').trim()
        }
      } else if (parts.length === 2) {
        return {
          symbol: parts[0].trim(),
          meaning: parts[1].trim()
        }
      }
    }

    // 旧格式：symbol=meaning
    const parts = trimmed.split('=')
    if (parts.length >= 2) {
      return {
        symbol: parts[0].trim(),
        meaning: parts[1].trim()
      }
    }

    return {
      symbol: trimmed,
      meaning: trimmed
    }
  }).filter(s => s.symbol)
}

/**
 * 解析变量字符串
 * 新格式: code|symbol|meaning (三字段，用 | 分隔)
 * 旧格式兼容: code:symbol 或 code=symbol (两字段)
 */
function parseVariables(varsStr: string): Variable[] {
  if (!varsStr.trim()) return []

  return varsStr.split(',').map(v => {
    const trimmed = v.trim()

    // 新格式：code|symbol|meaning (三个字段)
    if (trimmed.includes('|')) {
      const parts = trimmed.split('|')
      if (parts.length >= 3) {
        return {
          code: parts[0].trim(),
          symbol: parts[1].trim(),
          meaning: parts.slice(2).join('|').trim() // 含义可能包含 |
        }
      } else if (parts.length === 2) {
        return {
          code: parts[0].trim(),
          symbol: parts[1].trim(),
          meaning: parts[1].trim()
        }
      }
    }

    // 旧格式兼容：code:symbol 或 code=symbol
    const parts = trimmed.split(/[=:]/)
    if (parts.length >= 2) {
      return {
        code: parts[0].trim(),
        symbol: parts[1].trim(),
        meaning: parts[1].trim()
      }
    }

    return {
      code: trimmed,
      symbol: trimmed,
      meaning: trimmed
    }
  }).filter(v => v.code || v.symbol)
}

/**
 * 从 Python 源码解析步骤信息
 */
function parsePythonSource(code: string, methodId: string): MethodFlow {
  const lines = code.split('\n')
  const steps: FlowStep[] = []

  // 提取文件头信息
  let methodName = methodId.toUpperCase()
  let description = ''

  // 匹配文件头 docstring
  const docstringMatch = code.match(/"""([\s\S]*?)"""?/)
  if (docstringMatch) {
    const docstring = docstringMatch[1]
    const docLines = docstring.split('\n')

    // 第一行通常是方法名称
    if (docLines[0]?.trim()) {
      methodName = docLines[0].trim()
    }

    // 查找描述行
    for (const line of docLines) {
      if (line.startsWith('描述:') || line.startsWith('描述：')) {
        description = line.replace(/^描述[:：]\s*/, '').trim()
        break
      }
    }
  }

  // 解析 @step 注释
  let currentStep: Partial<FlowStep> | null = null
  let stepStartLine = -1

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 检测 @step 标记
    const stepMatch = line.match(/#\s*@step:\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*(.+)/)
    if (stepMatch) {
      // 保存上一个步骤
      if (currentStep && stepStartLine >= 0) {
        // 找到上一个步骤的代码行范围（到当前行之前）
        currentStep.codeLines = Array.from(
          { length: i - stepStartLine },
          (_, idx) => stepStartLine + idx
        )
        steps.push(currentStep as FlowStep)
      }

      // 开始新步骤
      currentStep = {
        id: parseInt(stepMatch[1]),
        name: stepMatch[2].trim(),
        description: stepMatch[3].trim(),
        codeLines: [],
        formula: {
          expression: '',
          symbols: [],
          explanation: ''
        },
        inputs: [],
        outputs: []
      }
      stepStartLine = i
      continue
    }

    // 如果在步骤块内，解析其他标记
    if (currentStep) {
      // @formula 标记
      const formulaMatch = line.match(/#\s*@formula:\s*(.+)/)
      if (formulaMatch) {
        currentStep.formula!.expression = formulaMatch[1].trim()
        continue
      }

      // @symbols 标记
      const symbolsMatch = line.match(/#\s*@symbols:\s*(.+)/)
      if (symbolsMatch) {
        currentStep.formula!.symbols = parseSymbols(symbolsMatch[1])
        continue
      }

      // @inputs 标记
      const inputsMatch = line.match(/#\s*@inputs:\s*(.+)/)
      if (inputsMatch) {
        currentStep.inputs = parseVariables(inputsMatch[1])
        continue
      }

      // @outputs 标记
      const outputsMatch = line.match(/#\s*@outputs:\s*(.+)/)
      if (outputsMatch) {
        currentStep.outputs = parseVariables(outputsMatch[1])
        continue
      }

      // @loop 标记
      const loopMatch = line.match(/#\s*@loop:\s*(.+)/)
      if (loopMatch) {
        currentStep.isLoop = true
        currentStep.loopCount = loopMatch[1].trim()
        continue
      }
    }
  }

  // 保存最后一个步骤
  if (currentStep && stepStartLine >= 0) {
    currentStep.codeLines = Array.from(
      { length: lines.length - stepStartLine },
      (_, idx) => stepStartLine + idx
    )
    steps.push(currentStep as FlowStep)
  }

  // 修正每个步骤的代码行范围，使其不超出到下一个步骤
  for (let i = 0; i < steps.length; i++) {
    const currentStepLines = steps[i].codeLines
    if (currentStepLines && currentStepLines.length > 0) {
      if (i < steps.length - 1) {
        const nextStepFirstLine = steps[i + 1].codeLines[0]
        steps[i].codeLines = currentStepLines.filter(l => l < nextStepFirstLine)
      }
    }
  }

  return {
    methodId,
    methodName,
    description,
    code: lines,
    steps
  }
}

// ========================================
// API Handler
// ========================================

export async function GET(
  request: NextRequest,
  { params }: { params: { methodId: string } }
) {
  const { methodId } = params

  try {
    // 读取 Python 源码文件
    const pyPath = path.join(process.cwd(), 'python', 'methods', `${methodId.toLowerCase()}.py`)

    if (!fs.existsSync(pyPath)) {
      return NextResponse.json({ error: 'Python source not found' }, { status: 404 })
    }

    const code = fs.readFileSync(pyPath, 'utf-8')
    const flowData = parsePythonSource(code, methodId)

    return NextResponse.json(flowData)
  } catch (error) {
    console.error(`Error loading flow data for ${methodId}:`, error)
    return NextResponse.json({ error: 'Failed to load flow data' }, { status: 500 })
  }
}
