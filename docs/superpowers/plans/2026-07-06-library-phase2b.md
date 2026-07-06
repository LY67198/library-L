# Phase 2b: 座位可视化前端 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现座位可视化前端页面，用户可浏览楼层/区域/座位网格，按时间段筛选，一键预约。

**Architecture:** 单页 SeatDashboard 组件树挂载在 App.vue 的 `<router-view>` 下。后端修改：`GET /api/v1/seats` → 可选认证 + SeatItem 增加 `floor_id`/`zone_id` 字段。

**Tech Stack:** Vue 3 + Composition API + Element Plus + vue-router 4, FastAPI (后端小幅修改)

---

## 文件结构

```
app/
├── backend/
│   ├── router/seat_router.py    ← 修改: get_required_user → get_current_user
│   ├── schemas/seat.py          ← 修改: SeatItem 增加 floor_id, zone_id
│   └── service/seat_service.py  ← 修改: list_seats 返回 floor_id, zone_id
tests/
└── test_seat_api.py             ← 新增: test_list_seats_anonymous

front/src/
├── main.ts                      ← 修改: 注册 ElementPlus + Router
├── App.vue                      ← 修改: 改为 <router-view />
├── api/
│   ├── client.ts                ← 新增: fetch 封装 + token 注入
│   ├── seats.ts                 ← 新增: 座位 API 函数
│   └── auth.ts                  ← 新增: 认证 API 函数
├── composables/
│   └── useAuth.ts               ← 新增: 认证状态管理
├── router/
│   └── index.ts                 ← 新增: 路由配置
├── views/
│   ├── HomeView.vue             ← 迁移: 原 App.vue 聊天界面
│   ├── LoginView.vue            ← 新增: 登录页面
│   └── SeatDashboard.vue        ← 新增: 座位预约主页面
└── components/
    ├── TimeSlotPicker.vue       ← 新增: 时段选择器
    ├── ZoneChips.vue            ← 新增: 区域 Chips 筛选
    ├── SeatGrid.vue             ← 新增: 座位网格
    ├── SeatCard.vue             ← 新增: 单个座位色块
    ├── BookingConfirmDialog.vue ← 新增: 预约确认弹窗
    └── SeatLegend.vue           ← 新增: 颜色图例
```

---

### Task 1: 后端 — SeatItem 增加 floor_id/zone_id 字段

**Files:**
- Modify: `app/backend/schemas/seat.py`
- Modify: `app/backend/service/seat_service.py`

- [ ] **Step 1: SeatItem schema 增加 floor_id, zone_id**

`app/backend/schemas/seat.py` 中 `SeatItem`:

```python
class SeatItem(BaseModel):
    seat_id: str
    floor_id: int       # 新增 — 前端筛选用
    floor_name: str
    zone_id: int        # 新增 — 前端筛选用
    zone_name: str
    seat_number: str
    status: str
    booked_by_me: bool
```

- [ ] **Step 2: list_seats 返回 floor_id, zone_id**

`app/backend/service/seat_service.py` 中 `list_seats` 方法，修改查询和组装逻辑：

```python
# 第 75 行 — select 增加 Zone.id, Floor.id
query = (
    select(Seat, Zone.id, Zone.name, Floor.id, Floor.name)
    .join(Zone, Seat.zone_id == Zone.id)
    .join(Floor, Zone.floor_id == Floor.id)
)

# 第 89 行 — 解包增加
for seat, zone_id, zone_name, floor_id, floor_name in rows:

# 第 113 行 — 字典增加 floor_id, zone_id
seats.append({
    "seat_id": seat.id,
    "floor_id": floor_id,       # 新增
    "floor_name": floor_name,
    "zone_id": zone_id,         # 新增
    "zone_name": zone_name,
    "seat_number": seat.seat_number,
    "status": status,
    "booked_by_me": booked_by_me,
})
```

- [ ] **Step 3: 运行已有测试确认无回归**

