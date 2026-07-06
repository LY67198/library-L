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
