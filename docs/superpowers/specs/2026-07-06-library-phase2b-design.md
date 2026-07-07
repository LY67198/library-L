# Phase 2b: 座位可视化前端 — 设计文档

## 概述

Phase 2b 实现座位可视化前端，用户可以在页面上直观地浏览楼层/区域/座位，按时间段筛选，一键预约。后端仅做 API 小幅增强（`GET /api/v1/seats` 增加查询参数）。

Celery 超时释放延后到 Phase 2c 单独处理，避免本 Phase 范围过大。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| 前端框架 | Vue 3 + Composition API + Element Plus（沿用现有技术栈） |
| 页面结构 | 单页座位置面板（`SeatDashboard.vue`），无需路由跳转 |
| 数据获取 | 前端直接调 REST API，组件内 `onMounted` + `watch` 驱动重新请求 |
| 状态管理 | 组件本地状态（`ref`/`reactive`），不引入 Pinia |
| 色码方案 | 绿（空闲）/ 红（已占）/ 黄（即将释放）/ 蓝（我的预约） |
| 预约弹窗 | Element Plus `ElDialog` + `ElMessage` |
| 未登录处理 | `router.push('/login')` 带 redirect 参数 |

## 组件树

```
views/SeatDashboard.vue          ← 主页面，管理筛选状态 (floorId, zoneId, slotType, date)
├── FloorTabs.vue                ← ElTabs 楼层切换，emit update:floorId
├── TimeSlotPicker.vue           ← ElRadioGroup 上午/下午/晚上，emit update:slotType
├── ZoneChips.vue                ← 当前楼层的区域 Chip 列表，emit update:zoneId
├── SeatGrid.vue                 ← CSS Grid 8 列座位网格
│   └── SeatCard.vue             ← 单个座位色块，props: seat, @click
├── BookingConfirmDialog.vue     ← ElDialog 预约确认弹窗
├── MyAppointmentBadge.vue       ← 快速查看/取消我的预约
└── SeatLegend.vue               ← 底部颜色图例
```

## 数据流

```
SeatDashboard (state: floorId, zoneId, slotType, date)
  │
  ├─ onMounted / watch([floorId, zoneId, slotType])
  │     → GET /api/v1/seats?floor_id=&zone_id=&date=&slot_type=
  │     → 返回 SeatItem[]: { seat_id, floor_name, zone_name, seat_number,
  │                           status: free|occupied|releasing, is_mine: bool }
  │     → seats = response.data.seats
  │
  ├─ FloorTabs       ← props: floors[],   emit @update:floorId   → 重新请求
  ├─ ZoneChips       ← props: zones[],    emit @update:zoneId    → 重新请求
  ├─ TimeSlotPicker  ←                      emit @update:slotType → 重新请求
  │
  ├─ SeatGrid        ← props: seats[]
  │   └─ SeatCard    ← props: seat, @click → emit(seat)
  │         │
  │         ├─ 空闲 → openBookingDialog(seat)
  │         ├─ 已占 → 无操作 (Tooltip: "已被预约")
  │         ├─ 即将释放 → 无操作 (Tooltip: "即将超时释放")
  │         └─ 我的预约 → openMyAppointment(seat)
  │
  └─ BookingConfirmDialog ← props: seat, visible
        └─ 确认 → POST /api/v1/seats/{id}/book { date, slot }
                → ElMessage.success → 刷新 seats
```

## 座位状态色码

| 状态 | 颜色 | CSS 类 | 点击行为 |
|------|------|--------|----------|
| `free` | 绿色 #c8e6c9 | `.seat--free` | 打开预约弹窗 |
| `occupied` | 红色 #ffcdd2 | `.seat--occupied` | 无操作 |
| `releasing` | 黄色 #fff9c4 | `.seat--releasing` | 无操作 |
| `mine` | 蓝色 #e3f2fd + 蓝色边框 | `.seat--mine` | 打开详情弹窗 |

