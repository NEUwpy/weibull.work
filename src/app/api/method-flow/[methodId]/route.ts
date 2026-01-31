import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export async function GET(
  request: NextRequest,
  { params }: { params: { methodId: string } }
) {
  const { methodId } = params

  try {
    // Construct path to flow data file
    const flowPath = path.join(process.cwd(), 'src', 'data', 'method_flows', `${methodId.toLowerCase()}.json`)

    // Check if file exists
    if (!fs.existsSync(flowPath)) {
      return NextResponse.json({ error: 'Flow data not found' }, { status: 404 })
    }

    // Read and parse JSON
    const flowData = JSON.parse(fs.readFileSync(flowPath, 'utf-8'))

    return NextResponse.json(flowData)
  } catch (error) {
    console.error(`Error loading flow data for ${methodId}:`, error)
    return NextResponse.json({ error: 'Failed to load flow data' }, { status: 500 })
  }
}
