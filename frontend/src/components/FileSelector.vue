<template>
  <div class="file-selector">
    <el-radio-group v-model="mode" size="small" class="mode-toggle" :disabled="disabled">
      <el-radio-button value="existing">选择已有文件</el-radio-button>
      <el-radio-button value="upload">上传新文件</el-radio-button>
    </el-radio-group>

    <div v-if="mode === 'existing'" class="existing-section">
      <div v-if="fetchFn" class="stage-filter">
        <span class="filter-label">是否展示全部文件</span>
        <el-switch v-model="showAllFiles" size="small" :disabled="disabled" />
      </div>
      <el-select
        :model-value="modelValue"
        placeholder="请选择文件"
        class="full-select"
        filterable
        :disabled="disabled"
        @update:model-value="$emit('update:modelValue', $event)"
      >
        <el-option
          v-for="f in internalFileOptions"
          :key="f.id"
          :label="f.filename"
          :value="f.id"
        >
          <span>{{ f.filename }}</span>
          <span style="float: right; color: #909399; font-size: 13px">
            <template v-if="f.text_field">字段: {{ f.text_field }}</template>
            <template v-if="f.record_count">{{ f.record_count }} 条记录</template>
          </span>
        </el-option>
      </el-select>
    </div>

    <div v-if="mode === 'upload'" class="upload-section">
      <el-upload
        :auto-upload="false"
        :limit="100"
        accept=".json,.md"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :on-exceed="handleExceed"
        :file-list="uploadFileList"
        drag
        class="inline-upload"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 .json 和 .md 格式文件；MD 可批量上传，JSON 仍为单文件上传</div>
        </template>
      </el-upload>

      <!-- JSON upload options -->
      <el-form v-if="!currentFileIsMd" label-width="90px" size="small" class="upload-form">
        <el-form-item label="文本字段名">
          <el-input v-model="uploadForm.text_field" placeholder="JSON中包含文本内容的字段名" />
        </el-form-item>
      </el-form>

      <!-- MD conversion options -->
      <div v-if="currentFileIsMd" class="md-options">
        <el-form label-width="90px" size="small">
          <el-form-item label="来源类型">
            <el-select v-model="mdForm.source_type" style="width: 100%">
              <el-option label="文献" value="文献" />
              <el-option label="图书" value="图书" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>

          <el-form-item label="转换策略">
            <el-radio-group v-model="mdForm.split_mode">
              <el-radio value="full">整篇不切分</el-radio>
              <el-radio value="section">按Markdown层级</el-radio>
              <el-radio value="paragraph">按段落切分</el-radio>
              <el-radio v-if="mdForm.split_mode === 'numbering' || numberingModeAvailable" value="numbering">按编号层级</el-radio>
            </el-radio-group>
          </el-form-item>

          <template v-if="mdForm.split_mode === 'section'">
            <el-form-item label="标题层级">
              <div class="heading-preview">
                <div v-if="headingPreviewLoading" class="heading-status">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <span>正在解析标题层级...</span>
                </div>
                <el-alert
                  v-else-if="headingPreviewError"
                  :title="headingPreviewError"
                  type="error"
                  show-icon
                  :closable="false"
                />
                <el-alert
                  v-else-if="headingLevelOptions.length === 0"
                  title="未识别到 Markdown 标题，不能按标题切分。可选择整篇不切分或按段落切分。"
                  type="warning"
                  show-icon
                  :closable="false"
                />
                <div v-else class="heading-level-panel">
                  <div class="heading-hint">选择一个实际存在的标题层级作为切分边界：</div>
                  <el-radio-group v-model="mdForm.heading_level" class="heading-level-group">
                    <el-radio-button
                      v-for="item in headingLevelOptions"
                      :key="item.level"
                      :value="item.level"
                    >
                      {{ formatHeadingLevel(item.level) }}（{{ item.count }}个）
                    </el-radio-button>
                  </el-radio-group>
                </div>
              </div>
            </el-form-item>
          </template>

          <template v-if="mdForm.split_mode === 'numbering'">
            <el-form-item label="编号深度">
              <div class="heading-preview">
                <div v-if="headingPreviewLoading" class="heading-status">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <span>正在解析编号层级...</span>
                </div>
                <el-alert
                  v-else-if="numberingDepthOptions.length === 0"
                  title="未检测到编号模式，不能按编号层级切分。可选择整篇不切分或按段落切分。"
                  type="warning"
                  show-icon
                  :closable="false"
                />
                <div v-else class="heading-level-panel">
                  <div class="heading-hint">选择编号深度作为切分边界：边界层级以上的内容合为一块，其下所有更细层级的内容也包含在内。</div>
                  <el-radio-group v-model="mdForm.numbering_depth" class="heading-level-group">
                    <el-radio-button
                      v-for="item in numberingDepthOptions"
                      :key="item.depth"
                      :value="item.depth"
                    >
                      {{ item.label }}（{{ item.count }}个）
                    </el-radio-button>
                  </el-radio-group>
                </div>
              </div>
            </el-form-item>
          </template>

          <template v-if="mdForm.split_mode === 'paragraph'">
            <el-form-item label="最小字符数">
              <el-input-number v-model="mdForm.min_chars" :min="10" :max="10000" size="small" style="width: 160px" />
            </el-form-item>
          </template>
        </el-form>
      </div>

      <div class="upload-actions">
        <el-button
          type="primary"
          :loading="uploadLoading"
          :disabled="uploadDisabled"
          @click="submitUpload"
        >
          {{ currentFileIsMd ? `上传 ${mdUploadFiles.length} 个 MD 文件` : '上传' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, UploadFilled } from '@element-plus/icons-vue'
import { previewMdHeadings, uploadManagedFile, uploadMdFile } from '../api'

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  fileOptions: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  fetchFn: { type: Function, default: null },
  expectedStage: { type: String, default: null },
  initialShowAll: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'upload-success'])

