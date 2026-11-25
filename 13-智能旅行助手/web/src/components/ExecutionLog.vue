<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { TraceEntry } from '../types'

const props = defineProps<{
  entries: TraceEntry[]
  phase: 'idle' | 'running' | 'done' | 'error'
}>()

const collapsed = ref(false)
const bodyRef = ref<HTMLElement | null>(null)

const phaseText = computed(() => {
  switch (props.phase) {
    case 'running':
      return '执行中'
    case 'done':
      return '已完成'
    case 'error':
      return '已中断'
    default:
      return '待命'
  }
})

// 新日志到达时滚动到底部，保证始终能看到最新一步
watch(
  () => props.entries.length,
  async () => {
    await nextTick()
    const el = bodyRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)
</script>

<template>
  <aside class="card trace" :class="[phase, { collapsed }]">
    <header class="trace-head">
      <div class="title">
        <span class="pulse" />
        执行追踪
        <span class="state">{{ phaseText }}</span>
      </div>
      <div class="head-right">
        <span class="count">{{ entries.length }} 条</span>
        <button class="toggle" @click="collapsed = !collapsed">
          {{ collapsed ? '展开' : '收起' }}
        </button>
      </div>
    </header>

    <div v-show="!collapsed" ref="bodyRef" class="trace-body">
      <p v-if="!entries.length" class="empty">
        提交需求后，这里会按时间顺序记录每一步：<br />
        前端提交 → Java 建任务 → Python 三路并发检索 → LLM 编排 → Java 算预算。
      </p>

      <ol v-else class="trace-list">
        <li v-for="(item, index) in entries" :key="index" :class="item.level">
          <span class="time">{{ item.time }}</span>
          <span class="tag">{{ item.tag }}</span>
          <span class="text">{{ item.text }}</span>
        </li>
      </ol>
    </div>

    <footer v-show="!collapsed" class="trace-foot">
      日志来自 SSE 实时事件，断线后按 Last-Event-ID 续传
    </footer>
  </aside>
</template>

<style scoped>
.trace {
  position: sticky;
  top: 24px;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  overflow: hidden;
  background: #0f1729;
  color: #cdd6ea;
  border: 1px solid #1e2942;
  box-shadow: 0 18px 50px rgba(15, 23, 41, 0.28);
}

.trace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.03);
}

.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #e8eeff;
}

.pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
}

.trace.running .pulse {
  background: #38bdf8;
  animation: breath 1.4s infinite;
}

.trace.done .pulse {
  background: #22c55e;
}

.trace.error .pulse {
  background: #f87171;
}

@keyframes breath {
  0% {
    box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.5);
  }
  70% {
    box-shadow: 0 0 0 8px rgba(56, 189, 248, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(56, 189, 248, 0);
  }
}

.state {
  font-size: 11px;
  font-weight: 500;
  color: #7c8aa8;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  padding: 2px 8px;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.count {
  font-size: 11px;
  color: #7c8aa8;
}

.toggle {
  font-size: 12px;
  color: #9fb0d0;
  padding: 2px 4px;
}

.toggle:hover {
  color: #fff;
}

.trace-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  scrollbar-width: thin;
}

.trace-body::-webkit-scrollbar {
  width: 6px;
}

.trace-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 999px;
}

.empty {
  margin: 8px 0;
  font-size: 12px;
  line-height: 1.9;
  color: #6b7a99;
}

.trace-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.trace-list li {
  display: grid;
  grid-template-columns: 58px 40px minmax(0, 1fr);
  gap: 6px;
  align-items: baseline;
  font-size: 12px;
  line-height: 1.65;
}

.time {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: #5f6e8d;
}

.tag {
  font-size: 10px;
  text-align: center;
  padding: 1px 0;
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.16);
  color: #a8b6d1;
  white-space: nowrap;
}

.text {
  color: #c3cee4;
  overflow-wrap: anywhere;
}

.trace-list li.ok .tag {
  background: rgba(34, 197, 94, 0.16);
  color: #4ade80;
}

.trace-list li.ok .text {
  color: #d9f7e3;
}

.trace-list li.warn .tag {
  background: rgba(251, 191, 36, 0.16);
  color: #fbbf24;
}

.trace-list li.warn .text {
  color: #fde68a;
}

.trace-list li.error .tag {
  background: rgba(248, 113, 113, 0.18);
  color: #f87171;
}

.trace-list li.error .text {
  color: #fecaca;
}

.trace-foot {
  padding: 9px 14px;
  font-size: 10px;
  color: #5f6e8d;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

@media (max-width: 1180px) {
  .trace {
    position: static;
    max-height: 340px;
  }
}
</style>
