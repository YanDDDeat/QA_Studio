<template>
  <div class="page-container">
    <h2>数据中心</h2>
    <p class="page-intro">以 JSON 文件为整体单位查看数据，点击文件预览其内容。</p>

    <!-- File list -->
    <el-card class="file-list-card">
      <div class="file-list-header">
        <span class="file-count">共 {{ fileTotal }} 个文件</span>
        <div class="file-list-controls">
          <el-switch
            v-if="isAdmin"
            v-model="showAllFiles"
            active-text="全部用户"
            inactive-text="仅自己"
            @change="onToggleAllFiles"
          />
          <el-input
            v-model="searchKeyword"
            placeholder="搜索文件名"
            clearable
            size="small"
            style="width: 180px"
            @input="onSearchChange"
          />
          <el-select v-model="sortMode" size="small" style="width: 140px" @change="fetchFiles">
            <el-option label="最新优先" value="time_desc" />
            <el-option label="最早优先" value="time_asc" />
            <el-option label="文件名排序" value="name_asc" />
          </el-select>
          <el-button type="success" size="small" :disabled="selectedFileIds.size < 2" @click="handleMergeDownload">
            合并下载 ({{ selectedFileIds.size }})
          </el-button>
          <el-button type="danger" size="small" :disabled="selectedFileIds.size === 0" @click="handleBatchDelete">
            批量删除 ({{ selectedFileIds.size }})
          </el-button>
          <el-button type="primary" size="small" @click="fetchFiles">刷新</el-button>
        </div>
      </div>

      <el-table
        ref="fileTableRef"
        :data="pagedFiles"
        v-loading="loading"
        stripe
        highlight-current-row
        @current-change="handleFileSelect"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column v-if="showAllFiles" prop="username" label="用户名" width="100" />
        <el-table-column label="来源阶段" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.source_stage" size="small" :type="stageTagType(row.source_stage)">
              {{ stageLabel(row.source_stage) }}
            </el-tag>
            <span v-else class="empty-field">上传文件</span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="handleFileSelect(row)">
              查看
            </el-button>
            <el-button type="success" link size="small" @click.stop="handleDownload(row)">
              下载
            </el-button>
            <el-button
              :icon="Refresh"
              type="warning"
              link
              size="small"
              :loading="syncLoading"
              @click.stop="handleSync(row)"
            >
              同步
            </el-button>
            <el-button type="danger" link size="small" @click.stop="handleDeleteFile(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="file-pagination">
        <el-pagination
          v-model:current-page="filePage"
          :page-size="10"
          :total="fileTotal"
          layout="total, prev, pager, next"
          @current-change="fetchFiles"
        />
      </div>
    </el-card>

    <!-- File content preview -->
    <el-card v-if="selectedFile" class="preview-card">
      <div class="preview-header">
        <div class="preview-title">
          <h3>{{ selectedFile.filename }}</h3>
          <span v-if="previewData" class="preview-meta">
            {{ previewData.total_records }} 条记录
          </span>
        </div>
        <el-button type="success" size="small" @click="handleDownload(selectedFile)">下载文件</el-button>
      </div>

      <!-- Record filter controls -->
      <div v-if="filterOptions" class="record-filter-bar">
        <el-select
          v-model="filterTaskType"
          placeholder="题型"
          clearable
          size="small"
          style="width: 120px"
          @change="loadPreview"
        >
          <el-option v-for="t in filterOptions.task_types" :key="t" :label="t" :value="t" />
        </el-select>
        <el-select
          v-model="filterDomain"
          placeholder="领域"
          clearable
          size="small"
          style="width: 120px"
          @change="loadPreview"
        >
          <el-option v-for="d in filterOptions.domains" :key="d" :label="d" :value="d" />
        </el-select>
        <el-select
          v-model="filterDifficulty"
          placeholder="难度"
          clearable
          size="small"
          style="width: 120px"
          @change="loadPreview"
        >
          <el-option v-for="d in filterOptions.difficulties" :key="d" :label="d" :value="d" />
        </el-select>
      </div>

      <div v-loading="previewLoading" class="preview-content">
        <template v-if="previewData && previewData.preview && previewData.preview.length">
          <el-table
            :data="flatPreviewData"
            stripe
            border
            size="small"
          >
            <el-table-column
              v-for="col in previewColumns"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              :width="col.width"
              :min-width="col.minWidth"
              show-overflow-tooltip
            />
            <el-table-column label="操作" width="70" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleRecordSelect(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="preview-pagination">
            <el-pagination
              v-model:current-page="previewPage"
              :page-size="10"
              :total="previewData.total_records"
              layout="total, prev, pager, next"
              @current-change="loadPreview"
            />
          </div>
        </template>

        <div v-else-if="previewData && (!previewData.preview || !previewData.preview.length)" class="empty-field">
          文件内容为空
        </div>
      </div>
    </el-card>

    <!-- Record detail — rendered directly below the preview -->
    <el-card v-if="selectedRecord" class="detail-card">
      <div class="detail-header">
        <h3>记录详情 #{{ selectedRecord.id || '-' }}</h3>
      </div>

      <el-descriptions :column="2" border size="small">
        <el-descriptions-item v-for="key in detailMetaFields" :key="key" :label="key">
          {{ detailFlatRecord[key] != null ? detailFlatRecord[key] : '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="detail-text-fields">
        <div v-for="key in detailLongTextFields" :key="key" class="text-field-block">
          <div class="field-label">{{ key }}</div>
          <div class="field-content" v-html="renderContent(detailFlatRecord[key])"></div>
        </div>
      </div>
    </el-card>

    <!-- Field selection dialog for export -->
    <FieldSelectDialog
      :visible="fieldSelectVisible"
      :fields="availableFields"
      :default-fields="DEFAULT_EXPORT_FIELDS"
      @confirm="onFieldSelectConfirm"
      @cancel="onFieldSelectCancel"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import katex from 'katex'
import FieldSelectDialog from '../components/FieldSelectDialog.vue'
import {
  getManagedFiles,
  getManagedFileContent,
  downloadManagedFile,
  deleteManagedFile,
  batchDeleteManagedFiles,
  mergeAndDownloadFiles,
  syncFileToDisk,
} from '../api'
import { categorizeFields, FIELD_LABELS } from '../utils/fieldLabels'

const STAGE_MAP = {
  question_generate: '问题生成',
  knowledge_generate: '知识体系生成',
  question_validate: '问题校验',
  answer_generate: '答案生成',
  answer_validate: '答案校验',
  data_evaluate: '数据评估',
}

// File list state
const loading = ref(false)
const files = ref([])
const fileTotal = ref(0)
const filePage = ref(1)
const route = useRoute()
const searchKeyword = ref('')
const sortMode = ref('time_desc')

// Computed: current page slice (backend now paginated, so files already is the page slice)
const pagedFiles = computed(() => files.value)

// File preview state
const selectedFile = ref(null)
const previewLoading = ref(false)
const previewData = ref(null)
const previewPage = ref(1)
const filterOptions = ref(null)
const filterTaskType = ref(null)
const filterDomain = ref(null)
const filterDifficulty = ref(null)

// Record detail state (inline, no dialog)
const selectedRecord = ref(null)

// Cross-page selection tracking
const selectedFileIds = ref(new Set())
const selectedFileInfo = ref(new Map()) // fileId → {filename, username}
const fileTableRef = ref(null)
const syncLoading = ref(false)

// Admin toggle
const showAllFiles = ref(false)
const isAdmin = computed(() => localStorage.getItem('username') === 'admin')

// Default fields for export selection (case-insensitive matching)
const DEFAULT_EXPORT_FIELDS = [
  'id', 'domain', 'category', 'task_type', 'input', 'output', 'cot',
  'corpus_cate', 'scene', 'source', 'source_id', 'originContent', 'source_type',
  'knowledge', 'difficulty', 'Relevance', 'Clarity', 'Scientific', 'Reasoning',
  'Terminology', 'score', 'Assessment',
]

// Field selection dialog state
const fieldSelectVisible = ref(false)
const availableFields = ref({ topLevel: [], extra: [] })
const pendingDownloadTarget = ref(null) // { type: 'single', row } or { type: 'merge' }

// Parse available fields from preview data
function normalizeFieldName(name, defaults) {
  const lowerDefaults = new Map(defaults.map(f => [f.toLowerCase(), f]))
  return lowerDefaults.get(name.toLowerCase()) || name
}

function parseAvailableFields() {
  if (!previewData.value?.preview?.length) {
    return { topLevel: [], extra: [] }
  }
  const topLevelSet = new Set()
  const extraSet = new Set()
  for (const row of previewData.value.preview) {
    if (!row || typeof row !== 'object') continue
    for (const key of Object.keys(row)) {
      if (key === 'extra_fields' || key === 'extra') {
        const extra = row[key]
        if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
          for (const ek of Object.keys(extra)) extraSet.add(normalizeFieldName(ek, DEFAULT_EXPORT_FIELDS))
        }
      } else {
        topLevelSet.add(normalizeFieldName(key, DEFAULT_EXPORT_FIELDS))
      }
    }
  }
  return {
    topLevel: [...topLevelSet].sort(),
    extra: [...extraSet].sort(),
  }
}

// Dynamic preview columns from actual data
const previewColumns = computed(() => {
  if (!previewData.value?.preview?.length) return []
  // Collect all unique keys across records, expanding extra_fields
  const allKeys = new Set()
  for (const row of previewData.value.preview) {
    if (!row || typeof row !== 'object') continue
    for (const key of Object.keys(row)) {
      if (key === 'extra_fields') {
        const extra = row[key]
        if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
          for (const ek of Object.keys(extra)) allKeys.add(ek)
        }
        // skip extra_fields itself
      } else {
        allKeys.add(key)
      }
    }
  }
  return [...allKeys].map(key => ({
    prop: key,
    label: key,
    width: key === 'id' ? 55 : undefined,
    minWidth: 100,
  }))
})

// Flatten preview rows: expand extra_fields into individual fields
const flatPreviewData = computed(() => {
  if (!previewData.value?.preview?.length) return []
  return previewData.value.preview.map(row => {
    if (!row || typeof row !== 'object') return row
    const flat = { ...row }
    const extra = flat.extra_fields
    if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
      delete flat.extra_fields
      for (const [k, v] of Object.entries(extra)) {
        if (!(k in flat)) flat[k] = v
      }
    } else {
      delete flat.extra_fields
    }
    return flat
  })
})

