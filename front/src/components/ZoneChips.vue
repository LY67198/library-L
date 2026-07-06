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
