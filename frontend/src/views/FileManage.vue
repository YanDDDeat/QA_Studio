<template>
  <div class="page-container">
    <h2>文件管理</h2>

    <!-- Upload section -->
    <el-card class="upload-card">
      <template #header>
        <span class="card-title">上传文件</span>
      </template>
      <div class="upload-area">
        <div class="upload-controls">
          <el-form :inline="true" class="text-field-form">
            <el-form-item label="文本字段名">
              <el-input
                v-model="textField"
                placeholder="指定JSON中包含文本内容的字段名"
                style="width: 220px"
              />
            </el-form-item>
          </el-form>
        </div>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :multiple="true"
          :limit="20"
          accept=".json"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          :on-exceed="handleExceed"
          :file-list="fileList"
          drag
          class="upload-dragger"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽JSON文件到此处，或<em>点击选择文件</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              仅支持.json格式文件，最多上传20个文件
            </div>
          </template>
        </el-upload>
        <el-button
          type="primary"
          :loading="uploadLoading"
          :disabled="fileList.length === 0"
          @click="handleUpload"
          class="upload-btn"
        >
          上传文件
        </el-button>
      </div>
    </el-card>

    <!-- File list section -->
    <el-card class="list-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">文件列表</span>
          <div class="header-actions">
            <el-select
              v-model="filterStage"
              placeholder="筛选来源阶段"
              clearable
              style="width: 180px"
              @change="fetchFiles"
            >
              <el-option
                label="上传文件（无阶段）"
                value=""
              />
              <el-option
                v-for="s in stageOptions"
                :key="s.value"
                :label="s.label"
                :value="s.value"
              />
            </el-select>
            <el-button
              type="success"
              :disabled="selectedFiles.length < 2"
              @click="handleMergeDownload"
            >
              合并下载 ({{ selectedFiles.length }})
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="paginatedFiles" v-loading="loading" stripe @selection-change="handleSelectionChange" ref="fileTableRef">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="filename" label="文件名" min-width="180" />
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column prop="source_stage" label="来源阶段" width="140">
          <template #default="{ row }">
            {{ stageLabel(row.source_stage) }}
          </template>
        </el-table-column>
        <el-table-column prop="text_field" label="文本字段" width="100" />
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="handleView(row)"
            >
              查看
            </el-button>
            <el-button
              type="primary"
              link
              size="small"
              @click="handleDownload(row)"
            >
              下载
            </el-button>
            <el-button
              type="danger"
              link
              size="small"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrap" v-if="totalFiles > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="totalFiles"
          layout="prev, pager, next"
          @current-change="fetchFiles"
        />
      </div>
    </el-card>

    <!-- JSON preview dialog -->
    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="720px"
      :close-on-click-modal="true"
      destroy-on-close
    >
      <div v-loading="previewLoading" class="preview-content">
        <div v-if="previewData" class="preview-info">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="文件名">{{ previewData.filename }}</el-descriptions-item>
            <el-descriptions-item label="文本字段">{{ previewData.text_field }}</el-descriptions-item>
            <el-descriptions-item label="总记录数">{{ previewData.total_records }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-if="previewData" class="preview-json">
          <pre class="json-preview">{{ formatJsonPreview(previewData.preview) }}</pre>
        </div>
        <div v-if="previewData && previewData.total_records > 50" class="preview-warning">
          <el-tag type="info" size="small">
            仅显示前50条记录，共{{ previewData.total_records }}条
          </el-tag>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import {
  getManagedFiles,
  getManagedFileContent,
  uploadManagedFile,
  deleteManagedFile,
  downloadManagedFile,
  mergeAndDownloadFiles,
} from '../api'

// Stage options for filter and display
const stageOptions = [
  { value: 'question_generate', label: '问题生成' },
  { value: 'knowledge_generate', label: '知识体系生成' },
  { value: 'question_validate', label: '问题校验' },
  { value: 'answer_generate', label: '答案生成' },
  { value: 'answer_validate', label: '答案校验' },
  { value: 'data_evaluate', label: '数据评估' },
]

// Upload state
const uploadRef = ref(null)
const fileList = ref([])
const textField = ref('text')
const uploadLoading = ref(false)

// File list state
const loading = ref(false)
const allFiles = ref([])
const filterStage = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const selectedFiles = ref([])
const fileTableRef = ref(null)

// Preview state
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewData = ref(null)
const previewTitle = ref('')

// Computed
const totalFiles = computed(() => allFiles.value.length)
const paginatedFiles = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return allFiles.value.slice(start, start + pageSize.value)
})

