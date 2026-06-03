<template>
  <div class="cot-hcot-text-preprocess">
    <el-alert type="info" :closable="false" style="margin-bottom: 16px">
      <template #title>
        <span>为标注流水线准备输入数据。「多 MD 合并」将多篇论文的Markdown格式合并为流水线可用的 JSON 数组；「大文献（博士论文）拆分及预处理」对上传的博士论文进行章节拆分和清洗，生成更适合 LLM 处理的数据。</span>
      </template>
    </el-alert>
    <el-card class="md-merge-card">
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-title">多 MD 合并 JSON</span>
            <p class="card-desc">将多篇的文献的MD格式合并为一个json文件，进行批量COT合成</p>
          </div>
          <el-tag type="info" effect="plain">仅前端生成下载</el-tag>
        </div>
      </template>

      <div class="merge-layout">
        <div class="upload-panel">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :multiple="true"
            accept=".md,.markdown,text/markdown,text/plain"
            :show-file-list="false"
            :on-change="handleMdFileChange"
            drag
            class="md-upload"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽 MD 文件到此处，或<em>点击选择文件</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持一次选择多个 .md 文件；输出字段固定为
                <el-tag size="small" type="success" effect="plain">source</el-tag>
                <el-tag size="small" type="success" effect="plain">text</el-tag>
              </div>
            </template>
          </el-upload>

          <div v-if="mdFiles.length" class="file-actions">
            <el-button type="primary" :icon="Download" :disabled="!canDownload" @click="handleDownload">
              下载 JSON
            </el-button>
            <el-button type="success" :icon="FolderAdd" :disabled="!canDownload" :loading="savingToDataCenter" @click="handleSaveToDataCenter">
              保存到数据中心
            </el-button>
            <el-button :icon="RefreshLeft" @click="handleClearAll">清空</el-button>
          </div>
        </div>

        <div class="summary-panel">
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-label">文件数</span>
              <span class="stat-value">{{ mdFiles.length }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">已读取</span>
              <span class="stat-value">{{ readyCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">总字符</span>
              <span class="stat-value">{{ totalChars }}</span>
            </div>
          </div>

          <el-alert
            v-if="!mdFiles.length"
            title="请先选择需要合并的 Markdown 文件"
            type="info"
            :closable="false"
            show-icon
          />
          <el-alert
            v-else-if="hasPending"
            title="文件读取中，请稍候..."
            type="info"
            :closable="false"
            show-icon
          />
          <el-alert
            v-else-if="hasError"
            title="部分文件读取失败，请移除后再下载"
            type="error"
            :closable="false"
            show-icon
          />
          <el-alert
            v-else
            title="JSON 已生成，可在下方预览或直接下载"
            type="success"
            :closable="false"
            show-icon
          />
        </div>
      </div>

      <el-table v-if="mdFiles.length" :data="mdFiles" stripe class="file-table" row-key="id">
        <el-table-column type="index" label="#" width="56" />
        <el-table-column prop="name" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="字符数" width="110" align="right">
          <template #default="{ row }">{{ row.text.length }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'pending'" type="info" size="small">读取中</el-tag>
            <el-tag v-else-if="row.status === 'ok'" type="success" size="small">已读取</el-tag>
            <el-tooltip v-else :content="row.error" placement="top">
              <el-tag type="danger" size="small">失败</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ $index }">
            <el-button type="danger" link size="small" :icon="Delete" @click="handleRemoveFile($index)">
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="mdFiles.length" class="preview-block">
        <div class="preview-header">
          <span class="card-title">JSON 预览</span>
          <span class="preview-tip">{{ outputFilename }}</span>
        </div>
        <el-input
          :model-value="jsonPreview"
          type="textarea"
          :rows="12"
          readonly
          resize="vertical"
          class="json-preview"
        />
      </div>
    </el-card>

    <TextPreprocess />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, RefreshLeft, UploadFilled, FolderAdd } from '@element-plus/icons-vue'
import { saveJsonContent } from '../../api'
import TextPreprocess from '../TextPreprocess.vue'

const uploadRef = ref(null)
const mdFiles = ref([])
const savingToDataCenter = ref(false)
let fileIdCounter = 0

const readyFiles = computed(() => mdFiles.value.filter(file => file.status === 'ok'))
const readyCount = computed(() => readyFiles.value.length)
const hasPending = computed(() => mdFiles.value.some(file => file.status === 'pending'))
const hasError = computed(() => mdFiles.value.some(file => file.status === 'error'))
const canDownload = computed(() => mdFiles.value.length > 0 && !hasPending.value && !hasError.value)
const totalChars = computed(() => readyFiles.value.reduce((sum, file) => sum + file.text.length, 0))
const mergedRecords = computed(() => readyFiles.value.map(file => ({
  source: file.name,
  text: file.text,
})))
const jsonPreview = computed(() => {
  if (!mdFiles.value.length) return ''
  if (hasPending.value) return '文件读取中...'
  if (hasError.value) return '存在读取失败的文件，请移除失败文件后预览。'
  return JSON.stringify(mergedRecords.value, null, 2)
})
const outputFilename = computed(() => `md_merge_${buildTimestamp()}.json`)

async function handleMdFileChange(uploadFile) {
  const raw = uploadFile.raw
  const name = uploadFile.name || raw?.name || ''

  if (!raw) {
    ElMessage.error(`文件 "${name}" 读取失败`)
    return
  }

  const lowerName = name.toLowerCase()
  if (!lowerName.endsWith('.md') && !lowerName.endsWith('.markdown')) {
    ElMessage.error(`文件 "${name}" 不是 .md 文件，已忽略`)
    return
  }

  const entryId = ++fileIdCounter
  mdFiles.value.push({
    id: entryId,
    name,
    size: raw.size,
    text: '',
    status: 'pending',
    error: '',
  })

  try {
    const text = await raw.text()
    const current = mdFiles.value.find(file => file.id === entryId)
    if (!current) return
    current.text = text
    current.status = 'ok'
  } catch (err) {
    const current = mdFiles.value.find(file => file.id === entryId)
    if (current) {
      current.status = 'error'
      current.error = err.message || '读取文件失败'
    }
    ElMessage.error(`文件 "${name}" 读取失败`)
  }
}

function handleRemoveFile(index) {
  mdFiles.value.splice(index, 1)
}

async function handleClearAll() {
  try {
    await ElMessageBox.confirm('确定清空所有已选择的 MD 文件吗？', '清空确认', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  mdFiles.value = []
  uploadRef.value?.clearFiles?.()
}

function handleDownload() {
  if (!canDownload.value) {
    ElMessage.warning('请等待文件读取完成，并移除读取失败的文件')
    return
  }

  const filename = outputFilename.value
  const blob = new Blob([JSON.stringify(mergedRecords.value, null, 2)], {
    type: 'application/json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  ElMessage.success(`已生成 ${readyFiles.value.length} 个文件的 JSON`)
}

async function handleSaveToDataCenter() {
  if (!canDownload.value) {
    ElMessage.warning('请等待文件读取完成，并移除读取失败的文件')
    return
  }
  savingToDataCenter.value = true
  try {
    const res = await saveJsonContent({
      filename: outputFilename.value,
      content: JSON.stringify(mergedRecords.value, null, 2),
      text_field: 'text',
    })
    const warning = res.warning
    if (warning) {
      ElMessage.warning({ message: `已保存到数据中心（文件ID: ${res.id}），但 ${warning}`, duration: 5000 })
    } else {
      ElMessage.success(`已保存到数据中心（文件ID: ${res.id}），可直接在流水线中使用`)
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '保存到数据中心失败')
  } finally {
    savingToDataCenter.value = false
  }
}

function buildTimestamp() {
  const now = new Date()
  const pad = value => String(value).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index > 0 ? 2 : 0)} ${units[index]}`
}
</script>

<style scoped>
.cot-hcot-text-preprocess {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.md-merge-card {
  margin-bottom: 4px;
}
.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.card-desc {
  margin: 6px 0 0;
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}
.merge-layout {
  display: grid;
  grid-template-columns: minmax(320px, 1.2fr) minmax(280px, 1fr);
  gap: 20px;
  align-items: stretch;
}
.upload-panel,
.summary-panel {
  min-width: 0;
}
.md-upload {
  width: 100%;
}
.md-upload :deep(.el-upload__tip) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  line-height: 1.8;
}
.file-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}
.stat-item {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
  background: #fafafa;
}
.stat-label {
  display: block;
  color: #909399;
  font-size: 12px;
}
.stat-value {
  display: block;
  margin-top: 6px;
  color: #303133;
  font-size: 22px;
  font-weight: 600;
}
.file-table {
  margin-top: 18px;
}
.preview-block {
  margin-top: 18px;
}
.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.preview-tip {
  color: #909399;
  font-size: 13px;
}
.json-preview :deep(.el-textarea__inner) {
  font-family: Consolas, Monaco, 'Courier New', monospace;
  line-height: 1.5;
}
@media (max-width: 960px) {
  .merge-layout {
    grid-template-columns: 1fr;
  }
  .stats-grid {
    grid-template-columns: repeat(3, minmax(80px, 1fr));
  }
}
</style>