const mode = ref('existing')
const uploadFileList = ref([])
const uploadForm = ref({ text_field: 'text' })
const uploadLoading = ref(false)
const showAllFiles = ref(props.initialShowAll)
const internalFileOptions = ref([])
const fetchLoading = ref(false)
const headingPreviewLoading = ref(false)
const headingPreviewError = ref('')
const headingPreview = ref({
  headings: [],
  available_levels: [],
  level_counts: {},
  numbering_depth_counts: {},
  numbering_available_depths: [],
  all_headings_same_md_level: false,
})
let headingPreviewRequestId = 0

const mdForm = ref({
  source_type: '图书',
  split_mode: 'full',
  heading_level: null,
  numbering_depth: 1,
  min_title_level: 1,
  max_title_level: 6,
  min_chars: 100,
})

const currentFileIsMd = computed(() => {
  if (uploadFileList.value.length === 0) return false
  const name = uploadFileList.value[0]?.name || ''
  return name.toLowerCase().endsWith('.md')
})

const mdUploadFiles = computed(() => (
  uploadFileList.value.filter(file => (file.name || '').toLowerCase().endsWith('.md'))
))

const headingLevelOptions = computed(() => {
  const counts = headingPreview.value.level_counts || {}
  return (headingPreview.value.available_levels || []).map(level => ({
    level,
    count: counts[String(level)] || 0,
  }))
})

const numberingDepthOptions = computed(() => {
  const counts = headingPreview.value.numbering_depth_counts || {}
  return (headingPreview.value.numbering_available_depths || [])
    .filter(d => d > 0)  // 排除 depth=0
    .map(d => ({
      depth: d,
      count: counts[String(d)] || 0,
      label: numberingDepthLabel(d),
    }))
})

function numberingDepthLabel(depth) {
  const labels = { 1: '章级', 2: '节级', 3: '小节级', 4: '更细' }
  return labels[depth] || `${depth}级`
}

const numberingModeAvailable = computed(() => {
  return headingPreview.value.all_headings_same_md_level === true
    && numberingDepthOptions.value.length > 0
})

const splitBlocked = computed(() => {
  if (!currentFileIsMd.value) return false
  if (headingPreviewLoading.value) return true
  if (mdForm.value.split_mode === 'section' && !mdForm.value.heading_level) return true
  if (mdForm.value.split_mode === 'numbering' && !mdForm.value.numbering_depth) return true
  return false
})

const uploadDisabled = computed(() => (
  uploadFileList.value.length === 0 || props.disabled || splitBlocked.value
))

function formatHeadingLevel(level) {
  const labels = ['一级标题', '二级标题', '三级标题', '四级标题', '五级标题', '六级标题']
  return labels[level - 1] || `${level}级标题`
}

onMounted(() => {
  if (props.fetchFn) {
    loadFiles()
  }
})

watch(() => props.fileOptions, (val) => {
  if (!props.fetchFn) {
    internalFileOptions.value = val || []
  }
}, { immediate: true })

watch(showAllFiles, () => {
  if (props.fetchFn) {
    loadFiles()
  }
})

async function loadFiles() {
  if (!props.fetchFn) return
  fetchLoading.value = true
  try {
    const res = await props.fetchFn(showAllFiles.value)
    internalFileOptions.value = Array.isArray(res) ? res : (res.items || [])
  } catch (err) {
    console.error('FileSelector fetch error:', err)
    internalFileOptions.value = []
  } finally {
    fetchLoading.value = false
  }
}

