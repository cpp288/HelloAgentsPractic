export interface TripRequest {
  city: string
  startDate: string
  endDate: string
  days: number
  preferences?: string
  budgetLevel?: string
  transportation?: string
  accommodation?: string
}

export interface Attraction {
  name: string
  address?: string
  visit_duration?: string
  description?: string
  ticket_price?: number
  latitude?: number | null
  longitude?: number | null
  image_url?: string | null
}

export interface WeatherInfo {
  date: string
  day_weather?: string
  night_weather?: string
  day_temp?: number
  night_temp?: number
  wind?: string
}

export interface Hotel {
  name: string
  address?: string
  price_per_night?: number
  rating?: string
}

export interface Meal {
  type: string
  name: string
  description?: string
  estimated_cost?: number
}

export interface DayPlan {
  day_index: number
  date: string
  theme: string
  attractions: Attraction[]
  meals: Meal[]
  hotel?: Hotel | null
  transportation?: string
  transportation_cost?: number
  notes?: string
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  summary: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  warnings?: string[]
}

export interface DayCost {
  dayIndex: number
  date: string
  attractionsCents: number
  hotelsCents: number
  mealsCents: number
  transportCents: number
  totalCents: number
}

export interface Budget {
  attractionsCents: number
  hotelsCents: number
  mealsCents: number
  transportCents: number
  totalCents: number
  currency: string
  unit: string
  days: DayCost[]
}

export interface TripView {
  jobId: string
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  request?: Record<string, unknown>
  tripId?: string
  version?: number
  plan?: TripPlan
  budget?: Budget
  errorCode?: string
  errorMessage?: string
}

export interface ProgressEvent {
  stage: string
  percent: number
  text: string
}

export type TraceLevel = 'info' | 'ok' | 'warn' | 'error'

/** 右侧执行追踪面板的一条日志 */
export interface TraceEntry {
  time: string
  tag: string
  text: string
  level: TraceLevel
}
