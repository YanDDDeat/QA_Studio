<template>
  <div class="gzip-test-page">
    <h2>Gzip 压缩上传测试</h2>
    <p style="color: #909399; margin-bottom: 16px;">
      文件在浏览器内用 Gzip 压缩后再上传。
    </p>

    <el-card style="max-width: 600px;">
      <div style="margin-bottom: 16px;">
        <el-upload
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          accept=".json"
        >
          <el-button type="primary" :icon="Upload">选择 JSON 文件</el-button>
        </el-upload>
      </div>

      <div v-if="selectedFile" style="margin-bottom: 16px;">
        <el-tag type="info" closable @close="handleFileRemove">
          {{ selectedFile.name }} ({{ formatSize(selectedFile.size) }})
        </el-tag>
      </div>

      <div style="margin-bottom: 16px;">
        <el-input
          v-model="textField"
          placeholder="text_field 字段名"
          style="width: 200px; margin-right: 12px;"
        />
        <el-button type="success" :loading="loading" @click="upload">
          压缩并上传
        </el-button>
      </div>

      <div v-if="result" style="margin-top: 16px;">
        <el-alert
          v-if="result.uploaded && result.uploaded.length"
          type="success"
          :closable="false"
        >
          <template #title>
            上传成功 — 防火墙已无法识别内容
          </template>
          <div v-for="item in result.uploaded" :key="item.filename" style="margin-top: 8px;">
            <p>文件名: <code>{{ item.filename }}</code></p>
            <p>压缩后: {{ item.compressed_bytes }} bytes → 原始: {{ item.decompressed_bytes }} bytes</p>
            <p>压缩比: {{ item.ratio }}，记录数: {{ item.record_count }}</p>
            <p v-if="item.warning" style="color: #e6a23c;">⚠ {{ item.warning }}</p>
          </div>
        </el-alert>

        <el-alert
          v-if="result.errors && result.errors.length"
          type="error"
          :closable="false"
        >
          <template #title>上传失败</template>
          <div v-for="err in result.errors" :key="err.filename">
            <p><code>{{ err.filename }}</code>: {{ err.error }}</p>
          </div>
        </el-alert>

        <div v-if="result.error" style="color: #f56c6c;">
          {{ result.error }}
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import api from '../utils/api'

const selectedFile = ref(null)
const textField = ref('text')
const loading = ref(false)
const result = ref(null)

function handleFileChange(uploadFile) {
  selectedFile.value = uploadFile.raw
  result.value = null
}

function handleFileRemove() {
  selectedFile.value = null
  result.value = null
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function upload() {
  if (!selectedFile.value) return
  loading.value = true
  result.value = null

  try {
    // Gzip 压缩文件流
    const stream = selectedFile.value.stream().pipeThrough(new CompressionStream('gzip'))
    const compressedBlob = await new Response(stream).blob()

    const formData = new FormData()
    formData.append('text_field', textField.value)
    formData.append('files', compressedBlob, selectedFile.value.name.replace(/\.json$/i, '.json.gz'))

    const res = await api.post('/file-manage/gzip-upload-test', formData)
    result.value = res
  } catch (err) {
    result.value = { error: err.response?.data?.detail || err.message }
  } finally {
    loading.value = false
  }
}
</script>
