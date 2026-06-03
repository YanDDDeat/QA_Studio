<template>
  <div class="page-container">
    <!-- 新建任务弹窗 -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建单COT生成"
      width="720px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="120px">
        <el-form-item label="运行名称" prop="run_name">
          <el-input v-model="createForm.run_name" placeholder="例如：论文A专业CoT构建" />
        </el-form-item>
        <el-form-item label="输入方式">
          <el-radio-group v-model="inputMode" @change="handleInputModeChange">
            <el-radio-button value="existing">选择已有文件</el-radio-button>
            <el-radio-button value="upload">上传新文件</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="inputMode === 'existing'" label="系统 JSON 文件" prop="source_file_id">
          <el-select
            v-model="createForm.source_file_id"
            placeholder="优先选择系统已有单篇或多篇 JSON 文件"
            filterable
            style="width: 100%"
            @change="handleSourceFileChange"
          >
            <el-option
              v-for="f in sourceFiles"
              :key="f.id"
              :label="f.filename"
              :value="f.id"
            >
              <span>{{ f.filename }}</span>
              <span style="float: right; color: #999; font-size: 12px">
                {{ f.file_type || 'json' }}<template v-if="f.text_field">，字段: {{ f.text_field }}</template>
              </span>
            </el-option>
          </el-select>
          <div class="upload-tip">顶层必须是非空数组，每个元素为一篇文献对象，支持单篇或多篇。</div>
        </el-form-item>
        <el-form-item v-else label="上传 JSON 文件" prop="file">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".json,application/json"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-button type="primary" plain>
              <el-icon><Upload /></el-icon>
              选择单篇或多篇 JSON
            </el-button>
            <template #tip>
              <div class="upload-tip">上传入口为辅助入口；建议先通过文件管理上传并在此选择已有文件。</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="正文字段名" prop="text_field">
          <el-select
            v-if="fieldOptions.length"
            v-model="createForm.text_field"
            placeholder="选择正文所在字段"
            filterable
            allow-create
            style="width: 100%"
          >
            <el-option v-for="field in fieldOptions" :key="field" :label="field" :value="field" />
          </el-select>
          <el-input v-else v-model="createForm.text_field" placeholder="默认 text，可手动改为 content / paper_text 等" />
        </el-form-item>
        <el-form-item label="提示词模板版本" prop="prompt_template_id">
          <el-select
            v-model="createForm.prompt_template_id"
            placeholder="选择提示词模板版本"
            style="width: 100%"
          >
            <el-option-group label="系统模板">
              <el-option
                v-for="t in systemPromptTemplates"
                :key="t.template_id"
                :label="t.name + (t.is_default ? '（我的默认）' : '')"
                :value="t.template_id"
              />
            </el-option-group>
            <el-option-group label="我的模板" v-if="userPromptTemplates.length">
              <el-option
                v-for="t in userPromptTemplates"
                :key="t.template_id"
                :label="t.name + (t.is_default ? '（我的默认）' : '')"
                :value="t.template_id"
              />
            </el-option-group>
          </el-select>
          <div class="upload-tip">新建任务将使用该模板包的全部提示词。若不选，默认使用您的默认模板或系统默认模板。</div>
        </el-form-item>
        <el-form-item label="LLM 配置" prop="llm_config_id">
          <el-select v-model="createForm.llm_config_id" placeholder="选择 LLM 配置" filterable style="width: 100%" @change="handleConfigChange">
            <el-option
              v-for="c in llmConfigs"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            >
              <span>{{ c.name }}</span>
              <span style="float: right; color: #999; font-size: 12px">
                {{ c.default_model }}
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="模型" prop="model">
          <el-select v-model="createForm.model" placeholder="选择模型" filterable allow-create style="width: 100%">
            <el-option
              v-for="m in selectedConfigModels"
              :key="m"
              :label="m"
              :value="m"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="生成规则">
          <el-alert
            title="JSON 数组中每篇文献生成 1 条样本；CoT 类型由 Step 3 模型在 10 类枚举中自动判定，若无可构建类型将停止并展示原因。多篇文献时逐篇串行处理。"
            type="info"
            :closable="false"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="createLoading" @click="handleCreate">
          <el-icon><Promotion /></el-icon>
          一键开始 Pipeline
        </el-button>
      </template>
    </el-dialog>

    <!-- 任务列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>单COT生成</span>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            新建流水线2
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="runs" stripe style="width: 100%">
        <el-table-column prop="run_name" label="名称" min-width="200">
          <template #default="{ row }">
            <div class="run-name">{{ row.run_name || row.run_id }}</div>
            <div class="run-id">{{ row.run_id }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="source_filename" label="源文件" min-width="150" />
        <el-table-column prop="input_count" label="文献数" width="90">
          <template #default="{ row }">
            {{ row.input_count ?? 1 }}
          </template>
        </el-table-column>
        <el-table-column label="模型判定 CoT 类型" min-width="180">
          <template #default="{ row }">
            {{ row.recommended_cot_type?.display_name || row.target_cot_type?.display_name || '待判定' }}
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="130" />
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress_percentage || 0"
              :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : ''"
              :stroke-width="16"
            />
            <span style="font-size: 12px; color: #666">
              {{ row.completed_steps || 0 }}/{{ row.total_steps || 0 }} 步
              <span v-if="row.skipped_steps">，跳过 {{ row.skipped_steps }}</span>
            </span>
            <span v-if="row.input_count > 1 && (row.success_count || row.failed_count)" style="font-size: 12px; color: #666; display: block; margin-top: 2px">
              成功 {{ row.success_count || 0 }}/{{ row.input_count }} 篇
              <span v-if="row.failed_count" style="color: #f56c6c">，失败 {{ row.failed_count }} 篇</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="sample_count" label="样本数" width="90" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="goToDetail(row.run_id)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handlePageSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Promotion, Upload } from '@element-plus/icons-vue'
import {
  getFileFields,
  getManagedFileContent,
  getLLMConfigs,
  getProfessionalCotSourceFiles,
  listProfessionalCotRuns,
  startProfessionalCotRun,
  listProfessionalCotPromptTemplates,
} from '../../api'

const router = useRouter()

const loading = ref(false)
const runs = ref([])
const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
})
const llmConfigs = ref([])
const sourceFiles = ref([])
const fieldOptions = ref([])
const inputMode = ref('existing')

