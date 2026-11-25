<script setup lang="ts">
import { computed } from 'vue'
import type { Budget, TripPlan, WeatherInfo } from '../types'

const props = defineProps<{
  plan: TripPlan
  budget: Budget
  version: number
  working: boolean
}>()

const emit = defineEmits<{
  (e: 'remove', dayIndex: number, attractionIndex: number): void
  (e: 'export'): void
  (e: 'restart'): void
}>()

function money(cents: number): string {
  return (cents / 100).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })
}

function price(value?: number): string {
  return !value ? '免费' : `¥${value}`
}

const breakdown = computed(() => {
  const b = props.budget
  const total = Math.max(b.totalCents, 1)
  return [
    { label: '景点门票', cents: b.attractionsCents, color: '#4f6ef7' },
    { label: '住宿', cents: b.hotelsCents, color: '#ff8a5b' },
    { label: '餐饮', cents: b.mealsCents, color: '#22b07d' },
    { label: '市内交通', cents: b.transportCents, color: '#a78bfa' },
  ].map((item) => ({ ...item, ratio: Math.round((item.cents / total) * 100) }))
})

const warnings = computed(() => props.plan.warnings ?? [])

function weatherOf(date: string): WeatherInfo | undefined {
  return props.plan.weather_info?.find((w) => w.date === date)
}

function initial(name: string): string {
  return name ? name.slice(0, 1) : '景'
}

const gradients = [
  'linear-gradient(135deg,#dfe7ff,#c2d0ff)',
  'linear-gradient(135deg,#ffe9df,#ffd3bf)',
  'linear-gradient(135deg,#e3f6ec,#c8ecd9)',
  'linear-gradient(135deg,#f0e8ff,#ddccff)',
]

function thumbStyle(index: number) {
  return { background: gradients[index % gradients.length] }
}
</script>

<template>
  <section class="result">
    <div class="card summary-card">
      <div class="summary-head">
        <div>
          <div class="place">{{ plan.city }}</div>
          <div class="dates">{{ plan.start_date }} — {{ plan.end_date }} · 共 {{ plan.days.length }} 天</div>
        </div>
        <span class="version">版本 v{{ version }}</span>
      </div>
      <p class="summary-text">{{ plan.summary }}</p>
      <div v-if="warnings.length" class="warnings">
        <span v-for="(w, i) in warnings" :key="i" class="warning">{{ w }}</span>
      </div>
    </div>

    <div class="layout">
      <div class="days">
        <article v-for="day in plan.days" :key="day.day_index" class="card day-card">
          <header class="day-head">
            <div class="day-index">D{{ day.day_index + 1 }}</div>
            <div class="day-title">
              <strong>{{ day.date }}</strong>
              <span class="theme">{{ day.theme || '自由活动' }}</span>
            </div>
            <div v-if="weatherOf(day.date)" class="weather">
              <span>{{ weatherOf(day.date)?.day_weather }}</span>
              <span class="temp">
                {{ weatherOf(day.date)?.day_temp }}° / {{ weatherOf(day.date)?.night_temp }}°
              </span>
            </div>
          </header>

          <div class="attractions">
            <div
              v-for="(attraction, index) in day.attractions"
              :key="attraction.name + index"
              class="attraction"
            >
              <div class="thumb" :style="thumbStyle(index)">
                <img v-if="attraction.image_url" :src="attraction.image_url" :alt="attraction.name" />
                <span v-else>{{ initial(attraction.name) }}</span>
              </div>
              <div class="attraction-body">
                <div class="attraction-title">
                  <strong>{{ attraction.name }}</strong>
                  <span class="price">{{ price(attraction.ticket_price) }}</span>
                </div>
                <div class="meta">
                  <span v-if="attraction.address">{{ attraction.address }}</span>
                  <span v-if="attraction.visit_duration">{{ attraction.visit_duration }}</span>
                </div>
                <p v-if="attraction.description" class="desc">{{ attraction.description }}</p>
              </div>
              <button
                class="remove"
                :disabled="working"
                title="移除该景点，预算会自动重算"
                @click="emit('remove', day.day_index, index)"
              >
                移除
              </button>
            </div>

            <p v-if="!day.attractions.length" class="empty muted">
              当天暂无景点，可点击「重新规划」换一版行程。
            </p>
          </div>

          <div class="extras">
            <div class="extra-block">
              <span class="extra-label">餐饮</span>
              <div class="meal-list">
                <span v-for="meal in day.meals" :key="meal.type + meal.name" class="meal">
                  {{ meal.type }} · {{ meal.name }}
                  <em>¥{{ meal.estimated_cost ?? 0 }}</em>
                </span>
              </div>
            </div>
            <div v-if="day.hotel" class="extra-block">
              <span class="extra-label">住宿</span>
              <span class="extra-value">
                {{ day.hotel.name }}
                <em>¥{{ day.hotel.price_per_night ?? 0 }}/晚</em>
              </span>
            </div>
            <div class="extra-block">
              <span class="extra-label">交通</span>
              <span class="extra-value">
                {{ day.transportation || '公共交通' }}
                <em>¥{{ day.transportation_cost ?? 0 }}</em>
              </span>
            </div>
            <p v-if="day.notes" class="notes">{{ day.notes }}</p>
          </div>
        </article>
      </div>

      <aside class="sidebar">
        <div class="card budget-card">
          <span class="budget-label">单人预算</span>
          <div class="total">
            <span class="currency">¥</span>
            <strong>{{ money(budget.totalCents) }}</strong>
          </div>
          <p class="unit muted">{{ budget.unit }}估算 · 不含往返大交通</p>

          <div class="breakdown">
            <div v-for="item in breakdown" :key="item.label" class="breakdown-row">
              <div class="breakdown-head">
                <span>{{ item.label }}</span>
                <strong>¥{{ money(item.cents) }}</strong>
              </div>
              <div class="track">
                <div
                  class="track-fill"
                  :style="{ width: `${Math.max(item.ratio, 2)}%`, background: item.color }"
                />
              </div>
            </div>
          </div>

          <div class="daily">
            <div v-for="cost in budget.days" :key="cost.dayIndex" class="daily-row">
              <span>D{{ cost.dayIndex + 1 }} · {{ cost.date }}</span>
              <strong>¥{{ money(cost.totalCents) }}</strong>
            </div>
          </div>

          <div class="actions">
            <button class="btn btn-primary" :disabled="working" @click="emit('export')">导出 HTML</button>
            <button class="btn btn-ghost" :disabled="working" @click="emit('restart')">重新规划</button>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.summary-card {
  padding: 26px 30px;
  margin-bottom: 20px;
}

