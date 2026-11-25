<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TripRequest } from '../types'

const emit = defineEmits<{ (e: 'submit', payload: TripRequest): void }>()

function fmt(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const startDate = ref(fmt(new Date(Date.now() + 7 * 86400000)))
const endDate = ref(fmt(new Date(Date.now() + 9 * 86400000)))
const city = ref('北京')
const preferences = ref('历史文化与城市漫步，节奏不要太赶')
const budgetLevel = ref('中等')
const transportation = ref('公共交通')
const accommodation = ref('经济型酒店')

const cities = ['北京', '上海', '杭州', '成都', '西安']

const days = computed(() => {
  const start = new Date(startDate.value)
  const end = new Date(endDate.value)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0
  return Math.round((end.getTime() - start.getTime()) / 86400000) + 1
})

const error = computed(() => {
  if (!city.value.trim()) return '请填写目的地城市'
  if (days.value <= 0) return '结束日期不能早于开始日期'
  if (days.value > 15) return '单次最多规划 15 天'
  return ''
})

function pickCity(name: string) {
  city.value = name
}

function submit() {
  if (error.value) return
  emit('submit', {
    city: city.value.trim(),
    startDate: startDate.value,
    endDate: endDate.value,
    days: days.value,
    preferences: preferences.value.trim(),
    budgetLevel: budgetLevel.value,
    transportation: transportation.value,
    accommodation: accommodation.value,
  })
}
</script>

<template>
  <section class="card planner">
    <div class="head">
      <div>
        <h2>去哪儿玩？</h2>
        <p class="muted">填写需求，Agent 会并行检索景点、天气与酒店，再编排每日行程。</p>
      </div>
      <span class="pill">{{ days > 0 ? `${days} 天` : '—' }}</span>
    </div>

    <div class="grid two">
      <label class="field">
        <span>目的地</span>
        <input v-model="city" placeholder="例如：北京" maxlength="32" />
      </label>
      <div class="field">
        <span>出发 / 返程</span>
        <div class="dates">
          <input v-model="startDate" type="date" />
          <span class="tilde">—</span>
          <input v-model="endDate" type="date" />
        </div>
      </div>
    </div>

    <div class="chips">
      <button
        v-for="name in cities"
        :key="name"
        class="chip"
        :class="{ active: city === name }"
        type="button"
        @click="pickCity(name)"
      >
        {{ name }}
      </button>
    </div>

    <label class="field">
      <span>偏好</span>
      <textarea
        v-model="preferences"
        rows="3"
        maxlength="200"
        placeholder="例如：喜欢人文历史，少走路，带老人同行"
      />
    </label>

    <div class="grid three">
      <label class="field">
        <span>预算档位</span>
        <select v-model="budgetLevel">
          <option>经济</option>
          <option>中等</option>
          <option>舒适</option>
        </select>
      </label>
      <label class="field">
        <span>市内交通</span>
        <select v-model="transportation">
          <option>公共交通</option>
          <option>地铁</option>
          <option>打车</option>
          <option>自驾</option>
          <option>步行</option>
        </select>
      </label>
      <label class="field">
        <span>住宿偏好</span>
        <select v-model="accommodation">
          <option>经济型酒店</option>
          <option>精品民宿</option>
          <option>舒适型酒店</option>
          <option>豪华酒店</option>
        </select>
      </label>
    </div>

    <div class="foot">
      <p class="hint" :class="{ error }">{{ error || '未配置 Key 时使用内置样例数据，链路照常可用。' }}</p>
      <button class="btn btn-primary" :disabled="!!error" @click="submit">开始规划</button>
    </div>
  </section>
</template>

<style scoped>
.planner {
  padding: 30px 32px 26px;
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
}

.head h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.head p {
  margin: 0;
  font-size: 13px;
}

.pill {
  background: var(--primary-soft);
  color: var(--primary-deep);
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 999px;
  white-space: nowrap;
}

.grid {
  display: grid;
  gap: 16px;
}

.grid.two {
  grid-template-columns: 1fr 1.4fr;
}

.grid.three {
  grid-template-columns: repeat(3, 1fr);
}

.field {
  display: block;
  margin-bottom: 16px;
}

.field > span {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-soft);
  margin-bottom: 7px;
  letter-spacing: 0.02em;
}

.dates {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tilde {
  color: var(--ink-soft);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: -2px 0 18px;
}

.chip {
  font-size: 12px;
  color: var(--ink-soft);
  background: #f2f4fa;
  padding: 6px 14px;
  border-radius: 999px;
  transition: all 0.15s;
}

.chip:hover {
  background: #e8ecfa;
}

.chip.active {
  background: var(--primary);
  color: #fff;
}

.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 6px;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--ink-soft);
}

.hint.error {
  color: #d64545;
}

@media (max-width: 720px) {
  .planner {
    padding: 22px 18px;
  }

  .grid.two,
  .grid.three {
    grid-template-columns: 1fr;
  }

  .foot {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