// 提示词模板数据
const promptTemplatesData = ref(null)
const systemPromptTemplates = computed(() =>
  (promptTemplatesData.value?.templates || []).filter(t => t.is_system)
)
const userPromptTemplates = computed(() =>
  (promptTemplatesData.value?.templates || []).filter(t => !t.is_system)
)

async function fetchRuns() {
  loading.value = true
  try {
    const res = await listProfessionalCotRuns({
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    })
    if (Array.isArray(res)) {
      const offset = (pagination.value.page - 1) * pagination.value.pageSize
      runs.value = res.slice(offset, offset + pagination.value.pageSize)
      pagination.value.total = res.length
      return
    }
    runs.value = res.items || []
    pagination.value.total = res.total || 0
    pagination.value.page = res.page || pagination.value.page
    pagination.value.pageSize = res.page_size || pagination.value.pageSize
  } catch (err) {
    ElMessage.error('获取流水线2列表失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(page) {
  pagination.value.page = page
  fetchRuns()
}

function handlePageSizeChange(pageSize) {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchRuns()
}

const createDialogVisible = ref(false)
const createLoading = ref(false)
const createFormRef = ref(null)
const uploadRef = ref(null)
const selectedFile = ref(null)

const createForm = ref({
  run_name: '',
  source_file_id: null,
  text_field: 'text',
  llm_config_id: null,
  model: '',
  file: null,
  prompt_template_id: '',
})

const createRules = {
  run_name: [{ required: true, message: '请输入运行名称', trigger: 'blur' }],
  source_file_id: [],
  file: [],
  text_field: [{ required: true, message: '请选择或输入正文字段名', trigger: 'change' }],
  llm_config_id: [{ required: true, message: '请选择 LLM 配置', trigger: 'change' }],
  model: [{ required: true, message: '请选择模型', trigger: 'change' }],
}

const selectedConfig = computed(() => llmConfigs.value.find(c => c.id === createForm.value.llm_config_id))
const selectedConfigModels = computed(() => selectedConfig.value?.models || [])

function handleConfigChange(id) {
  const cfg = llmConfigs.value.find(c => c.id === id)
  createForm.value.model = cfg?.default_model || ''
}

function handleFileChange(uploadFile) {
  selectedFile.value = uploadFile.raw
  createForm.value.file = uploadFile.raw
  createFormRef.value?.validateField('file')
}

function handleFileRemove() {
  selectedFile.value = null
  createForm.value.file = null
}

function handleInputModeChange() {
  createForm.value.source_file_id = null
  createForm.value.file = null
  selectedFile.value = null
  fieldOptions.value = []
  createForm.value.text_field = 'text'
  uploadRef.value?.clearFiles?.()
}

async function handleSourceFileChange(fileId) {
  fieldOptions.value = []
  createForm.value.text_field = 'text'
  if (!fileId) return
  try {
    const res = await getFileFields(fileId)
    fieldOptions.value = res.fields || []
    if (fieldOptions.value.includes('text')) {
      createForm.value.text_field = 'text'
    } else {
      const selected = sourceFiles.value.find(f => f.id === fileId)
      createForm.value.text_field = selected?.text_field || fieldOptions.value[0] || 'text'
    }
  } catch (err) {
    ElMessage.warning('读取文件字段失败，可手动输入正文字段名')
  }
}

async function openCreateDialog() {
  createForm.value = {
    run_name: '',
    source_file_id: null,
    text_field: 'text',
    llm_config_id: null,
    model: '',
    file: null,
    prompt_template_id: '',
  }
  inputMode.value = 'existing'
  fieldOptions.value = []
  selectedFile.value = null
  uploadRef.value?.clearFiles?.()
  createDialogVisible.value = true
  await fetchDialogData()
}

async function fetchDialogData() {
  try {
    const [configs, files, templates] = await Promise.all([
      getLLMConfigs(),
      getProfessionalCotSourceFiles({ sort: 'time_desc' }),
      listProfessionalCotPromptTemplates(),
    ])
    llmConfigs.value = configs
    sourceFiles.value = (files.items || files || []).filter(f => (f.file_type || '').toLowerCase() === 'json')
    promptTemplatesData.value = templates
    // 默认选择用户默认模板或系统默认模板
    const effectiveDefault = templates.effective_default_template_id || templates.system_template_id
    if (effectiveDefault) {
      createForm.value.prompt_template_id = effectiveDefault
    }
  } catch (err) {
    ElMessage.error('获取配置数据失败')
  }
}

async function handleCreate() {
  const formRef = createFormRef.value
  if (!formRef) return
  try {
    await formRef.validate()
  } catch {
    return
  }
  if (inputMode.value === 'existing' && !createForm.value.source_file_id) {
    ElMessage.error('请选择系统已有 JSON 文件')
    return
  }
  if (inputMode.value === 'upload' && !selectedFile.value) {
    ElMessage.error('请选择要上传的 JSON 文件')
    return
  }

  // Check if JSON elements have 'source' field; warn user if missing
  try {
    let jsonItems = null
    if (inputMode.value === 'upload' && selectedFile.value) {
      const text = await selectedFile.value.text()
      const parsed = JSON.parse(text)
      if (Array.isArray(parsed)) jsonItems = parsed
    } else if (inputMode.value === 'existing' && createForm.value.source_file_id) {
      const res = await getManagedFileContent(createForm.value.source_file_id, { page: 1, page_size: 10 })
      if (res?.data?.length) jsonItems = res.data
    }

    if (jsonItems && jsonItems.length > 0) {
      const hasSource = jsonItems.some(item => item.source != null && item.source !== '')
      if (!hasSource) {
        try {
          await ElMessageBox.confirm(
            '当前 JSON 文件中元素没有 source 字段，最终产出样本将无法追溯文献来源。是否继续？',
            '缺少来源字段',
            { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
          )
        } catch {
          return
        }
      }
    }
  } catch {
    // JSON parse or preview fetch failed — skip check, proceed as-is
  }

  createLoading.value = true
  try {
    const formData = new FormData()
    if (inputMode.value === 'existing') {
      formData.append('source_file_id', createForm.value.source_file_id)
    } else {
      formData.append('file', selectedFile.value)
    }
    formData.append('text_field', createForm.value.text_field)
    formData.append('llm_config_id', createForm.value.llm_config_id)
    formData.append('model', createForm.value.model)
    formData.append('run_name', createForm.value.run_name)
    if (createForm.value.prompt_template_id) {
      formData.append('prompt_template_id', createForm.value.prompt_template_id)
    }

    const res = await startProfessionalCotRun(formData)
    const inputCountInfo = res.input_count ? `，包含 ${res.input_count} 篇文献` : ''
    ElMessage.success(`单COT生成已启动 (Run: ${res.run_id})${inputCountInfo}`)
    createDialogVisible.value = false
    pagination.value.page = 1
    await fetchRuns()
    router.push(`/professional-cot-runs/${res.run_id}`)
  } catch (err) {
    const detail = err.response?.data?.detail || '创建失败'
    ElMessage.error(detail)
  } finally {
    createLoading.value = false
  }
}

function goToDetail(id) {
  router.push(`/professional-cot-runs/${id}`)
}

function statusTagType(s) {
  const map = { running: 'primary', completed: 'success', failed: 'danger', pending: 'info', paused: 'warning', skipped: 'info' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { running: '运行中', completed: '已完成', failed: '失败', pending: '待执行', paused: '已暂停', skipped: '已跳过' }
  return map[s] || s
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

onMounted(async () => {
  await fetchRuns()
})
</script>

<style scoped>
.page-container {
  max-width: 1200px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.cot-type-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.run-name {
  font-weight: 600;
  color: #303133;
}
.run-id {
  margin-top: 2px;
  color: #909399;
  font-size: 12px;
  font-family: Consolas, Monaco, monospace;
}
.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
