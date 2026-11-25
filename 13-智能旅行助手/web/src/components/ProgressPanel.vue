<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  percent: number
  text: string
}>()

const ring = computed(() => `${Math.max(2, Math.min(props.percent, 100))}%`)
</script>

<template>
  <section class="card progress">
    <div class="ring" :style="{ background: `conic-gradient(#4f6ef7 ${ring}, #eef1f8 ${ring})` }">
      <div class="ring-inner">
        <strong>{{ Math.round(percent) }}<small>%</small></strong>
      </div>
    </div>

    <div class="detail">
      <div class="live">
        <span class="dot" />
        <span>{{ text || '正在连接 Agent 服务' }}</span>
      </div>
      <div class="bar">
        <div class="bar-fill" :style="{ width: `${Math.min(percent, 100)}%` }" />
      </div>
      <p class="tip muted">
        执行细节见右侧「执行追踪」。行程生成是异步任务，页面可刷新或断线；SSE 会按 Last-Event-ID 自动续传。
      </p>
    </div>
  </section>
</template>

<style scoped>
.progress {
  display: flex;
  gap: 36px;
  align-items: center;
  padding: 38px 40px;
}

.ring {
  width: 148px;
  height: 148px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  transition: background 0.4s ease;
}

.ring-inner {
  width: 118px;
  height: 118px;
  border-radius: 50%;
  background: #fff;
  display: grid;
  place-items: center;
  box-shadow: inset 0 2px 10px rgba(23, 32, 58, 0.04);
}

.ring-inner strong {
  font-size: 30px;
  letter-spacing: -0.03em;
}

.ring-inner small {
  font-size: 14px;
  color: var(--ink-soft);
  margin-left: 2px;
}

.detail {
  flex: 1;
  min-width: 0;
}

.live {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 14px;
}

.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 0 0 rgba(79, 110, 247, 0.5);
  animation: pulse 1.4s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(79, 110, 247, 0.45);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(79, 110, 247, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(79, 110, 247, 0);
  }
}

.bar {
  height: 6px;
  background: #eef1f8;
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 18px;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #7d95ff, #4f6ef7);
  transition: width 0.45s ease;
}

.tip {
  margin: 18px 0 0;
  font-size: 12px;
}

@media (max-width: 720px) {
  .progress {
    flex-direction: column;
    padding: 30px 22px;
    gap: 22px;
  }
}
</style>
