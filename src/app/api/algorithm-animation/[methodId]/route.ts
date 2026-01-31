import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export async function GET(
  request: NextRequest,
  { params }: { params: { methodId: string } }
) {
  const { methodId } = params

  try {
    // Construct path to animation data file
    const animationPath = path.join(
      process.cwd(),
      'src',
      'data',
      'algorithm_animations',
      `${methodId.toLowerCase()}.json`
    )

    // Check if file exists
    if (!fs.existsSync(animationPath)) {
      return NextResponse.json(
        { error: 'Animation data not found', methodId },
        { status: 404 }
      )
    }

    // Read and parse JSON
    const animationData = JSON.parse(
      fs.readFileSync(animationPath, 'utf-8')
    )

    return NextResponse.json(animationData)
  } catch (error) {
    console.error(`Error loading animation data for ${methodId}:`, error)
    return NextResponse.json(
      { error: 'Failed to load animation data' },
      { status: 500 }
    )
  }
}