function resetHeadingPreview() {
  headingPreviewRequestId += 1
  headingPreviewLoading.value = false
  headingPreviewError.value = ''
  headingPreview.value = {
    headings: [],
    available_levels: [],
    level_counts: {},
    numbering_depth_counts: {},
    numbering_available_depths: [],
    all_headings_same_md_level: false,
  }
  mdForm.value.heading_level = null
  mdForm.value.numbering_depth = 1
}

async function loadHeadingPreview(file) {
  resetHeadingPreview()
  const rawFile = file?.raw
  if (!rawFile || !file.name?.toLowerCase().endsWith('.md')) return

  const requestId = headingPreviewRequestId
  headingPreviewLoading.value = true
  const formData = new FormData()
  formData.append('file', rawFile)

  try {
    const res = await previewMdHeadings(formData)
    if (requestId !== headingPreviewRequestId) return
    headingPreview.value = {
      headings: res.headings || [],
      available_levels: res.available_levels || [],
      level_counts: res.level_counts || {},
      numbering_depth_counts: res.numbering_depth_counts || {},
      numbering_available_depths: res.numbering_available_depths || [],
      all_headings_same_md_level: res.all_headings_same_md_level || false,
    }
    if (headingPreview.value.available_levels.length === 1) {
      mdForm.value.heading_level = headingPreview.value.available_levels[0]
    }
    // 检测到编号模式 → 询问用户是否按编号切分
    if (headingPreview.value.all_headings_same_md_level && numberingDepthOptions.value.length > 0) {
      const depthSummary = numberingDepthOptions.value
        .map(o => `${o.label}${o.count}个`)
        .join('、')
      const mdSymbol = '#'.repeat(headingLevelOptions.value[0]?.level || 1)
      const totalCount = headingLevelOptions.value[0]?.count || 0
      const message = [
        `该文件有 ${totalCount} 个标题，全部都是 <b>${mdSymbol}</b>，无法按 Markdown 层级区分章节。`,
        `但标题文本包含编号：<b>${depthSummary}</b>`,
        '',
        '👉 <b>按编号切分</b> → 用编号（1/1.1/1.2.3）判断层级，每章/节完整一块',
        '👉 <b>按Markdown层级</b> → 用 #/##/### 判断层级，但本文件全都是 #，会切成碎片',
      ].join('<br>')
      ElMessageBox.confirm(
        message,
        '检测到编号层级',
        {
          confirmButtonText: '按编号切分',
          cancelButtonText: '仍按Markdown层级',
          type: 'info',
          dangerouslyUseHTMLString: true,
        }
      ).then(() => {
        mdForm.value.split_mode = 'numbering'
        // 默认选最浅的编号深度（通常是章级）
        if (numberingDepthOptions.value.length > 0) {
          mdForm.value.numbering_depth = numberingDepthOptions.value[0].depth
        }
      }).catch(() => {
        // 用户选择仍按标题层级，不做任何改动
      })
    }
  } catch (err) {
    if (requestId !== headingPreviewRequestId) return
    headingPreviewError.value = err.response?.data?.detail || '标题解析失败，请检查文件编码或稍后重试'
  } finally {
    if (requestId === headingPreviewRequestId) {
      headingPreviewLoading.value = false
    }
  }
}

function handleFileChange(file, fileList) {
  const filename = file.name || ''
  const lowerName = filename.toLowerCase()

  if (lowerName.endsWith('.md')) {
    uploadFileList.value = fileList.filter(item => (item.name || '').toLowerCase().endsWith('.md'))
  } else if (lowerName.endsWith('.json')) {
    if (fileList.length > 1) {
      ElMessage.warning('JSON 只能上传一个文件，已保留最后选择的 JSON 文件')
    }
    uploadFileList.value = [file]
  } else {
    ElMessage.warning('仅支持 .json 和 .md 格式文件')
    uploadFileList.value = fileList.filter(item => {
      const name = (item.name || '').toLowerCase()
      return name.endsWith('.md') || name.endsWith('.json')
    })
  }

  if (uploadFileList.value.length === 0) {
    resetHeadingPreview()
    return
  }
  if (currentFileIsMd.value) {
    const previewFile = uploadFileList.value[uploadFileList.value.length - 1]
    loadHeadingPreview(previewFile)
  } else {
    resetHeadingPreview()
  }
}

function handleFileRemove(file, fileList) {
  uploadFileList.value = fileList
  if (currentFileIsMd.value && uploadFileList.value.length > 0) {
    loadHeadingPreview(uploadFileList.value[uploadFileList.value.length - 1])
  } else {
    resetHeadingPreview()
  }
}

