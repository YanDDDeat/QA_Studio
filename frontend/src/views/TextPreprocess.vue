<template>
  <div class="page-container">

    <el-card class="tool-card">
      <template #header>
      <span class="card-title">大文献（博士论文）拆分及预处理</span>
      <p class="card-desc">对上传的博士论文进行章节拆分和清洗，生成更适合 LLM 处理的数据。</p>
      </template>
      <div class="config-layout">
        <div class="config-form">
          <el-form :model="form" label-width="110px" :disabled="loading">
            <el-form-item label="选择文件">
              <FileSelector
                v-model="form.file_id"
                :file-options="fileOptions"
                :disabled="loading"
                @upload-success="handleUploadSuccess"
              />
            </el-form-item>

            <el-form-item v-if="form.file_id" label="文本字段">
              <el-select v-model="form.text_field" placeholder="选择文本字段" style="width: 100%" filterable>
                <el-option v-for="field in fileFields" :key="field" :label="field" :value="field" />
              </el-select>
            </el-form-item>

            <el-form-item label="最小 token">
              <el-input-number
                v-model="form.min_token_threshold"
                :min="1"
                :max="10000"
                :step="10"
                controls-position="right"
                style="width: 180px"
              />
              <span class="form-tip">低于该值会尝试向后合并，仍不足则写入过滤明细</span>
            </el-form-item>

            <el-form-item label="合并策略">
              <el-switch
                v-model="form.merge_before_classify"
                active-text="先合并后过滤"
                inactive-text="先过滤后合并"
              />
              <span class="form-tip">微chunk场景（每条约1-2字）建议开启"先合并后过滤"</span>
            </el-form-item>

            <el-form-item label="输出文件名">
              <el-input v-model="form.output_filename" placeholder="可选，系统会追加时间戳和后缀" clearable />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="loading" :disabled="!canRun" @click="handleRun">
                开始预处理
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="result-panel">
          <template v-if="result">
            <div class="stats-grid">
              <div class="stat-item">
                <span class="stat-label">原始</span>
                <span class="stat-value">{{ result.stats.original_count }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">保留</span>
                <span class="stat-value">{{ result.stats.kept_count }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">合并</span>
                <span class="stat-value">{{ result.stats.kept_by_merge_count }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">跳过</span>
                <span class="stat-value">{{ result.stats.skipped_count }}</span>
              </div>
            </div>

            <div class="file-result">
              <div class="file-row">
                <span class="file-label">预处理文件</span>
                <span class="file-name">{{ result.processed_file.filename }}</span>
                <el-button size="small" @click="goDataCenter(result.processed_file)">查看</el-button>
              </div>
              <div v-if="result.filtered_file" class="file-row">
                <span class="file-label">过滤明细</span>
                <span class="file-name">{{ result.filtered_file.filename }}</span>
                <el-button size="small" @click="goDataCenter(result.filtered_file)">查看</el-button>
              </div>
            </div>

            <el-table
              v-if="breakdownRows.length"
              :data="breakdownRows"
              size="small"
              border
              class="breakdown-table"
            >
              <el-table-column prop="reason" label="跳过原因" />
              <el-table-column prop="count" label="数量" width="100" align="right" />
            </el-table>
          </template>
          <el-empty v-else description="预处理完成后将在此显示统计结果" />
        </div>
      </div>
    </el-card>

    <PreviewCard
      v-if="form.file_id"
      title="源文件预览"
      empty-text="点击加载预览查看源文件内容"
      :filename="sourcePreview.fileName"
      :data="sourcePreview.data"
      :columns="sourcePreview.columns"
      :total="sourcePreview.total"
      :page="sourcePreview.page"
      :loading="sourcePreview.loading"
      @load="sourcePreview.load"
      @page-change="sourcePreview.changePage"
      @show-detail="sourcePreview.showDetail"
    />

    <PreviewCard
      v-if="result?.processed_file"
      title="预处理结果预览"
      empty-text="点击加载预览查看清洗后的文件内容"
      :filename="resultPreview.fileName"
      :data="resultPreview.data"
      :columns="resultPreview.columns"
      :total="resultPreview.total"
      :page="resultPreview.page"
      :loading="resultPreview.loading"
      @load="resultPreview.load"
      @page-change="resultPreview.changePage"
      @show-detail="resultPreview.showDetail"
    />

    <el-dialog v-model="detailVisible" :title="detailTitle" width="700px" :append-to-body="true">
      <template v-if="detailRecord">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item v-for="key in detailMetaFields" :key="key" :label="FIELD_LABELS[key] || key">
            {{ detailRecord[key] != null ? detailRecord[key] : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="detail-text-fields">
          <div v-for="key in detailLongTextFields" :key="key" class="text-field-block">
            <div class="field-label">{{ FIELD_LABELS[key] || key }}</div>
            <div class="field-content" v-html="renderDetailContent(detailRecord[key])"></div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref, resolveComponent, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getFileFields,
  getTextPreprocessSourceFiles,
  runTextPreprocess,
} from '../api'
import FileSelector from '../components/FileSelector.vue'
import { useSourcePreview } from '../composables/useSourcePreview'
import { categorizeFields, FIELD_LABELS } from '../utils/fieldLabels'
import { buildDefaultOutputFilename } from '../utils/stageLabels'

const router = useRouter()
const username = computed(() => localStorage.getItem('username') || 'unknown')

const loading = ref(false)
const fileOptions = ref([])
const fileFields = ref([])
const result = ref(null)

const form = ref({
  file_id: null,
  text_field: 'text',
  min_token_threshold: 300,
  output_filename: '',
  merge_before_classify: true,
})

const canRun = computed(() => (
  form.value.file_id &&
  form.value.text_field &&
  form.value.min_token_threshold
))

const breakdownRows = computed(() => {
  const breakdown = result.value?.stats?.skip_breakdown || {}
  return Object.entries(breakdown).map(([reason, count]) => ({ reason, count }))
})

const resultFileId = computed(() => result.value?.processed_file?.id || null)

const sourcePreviewRaw = useSourcePreview(computed(() => form.value.file_id), fileOptions)
const resultPreviewRaw = useSourcePreview(resultFileId, computed(() => result.value?.processed_file ? [result.value.processed_file] : []))

const sourcePreview = createPreviewModel(sourcePreviewRaw)
const resultPreview = createPreviewModel(resultPreviewRaw)

const detailVisible = ref(false)
const detailTitle = ref('记录详情')
const detailRecord = ref(null)

const detailMetaFields = computed(() => {
  if (!detailRecord.value) return []
  return categorizeFields(detailRecord.value).meta
})
const detailLongTextFields = computed(() => {
  if (!detailRecord.value) return []
  return categorizeFields(detailRecord.value).longText
})

watch(() => form.value.file_id, async (fileId) => {
  result.value = null
  if (!fileId) {
    fileFields.value = []
    form.value.text_field = 'text'
    return
  }

  const file = fileOptions.value.find(f => f.id === fileId)
  if (file && !form.value.output_filename) {
    form.value.output_filename = buildDefaultOutputFilename(file.filename, 'text_preprocess', username.value)
  }

  try {
    const res = await getFileFields(fileId)
    fileFields.value = res.fields || []
    const preferred = file?.text_field || form.value.text_field || 'text'
    form.value.text_field = fileFields.value.includes(preferred)
      ? preferred
      : (fileFields.value[0] || preferred)
  } catch {
    fileFields.value = []
  }
})

async function fetchFiles() {
  try {
    const res = await getTextPreprocessSourceFiles({ show_all: false })
    fileOptions.value = Array.isArray(res) ? res : []
  } catch (err) {
    ElMessage.error('获取文件列表失败')
    fileOptions.value = []
  }
}

async function handleUploadSuccess(file) {
  await fetchFiles()
  form.value.file_id = file.id
}

async function handleRun() {
  if (!canRun.value) return
  loading.value = true
  try {
    const res = await runTextPreprocess({
      file_id: form.value.file_id,
      text_field: form.value.text_field,
      min_token_threshold: form.value.min_token_threshold,
      output_filename: form.value.output_filename || null,
      merge_before_classify: form.value.merge_before_classify,
    })
    result.value = res
    ElMessage.success('预处理完成，已生成新文件')
    await fetchFiles()
    resultPreviewRaw.sourcePage.value = 1
    await resultPreviewRaw.loadSourcePreview()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '预处理失败')
  } finally {
    loading.value = false
  }
}

function goDataCenter(file) {
  if (file?.id) {
    router.push('/app/data-manage?file_id=' + file.id)
  }
}

function showDetail(row, title) {
  detailRecord.value = row
  detailTitle.value = title
  detailVisible.value = true
}

function renderDetailContent(text) {
  if (!text) return '-'
  if (typeof text !== 'string') {
    try { text = JSON.stringify(text) } catch { text = String(text) }
  }
  return text.replace(/\n/g, '<br>')
}

function createPreviewModel(preview) {
  return {
    get data() { return preview.sourceData.value },
    get total() { return preview.sourceTotal.value },
    get loading() { return preview.sourceLoading.value },
    get page() { return preview.sourcePage.value },
    get fileName() { return preview.sourceFileName.value },
    get columns() { return preview.sourceColumns.value },
    load: preview.loadSourcePreview,
    changePage: preview.handleSourcePageChange,
    showDetail: (row, title) => showDetail(row, title),
  }
}

onMounted(fetchFiles)

const PreviewCard = defineComponent({
  name: 'PreviewCard',
  props: {
    title: { type: String, required: true },
    filename: { type: String, default: '' },
    emptyText: { type: String, required: true },
    data: { type: Array, default: () => [] },
    columns: { type: Array, default: () => [] },
    total: { type: Number, default: 0 },
    page: { type: Number, default: 1 },
    loading: { type: Boolean, default: false },
  },
  emits: ['load', 'page-change', 'show-detail'],
  setup(props, { emit }) {
    const ElButton = resolveComponent('el-button')
    const ElCard = resolveComponent('el-card')
    const ElPagination = resolveComponent('el-pagination')
    const ElTable = resolveComponent('el-table')
    const ElTableColumn = resolveComponent('el-table-column')

    const truncate = (value) => {
      if (value == null) return ''
      const text = typeof value === 'string' ? value : JSON.stringify(value)
      return text.length > 80 ? text.slice(0, 80) + '...' : text
    }

    return () => h(
      ElCard,
      { class: 'source-preview-card' },
      {
        header: () => h('span', { class: 'card-title' }, `${props.title} - ${props.filename || ''}`),
        default: () => h('div', { class: 'results-body' }, [
          h('div', { class: 'results-toolbar' }, [
            h(ElButton, {
              type: 'primary',
              size: 'small',
              loading: props.loading,
              onClick: () => emit('load'),
            }, () => '加载预览'),
            props.total > 0
              ? h('span', { class: 'results-count' }, `共 ${props.total} 条`)
              : null,
          ]),
          props.data.length > 0
            ? h(ElTable, {
              data: props.data,
              stripe: true,
              border: true,
              size: 'small',
              style: 'width: 100%',
              loading: props.loading,
            }, () => [
              ...props.columns.map(col => h(ElTableColumn, {
                key: col.prop,
                prop: col.prop,
                label: col.label,
                width: col.width,
                minWidth: col.minWidth,
                showOverflowTooltip: true,
              }, {
                default: ({ row }) => truncate(row[col.prop]),
              })),
              h(ElTableColumn, {
                label: '操作',
                width: 80,
                fixed: 'right',
              }, {
                default: ({ row }) => h(ElButton, {
                  type: 'primary',
                  link: true,
                  size: 'small',
                  onClick: () => emit('show-detail', row, props.title + '记录详情'),
                }, () => '查看'),
              }),
            ])
            : h('div', { class: 'results-empty' }, props.emptyText),
          props.total > 0
            ? h('div', { class: 'results-pagination' }, [
              h(ElPagination, {
                currentPage: props.page,
                pageSize: 10,
                total: props.total,
                layout: 'total, prev, pager, next',
                'onUpdate:currentPage': page => emit('page-change', page),
                onCurrentChange: page => emit('page-change', page),
              }),
            ])
            : null,
        ]),
      },
    )
  },
})
</script>

<style scoped>
.tool-card {
  margin-bottom: 20px;
}
.source-preview-card {
  margin-bottom: 20px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}
.card-desc {
  margin: 6px 0 0;
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}
.config-layout {
  display: flex;
  gap: 24px;
}
.config-form {
  flex: 3;
  min-width: 0;
}
.result-panel {
  flex: 2;
  min-width: 0;
}
.form-tip {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(70px, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}
.stat-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background: #fafafa;
}
.stat-label {
  display: block;
  color: #909399;
  font-size: 12px;
}
.stat-value {
  display: block;
  margin-top: 4px;
  color: #303133;
  font-size: 20px;
  font-weight: 600;
}
.file-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.file-row {
  display: grid;
  grid-template-columns: 80px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.file-label {
  color: #606266;
  font-size: 13px;
}
.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.breakdown-table {
  width: 100%;
}
.results-body {
  padding-top: 4px;
}
.results-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.results-count {
  color: #909399;
  font-size: 13px;
}
.results-empty {
  text-align: center;
  color: #909399;
  padding: 20px;
}
.results-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
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
@media (max-width: 960px) {
  .config-layout {
    flex-direction: column;
  }
}
</style>