```bash
cd deep_research_scaffold && uv run pytest tests/test_seat_api.py -v
```
Expected: 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/backend/schemas/seat.py app/backend/service/seat_service.py
git commit -m "feat: SeatItem 增加 floor_id/zone_id 字段，支持前端筛选"
```

---

### Task 2: 后端 — 座位列表接口改为可选认证

**Files:**
- Modify: `app/backend/router/seat_router.py:22,57`
- Modify: `tests/test_seat_api.py` — 新增匿名访问测试

- [ ] **Step 1: 修改 import 和依赖注入**

`app/backend/router/seat_router.py`:

```python
# 第 23 行 — get_required_user → get_current_user
from core.deps import get_current_user

# 第 57 行 — Depends 参数
user: User | None = Depends(get_current_user),
```

- [ ] **Step 2: 运行已有测试**

```bash
cd deep_research_scaffold && uv run pytest tests/test_seat_api.py -v
```
Expected: 4 tests PASS（test_unauthorized_access 只测 book 端点，不受影响）

- [ ] **Step 3: 新增匿名访问测试**

`tests/test_seat_api.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_list_seats_anonymous(db_session, redis_client):
    """匿名用户可浏览座位，booked_by_me 为 False"""
    app = await _setup_overrides(db_session, redis_client)

    from models import Floor, Zone, ZoneType, Seat

    floor = Floor(name="1楼", sort_order=1)
    zone = Zone(name="A区", zone_type=ZoneType.open, sort_order=1, floor=floor)
    seat = Seat(seat_number="001", zone=zone)
    db_session.add_all([floor, zone, seat])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/seats?date=2026-07-10&slot=morning")
        assert resp.status_code == 200
        seats = resp.json()["seats"]
        assert len(seats) == 1
        assert seats[0]["status"] == "available"
        assert seats[0]["booked_by_me"] is False

    app.dependency_overrides.clear()
```

- [ ] **Step 4: 运行新测试**

```bash
cd deep_research_scaffold && uv run pytest tests/test_seat_api.py::test_list_seats_anonymous -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/backend/router/seat_router.py tests/test_seat_api.py
git commit -m "fix: GET /api/v1/seats 改为可选认证，匿名用户可浏览座位"
```

---

### Task 3: 安装前端依赖 + 搭建路由和 Element Plus

**Files:**
- Modify: `front/src/main.ts`
- Create: `front/src/App.vue`（重写）
- Create: `front/src/router/index.ts`
- Create: `front/src/views/HomeView.vue`（迁移原 App.vue）

- [ ] **Step 1: 安装依赖**

```bash
cd deep_research_scaffold/front && npm install vue-router@4 element-plus @element-plus/icons-vue
```

- [ ] **Step 2: 创建路由配置**

`front/src/router/index.ts`:

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/seats',
      name: 'Seats',
      component: () => import('@/views/SeatDashboard.vue'),
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
    },
  ],
})

export default router
```

- [ ] **Step 3: 迁移原聊天界面到 HomeView**

将 `front/src/App.vue` 的全部内容复制到 `front/src/views/HomeView.vue`（`<script setup>` + `<template>` 完整移过去）。

- [ ] **Step 4: 重写 App.vue 为路由壳**

`front/src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 5: 更新 main.ts 注册 router 和 Element Plus**

`front/src/main.ts`:

```typescript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './assets/main.css'

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
```

- [ ] **Step 6: 验证编译**

```bash
cd deep_research_scaffold/front && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: 无类型错误

- [ ] **Step 7: Commit**

```bash
git add front/package.json front/package-lock.json front/src/main.ts front/src/App.vue front/src/router/ front/src/views/HomeView.vue
git commit -m "feat: 搭建 vue-router + Element Plus 应用壳，迁移聊天界面"
```

---

### Task 4: 创建 API 层

**Files:**
- Create: `front/src/api/client.ts`
- Create: `front/src/api/seats.ts`
- Create: `front/src/api/auth.ts`

- [ ] **Step 1: 创建 API 客户端**

`front/src/api/client.ts`:

```typescript
function getToken(): string | null {
  return localStorage.getItem('access_token')
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v)
    })
  }
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`/api/v1${url.pathname}${url.search}`, { headers })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(body.detail?.message || body.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`/api/v1${path}`, {
    method: 'POST',
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({}))
    throw new Error(errBody.detail?.message || errBody.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}
```

- [ ] **Step 2: 创建座位 API**

`front/src/api/seats.ts`:

