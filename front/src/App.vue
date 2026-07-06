<script setup lang="ts">
import { nextTick, ref } from 'vue'

type StreamEvent = {
  type: 'status' | 'phase' | 'route' | 'final' | 'error'
  node?: string
  message?: string
  final?: string
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'status'
  content: string
}

const query = ref('Compare RAG and multi-agent research workflows')
const userId = ref('default_user')
const threadId = ref('default_thread')
const tenantId = ref('default_tenant')
const loading = ref(false)
const error = ref('')
const messages = ref<ChatMessage[]>([
  {
    id: 'welcome',
    role: 'assistant',
    content: 'Send a research request to exercise the scaffold workflow.',
  },
])
const logs = ref<string[]>([])
const messageListRef = ref<HTMLElement | null>(null)

const runResearch = async () => {
  const text = query.value.trim()
  if (!text || loading.value) return

  loading.value = true
  error.value = ''
  logs.value = []
  messages.value.push({ id: crypto.randomUUID(), role: 'user', content: text })
  const statusId = crypto.randomUUID()
  messages.value.push({ id: statusId, role: 'status', content: 'Starting workflow...' })
  query.value = ''
  await scrollToBottom()

  try {
    const response = await fetch('/api/v1/research/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: text,
        user_id: userId.value || 'default_user',
        thread_id: threadId.value || 'default_thread',
        tenant_id: tenantId.value || 'default_tenant',
      }),
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
        const line = frame.split('\n').find((item) => item.startsWith('data: '))
        if (!line) continue
        const event = JSON.parse(line.slice(6)) as StreamEvent
        handleEvent(event, statusId)
      }
      await scrollToBottom()
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown request error'
    error.value = message
    messages.value = messages.value.filter((item) => item.id !== statusId)
    messages.value.push({ id: crypto.randomUUID(), role: 'assistant', content: message })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

const handleEvent = (event: StreamEvent, statusId: string) => {
  if (event.type === 'phase' || event.type === 'status' || event.type === 'route') {
    const line = event.node ? `${event.node}: ${event.message}` : event.message || event.type
    logs.value.push(line)
    const status = messages.value.find((item) => item.id === statusId)
    if (status) status.content = logs.value.map((item) => `- ${item}`).join('\n')
  }
  if (event.type === 'final') {
    messages.value = messages.value.filter((item) => item.id !== statusId)
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: event.final || 'No final answer returned.',
    })
  }
  if (event.type === 'error') {
    throw new Error(event.message || 'Workflow error')
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}
</script>

<template>
  <main class="shell">
    <aside class="sidebar">
      <div>
        <p class="eyebrow">Scaffold</p>
        <h1>Deep Research</h1>
        <p class="description">A reusable LangGraph + FastAPI + SSE starter.</p>
      </div>

      <label>
        User ID
        <input v-model="userId" />
      </label>
      <label>
        Thread ID
        <input v-model="threadId" />
      </label>
      <label>
        Tenant ID
        <input v-model="tenantId" />
      </label>
    </aside>

    <section class="workspace">
      <header>
        <h2>Research Console</h2>
        <p>Use this page to verify the backend stream and workflow phases.</p>
      </header>

      <div ref="messageListRef" class="messages">
        <article v-for="message in messages" :key="message.id" :class="['message', message.role]">
          <div class="avatar">{{ message.role === 'user' ? 'U' : message.role === 'status' ? '...' : 'AI' }}</div>
          <pre>{{ message.content }}</pre>
        </article>
      </div>

      <form class="composer" @submit.prevent="runResearch">
        <textarea v-model="query" :disabled="loading" rows="3" />
        <button :disabled="loading || !query.trim()">{{ loading ? 'Running...' : 'Run' }}</button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </main>
</template>

