import { NextRequest, NextResponse } from 'next/server'
import OpenAI from 'openai'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

// Load config from JSON
const configPath = path.join(process.cwd(), 'src/app/api/chat/config.json')
const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'))

// Initialize Moonshot API client
const client = new OpenAI({
  apiKey: config.moonshot.apiKey,
  baseURL: config.moonshot.baseURL
})

// Helper: Read text file with encoding detection
function readTextFile(filePath: string): string {
  const buffer = fs.readFileSync(filePath)
  try {
    const decoder = new TextDecoder('utf-8', { fatal: true })
    return decoder.decode(buffer)
  } catch (e) {
    try {
      const decoder = new TextDecoder('gbk')
      return decoder.decode(buffer)
    } catch (e2) {
      return buffer.toString('binary')
    }
  }
}

// Helper: Extract headings from markdown
function extractHeadings(markdown: string) {
  const headings: { level: number; text: string; slug: string }[] = []
  const lines = markdown.split(/\r?\n/)
  const headingRegex = /^(#{1,3})\s+(.+)$/

  lines.forEach(line => {
    const match = line.trimEnd().match(headingRegex)
    if (match) {
      const text = match[2].trim()
      const slug = text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w\u4e00-\u9fa5-]/g, '')
      headings.push({ level: match[1].length, text, slug })
    }
  })
  return headings
}

// Helper: Read prompt template
function readPromptTemplate(filename: string): string {
  const filePath = path.join(process.cwd(), 'src/content/prompts', filename)
  if (!fs.existsSync(filePath)) {
    console.warn(`Prompt template not found: ${filename}`)
    return ''
  }
  const { content } = matter(readTextFile(filePath))
  return content
}

// Helper: Create a timeout promise
function timeoutPromise(ms: number, message: string) {
  return new Promise((_, reject) =>
    setTimeout(() => reject(new Error(message)), ms)
  )
}

// STAGE 1: Filter papers based on user query
async function stage1FilterPapers(
  userQuery: string,
  papers: any[],
  model: string,
  temperature: number,
  controller?: ReadableStreamDefaultController<any>,
  encoder?: TextEncoder
): Promise<string[]> {
  // Simplify data to reduce token count - only send essential info
  const papersData = papers.map(p => ({
    id: p.slug,
    title: p.title,
    tags: p.tags || []
  }))

  const systemPrompt = readPromptTemplate('rag_stage1_filter.md') +
    '\n\n# 当前任务\n' +
    `用户问题：${userQuery}\n\n` +
    `文献列表（精简版）：\n${JSON.stringify(papersData, null, 2)}`

  // Send debug info
  if (controller && encoder) {
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      debug: {
        stage: 'Stage 1: 筛选文献',
        action: '发送API请求',
        payload: {
          model,
          prompt: systemPrompt.slice(0, 200) + '...'
        }
      }
    })}\n\n`))
  }

  try {
    const response = await client.chat.completions.create({
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: '请返回相关的文献列表（JSON格式）' }
      ],
      temperature,
      max_tokens: 4096
    })

    const content = response.choices[0]?.message?.content || ''

    // Send debug response
    if (controller && encoder) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({
        debug: {
          stage: 'Stage 1: 筛选文献',
          action: '收到API响应',
          response: content.slice(0, 300) + '...'
        }
      })}\n\n`))
    }

    const jsonMatch = content.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      const result = JSON.parse(jsonMatch[0])
      const slugs = result.relevant_papers?.map((p: any) => p.slug) || []

      if (controller && encoder) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          debug: {
            stage: 'Stage 1: 筛选文献',
            action: '解析结果',
            result: `找到 ${slugs.length} 篇相关文献: ${slugs.join(', ')}`
          }
        })}\n\n`))
      }

      return slugs
    }
  } catch (error) {
    console.error('Stage 1 error:', error)
    if (controller && encoder) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({
        debug: {
          stage: 'Stage 1: 筛选文献',
          action: 'API错误',
          error: String(error)
        }
      })}\n\n`))
    }
  }

  // Fallback: Return all papers
  return papers.map(p => p.slug)
}

