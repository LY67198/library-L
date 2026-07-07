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