// Flattened record for detail display (extra_fields expanded)
const detailFlatRecord = computed(() => {
  if (!selectedRecord.value) return null
  const flat = { ...selectedRecord.value }
  const extra = flat.extra_fields
  if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
    delete flat.extra_fields
    for (const [k, v] of Object.entries(extra)) {
      if (!(k in flat)) flat[k] = v
    }
  } else {
    delete flat.extra_fields
  }
  return flat
})

// Detail fields: split into meta (short) and long-text
const detailMetaFields = computed(() => {
  if (!detailFlatRecord.value) return []
  return categorizeFields(detailFlatRecord.value).meta
})

const detailLongTextFields = computed(() => {
  if (!detailFlatRecord.value) return []
  return categorizeFields(detailFlatRecord.value).longText
})

function stageLabel(stage) {
  if (!stage) return '-'
  return STAGE_MAP[stage] || stage
}

function stageTagType(stage) {
  const map = {
    question_generate: '',
    knowledge_generate: 'warning',
    question_validate: 'success',
    answer_generate: '',
    answer_validate: 'success',
    data_evaluate: 'info',
  }
  return map[stage] || ''
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

let searchTimer = null
function onSearchChange() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    filePage.value = 1
    fetchFiles()
  }, 300)
}

function onToggleAllFiles() {
  filePage.value = 1
  selectedFileIds.value = new Set()
  selectedFileInfo.value = new Map()
  selectedFile.value = null
  previewData.value = null
  selectedRecord.value = null
  fetchFiles()
}

