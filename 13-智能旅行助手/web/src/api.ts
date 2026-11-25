import type { Attraction, Budget, TripPlan, TripRequest, TripView } from './types'

const ANON_KEY = 'trip_anon_id'

function newUuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return 'anon-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

/** 打开即用：前端生成并持久化匿名标识，不做登录 */
export const anonId: string = (() => {
  let value = localStorage.getItem(ANON_KEY)
  if (!value) {
    value = newUuid()
    localStorage.setItem(ANON_KEY, value)
  }
  document.cookie = `${ANON_KEY}=${value}; path=/; max-age=31536000`
  return value
})()

const BASE = '/api/trips'

function headers(extra?: Record<string, string>): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Anon-Id': anonId,
    ...extra,
  }
}

async function parseError(response: Response): Promise<never> {
  let message = `请求失败（HTTP ${response.status}）`
  try {
    const body = await response.json()
    if (body?.message) message = body.message
  } catch {
    // 忽略非 JSON 响应
  }
  throw new Error(message)
}

export async function createTrip(payload: TripRequest): Promise<{ jobId: string; created: boolean }> {
  const response = await fetch(BASE, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  })
  if (!response.ok) return parseError(response)
  return response.json()
}

export async function getTrip(jobId: string): Promise<TripView> {
  const response = await fetch(`${BASE}/${jobId}`, { headers: headers() })
  if (!response.ok) return parseError(response)
  return response.json()
}

export async function updateAttractions(
  jobId: string,
  dayIndex: number,
  attractions: Attraction[],
): Promise<{ plan: TripPlan; budget: Budget; version: number }> {
  const response = await fetch(`${BASE}/${jobId}/days/${dayIndex}/attractions`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ attractions }),
  })
  if (!response.ok) return parseError(response)
  return response.json()
}

export async function exportTrip(jobId: string): Promise<Blob> {
  const response = await fetch(`${BASE}/${jobId}/export`, {
    method: 'POST',
    headers: headers(),
  })
  if (!response.ok) return parseError(response)
  return response.blob()
}

/** EventSource 不能带自定义请求头，anonId 通过查询参数传递 */
export function eventsUrl(jobId: string): string {
  return `${BASE}/${jobId}/events?anonId=${encodeURIComponent(anonId)}`
}
