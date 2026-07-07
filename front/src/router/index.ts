import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

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

router.beforeEach(async (to, _from, next) => {
  const { checkAuth } = useAuth()

  if (to.path === '/login') {
    const loggedIn = await checkAuth()
    if (loggedIn) return next('/')
    return next()
  }

  const loggedIn = await checkAuth()
  if (!loggedIn) return next(`/login?redirect=${to.path}`)
  next()
})

export default router