function handleExceed(files) {
  const hasMd = Array.from(files || []).some(file => (file.name || '').toLowerCase().endsWith('.md'))
  if (hasMd || currentFileIsMd.value) {
    ElMessage.warning('一次最多选择 100 个 MD 文件，请分批上传')
    return
  }
  ElMessage.warning('JSON 只能上传一个文件，请先移除已选文件')
}

async function submitUpload() {
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }

  if (splitBlocked.value) {
    ElMessage.warning(headingPreviewLoading.value ? '标题层级仍在解析，请稍候' : '请选择标题层级或编号深度')
    return
  }

  uploadLoading.value = true
  const formData = new FormData()

  try {
    let res
    if (currentFileIsMd.value) {
      mdUploadFiles.value.forEach(file => {
        if (file.raw) formData.append('files', file.raw)
      })
      formData.append('source_type', mdForm.value.source_type)
      formData.append('split_mode', mdForm.value.split_mode)
      if (mdForm.value.split_mode === 'section' && mdForm.value.heading_level) {
        formData.append('heading_level', mdForm.value.heading_level)
      }
      if (mdForm.value.split_mode === 'numbering') {
        formData.append('depth', mdForm.value.numbering_depth)
      }
      formData.append('min_title_level', mdForm.value.min_title_level)
      formData.append('max_title_level', mdForm.value.max_title_level)
      formData.append('min_chars', mdForm.value.min_chars)
      res = await uploadMdFile(formData)
    } else {
      formData.append('files', uploadFileList.value[0].raw)
      formData.append('text_field', uploadForm.value.text_field)
      res = await uploadManagedFile(formData)
    }

    const uploaded = res.uploaded || []
    const errors = res.errors || []

    if (uploaded.length > 0) {
      const successMsg = errors.length > 0
        ? `已成功上传 ${uploaded.length} 个文件，${errors.length} 个失败`
        : `成功上传 ${uploaded.length} 个文件`
      ElMessage.success(successMsg)
      uploaded
        .filter(item => item.warning)
        .forEach(item => ElMessage.warning({ message: `${item.filename || '文件'}: ${item.warning}`, duration: 8000 }))
      emit('update:modelValue', uploaded[0].id)
      emit('upload-success', uploaded[0])
      mode.value = 'existing'
      uploadFileList.value = []
      uploadForm.value = { text_field: 'text' }
      mdForm.value = { source_type: '图书', split_mode: 'full', heading_level: null, numbering_depth: 1, min_title_level: 1, max_title_level: 6, min_chars: 100 }
      resetHeadingPreview()
      if (props.fetchFn) {
        showAllFiles.value = true
        await loadFiles()
      }
    }
    if (errors.length > 0) {
      const msg = errors.map(e => `${e.filename}: ${e.error}`).join('\n')
      ElMessage.error({ message: `上传失败 ${errors.length} 个文件:\n${msg}`, duration: 8000 })
    }
  } catch (err) {
    const detail = err.response?.data?.detail
    const status = err.response?.status
    const msg = detail
      ? `上传失败: ${detail}`
      : status
        ? `上传失败 (HTTP ${status})${err.message ? ' ' + err.message : ''}`
        : `上传失败: ${err.message || '未知错误'}`
    ElMessage.error(msg)
  } finally {
    uploadLoading.value = false
  }
}

defineExpose({ refresh: loadFiles })
</script>

<style scoped>
.file-selector {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mode-toggle {
  width: 100%;
}
.mode-toggle .el-radio-button {
  flex: 1;
}
.mode-toggle :deep(.el-radio-button__inner) {
  width: 100%;
}

.stage-filter {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 4px;
}
.filter-label {
  font-size: 12px;
  color: #909399;
}

.full-select {
  width: 100%;
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inline-upload {
  width: 100%;
}
.inline-upload :deep(.el-upload-dragger) {
  padding: 16px;
}
.inline-upload :deep(.el-upload) {
  width: 100%;
}

.upload-form {
  margin-top: 4px;
}

.md-options {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.md-options :deep(.el-form-item) {
  margin-bottom: 8px;
}
.md-options :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.heading-preview {
  width: 100%;
}
.heading-status {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #606266;
  font-size: 13px;
}
.heading-level-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.heading-hint {
  color: #606266;
  font-size: 12px;
  line-height: 1.4;
}
.heading-level-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.heading-level-group :deep(.el-radio-button__inner) {
  border-radius: 4px;
}

.upload-actions {
  margin-top: 4px;
}
</style>