// STAGE 2: Rank sections based on user query
async function stage2RankSections(
  userQuery: string,
  paperSlugs: string[],
  model: string,
  temperature: number,
  controller?: ReadableStreamDefaultController<any>,
  encoder?: TextEncoder
): Promise<any[]> {
  const contentDir = path.join(process.cwd(), 'src/content')
  const paperTocs: any[] = []

  // Read TOC from each paper
  paperSlugs.forEach(slug => {
    const filePaths = [
      path.join(contentDir, `${slug}-pdf翻译.md`),
      path.join(contentDir, `${slug}-pdf原文.md`)
    ]

    for (const filePath of filePaths) {
      if (fs.existsSync(filePath)) {
        const content = readTextFile(filePath)
        const { data } = matter(content)
        const body = content.slice(content.indexOf('---', 3) + 3)
        const headings = extractHeadings(body)

        // Limit headings to reduce token count
        const limitedHeadings = headings.slice(0, 50)

        paperTocs.push({
          slug,
          title: data.title || slug,
          headings: limitedHeadings
        })
        break
      }
    }
  })

  const systemPrompt = readPromptTemplate('rag_stage2_rank.md') +
    '\n\n# 当前任务\n' +
    `用户问题：${userQuery}\n\n` +
    `文献目录（已精简）：\n${JSON.stringify(paperTocs, null, 2)}`

  // Send debug info
  if (controller && encoder) {
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      debug: {
        stage: 'Stage 2: 分析章节',
        action: '读取文献目录',
        result: `从 ${paperSlugs.length} 篇文献中提取了 ${paperTocs.length} 篇的目录结构`
      }
    })}\n\n`))
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      debug: {
        stage: 'Stage 2: 分析章节',
        action: '发送API请求',
        payload: {
          model,
          prompt: systemPrompt.slice(0, 200) + '...'
        }
      }
    })}\n\n`))
  }

  try {
    const response = await Promise.race([
      client.chat.completions.create({
        model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: '请返回相关的章节列表（JSON格式）' }
        ],
        temperature,
        max_tokens: 4096
      }),
      timeoutPromise(120000, 'Stage 2 API timeout after 120s')
    ]) as any

    console.log('Stage 2 - API response received')

    const content = response.choices[0]?.message?.content || ''

    // Send debug response
    if (controller && encoder) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({
        debug: {
          stage: 'Stage 2: 分析章节',
          action: '收到API响应',
          response: content.slice(0, 300) + '...'
        }
      })}\n\n`))
    }

    const jsonMatch = content.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      const result = JSON.parse(jsonMatch[0])
      const sections = result.relevant_sections || []

      if (controller && encoder) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          debug: {
            stage: 'Stage 2: 分析章节',
            action: '解析结果',
            result: `定位到 ${sections.length} 个相关章节`
          }
        })}\n\n`))
      }

      return sections
    }
  } catch (error) {
    console.error('Stage 2 error:', error)
    if (controller && encoder) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({
        debug: {
          stage: 'Stage 2: 分析章节',
          action: 'API错误',
          error: String(error)
        }
      })}\n\n`))
    }
  }

  return []
}

// STAGE 3: Generate answer with sources (streaming)
async function stage3GenerateAnswer(
  userQuery: string,
  sections: any[],
  model: string,
  temperature: number,
  controller: ReadableStreamDefaultController<any>,
  encoder: TextEncoder
): Promise<{ content: string; sources: string[] }> {
  const contentDir = path.join(process.cwd(), 'src/content')
  const sectionContents: any[] = []

  // Read section content
  sections.forEach((section: any) => {
    const filePaths = [
      path.join(contentDir, `${section.paper_slug}-pdf翻译.md`),
      path.join(contentDir, `${section.paper_slug}-pdf原文.md`)
    ]

    for (const filePath of filePaths) {
      if (fs.existsSync(filePath)) {
        const content = readTextFile(filePath)
        const { data } = matter(content)
        const body = content.slice(content.indexOf('---', 3) + 3)

        // Skip if no section_heading
        if (!section.section_heading) {
          console.warn('Missing section_heading for', section.paper_slug)
          break
        }

        // Find the section by heading
        const lines = body.split(/\r?\n/)
        let sectionStart = -1
        let sectionEnd = lines.length

        for (let i = 0; i < lines.length; i++) {
          const match = lines[i].match(/^#{1,3}\s+(.+)$/)
          if (match && match[2] && match[2].trim() === section.section_heading) {
            sectionStart = i
            continue
          }
          if (sectionStart >= 0 && lines[i].match(/^#{1,3}\s/)) {
            sectionEnd = i
            break
          }
        }

        if (sectionStart >= 0) {
          const sectionText = lines.slice(sectionStart, sectionEnd).join('\n')
          sectionContents.push({
            paper_slug: section.paper_slug,
            paper_title: section.paper_title,
            section_heading: section.section_heading,
            content: sectionText.slice(0, 3000) // Limit content length
          })
        }
        break
      }
    }
  })

  const systemPrompt = readPromptTemplate('rag_stage3_answer.md') +
    '\n\n# 当前任务\n' +
    `用户问题：${userQuery}\n\n` +
    `相关章节内容：\n${JSON.stringify(sectionContents, null, 2)}`

  const sources = Array.from(new Set(sectionContents.map(s => `[${s.paper_slug}] ${s.paper_title}`)))

  try {
    // Check if using k2.5 model (which supports thinking)
    const useThinking = model === 'kimi-k2.5'

    const response = await client.chat.completions.create({
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: '请基于以上文献内容回答用户问题' }
      ],
      temperature,
      max_tokens: 8192,
      stream: true,
      ...(useThinking && { thinking: { type: 'enabled' } as any })
    })

    let fullContent = ''
    let fullThinking = ''

    // Stream the response
    for await (const chunk of response) {
      const choice = chunk.choices[0]

      // Handle reasoning content (thinking)
      if (useThinking && (choice?.delta as any)?.reasoning_content) {
        fullThinking += (choice.delta as any).reasoning_content
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ thinking: (choice.delta as any).reasoning_content })}\n\n`))
      }

      // Handle regular content
      if (choice?.delta?.content) {
        fullContent += choice.delta.content
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ content: choice.delta.content })}\n\n`))
      }
    }

    // Send final message with sources
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({ sources, done: true })}\n\n`))

    return { content: fullContent, sources }
  } catch (error) {
    console.error('Stage 3 error:', error)
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({ content: '抱歉，生成回答时发生错误。', sources: [] })}\n\n`))
    return { content: '抱歉，生成回答时发生错误。', sources }
  }
}

// Main API handler
export async function POST(request: NextRequest) {
  try {
    const { question, papers, modelKey } = await request.json()

    if (!question || !papers) {
      return NextResponse.json({ error: 'Missing question or papers' }, { status: 400 })
    }

    // Get model config from config, use default if not specified
    const modelConfig = modelKey && config.moonshot.models[modelKey]
      ? config.moonshot.models[modelKey]
      : config.moonshot.models[config.moonshot.defaultModel]

    // Handle both old format (string) and new format (object with id and temperature)
    const model = typeof modelConfig === 'string' ? modelConfig : modelConfig.id
    const modelTemp = typeof modelConfig === 'object' && modelConfig.temperature ? modelConfig.temperature : 1

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      async start(controller) {
        try {
          // STAGE 1: Filter papers
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ stage: 'filtering', message: '正在分析问题，筛选相关文献...' })}\n\n`))
          const relevantPaperSlugs = await stage1FilterPapers(question, papers, model, modelTemp, controller, encoder)
          console.log('Stage 1 - Relevant papers:', relevantPaperSlugs)

          // STAGE 2: Rank sections
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ stage: 'ranking', message: '正在深入分析相关章节...' })}\n\n`))
          const relevantSections = await stage2RankSections(question, relevantPaperSlugs, model, modelTemp, controller, encoder)
          console.log('Stage 2 - Relevant sections:', relevantSections.length)

          // STAGE 3: Generate answer (with streaming)
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ stage: 'generating', message: '正在思考并生成回答...' })}\n\n`))
          await stage3GenerateAnswer(question, relevantSections, model, modelTemp, controller, encoder)

          controller.enqueue(encoder.encode('data: [DONE]\n\n'))
        } catch (error) {
          console.error('Streaming error:', error)
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ content: '发生错误，请稍后重试。', sources: [] })}\n\n`))
        } finally {
          controller.close()
        }
      }
    })

    return new NextResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
      }
    })

  } catch (error) {
    console.error('API error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// GET: Return available models
export async function GET() {
  return NextResponse.json({
    models: config.moonshot.models,
    defaultModel: config.moonshot.defaultModel
  })
}

// Allow OPTIONS for CORS
export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    }
  })
}
