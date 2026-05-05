<template>
  <div class="file-selector">
    <el-radio-group v-model="mode" size="small" class="mode-toggle" :disabled="disabled">
      <el-radio-button value="existing">选择已有文件</el-radio-button>
      <el-radio-button value="upload">上传新文件</el-radio-button>
    </el-radio-group>

    <div v-if="mode === 'existing'" class="existing-section">
      <div v-if="fetchFn && expectedStage" class="stage-filter">
        <span class="filter-label">{{ showAllFiles ? '显示所有阶段文件' : `仅显示上一阶段（${expectedStageLabel}）文件` }}</span>
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
        accept=".json"
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
          <div class="el-upload__tip">仅支持 .json 格式文件</div>
        </template>
      </el-upload>
      <el-form label-width="90px" size="small" class="upload-form">
        <el-form-item label="文本字段名">
          <el-input
            v-model="uploadForm.text_field"
            placeholder="JSON中包含文本内容的字段名"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="uploadLoading"
            :disabled="uploadFileList.length === 0 || disabled"
            @click="submitUpload"
          >
            上传
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadManagedFile } from '../api'
import { getStageLabel } from '../utils/stageLabels'

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

const expectedStageLabel = computed(() => {
  return props.expectedStage ? getStageLabel(props.expectedStage) : ''
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

watch(() => props.modelValue, (val) => {
  if (val && mode.value === 'upload') {
    // Don't switch — user just uploaded, keep upload view briefly
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
  formData.append('text_field', uploadForm.value.text_field)
  formData.append('files', uploadFileList.value[0].raw)

  try {
    const res = await uploadManagedFile(formData)
    const uploaded = res.uploaded || []
    const errors = res.errors || []

    if (uploaded.length > 0) {
      ElMessage.success('文件上传成功')
      emit('update:modelValue', uploaded[0].id)
      emit('upload-success', uploaded[0])
      mode.value = 'existing'
      uploadFileList.value = []
      uploadForm.value = { text_field: 'text' }
      // Reload file list after upload
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
</style>
