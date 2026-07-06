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
