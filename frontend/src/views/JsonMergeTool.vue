<template>
  <div class="page-container">
    <div class="page-header">
      <h2>JSON 文件合并工具</h2>
      <p class="page-desc">上传多个 JSON 数组文件，自动校验必填字段并按字段交集合并下载。</p>
    </div>

    <!-- Upload area -->
    <el-card class="upload-card">
      <template #header>
        <span class="card-title">上传 JSON 文件</span>
      </template>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :multiple="true"
        accept=".json"
        :on-change="handleFileChange"
        :show-file-list="false"
        drag
        class="upload-dragger"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽 JSON 文件到此处，或<em>点击选择文件</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            仅支持 .json 文件，单文件最大 50MB。文件根必须是 JSON 数组，每条记录必须包含
            <el-tag size="small" type="success" effect="plain">source_id</el-tag>
            <el-tag size="small" type="success" effect="plain">source</el-tag>
            <el-tag size="small" type="success" effect="plain">source_type</el-tag>
            三个字段（值不可为空）。
          </div>
        </template>
      </el-upload>
    </el-card>

    <!-- File list -->
    <el-card v-if="files.length > 0" class="list-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">文件列表（{{ files.length }}）</span>
          <el-button
            type="danger"
            link
            size="small"
            @click="handleClearAll"
          >
            清空全部
          </el-button>
        </div>
      </template>
      <el-table :data="files" stripe row-key="id">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="name" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="大小" width="110">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column label="记录数" width="100" align="right">
          <template #default="{ row }">
            {{ row.recordCount === null ? '-' : row.recordCount }}
          </template>
        </el-table-column>
        <el-table-column label="校验状态" width="180">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'pending'" type="info" size="small">校验中...</el-tag>
            <el-tag v-else-if="row.status === 'ok'" type="success" size="small">OK</el-tag>
            <el-tooltip
              v-else
              effect="dark"
              :content="row.error"
              placement="top"
              popper-class="merge-error-tooltip"
            >
              <el-tag type="danger" size="small">失败</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ $index }">
            <el-button
              type="danger"
              link
              size="small"
              :icon="Delete"
              @click="handleRemoveFile($index)"
            >
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Stats and merge action -->
    <el-card class="action-card">
      <template #header>
        <span class="card-title">合并预览</span>
      </template>

      <div v-if="statsVisible" class="stats-area">
        <div class="stats-row">
          <div class="stat-item">
            <div class="stat-label">文件数</div>
            <div class="stat-value">{{ files.length }}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">合计记录数</div>
            <div class="stat-value">{{ totalRecords }}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">公共字段数</div>
            <div class="stat-value">{{ orderedCommonFields.length }}</div>
          </div>
        </div>
        <div class="fields-row">
          <span class="fields-label">公共字段：</span>
          <div class="fields-tags">
            <el-tag
              v-for="field in orderedCommonFields"
              :key="field"
              size="small"
              :type="REQUIRED_FIELDS.includes(field) ? 'success' : 'info'"
              class="field-tag"
            >
              {{ field }}
            </el-tag>
          </div>
        </div>
      </div>

      <el-alert
        v-else-if="files.length === 0"
        title="请先上传至少 2 个 JSON 文件以开始合并"
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="hasPending"
        title="文件校验中，请稍候..."
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="files.length < 2"
        title="至少需要 2 个文件才能合并"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else
        title="存在校验失败的文件，请处理后再合并"
        type="error"
        :closable="false"
        show-icon
      />

      <div class="action-row">
        <el-button
          type="primary"
          size="large"
          :icon="Download"
          :disabled="!canMerge"
          @click="handleMergeDownload"
        >
          合并并下载
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UploadFilled,
  Delete,
  Download,
} from '@element-plus/icons-vue'

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const REQUIRED_FIELDS = ['source_id', 'source', 'source_type']

const uploadRef = ref(null)
const files = ref([])
let fileIdCounter = 0

// ---------- Computed ----------
const allValid = computed(
  () => files.value.length > 0 && files.value.every(f => f.status === 'ok')
)

const hasPending = computed(() => files.value.some(f => f.status === 'pending'))

const canMerge = computed(() => files.value.length >= 2 && allValid.value)

const statsVisible = computed(() => files.value.length >= 2 && allValid.value)

const totalRecords = computed(() =>
  files.value.reduce((acc, f) => acc + (f.recordCount || 0), 0)
)

// Common fields = intersection of field names across every record of every file.
// We precompute per-file record-intersection during validation, so here we just
// intersect those small sets and then order by the first file's first record.
const orderedCommonFields = computed(() => {
  if (!statsVisible.value) return []
  let intersection = null
  for (const file of files.value) {
    const fileSet = file.fieldIntersection
    if (!fileSet) return []
    if (intersection === null) {
      intersection = new Set(fileSet)
    } else {
      intersection = new Set([...intersection].filter(k => fileSet.has(k)))
    }
  }
  if (!intersection || intersection.size === 0) return []
  const firstFile = files.value[0]
  if (!firstFile.records || firstFile.records.length === 0) return []
  const firstRecordKeys = Object.keys(firstFile.records[0])
  return firstRecordKeys.filter(k => intersection.has(k))
})

