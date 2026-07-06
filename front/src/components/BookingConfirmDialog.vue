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