.summary-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.place {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.dates {
  color: var(--ink-soft);
  font-size: 13px;
  margin-top: 6px;
}

.version {
  font-size: 12px;
  color: var(--primary-deep);
  background: var(--primary-soft);
  padding: 6px 12px;
  border-radius: 999px;
  white-space: nowrap;
}

.summary-text {
  margin: 18px 0 0;
  color: #3c4761;
  line-height: 1.75;
  font-size: 14px;
}

.warnings {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.warning {
  font-size: 12px;
  color: #9a5b00;
  background: #fff5e2;
  border: 1px solid #ffe3b3;
  padding: 4px 10px;
  border-radius: 8px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  align-items: start;
}

.days {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.day-card {
  padding: 22px 24px;
}

.day-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}

.day-index {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--primary-soft);
  color: var(--primary-deep);
  font-weight: 700;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.day-title {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.theme {
  font-size: 12px;
  color: var(--ink-soft);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.weather {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 12px;
  color: var(--ink-soft);
}

.weather .temp {
  font-weight: 600;
  color: var(--ink);
}

.attractions {
  display: flex;
  flex-direction: column;
}

.attraction {
  display: flex;
  gap: 14px;
  padding: 16px 0;
  border-bottom: 1px dashed #eef0f6;
}

.attraction:last-child {
  border-bottom: none;
}

.thumb {
  width: 58px;
  height: 58px;
  border-radius: 14px;
  flex-shrink: 0;
  overflow: hidden;
  display: grid;
  place-items: center;
  color: #4b5a7d;
  font-weight: 700;
  font-size: 20px;
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.attraction-body {
  flex: 1;
  min-width: 0;
}

.attraction-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.attraction-title strong {
  font-size: 15px;
}

.price {
  font-size: 12px;
  color: var(--accent);
  font-weight: 600;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: var(--ink-soft);
  margin-top: 4px;
}

.desc {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.65;
  color: #4a5570;
}

.remove {
  align-self: flex-start;
  font-size: 12px;
  color: #9aa3b8;
  padding: 5px 10px;
  border-radius: 8px;
  transition: all 0.15s;
}

.remove:hover:not(:disabled) {
  background: #fff0f0;
  color: #d64545;
}

.remove:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.empty {
  font-size: 13px;
  padding: 14px 0;
  margin: 0;
}

.extras {
  margin-top: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.extra-block {
  display: flex;
  gap: 12px;
  font-size: 13px;
  align-items: baseline;
}

.extra-label {
  font-size: 11px;
  color: #8b94a9;
  background: #f2f4fa;
  padding: 3px 8px;
  border-radius: 6px;
  flex-shrink: 0;
}

.extra-value {
  color: #3c4761;
}

.extra-value em,
.meal em {
  font-style: normal;
  color: var(--ink-soft);
  font-size: 12px;
  margin-left: 6px;
}

.meal-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
}

.meal {
  color: #3c4761;
}

.notes {
  margin: 2px 0 0;
  font-size: 12px;
  color: #8b94a9;
}

.sidebar {
  position: sticky;
  top: 24px;
}

.budget-card {
  padding: 26px 24px;
}

.budget-label {
  font-size: 12px;
  color: var(--ink-soft);
  letter-spacing: 0.06em;
}

.total {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 6px;
}

.total .currency {
  font-size: 18px;
  color: var(--ink-soft);
}

.total strong {
  font-size: 38px;
  letter-spacing: -0.03em;
}

.unit {
  margin: 2px 0 20px;
  font-size: 12px;
}

.breakdown {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line);
}

.breakdown-head {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin-bottom: 7px;
  color: #3c4761;
}

.track {
  height: 6px;
  background: #f0f2f8;
  border-radius: 999px;
  overflow: hidden;
}

.track-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.4s ease;
}

.daily {
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
  border-bottom: 1px solid var(--line);
}

.daily-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--ink-soft);
}

.daily-row strong {
  color: var(--ink);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 18px;
}

.actions .btn {
  width: 100%;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }
}
</style>
