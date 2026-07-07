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
