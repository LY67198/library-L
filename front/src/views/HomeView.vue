<script setup lang="ts">
import { nextTick, ref } from 'vue'

type SSEEvent = {
  type: 'intent' | 'token' | 'done' | 'error'
  intent?: string
  content?: string
  data?: string
  response?: string
  sources?: Array<Record<string, unknown>>
}

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  sources?: Array<Record<string, unknown>>
}

const query = ref('')
const loading = ref(false)
const error = ref('')
const messages = ref<Message[]>([
  {
    id: 'welcome',
    role: 'assistant',
    content:
      '您好！我是图书馆智能助手。\n\n可以帮您：\n- 检索图书（"有没有《三体》"）\n- 推荐书籍（"推荐几本小说"）\n- 政策咨询（"图书馆几点关门"）\n- 座位预约（"我要预约座位"）',
  },
])
const messageListRef = ref<HTMLElement | null>(null)

const sendMessage = async () => {
  const text = query.value.trim()
  if (!text || loading.value) return

  loading.value = true
  error.value = ''
  messages.value.push({ id: crypto.randomUUID(), role: 'user', content: text })
  query.value = ''
  await scrollToBottom()

  const assistantId = crypto.randomUUID()
  messages.value.push({ id: assistantId, role: 'assistant', content: '', intent: '', sources: [] })
  await scrollToBottom()

  try {
    const response = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text }),
    })
    if (!response.ok || !response.body) {
      throw new Error(`Request failed: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() || ''
      for (const frame of frames) {
        const lines = frame.split('\n')
        let eventType = ''
        let data = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7)
          if (line.startsWith('data: ')) data = line.slice(6)
        }
        if (!data) continue
        try {
          const event = JSON.parse(data) as SSEEvent
          const msg = messages.value.find((m) => m.id === assistantId)
          if (!msg) continue
          if (eventType === 'intent') {
            msg.intent = event.data || event.intent
          }
          if (eventType === 'token') {
            msg.content += event.content || ''
          }
          if (eventType === 'done') {
            msg.intent = event.intent || msg.intent
            msg.content = event.response || msg.content
            msg.sources = event.sources || []
          }
          if (eventType === 'error') {
            msg.content += `\n[错误: ${event.content || '服务异常'}]`
          }
        } catch {
          // 跳过无法解析的帧
        }
      }
      await scrollToBottom()
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Request failed'
    error.value = message
    const msg = messages.value.find((m) => m.id === assistantId)
    if (msg) msg.content = `请求失败: ${message}`
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const intentLabel = (intent: string) => {
  const map: Record<string, string> = {
    search_book: '图书检索',
    recommend_book: '推荐',
    policy_query: '政策咨询',
    book_seat: '座位预约',
    query_appointment: '预约查询',
    cancel_appointment: '取消预约',
    profile_query: '读者画像',
    greeting: '问候',
    other: '其他',
  }
  return map[intent] || intent
}
</script>

<template>
  <main class="shell">
    <aside class="sidebar">
      <h1>图书馆智能助手</h1>
      <p class="description">AI 驱动的图书馆服务系统</p>
      <div class="features">
        <span>检索</span><span>推荐</span><span>政策咨询</span><span>座位预约</span>
      </div>
      <div class="nav-links">
        <router-link to="/seats" class="nav-link">座位预约</router-link>
      </div>
    </aside>

    <section class="workspace">
      <div ref="messageListRef" class="messages">
        <article
          v-for="message in messages"
          :key="message.id"
          :class="['message', message.role]"
        >
          <div class="avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
          <div class="bubble">
            <span v-if="message.intent" class="intent-tag">{{ intentLabel(message.intent) }}</span>
            <pre>{{ message.content }}</pre>
          </div>
        </article>
      </div>

      <form class="composer" @submit.prevent="sendMessage">
        <textarea
          v-model="query"
          :disabled="loading"
          rows="2"
          placeholder="输入您的问题..."
        />
        <button :disabled="loading || !query.trim()">
          {{ loading ? '...' : '发送' }}
        </button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </main>
</template>