// ---------- Validation ----------
// One-pass: validate every record and collect the field-name intersection at the
// same time. Returns { error } on the first failure, or { fieldIntersection } on
// success. Halves the work vs. validating then re-walking to compute fields.
function validateAndExtractFields(name, parsed) {
  if (!Array.isArray(parsed)) {
    return { error: `文件 "${name}" 内容不是 JSON 数组（顶层必须是 []）` }
  }
  if (parsed.length === 0) {
    return { error: `文件 "${name}" 是空数组，没有可合并的记录` }
  }
  let intersection = null
  for (let i = 0; i < parsed.length; i++) {
    const item = parsed[i]
    if (item === null || typeof item !== 'object' || Array.isArray(item)) {
      return { error: `文件 "${name}" 第 ${i + 1} 条记录不是合法对象` }
    }
    for (const field of REQUIRED_FIELDS) {
      const val = item[field]
      if (val === undefined || val === null || val === '') {
        return { error: `文件 "${name}" 第 ${i + 1} 条记录缺少必填字段：${field}` }
      }
    }
    const keys = Object.keys(item)
    if (intersection === null) {
      intersection = new Set(keys)
    } else {
      // Shrink intersection by keeping only keys present in this record.
      const next = new Set()
      const keySet = new Set(keys)
      for (const k of intersection) {
        if (keySet.has(k)) next.add(k)
      }
      intersection = next
    }
  }
  return { fieldIntersection: intersection || new Set() }
}

// ---------- File handlers ----------
async function handleFileChange(uploadFile) {
  const raw = uploadFile.raw
  const name = uploadFile.name

  // Extension guard (accept=".json" is only a hint)
  if (!name.toLowerCase().endsWith('.json')) {
    ElMessage.error(`文件 "${name}" 不是 .json 文件，已忽略`)
    return
  }

  // Size guard
  if (raw.size > MAX_FILE_SIZE) {
    ElMessage.error(`文件 "${name}" 超过 50MB，已拒收`)
    return
  }

  // Add to list as pending. Important: push the raw object, then grab the
  // reactive proxy back out of the array via find(). Mutating the local
  // `entry` ref directly skips Vue's proxy and computed/watchers wouldn't
  // be notified (the table column happens to re-render via other deps,
  // but the merge-preview computed stays stale).
  const entryId = ++fileIdCounter
  files.value.push({
    id: entryId,
    name,
    size: raw.size,
    raw,
    status: 'pending',
    error: '',
    records: null,
    recordCount: null,
    fieldIntersection: null,
  })
  const entry = files.value.find(f => f.id === entryId)

  // Read + parse + validate asynchronously
  try {
    const text = await raw.text()
    let parsed
    try {
      parsed = JSON.parse(text)
    } catch (e) {
      throw new Error(`文件 "${name}" 不是合法 JSON：${e.message}`)
    }
    const result = validateAndExtractFields(name, parsed)
    if (result.error) throw new Error(result.error)

    // entry may have been removed by the user during the await; guard.
    const current = files.value.find(f => f.id === entryId)
    if (!current) return
    current.records = parsed
    current.recordCount = parsed.length
    current.fieldIntersection = result.fieldIntersection
    current.status = 'ok'
  } catch (err) {
    const current = files.value.find(f => f.id === entryId)
    if (current) {
      current.status = 'error'
      current.error = err.message
    }
    ElMessage.error(err.message)
  }
}

function handleRemoveFile(index) {
  files.value.splice(index, 1)
}

async function handleClearAll() {
  try {
    await ElMessageBox.confirm('确定清空所有已上传文件吗？', '清空确认', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  files.value = []
  uploadRef.value?.clearFiles?.()
}

// ---------- Merge & download ----------
function handleMergeDownload() {
  // Defensive re-validation against edge cases
  if (files.value.length < 2) {
    ElMessage.warning('至少需要 2 个文件')
    return
  }
  if (!allValid.value) {
    const failed = files.value.find(f => f.status !== 'ok')
    ElMessage.error(failed ? failed.error : '存在校验失败的文件')
    return
  }
  const commonFields = orderedCommonFields.value
  if (commonFields.length === 0) {
    ElMessage.error('未能计算出公共字段，无法合并')
    return
  }

  // Build merged array: concat in upload order, trim each record to common fields
  const merged = []
  for (const file of files.value) {
    for (const record of file.records) {
      const trimmed = {}
      for (const key of commonFields) {
        trimmed[key] = record[key]
      }
      merged.push(trimmed)
    }
  }

  // Filename: merged_{N}files_{YYYYMMDD_HHmmss}.json (local time, zero-padded)
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const stamp =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
    `_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  const filename = `merged_${files.value.length}files_${stamp}.json`

  // Browser download
  const blob = new Blob([JSON.stringify(merged, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)

  ElMessage.success(
    `已合并 ${files.value.length} 个文件，共 ${merged.length} 条记录`
  )
}

// ---------- Helpers ----------
function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 2 : 0)} ${units[i]}`
}
</script>

<style scoped>
.page-container {}
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0 0 8px 0;
}
.page-desc {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.upload-card,
.list-card,
.action-card {
  margin-bottom: 20px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.upload-dragger {
  width: 100%;
}
.upload-dragger :deep(.el-upload__tip) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  line-height: 1.8;
}

.stats-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.stats-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.stat-item {
  flex: 1;
  min-width: 140px;
  padding: 16px 20px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
.fields-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  border: 1px dashed #dcdfe6;
}
.fields-label {
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
  padding-top: 2px;
}
.fields-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.field-tag {
  margin: 0;
}

.action-row {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>

<style>
/* unscoped so it reaches the tooltip popper rendered in body */
.merge-error-tooltip {
  max-width: 420px;
  word-break: break-all;
  line-height: 1.6;
}
</style>