状态判断逻辑（后端 `SeatService.get_seats`）：
- `free`：`Seat.status = available` 且该时段无 `SeatTimeSlot` 记录
- `occupied`：该时段有 `SeatTimeSlot`（非当前用户）
- `releasing`：该时段有 `SeatTimeSlot`，且预约时间已过 slot_start + 30min（懒清理未触发前）
- `mine`：`is_current_user = true` 覆盖以上所有状态

## 交互细节

| 场景 | 行为 |
|------|------|
| 点击空闲座位 | `ElDialog` 弹出确认：座位号 + 楼层/区域 + 日期 + 时段，点击"确认预约"调 book API |
| 点击已占/即将释放 | 无点击响应，`ElTooltip` 悬停显示文字 |
| 点击"我的预约"座位 | `ElDialog` 弹出详情：预约时间 + 剩余时长，可点"取消预约"调 cancel API |
| 当前区域无空闲座位 | `ElEmpty` 空状态提示："本区域该时段暂无空闲座位，试试切换楼层或时段" |
| 未登录点预约 | `router.push({ path: '/login', query: { redirect: '/seats' } })` |
| 预约成功 | `ElMessage.success("预约成功")` + 自动刷新网格 |
| 预约冲突 (409) | `ElMessage.error("该座位已被他人预约")` |
| 网络错误 | `ElMessage.error("网络异常，请稍后重试")` |

## API 增强

`GET /api/v1/seats` 当前支持 `floor_id` 和 `zone_id`，Phase 2b 新增：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `date` | `str` | 否 | 日期 YYYY-MM-DD，默认今天 |
| `slot_type` | `str` | 否 | morning / afternoon / evening，默认当前时段 |

返回 `SeatItem` 新增 `is_mine: bool` 字段（Phase 2a 设计中已有 `booked_by_me`，统一用 `is_mine`）。

后端改动范围：
- `app/backend/service/seat_service.py` — `get_seats()` 方法增加 `date`、`slot_type` 参数，查 `SeatTimeSlot` 计算状态
- `app/backend/schemas/seat.py` — `SeatItem` 确认 `is_mine` 字段
- `app/backend/router/seat_router.py` — `GET /api/v1/seats` 增加 Query 参数

## 前端路由

```typescript
// front/src/router/index.ts 新增
{ path: '/seats', name: 'Seats', component: () => import('@/views/SeatDashboard.vue'),
  meta: { requiresAuth: false } }  // 浏览不需要登录，预约需要
```

## 前端目录

```
front/src/
├── views/
│   └── SeatDashboard.vue          ← 新增
├── components/
│   ├── FloorTabs.vue              ← 新增
│   ├── TimeSlotPicker.vue         ← 新增
│   ├── ZoneChips.vue              ← 新增
│   ├── SeatGrid.vue               ← 新增
│   ├── SeatCard.vue               ← 新增
│   ├── BookingConfirmDialog.vue   ← 新增
│   ├── SeatLegend.vue             ← 新增
│   └── MyAppointmentBadge.vue     ← 新增
└── api/
    └── seats.ts                   ← 新增（封装 GET /seats, POST book, GET appointments, POST cancel）
```

## 测试策略

| 层级 | 内容 | 数量估计 |
|------|------|---------|
| 后端单元 | `SeatService.get_seats()` 按 date/slot_type 查询 + 状态计算 | ~5 |
| 后端 API | `GET /api/v1/seats` 参数组合、`is_mine` 正确性 | ~4 |
| 前端组件 | `SeatGrid` 渲染 + `SeatCard` 状态色 + `BookingConfirmDialog` 交互 | ~6 |
| E2E | 完整预约流程：浏览 → 选座 → 预约 → 查看 → 取消 | ~2 |

**明确不测：** 浏览器兼容性、移动端响应式（不做移动端适配）、Celery 超时释放（Phase 2c）。

## 依赖

无新增后端依赖。前端使用 Element Plus 已有组件（`ElTabs`、`ElRadioGroup`、`ElDialog`、`ElTooltip`、`ElEmpty`、`ElMessage`）。

## 不在范围内

- Celery 超时释放（延后到 Phase 2c）
- 座位签到功能
- 移动端适配
- 座位实时推送（WebSocket/SSE）
- 管理员座位管理界面
