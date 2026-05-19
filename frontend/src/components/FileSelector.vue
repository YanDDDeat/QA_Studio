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
        :limit="1"
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
          <div class="el-upload__tip">支持 .json 和 .md 格式文件</div>
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
              <el-radio value="section">按章节切分</el-radio>
              <el-radio value="paragraph">按段落切分</el-radio>
            </el-radio-group>
          </el-form-item>

          <template v-if="mdForm.split_mode === 'section'">
            <el-form-item label="标题层级">
              <span style="margin-right: 4px">最小</span>
              <el-input-number v-model="mdForm.min_title_level" :min="1" :max="6" size="small" style="width: 80px" />
              <span style="margin: 0 8px">至 最大</span>
              <el-input-number v-model="mdForm.max_title_level" :min="1" :max="6" size="small" style="width: 80px" />
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
          :disabled="uploadFileList.length === 0 || disabled"
          @click="submitUpload"
        >
          上传
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadManagedFile, uploadMdFile } from '../api'

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  fileOptions: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  fetchFn: { type: Function, default: null },
  expectedStage: { type: String, default: null },
})

const emit = defineEmits(['update:modelValue', 'upload-success'])

const mode = ref('existing')
const uploadFileList = ref([])
const uploadForm = ref({ text_field: 'text' })
const uploadLoading = ref(false)
const showAllFiles = ref(false)
const internalFileOptions = ref([])
const fetchLoading = ref(false)

const mdForm = ref({
  source_type: '图书',
  split_mode: 'full',
  min_title_level: 1,
  max_title_level: 6,
  min_chars: 100,
})

const currentFileIsMd = computed(() => {
  if (uploadFileList.value.length === 0) return false
  const name = uploadFileList.value[0]?.name || ''
  return name.toLowerCase().endsWith('.md')
})

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

function handleFileChange(file, fileList) {
  uploadFileList.value = fileList
}

function handleFileRemove(file, fileList) {
  uploadFileList.value = fileList
}

function handleExceed() {
  ElMessage.warning('只能上传一个文件，请先移除已选文件')
}

async function submitUpload() {
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }

  uploadLoading.value = true
  const formData = new FormData()
  formData.append('files', uploadFileList.value[0].raw)

  try {
    let res
    if (currentFileIsMd.value) {
      formData.append('source_type', mdForm.value.source_type)
      formData.append('split_mode', mdForm.value.split_mode)
      formData.append('min_title_level', mdForm.value.min_title_level)
      formData.append('max_title_level', mdForm.value.max_title_level)
      formData.append('min_chars', mdForm.value.min_chars)
      res = await uploadMdFile(formData)
    } else {
      formData.append('text_field', uploadForm.value.text_field)
      res = await uploadManagedFile(formData)
    }

    const uploaded = res.uploaded || []
    const errors = res.errors || []

    if (uploaded.length > 0) {
      ElMessage.success('文件上传成功')
      if (uploaded[0].warning) {
        ElMessage.warning({ message: uploaded[0].warning, duration: 8000 })
      }
      emit('update:modelValue', uploaded[0].id)
      emit('upload-success', uploaded[0])
      mode.value = 'existing'
      uploadFileList.value = []
      uploadForm.value = { text_field: 'text' }
      mdForm.value = { source_type: '图书', split_mode: 'full', min_title_level: 1, max_title_level: 6, min_chars: 100 }
      if (props.fetchFn) {
        showAllFiles.value = true
        await loadFiles()
      }
    }
    if (errors.length > 0) {
      const msg = errors.map(e => `${e.filename}: ${e.error}`).join('\n')
      ElMessage.error(`上传失败: ${msg}`)
    }
  } catch (err) {
    const detail = err.response?.data?.detail || '上传失败'
    ElMessage.error(detail)
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

.upload-actions {
  margin-top: 4px;
}
</style>