async function fetchFiles() {
  loading.value = true
  try {
    const params = {
      page: filePage.value,
      page_size: 10,
      sort: sortMode.value,
    }
    if (searchKeyword.value) params.search = searchKeyword.value
    if (showAllFiles.value) params.all_users = true
    const res = await getManagedFiles(params)
    files.value = res.items || []
    fileTotal.value = res.total || 0
    // Restore cross-page selections
    await nextTick()
    pagedFiles.value.forEach(row => {
      if (selectedFileIds.value.has(row.id)) {
        fileTableRef.value?.toggleRowSelection(row, true)
      }
    })
  } catch (err) {
    ElMessage.error('获取文件列表失败')
    files.value = []
    fileTotal.value = 0
  } finally {
    loading.value = false
  }
}

function handleFileSelect(row) {
  if (row) {
    selectedFile.value = row
    previewPage.value = 1
    selectedRecord.value = null
    // Reset filters when selecting a new file
    filterTaskType.value = null
    filterDomain.value = null
    filterDifficulty.value = null
    loadPreview()
  }
}

async function loadPreview() {
  previewLoading.value = true
  previewData.value = null
  try {
    const params = {
      page: previewPage.value,
      page_size: 10,
    }
    if (filterTaskType.value) params.task_type = filterTaskType.value
    if (filterDomain.value) params.domain = filterDomain.value
    if (filterDifficulty.value) params.difficulty = filterDifficulty.value
    const res = await getManagedFileContent(selectedFile.value.id, params)
    previewData.value = res
    filterOptions.value = res.filter_options || null
  } catch (err) {
    const detail = err.response?.data?.detail || '预览文件内容失败'
    ElMessage.error(detail)
    previewData.value = null
  } finally {
    previewLoading.value = false
  }
}

