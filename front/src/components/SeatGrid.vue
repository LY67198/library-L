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