// Upload handlers
function handleFileChange(file, newFileList) {
  fileList.value = newFileList
}

function handleFileRemove(file, newFileList) {
  fileList.value = newFileList
}

function handleExceed() {
  ElMessage.warning('最多上传20个文件')
}

async function handleUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }

  uploadLoading.value = true
  const formData = new FormData()
  formData.append('text_field', textField.value)

  for (const file of fileList.value) {
    formData.append('files', file.raw)
  }

  try {
    const res = await uploadManagedFile(formData)
    const uploadedCount = res.uploaded?.length || 0
    const errorCount = res.errors?.length || 0

    if (uploadedCount > 0) {
      ElMessage.success(`成功上传${uploadedCount}个文件`)
    }
    if (errorCount > 0) {
      const errorMessages = res.errors.map(e => `${e.filename}: ${e.error}`).join('\n')
      ElMessage.error(`上传失败${errorCount}个文件:\n${errorMessages}`)
    }

    // Clear upload area
    fileList.value = []
    uploadRef.value?.clearFiles()
    await fetchFiles()
  } catch (err) {
    const detail = err.response?.data?.detail || '上传失败'
    ElMessage.error(detail)
  } finally {
    uploadLoading.value = false
  }
}

// Fetch files
async function fetchFiles() {
  loading.value = true
  try {
    const params = {}
    if (filterStage.value) {
      params.source_stage = filterStage.value
    }
    const res = await getManagedFiles(params)
    allFiles.value = res.items || []
  } catch (err) {
    const detail = err.response?.data?.detail || '获取文件列表失败'
    ElMessage.error(detail)
    allFiles.value = []
  } finally {
    loading.value = false
  }
}

// View JSON content
async function handleView(row) {
  if (row.file_type !== 'json') {
    ElMessage.info('仅JSON文件支持内容预览')
    return
  }

  previewTitle.value = `文件预览 - ${row.filename}`
  previewVisible.value = true
  previewLoading.value = true
  previewData.value = null

  try {
    const res = await getManagedFileContent(row.id)
    previewData.value = res
  } catch (err) {
    const detail = err.response?.data?.detail || '获取文件内容失败'
    ElMessage.error(detail)
    previewVisible.value = false
  } finally {
    previewLoading.value = false
  }
}

// Download
async function handleDownload(row) {
  try {
    const blob = await downloadManagedFile(row.id)
    // Create download link
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = row.filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    const detail = err.response?.data?.detail || '下载失败'
    ElMessage.error(detail)
  }
}

// Multi-select
function handleSelectionChange(selection) {
  selectedFiles.value = selection
}

// Merge download
async function handleMergeDownload() {
  if (selectedFiles.value.length < 2) {
    ElMessage.warning('请至少选择2个文件')
    return
  }
  const ids = selectedFiles.value.map(f => f.id)
  try {
    const blob = await mergeAndDownloadFiles(ids)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `merged_${ids.length}files.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success(`已合并${ids.length}个文件，下载中`)
  } catch (err) {
    const detail = err.response?.data?.detail || '合并下载失败'
    ElMessage.error(detail)
  }
}

// Delete
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件 "${row.filename}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return // cancelled
  }

  try {
    await deleteManagedFile(row.id)
    ElMessage.success('文件已删除')
    await fetchFiles()
  } catch (err) {
    const detail = err.response?.data?.detail || '删除失败'
    ElMessage.error(detail)
  }
}

// Formatting helpers
function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
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

function stageLabel(stage) {
  if (!stage) return '上传文件'
  const found = stageOptions.find(s => s.value === stage)
  return found ? found.label : stage
}

function formatJsonPreview(data) {
  if (!data) return ''
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

onMounted(() => {
  fetchFiles()
})
</script>

<style scoped>
.page-container {}
.page-container h2 {
  margin-bottom: 16px;
}

.upload-card {
  margin-bottom: 20px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}
.upload-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.text-field-form {
  margin-bottom: 0;
}
.upload-dragger {
  width: 100%;
}
.upload-btn {
  align-self: flex-start;
}

.list-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.preview-content {
  min-height: 100px;
}
.preview-info {
  margin-bottom: 16px;
}
.preview-json {
  max-height: 500px;
  overflow-y: auto;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
}
.json-preview {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.preview-warning {
  margin-top: 8px;
}
</style>