function handleRecordSelect(row) {
  selectedRecord.value = row || null
}

async function handleDownload(row) {
  // If preview data not loaded for this file, fetch it to discover fields
  if (!previewData.value || selectedFile.value?.id !== row.id) {
    try {
      const res = await getManagedFileContent(row.id, { page: 1, page_size: 5 })
      previewData.value = res
      selectedFile.value = row
      filterOptions.value = res.filter_options || null
    } catch (err) {
      ElMessage.error('加载文件字段信息失败')
      return
    }
  }
  availableFields.value = parseAvailableFields()
  if (availableFields.value.topLevel.length === 0 && availableFields.value.extra.length === 0) {
    ElMessage.warning('无法解析字段信息，请检查文件格式')
    return
  }
  // Show field selection dialog
  pendingDownloadTarget.value = { type: 'single', row }
  fieldSelectVisible.value = true
}

function onFieldSelectConfirm(fields) {
  fieldSelectVisible.value = false
  const target = pendingDownloadTarget.value
  if (!target) return
  pendingDownloadTarget.value = null

  if (target.type === 'single') {
    doDownloadSingle(target.row, fields)
  } else if (target.type === 'merge') {
    doMergeDownload(fields)
  }
}

function onFieldSelectCancel() {
  fieldSelectVisible.value = false
  pendingDownloadTarget.value = null
}

async function doDownloadSingle(row, fields) {
  try {
    const blob = await downloadManagedFile(row.id, fields)
    triggerDownload(blob, row.filename)
  } catch (err) {
    ElMessage.error('下载文件失败')
  }
}

function triggerDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

function handleSelectionChange(selection) {
  // Remove all current-page IDs from tracking
  pagedFiles.value.forEach(row => {
    selectedFileIds.value.delete(row.id)
    selectedFileInfo.value.delete(row.id)
  })
  // Add back only the currently selected ones
  selection.forEach(row => {
    selectedFileIds.value.add(row.id)
    selectedFileInfo.value.set(row.id, {
      filename: row.filename,
      username: row.username || '',
    })
  })
}

async function handleMergeDownload() {
  if (selectedFileIds.value.size < 2) {
    ElMessage.warning('请至少选择2个文件')
    return
  }

  // If no preview data loaded, fetch from one selected file to discover fields
  availableFields.value = parseAvailableFields()
  if (availableFields.value.topLevel.length === 0 && availableFields.value.extra.length === 0) {
    const firstId = [...selectedFileIds.value][0]
    try {
      const res = await getManagedFileContent(firstId, { page: 1, page_size: 5 })
      previewData.value = res
      filterOptions.value = res.filter_options || null
    } catch (err) {
      ElMessage.error('加载文件字段信息失败')
      return
    }
    availableFields.value = parseAvailableFields()
  }

  if (availableFields.value.topLevel.length === 0 && availableFields.value.extra.length === 0) {
    ElMessage.warning('无法解析字段信息，请检查文件格式')
    return
  }

  // Show field selection dialog
  pendingDownloadTarget.value = { type: 'merge' }
  fieldSelectVisible.value = true
}

async function doMergeDownload(fields) {
  const ids = [...selectedFileIds.value]
  try {
    const blob = await mergeAndDownloadFiles(ids, fields)
    triggerDownload(blob, `merged_${ids.length}files.json`)
    ElMessage.success(`已合并${ids.length}个文件，下载中`)
  } catch (err) {
    const detail = err.response?.data?.detail || '合并下载失败'
    ElMessage.error(detail)
  }
}

