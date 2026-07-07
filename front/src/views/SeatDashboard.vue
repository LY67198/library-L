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

// Extract unique zones from seat list for ZoneChips
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

watch(slotType, () => { zoneId.value = null; loadSeats() })
watch(zoneId, () => { loadSeats() })
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
