<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="layout-aside">
      <div class="logo-area">
        <h2>QA Studio</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="side-menu"
      >
        <el-sub-menu index="group-question">
          <template #title>
            <el-icon><EditPen /></el-icon>
            <span>问题生成</span>
          </template>
          <el-menu-item index="/question-generate">
            <el-icon><EditPen /></el-icon>
            <span>问题生成</span>
          </el-menu-item>
          <el-menu-item index="/knowledge-generate">
            <el-icon><Share /></el-icon>
            <span>知识体系生成</span>
          </el-menu-item>
          <el-menu-item index="/question-validate">
            <el-icon><Checked /></el-icon>
            <span>问题校验</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="group-answer">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>答案生成</span>
          </template>
          <el-menu-item index="/answer-generate">
            <el-icon><Document /></el-icon>
            <span>答案生成</span>
          </el-menu-item>
          <el-menu-item index="/answer-validate">
            <el-icon><Select /></el-icon>
            <span>答案校验</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="group-evaluate">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>数据评估</span>
          </template>
          <el-menu-item index="/data-evaluate">
            <el-icon><DataAnalysis /></el-icon>
            <span>数据评估</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="group-postprocess">
          <template #title>
            <el-icon><Operation /></el-icon>
            <span>数据后处理</span>
          </template>
          <el-menu-item index="/cot-filter">
            <el-icon><Filter /></el-icon>
            <span>COT过滤</span>
          </el-menu-item>
          <el-menu-item index="/dataset-processing">
            <el-icon><Grid /></el-icon>
            <span>测试集切分</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="group-tools">
          <template #title>
            <el-icon><Tools /></el-icon>
            <span>工具</span>
          </template>
          <el-menu-item index="/json-merge-tool">
            <el-icon><Connection /></el-icon>
            <span>JSON 文件合并</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="group-admin">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>管理中心</span>
          </template>
          <el-menu-item index="/my-tasks">
            <el-icon><List /></el-icon>
            <span>我的任务</span>
          </el-menu-item>
          <el-menu-item index="/config-center">
            <el-icon><Setting /></el-icon>
            <span>配置中心</span>
          </el-menu-item>
          <el-menu-item index="/user-manage">
            <el-icon><UserFilled /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/data-manage">
            <el-icon><Folder /></el-icon>
            <span>数据中心</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout-header">
        <span class="page-title">{{ currentTitle }}</span>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              {{ username }} <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="changePassword">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="layout-main">
        <router-view />
      </el-main>

      <!-- 修改密码弹窗 -->
      <el-dialog
        v-model="passwordDialogVisible"
        title="修改密码"
        width="420px"
        :close-on-click-modal="false"
        destroy-on-close
      >
        <el-form
          ref="passwordFormRef"
          :model="passwordForm"
          :rules="passwordRules"
          label-width="100px"
        >
          <el-form-item label="当前密码" prop="old_password">
            <el-input
              v-model="passwordForm.old_password"
              type="password"
              placeholder="请输入当前密码"
              show-password
            />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input
              v-model="passwordForm.new_password"
              type="password"
              placeholder="请输入新密码（4-128个字符）"
              show-password
            />
          </el-form-item>
          <el-form-item label="确认新密码" prop="confirm_password">
            <el-input
              v-model="passwordForm.confirm_password"
              type="password"
              placeholder="请再次输入新密码"
              show-password
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="passwordDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="passwordLoading" @click="handleChangePassword">
            确认修改
          </el-button>
        </template>
      </el-dialog>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMe, changePassword } from '../api'
import {
  EditPen, Share, Checked, Document, Select,
  DataAnalysis, Folder, Setting, ArrowDown, UserFilled,
  Operation, Filter, Grid, List, Tools, Connection,
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || 'QA Studio')
const username = computed(() => localStorage.getItem('username') || 'User')

// ---------- 修改密码 ----------
const passwordDialogVisible = ref(false)
const passwordLoading = ref(false)
const passwordFormRef = ref(null)
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const validateConfirmPassword = (_rule, value, callback) => {
  if (value !== passwordForm.value.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 4, max: 128, message: '密码长度需在 4-128 个字符之间', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleChangePassword() {
  const formRef = passwordFormRef.value
  if (!formRef) return

  try {
    await formRef.validate()
  } catch {
    return
  }

  passwordLoading.value = true
  try {
    await changePassword({
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    passwordDialogVisible.value = false
    // 清除登录态，跳转登录页
    setTimeout(() => {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      localStorage.removeItem('user_id')
      router.push('/login')
    }, 1000)
  } catch (err) {
    const detail = err.response?.data?.detail || '密码修改失败'
    ElMessage.error(detail)
  } finally {
    passwordLoading.value = false
  }
}

// Fetch current user info on mount to validate session
onMounted(async () => {
  try {
    const res = await getMe()
    localStorage.setItem('username', res.username)
    localStorage.setItem('user_id', res.id)
  } catch {
    // Token invalid or expired - redirect to login
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id')
    router.push('/login')
  }
})

function handleCommand(command) {
  if (command === 'changePassword') {
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    passwordDialogVisible.value = true
  } else if (command === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id')
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.layout-aside {
  background-color: #1d1e2c;
  overflow-y: auto;
}
.logo-area {
  padding: 16px;
  text-align: center;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}
.logo-area h2 {
  margin: 0;
  font-size: 20px;
}
.side-menu {
  background-color: #1d1e2c;
  border-right: none;
}
.side-menu .el-menu-item {
  color: rgba(255, 255, 255, 0.85);
}
.side-menu .el-menu-item:hover,
.side-menu .el-menu-item.is-active {
  color: #fff;
  background-color: #409eff;
}
:deep(.el-sub-menu__title) {
  color: #fff !important;
  font-size: 15px;
  font-weight: 600;
}
:deep(.el-sub-menu__title:hover) {
  color: #fff !important;
  background-color: rgba(255, 255, 255, 0.08) !important;
}
:deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: #409eff !important;
}
:deep(.el-sub-menu__title .el-sub-menu__icon-arrow) {
  color: rgba(255, 255, 255, 0.85) !important;
}
:deep(.el-sub-menu .el-menu) {
  background-color: #161724;
}
:deep(.el-sub-menu .el-menu .el-menu-item) {
  color: rgba(255, 255, 255, 0.85);
}
:deep(.el-sub-menu .el-menu .el-menu-item:hover),
:deep(.el-sub-menu .el-menu .el-menu-item.is-active) {
  color: #fff;
  background-color: #409eff;
}
.layout-header {
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
}
.user-info {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}
.layout-main {
  background: #f0f2f5;
  padding: 24px;
  overflow-y: auto;
}
</style>