```typescript
import { apiGet, apiPost } from './client'

export interface SeatItem {
  seat_id: string
  floor_id: number
  floor_name: string
  zone_id: number
  zone_name: string
  seat_number: string
  status: string
  booked_by_me: boolean
}

export function fetchSeats(params: {
  floor_id?: number; zone_id?: number; date?: string; slot?: string
}): Promise<{ seats: SeatItem[] }> {
  const q: Record<string, string> = {}
  if (params.floor_id != null) q.floor_id = String(params.floor_id)
  if (params.zone_id != null) q.zone_id = String(params.zone_id)
  if (params.date) q.date = params.date
  if (params.slot) q.slot = params.slot
  return apiGet('/seats', q)
}

export function bookSeat(seatId: string, date: string, slot: string) {
  return apiPost<{
    appointment_id: string; seat_id: string; floor_name: string
    zone_name: string; seat_number: string; date: string; slot: string
  }>(`/seats/${seatId}/book`, { date, slot })
}
```

- [ ] **Step 3: 创建认证 API**

`front/src/api/auth.ts`:

```typescript
import { apiPost, apiGet } from './client'

export interface UserProfile {
  user_id: string; username: string; display_name: string; student_id: string
}

export function login(username: string, password: string) {
  return apiPost<{ access_token: string; refresh_token: string; token_type: string }>(
    '/auth/login', { username, password })
}

export function fetchMe() {
  return apiGet<UserProfile>('/auth/me')
}
```

- [ ] **Step 4: Commit**

```bash
git add front/src/api/
git commit -m "feat: 创建 API 层 — client, seats, auth 接口封装"
```

---

### Task 5: 创建 useAuth 组合式函数

**Files:**
- Create: `front/src/composables/useAuth.ts`

- [ ] **Step 1: 创建 useAuth**

`front/src/composables/useAuth.ts`:

```typescript
import { ref, computed } from 'vue'
import { login as apiLogin, fetchMe, type UserProfile } from '@/api/auth'

const user = ref<UserProfile | null>(null)
const loading = ref(false)

export function useAuth() {
  const isLoggedIn = computed(() => user.value !== null)

  async function checkAuth(): Promise<boolean> {
    const token = localStorage.getItem('access_token')
    if (!token) return false
    try {
      user.value = await fetchMe()
      return true
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      return false
    }
  }

  async function login(username: string, password: string): Promise<void> {
    loading.value = true
    try {
      const resp = await apiLogin(username, password)
      localStorage.setItem('access_token', resp.access_token)
      localStorage.setItem('refresh_token', resp.refresh_token)
      user.value = await fetchMe()
    } finally {
      loading.value = false
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
  }

  return { user, isLoggedIn, loading, checkAuth, login, logout }
}
```

- [ ] **Step 2: Commit**

```bash
git add front/src/composables/
git commit -m "feat: 创建 useAuth 认证组合式函数"
```

---

### Task 6: 创建登录页面

**Files:**
- Create: `front/src/views/LoginView.vue`

- [ ] **Step 1: 创建 LoginView**

`front/src/views/LoginView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const { login, loading } = useAuth()

const username = ref('')
const password = ref('')

async function handleLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  try {
    await login(username.value, password.value)
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || '/')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '登录失败')
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1>图书馆智能服务系统</h1>
      <p class="subtitle">登录以预约座位</p>
      <el-form @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width:100%">
          登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex; align-items: center; justify-content: center; min-height: 100vh;
  background: #f4f6f8;
}
.login-card {
  width: 400px; padding: 40px; background: #fff;
  border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.login-card h1 { margin: 0 0 4px; font-size: 20px; text-align: center; }
.subtitle { margin: 0 0 24px; color: #667085; text-align: center; font-size: 14px; }
</style>
```

- [ ] **Step 2: 验证编译**

```bash
cd deep_research_scaffold/front && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add front/src/views/LoginView.vue
git commit -m "feat: 创建登录页面"
```

---

### Task 7: 创建筛选组件 — TimeSlotPicker + ZoneChips

**Files:**
- Create: `front/src/components/TimeSlotPicker.vue`
- Create: `front/src/components/ZoneChips.vue`

- [ ] **Step 1: 创建 TimeSlotPicker**

`front/src/components/TimeSlotPicker.vue`:

```vue
<script setup lang="ts">
defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const slots = [
  { value: 'morning', label: '上午 8-12' },
  { value: 'afternoon', label: '下午 13-17' },
  { value: 'evening', label: '晚上 18-22' },
]
</script>

<template>
  <el-radio-group :model-value="modelValue" @update:model-value="(v: string) => emit('update:modelValue', v)">
    <el-radio-button v-for="s in slots" :key="s.value" :value="s.value">{{ s.label }}</el-radio-button>
  </el-radio-group>
</template>
```

- [ ] **Step 2: 创建 ZoneChips**

`front/src/components/ZoneChips.vue`:

```vue
<script setup lang="ts">
defineProps<{
  zones: { id: number; name: string }[]
  modelValue: number | null
}>()
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
</script>

<template>
  <div class="zone-chips">
    <el-tag
      v-for="z in zones" :key="z.id"
      :type="modelValue === z.id ? 'primary' : 'info'"
      :effect="modelValue === z.id ? 'dark' : 'plain'"
      style="cursor:pointer"
      @click="emit('update:modelValue', modelValue === z.id ? null : z.id)"
    >{{ z.name }}</el-tag>
  </div>
</template>

<style scoped>
.zone-chips { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add front/src/components/TimeSlotPicker.vue front/src/components/ZoneChips.vue
git commit -m "feat: 创建筛选组件 — TimeSlotPicker, ZoneChips"
```

---

### Task 8: 创建座位展示组件 — SeatCard + SeatGrid + SeatLegend

**Files:**
- Create: `front/src/components/SeatCard.vue`
- Create: `front/src/components/SeatGrid.vue`
- Create: `front/src/components/SeatLegend.vue`

- [ ] **Step 1: 创建 SeatCard**

`front/src/components/SeatCard.vue`:

```vue
<script setup lang="ts">
import type { SeatItem } from '@/api/seats'

defineProps<{ seat: SeatItem }>()
defineEmits<{ click: [seat: SeatItem] }>()

function statusText(status: string, bookedByMe: boolean): string {
  if (bookedByMe) return '我的预约'
  return { available: '空闲', booked: '已占', disabled: '维护中' }[status] || status
}
</script>

<template>
  <el-tooltip :content="statusText(seat.status, seat.booked_by_me)" placement="top">
    <div
      :class="['seat-card', `seat--${seat.booked_by_me ? 'mine' : seat.status}`]"
      @click="(seat.status === 'available' || seat.booked_by_me) && $emit('click', seat)"
    >
      <span class="seat-number">{{ seat.seat_number }}</span>
      <span class="seat-zone">{{ seat.zone_name }}</span>
    </div>
  </el-tooltip>
</template>

<style scoped>
.seat-card {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border-radius: 8px; padding: 12px 8px; min-height: 64px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.seat--available { background: #c8e6c9; cursor: pointer; }
.seat--available:hover { transform: scale(1.05); box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
.seat--booked { background: #ffcdd2; cursor: default; }
.seat--disabled { background: #e0e0e0; color: #999; cursor: default; }
.seat--mine { background: #e3f2fd; border: 2px solid #1976d2; cursor: pointer; }
.seat-number { font-weight: 700; font-size: 16px; }
.seat-zone { font-size: 11px; color: #666; margin-top: 2px; }
</style>
```

- [ ] **Step 2: 创建 SeatGrid**

`front/src/components/SeatGrid.vue`:

```vue
<script setup lang="ts">
import type { SeatItem } from '@/api/seats'
import SeatCard from './SeatCard.vue'

defineProps<{ seats: SeatItem[] }>()
const emit = defineEmits<{ click: [seat: SeatItem] }>()
</script>

<template>
  <div class="seat-grid">
    <SeatCard v-for="s in seats" :key="s.seat_id" :seat="s" @click="emit('click', s)" />
  </div>
</template>

<style scoped>
.seat-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; }
</style>
```

- [ ] **Step 3: 创建 SeatLegend**

`front/src/components/SeatLegend.vue`:

```vue
<template>
  <div class="legend">
    <span class="legend-item"><span class="dot dot--free"></span>空闲</span>
    <span class="legend-item"><span class="dot dot--occupied"></span>已占</span>
    <span class="legend-item"><span class="dot dot--mine"></span>我的预约</span>
    <span class="legend-item"><span class="dot dot--disabled"></span>维护中</span>
  </div>
</template>

<style scoped>
.legend { display: flex; gap: 20px; justify-content: center; padding: 16px 0; font-size: 13px; color: #666; }
.legend-item { display: flex; align-items: center; gap: 6px; }
.dot { width: 14px; height: 14px; border-radius: 4px; }
.dot--free { background: #c8e6c9; }
.dot--occupied { background: #ffcdd2; }
.dot--mine { background: #e3f2fd; border: 2px solid #1976d2; }
.dot--disabled { background: #e0e0e0; }
</style>
```

- [ ] **Step 4: Commit**

```bash
git add front/src/components/SeatCard.vue front/src/components/SeatGrid.vue front/src/components/SeatLegend.vue
git commit -m "feat: 创建座位展示组件 — SeatCard, SeatGrid, SeatLegend"
```

---

### Task 9: 创建 BookingConfirmDialog

**Files:**
- Create: `front/src/components/BookingConfirmDialog.vue`

- [ ] **Step 1: 创建 BookingConfirmDialog**

`front/src/components/BookingConfirmDialog.vue`:

```vue
<script setup lang="ts">
import type { SeatItem } from '@/api/seats'
import { bookSeat } from '@/api/seats'
import { ElMessage } from 'element-plus'
import { ref } from 'vue'

const props = defineProps<{
  seat: SeatItem | null
  date: string
  slot: string
}>()

const emit = defineEmits<{
  close: []
  booked: []
}>()

const loading = ref(false)

const slotLabels: Record<string, string> = {
  morning: '上午 8-12', afternoon: '下午 13-17', evening: '晚上 18-22',
}

async function handleBook() {
  if (!props.seat) return
  loading.value = true
  try {
    await bookSeat(props.seat.seat_id, props.date, props.slot)
    ElMessage.success('预约成功')
    emit('booked')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '预约失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog :model-value="seat !== null" title="确认预约" width="400px" @close="$emit('close')">
    <div v-if="seat" class="booking-info">
      <p><strong>座位号：</strong>{{ seat.floor_name }} - {{ seat.zone_name }} - {{ seat.seat_number }}</p>
      <p><strong>日期：</strong>{{ date }}</p>
      <p><strong>时段：</strong>{{ slotLabels[slot] || slot }}</p>
    </div>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleBook">确认预约</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.booking-info p { margin: 0 0 12px; font-size: 15px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add front/src/components/BookingConfirmDialog.vue
git commit -m "feat: 创建预约确认弹窗组件"
```

---

### Task 10: 创建 SeatDashboard 主页面

**Files:**
- Create: `front/src/views/SeatDashboard.vue`

- [ ] **Step 1: 创建 SeatDashboard**

`front/src/views/SeatDashboard.vue`:

```vue
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchSeats, type SeatItem } from '@/api/seats'
import { useAuth } from '@/composables/useAuth'
import TimeSlotPicker from '@/components/TimeSlotPicker.vue'
import ZoneChips from '@/components/ZoneChips.vue'
import SeatGrid from '@/components/SeatGrid.vue'
import SeatLegend from '@/components/SeatLegend.vue'
import BookingConfirmDialog from '@/components/BookingConfirmDialog.vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const { isLoggedIn, checkAuth } = useAuth()

const seats = ref<SeatItem[]>([])
const zoneId = ref<number | null>(null)
const slotType = ref('morning')
const selectedSeat = ref<SeatItem | null>(null)
const loading = ref(false)
const today = new Date().toISOString().slice(0, 10)

// 从座位列表中提取唯一楼层和区域
const floors = computed(() => {
  const map = new Map<number, string>()
  for (const s of seats.value) map.set(s.floor_id, s.floor_name)
  return [...map.entries()].map(([id, name]) => ({ id, name }))
})

const zones = computed(() => {
  const map = new Map<number, string>()
  for (const s of seats.value) map.set(s.zone_id, s.zone_name)
  return [...map.entries()].map(([id, name]) => ({ id, name }))
})

async function loadSeats() {
  loading.value = true
  try {
    const resp = await fetchSeats({ date: today, slot: slotType.value, zone_id: zoneId.value ?? undefined })
    seats.value = resp.seats
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function handleSeatClick(seat: SeatItem) {
  if (!isLoggedIn.value) {
    router.push({ path: '/login', query: { redirect: '/seats' } })
    return
  }
  if (seat.booked_by_me) {
    ElMessage.info(`你的预约: ${seat.floor_name} ${seat.zone_name} ${seat.seat_number}`)
    return
  }
  selectedSeat.value = seat
}

function handleBooked() {
  selectedSeat.value = null
  loadSeats()
}

watch([slotType, zoneId], () => { zoneId.value = null; loadSeats() })
onMounted(async () => { await checkAuth(); await loadSeats() })
</script>

<template>
  <div class="dashboard">
    <header class="dashboard-header">
      <h1>座位预约</h1>
      <div class="header-actions">
        <el-button v-if="!isLoggedIn" size="small" @click="router.push('/login')">登录</el-button>
        <span v-else class="user-greeting">已登录</span>
        <el-button size="small" @click="router.push('/')">返回首页</el-button>
      </div>
    </header>

    <div class="filters">
      <TimeSlotPicker v-model="slotType" />
      <ZoneChips v-if="zones.length > 0" v-model="zoneId" :zones="zones" />
    </div>

    <div class="seat-area" v-loading="loading">
      <el-empty v-if="!loading && seats.length === 0" description="该时段暂无空闲座位，试试切换时段" />
      <SeatGrid v-else :seats="seats" @click="handleSeatClick" />
    </div>

    <SeatLegend />

    <BookingConfirmDialog
      :seat="selectedSeat"
      :date="today"
      :slot="slotType"
      @close="selectedSeat = null"
      @booked="handleBooked"
    />
  </div>
</template>

<style scoped>
.dashboard { max-width: 960px; margin: 0 auto; padding: 24px; }
.dashboard-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.dashboard-header h1 { margin: 0; font-size: 22px; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.user-greeting { color: #667085; font-size: 14px; }
.filters { display: flex; gap: 16px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
.seat-area { min-height: 200px; padding: 20px 0; }
</style>
```

- [ ] **Step 2: 验证编译**

```bash
cd deep_research_scaffold/front && npx vue-tsc --noEmit 2>&1 | head -30
```
Expected: 无类型错误（Element Plus 内部类型警告可忽略）

- [ ] **Step 3: Commit**

```bash
git add front/src/views/SeatDashboard.vue
git commit -m "feat: 创建 SeatDashboard 座位预约主页面"
```

---

### Task 11: 聊天页添加座位预约导航入口

**Files:**
- Modify: `front/src/views/HomeView.vue`

- [ ] **Step 1: 在 sidebar 添加导航按钮**

在 HomeView.vue 的 `<template>` 中，`.features` div 之后追加：

```vue
<div class="nav-links">
  <router-link to="/seats" class="nav-link">座位预约</router-link>
</div>
```

在 `<style scoped>` 末尾追加（如果原 HomeView 用 scoped，需要加在对应区块内）：

```css
.nav-links { margin-top: 16px; }
.nav-link {
  display: inline-block; padding: 10px 24px; color: #fff; background: #0f766e;
  border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px;
}
.nav-link:hover { background: #0d6b63; }
```

注意：原 `App.vue` 的 sidebar 样式在 `main.css` 中（全局）。如需添加导航样式，可加在 `main.css` 末尾，或使用 `<style>` 不加 scoped。

- [ ] **Step 2: 验证编译**

```bash
cd deep_research_scaffold/front && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add front/src/views/HomeView.vue
git commit -m "feat: 聊天页添加座位预约导航入口"
```

---

### Task 12: 后端测试 — 确认全部通过

- [ ] **Step 1: 运行全部后端测试**

```bash
cd deep_research_scaffold && uv run pytest tests/ -v
```
Expected: ~56 tests PASS（含新增的 test_list_seats_anonymous）

- [ ] **Step 2: 如有失败，修复后重新运行直到全部通过**

---

### Task 13: 前端构建验证

- [ ] **Step 1: 构建前端**

```bash
cd deep_research_scaffold/front && npm run build
```
Expected: 构建成功，dist/ 目录生成

- [ ] **Step 2: 最终 commit**

```bash
git status
git add -A
git commit -m "feat: Phase 2b 座位可视化前端完成"
```
