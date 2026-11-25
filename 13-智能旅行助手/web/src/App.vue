<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import ExecutionLog from './components/ExecutionLog.vue'
import PlannerForm from './components/PlannerForm.vue'
import ProgressPanel from './components/ProgressPanel.vue'
import TripResult from './components/TripResult.vue'
import { createTrip, eventsUrl, exportTrip, getTrip, updateAttractions } from './api'
import type { Budget, TraceEntry, TraceLevel, TripPlan, TripRequest, TripView } from './types'

type Phase = 'idle' | 'running' | 'done' | 'error'

const phase = ref<Phase>('idle')
const percent = ref(0)
const stageText = ref('')
const trace = ref<TraceEntry[]>([])
const plan = ref<TripPlan | null>(null)
const budget = ref<Budget | null>(null)
const version = ref(1)
const jobId = ref('')
const errorText = ref('')
const working = ref(false)

let source: EventSource | null = null
let pollTimer: number | null = null

function stamp() {
  const now = new Date()
  const pad = (value: number, size = 2) => String(value).padStart(size, '0')
  return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function pushTrace(tag: string, text: string, level: TraceLevel = 'info') {
  if (!text) return
  const last = trace.value[trace.value.length - 1]
  if (last && last.text === text && last.tag === tag) return
  trace.value.push({ time: stamp(), tag, text, level })
}

function closeStream() {
  if (source) {
    source.close()
    source = null
  }
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function applyView(view: TripView) {
  if (view.plan) plan.value = view.plan
  if (view.budget) budget.value = view.budget
  if (typeof view.version === 'number') version.value = view.version
}

function fail(message: string) {
  closeStream()
  stopPolling()
  errorText.value = message
  phase.value = 'error'
  pushTrace('错误', message, 'error')
}

async function refresh(job: string): Promise<TripView | null> {
  try {
    const view = await getTrip(job)
    applyView(view)
    return view
  } catch (e) {
    return null
  }
}

async function settle(job: string) {
  closeStream()
  stopPolling()
  pushTrace('Java', '收到 done 事件，读取行程与预算')
  const view = await refresh(job)
  if (!view) {
    fail('行程已生成，但读取结果失败，请稍后重试。')
    return
  }
  if (view.status === 'SUCCEEDED' && view.plan && view.budget) {
    percent.value = 100
    phase.value = 'done'
    pushTrace(
      '完成',
      `${view.plan.city} · ${view.plan.days.length} 天 · 预算 ¥${(view.budget.totalCents / 100).toFixed(0)}，版本 v${view.version ?? 1}`,
      'ok',
    )
  } else if (view.status === 'FAILED') {
    fail(view.errorMessage || '生成失败，请重试。')
  } else {
    fail('连接已断开，任务可能仍在后台执行，请稍后刷新重试。')
  }
}

/** SSE 断开时兜底轮询，避免事件丢失后页面卡住 */
function startPolling(job: string) {
  if (pollTimer !== null) return
  pushTrace('SSE', '连接中断，切换为每 2 秒轮询任务状态', 'warn')
  pollTimer = window.setInterval(async () => {
    const view = await refresh(job)
    if (!view) return
    if (view.status === 'SUCCEEDED') {
      percent.value = 100
      phase.value = 'done'
      closeStream()
      stopPolling()
      pushTrace('完成', '轮询到任务成功，已加载行程', 'ok')
    } else if (view.status === 'FAILED') {
      fail(view.errorMessage || '生成失败，请重试。')
    }
  }, 2000)
}

function openStream(job: string) {
  closeStream()
  pushTrace('SSE', `连接事件流 /api/trips/${job}/events`)
  source = new EventSource(eventsUrl(job))

  source.addEventListener('progress', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as {
      stage?: string
      percent?: number
      text?: string
    }
    // 前端只推进不退步，避免并发节点事件乱序导致进度回跳
    percent.value = Math.max(percent.value, Math.min(data.percent ?? 0, 99))
    stageText.value = data.text || stageText.value
  })

  // 详细执行追踪：Java / Python 各节点与工具调用都会以 trace 事件推送
  source.addEventListener('trace', (event) => {
    try {
      const data = JSON.parse((event as MessageEvent).data) as {
        tag?: string
        text?: string
        level?: TraceLevel
      }
      pushTrace(data.tag || '事件', data.text || '', data.level || 'info')
    } catch {
      // 忽略无法解析的追踪事件
    }
  })

  source.addEventListener('done', () => {
    void settle(job)
  })

  source.addEventListener('error', (event) => {
    const message = (event as MessageEvent).data
    if (message) {
      try {
        const data = JSON.parse(message) as { message?: string; traceId?: string }
        fail(data.message || '生成失败，请重试。')
      } catch {
        fail('生成失败，请重试。')
      }
      return
    }
    // 浏览器层面的连接错误：回落到轮询
    source?.close()
    source = null
    startPolling(job)
  })
}

async function onSubmit(payload: TripRequest) {
  phase.value = 'running'
  percent.value = 4
  stageText.value = '正在创建规划任务'
  trace.value = []
  errorText.value = ''
  plan.value = null
  budget.value = null
  version.value = 1

  pushTrace('前端', `提交需求：${payload.city} · ${payload.days} 天 · ${payload.budgetLevel ?? '中等'}预算`)
  try {
    const created = await createTrip(payload)
    jobId.value = created.jobId
    pushTrace(
      'Java',
      created.created
        ? `POST /api/trips 返回 202，jobId=${created.jobId}`
        : `命中 10 分钟幂等缓存，复用 jobId=${created.jobId}`,
    )
    openStream(created.jobId)
  } catch (e) {
    fail(e instanceof Error ? e.message : '提交失败，请检查服务是否启动。')
  }
}

async function onRemove(dayIndex: number, attractionIndex: number) {
  if (!plan.value || working.value) return
  const day = plan.value.days.find((item) => item.day_index === dayIndex)
  if (!day) return

  const removed = day.attractions[attractionIndex]
  const before = budget.value?.totalCents ?? 0
  const next = day.attractions.filter((_, index) => index !== attractionIndex)
  working.value = true
  pushTrace('编辑', `D${dayIndex + 1} 移除景点「${removed?.name ?? '未知'}」`)
  try {
    const result = await updateAttractions(jobId.value, dayIndex, next)
    applyView({ ...result, jobId: jobId.value, status: 'SUCCEEDED' })
    pushTrace(
      'Java',
      `PATCH 成功，预算 ¥${(before / 100).toFixed(0)} → ¥${(result.budget.totalCents / 100).toFixed(0)}，版本 v${result.version}`,
      'ok',
    )
  } catch (e) {
    pushTrace('错误', e instanceof Error ? e.message : '移除失败', 'error')
  } finally {
    working.value = false
  }
}

async function onExport() {
  if (!jobId.value || working.value) return
  working.value = true
  pushTrace('导出', '请求服务端渲染 HTML')
  try {
    const blob = await exportTrip(jobId.value)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${plan.value?.city || '行程'}-旅行计划.html`
    link.click()
    URL.revokeObjectURL(url)
    pushTrace('导出', `已生成 ${(blob.size / 1024).toFixed(1)} KB HTML，触发下载`, 'ok')
  } catch (e) {
    pushTrace('错误', e instanceof Error ? e.message : '导出失败', 'error')
  } finally {
    working.value = false
  }
}

function reset() {
  closeStream()
  stopPolling()
  phase.value = 'idle'
  percent.value = 0
  stageText.value = ''
  trace.value = []
  plan.value = null
  budget.value = null
  errorText.value = ''
  jobId.value = ''
}

onBeforeUnmount(() => {
  closeStream()
  stopPolling()
})
</script>

<template>
  <div class="page with-trace">
    <main class="main">
      <header class="hero">
        <div>
          <h1>智能旅行助手</h1>
          <p>Java 业务层 + Python Agent 层 · 无 Key 也能跑通的端到端链路</p>
        </div>
        <span class="hero-badge">打开即用 · 无需登录</span>
      </header>

      <PlannerForm v-if="phase === 'idle'" @submit="onSubmit" />

      <ProgressPanel v-else-if="phase === 'running'" :percent="percent" :text="stageText" />

      <TripResult
        v-else-if="phase === 'done' && plan && budget"
        :plan="plan"
        :budget="budget"
        :version="version"
        :working="working"
        @remove="onRemove"
        @export="onExport"
        @restart="reset"
      />

      <section v-else-if="phase === 'error'" class="card error-card">
        <h2>规划失败</h2>
        <p class="muted">{{ errorText }}</p>
        <div class="error-actions">
          <button class="btn btn-primary" @click="reset">重新填写</button>
        </div>
      </section>
    </main>

    <ExecutionLog :entries="trace" :phase="phase" />
  </div>
</template>

<style scoped>
.page.with-trace {
  max-width: 1480px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 350px;
  gap: 24px;
  align-items: start;
}

.main {
  min-width: 0;
}

.error-card {
  padding: 40px 36px;
}

.error-card h2 {
  margin: 0 0 10px;
  font-size: 20px;
}

.error-card p {
  margin: 0 0 22px;
  font-size: 14px;
  line-height: 1.7;
}

.error-actions {
  display: flex;
  gap: 12px;
}

@media (max-width: 1180px) {
  .page.with-trace {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .page.with-trace {
    padding: 20px 14px 40px;
  }
}
</style>
