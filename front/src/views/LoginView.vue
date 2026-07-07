<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const { login, register, loading } = useAuth()

const activeTab = ref<'login' | 'register'>('login')

// 登录字段
const username = ref('')
const password = ref('')

// 注册字段
const regUsername = ref('')
const regPassword = ref('')
const regDisplayName = ref('')
const regStudentId = ref('')

const redirect = (route.query.redirect as string) || '/'

async function handleLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  try {
    await login(username.value, password.value)
    ElMessage.success('登录成功')
    router.push(redirect)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '登录失败')
  }
}

async function handleRegister() {
  if (!regUsername.value || !regPassword.value || !regDisplayName.value || !regStudentId.value) {
    ElMessage.warning('请填写所有字段')
    return
  }
  try {
    await register(regUsername.value, regPassword.value, regDisplayName.value, regStudentId.value)
    ElMessage.success('注册成功')
    router.push(redirect)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '注册失败')
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1>图书馆智能服务系统</h1>
      <p class="subtitle">登录或注册以使用完整功能</p>

      <el-tabs v-model="activeTab" class="auth-tabs">
        <el-tab-pane label="登录" name="login">
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
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form @submit.prevent="handleRegister" label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="regUsername" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="regPassword" type="password" placeholder="请输入密码" show-password />
            </el-form-item>
            <el-form-item label="显示名">
              <el-input v-model="regDisplayName" placeholder="请输入显示名" />
            </el-form-item>
            <el-form-item label="学号">
              <el-input v-model="regStudentId" placeholder="请输入学号" />
            </el-form-item>
            <el-button type="primary" native-type="submit" :loading="loading" style="width:100%">
              注册
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex; align-items: center; justify-content: center; min-height: 100vh;
  background: #f4f6f8;
}
.login-card {
  width: 420px; padding: 40px; background: #fff;
  border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.login-card h1 { margin: 0 0 4px; font-size: 20px; text-align: center; }
.subtitle { margin: 0 0 16px; color: #667085; text-align: center; font-size: 14px; }
.auth-tabs :deep(.el-tabs__nav) { width: 100%; display: flex; }
.auth-tabs :deep(.el-tabs__item) { flex: 1; text-align: center; }
</style>
