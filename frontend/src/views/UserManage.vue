<template>
  <div class="user-manage-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" @click="showCreateDialog">创建新用户</el-button>
        </div>
      </template>

      <el-table :data="userList" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" width="200" />
        <el-table-column prop="created_at" label="创建时间">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="createDialogVisible"
      title="创建新用户"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="管理员密码" prop="admin_password">
          <el-input
            v-model="createForm.admin_password"
            type="password"
            placeholder="请输入管理员密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="createForm.username"
            placeholder="请输入用户名"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listUsers, createUser } from '../api'

const loading = ref(false)
const userList = ref([])
const createDialogVisible = ref(false)
const createLoading = ref(false)
const createFormRef = ref(null)

const createForm = ref({
  admin_password: '',
  username: '',
  password: '',
})

const createRules = {
  admin_password: [{ required: true, message: '请输入管理员密码', trigger: 'blur' }],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '用户名长度为2-64个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, max: 128, message: '密码长度为4-128个字符', trigger: 'blur' },
  ],
}

async function fetchUsers() {
  loading.value = true
  try {
    const res = await listUsers()
    userList.value = res.users || []
  } catch (err) {
    const detail = err.response?.data?.detail || '获取用户列表失败'
    ElMessage.error(detail)
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  createForm.value = {
    admin_password: '',
    username: '',
    password: '',
  }
  createDialogVisible.value = true
}

async function handleCreate() {
  const formRef = createFormRef.value
  if (!formRef) return

  try {
    await formRef.validate()
  } catch {
    return
  }

  createLoading.value = true
  try {
    await createUser({
      username: createForm.value.username,
      password: createForm.value.password,
      admin_password: createForm.value.admin_password,
    })
    ElMessage.success('用户创建成功')
    createDialogVisible.value = false
    await fetchUsers()
  } catch (err) {
    const detail = err.response?.data?.detail || '创建用户失败'
    ElMessage.error(detail)
  } finally {
    createLoading.value = false
  }
}

function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.user-manage-container {
  max-width: 800px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header span {
  font-size: 16px;
  font-weight: 600;
}
</style>