async function handleDeleteFile(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件 "${row.filename}" 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteManagedFile(row.id)
    ElMessage.success('已删除')
    // Clear preview if deleted file was selected
    if (selectedFile.value && selectedFile.value.id === row.id) {
      selectedFile.value = null
      previewData.value = null
      selectedRecord.value = null
    }
    await fetchFiles()
  } catch (err) {
    const detail = err.response?.data?.detail || '删除失败'
    ElMessage.error(detail)
  }
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedFileIds.value.size} 个文件吗？此操作不可恢复。`,
      '批量删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  try {
    const res = await batchDeleteManagedFiles([...selectedFileIds.value])
    const deletedCount = res.deleted?.length || 0
    const skippedCount = res.skipped?.length || 0

    if (skippedCount > 0) {
      ElMessage.warning(`已删除 ${deletedCount} 个文件，${skippedCount} 个因有运行中任务被跳过`)
    } else {
      ElMessage.success(`已删除 ${deletedCount} 个文件`)
    }

    selectedFileIds.value.clear()
    selectedFileInfo.value.clear()

    if (selectedFile.value && res.deleted?.includes(selectedFile.value.id)) {
      selectedFile.value = null
      previewData.value = null
      selectedRecord.value = null
    }

    await fetchFiles()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '批量删除失败')
  }
}

async function handleSync(row) {
  try {
    await ElMessageBox.confirm(
      '确定要将数据库中的数据同步到文件吗？这将覆盖文件当前内容。',
      '同步确认',
      { confirmButtonText: '同步', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  syncLoading.value = true
  try {
    const res = await syncFileToDisk(row.id)
    ElMessage.success(`已同步 ${res.synced_count} 条记录到文件`)
    // Auto refresh preview if the synced file is currently selected
    if (selectedFile.value && selectedFile.value.id === row.id) {
      loadPreview()
    }
  } catch (err) {
    const detail = err.response?.data?.detail || '同步失败'
    ElMessage.error(detail)
  } finally {
    syncLoading.value = false
  }
}

// ---------- LaTeX / content rendering ----------

function renderLatex(text) {
  if (!text) return ''
  let html = text

  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return match
    }
  })

  html = html.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return match
    }
  })

  return html
}

function renderContent(text) {
  if (!text) return '<span class="empty-field">-</span>'
  if (typeof text !== 'string') {
    try {
      const formatted = JSON.stringify(text, null, 2)
      return '<pre class="knowledge-json">' + escapeHtml(formatted) + '</pre>'
    } catch {
      return String(text)
    }
  }
  let html = escapeHtml(text)
  html = renderLatex(html)
  html = html.replace(/\n/g, '<br>')
  return html
}

function renderKnowledge(knowledge) {
  if (!knowledge) return '<span class="empty-field">-</span>'
  if (typeof knowledge === 'string') return renderContent(knowledge)
  try {
    const formatted = JSON.stringify(knowledge, null, 2)
    return '<pre class="knowledge-json">' + escapeHtml(formatted) + '</pre>'
  } catch {
    return String(knowledge)
  }
}

function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

onMounted(async () => {
  await fetchFiles()
  // Auto-select file if file_id is in URL query params
  const fileId = route.query.file_id
  if (fileId) {
    const id = parseInt(fileId)
    const match = files.value.find(f => f.id === id)
    if (match) {
      selectedFile.value = match
      previewPage.value = 1
      selectedRecord.value = null
      loadPreview()
    } else {
      // File might be on a different page — search through all pages
      await autoSelectFile(id)
    }
  }
})

async function autoSelectFile(targetId) {
  const totalPages = Math.ceil(fileTotal.value / 10)
  for (let p = 1; p <= totalPages; p++) {
    filePage.value = p
    await fetchFiles()
    const match = files.value.find(f => f.id === targetId)
    if (match) {
      selectedFile.value = match
      previewPage.value = 1
      selectedRecord.value = null
      loadPreview()
      return
    }
  }
  ElMessage.warning('未找到指定文件')
}
</script>

<style scoped>
@import 'katex/dist/katex.min.css';

.page-container {}
.page-container h2 {
  margin-bottom: 8px;
}
.page-intro {
  color: #606266;
  font-size: 14px;
  margin-bottom: 16px;
}

.file-list-card {
  margin-bottom: 16px;
}
.file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.file-list-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.file-count {
  color: #909399;
  font-size: 13px;
}
.file-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.preview-card {
  margin-bottom: 16px;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.preview-title h3 {
  margin: 0;
  font-size: 16px;
}
.preview-meta {
  color: #909399;
  font-size: 13px;
  margin-left: 12px;
}
.record-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.preview-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.detail-card {
  margin-bottom: 16px;
}
.detail-header h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
}
.detail-text-fields {
  margin-top: 16px;
}
.text-field-block {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.text-field-block .field-label {
  font-weight: 600;
  margin-bottom: 8px;
  color: #303133;
  font-size: 14px;
}
.text-field-block .field-content {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  color: #606266;
}
.empty-field {
  color: #c0c4cc;
}
.knowledge-json {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  background: transparent;
}
</style>