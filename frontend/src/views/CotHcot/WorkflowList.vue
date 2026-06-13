<template>
  <div class="page-container">
    <!-- 新建任务弹窗 -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建多COT生成"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="120px">
        <el-form-item label="流水线名称" prop="pipeline_name">
          <el-input v-model="createForm.pipeline_name" placeholder="例如：论文A的H-CoT标注" />
        </el-form-item>
        <el-form-item label="标注模式" prop="pipeline_mode">
          <el-radio-group v-model="createForm.pipeline_mode">
            <el-radio value="hcot">H-CoT（博士论文，层级结构）</el-radio>
            <el-radio value="cot">CoT（研究论文，独立问题）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="源文件" prop="source_file_id">
          <el-select
            v-model="createForm.source_file_id"
            placeholder="选择源文件"
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
                {{ f.file_type || 'json' }}
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="内容字段名" prop="content_field">
          <el-input
            v-model="createForm.content_field"
            placeholder="例如：text、content、originContent、paper_text"
          />
          <div class="form-tip">
            用于从 JSON 每条记录中读取正文内容；留空时使用 input/originContent 兼容逻辑
          </div>
        </el-form-item>
        <el-form-item label="LLM 配置" prop="llm_config_id">
          <el-select v-model="createForm.llm_config_id" placeholder="选择 LLM 配置" filterable style="width: 100%">
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
        <el-form-item label="提示词模板">
          <el-select v-model="createForm.prompt_template_id" placeholder="使用默认模板" filterable clearable style="width: 100%">
            <el-option-group label="系统模板">
              <el-option
                v-for="t in promptTemplates.filter(t => t.is_system)"
                :key="t.template_id"
                :label="t.name + (t.is_default ? '（默认）' : '')"
                :value="t.template_id"
              />
            </el-option-group>
            <el-option-group label="我的模板" v-if="promptTemplates.filter(t => !t.is_system).length">
              <el-option
                v-for="t in promptTemplates.filter(t => !t.is_system)"
                :key="t.template_id"
                :label="t.name + (t.is_default ? '（默认）' : '')"
                :value="t.template_id"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">创建并启动首步</el-button>
        <el-button type="success" :loading="autoLoading" @click="handleCreateAuto">创建并一键运行</el-button>
      </template>
    </el-dialog>

    <!-- 任务列表 -->
    <el-alert type="info" :closable="false" style="margin-bottom: 16px">
      <template #title>
        <span>CoT/H-CoT 标注：从论文自动生成思维链（Chain-of-Thought）训练数据。H-CoT 适用于博士论文，生成层级式推理树；CoT 适用于研究论文，生成独立问答。上传论文 → 自动分段 → 逐步生成事实卡、问题、推理链 → 质检导出。</span>
      </template>
    </el-alert>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>多COT标注任务</span>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            新建流水线
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="pagedWorkflows" stripe style="width: 100%">
        <el-table-column prop="pipeline_name" label="名称" min-width="180" />
        <el-table-column prop="pipeline_mode" label="模式" width="100">
          <template #default="{ row }">
            <el-tag :type="row.pipeline_mode === 'hcot' ? 'warning' : 'success'" size="small">
              {{ row.pipeline_mode === 'hcot' ? 'H-CoT' : 'CoT' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="源文件" min-width="140">
          <template #default="{ row }">
            {{ row.source_file?.filename || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="120" />
        <el-table-column label="进度" width="140">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.completed_steps / row.total_steps) * 100)"
              :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : ''"
              :stroke-width="16"
            />
            <span style="font-size: 12px; color: #666">
              {{ row.completed_steps }}/{{ row.total_steps }} 步
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="goToDetail(row.id)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div style="margin-top: 16px; display: flex; justify-content: center">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="workflows.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  listCothcotWorkflows,
  startCothcotPipeline,
  autoRunCothcotPipeline,
  getCothcotSourceFiles,
  getLLMConfigs,
  listHcotPromptTemplates,
} from '../../api'

const router = useRouter()

// --- 列表数据 ---
const loading = ref(false)
const workflows = ref([])

// --- 分页 ---
const currentPage = ref(1)
const pageSize = ref(10)

const pagedWorkflows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return workflows.value.slice(start, end)
})

async function fetchWorkflows() {
  loading.value = true
  try {
    const res = await listCothcotWorkflows()
    workflows.value = res
  } catch (err) {
    ElMessage.error('获取流水线列表失败')
  } finally {
    loading.value = false
  }
}

// --- 新建弹窗 ---
const createDialogVisible = ref(false)
const createLoading = ref(false)
const autoLoading = ref(false)
const createFormRef = ref(null)
const sourceFiles = ref([])
const llmConfigs = ref([])
const promptTemplates = ref([])

const createForm = ref({
  pipeline_name: '',
  pipeline_mode: 'hcot',
  source_file_id: null,
  content_field: 'text',
  llm_config_id: null,
  prompt_template_id: null,
})

const createRules = {
  pipeline_name: [{ required: true, message: '请输入流水线名称', trigger: 'blur' }],
  pipeline_mode: [{ required: true, message: '请选择标注模式', trigger: 'change' }],
  source_file_id: [{ required: true, message: '请选择源文件', trigger: 'change' }],
  llm_config_id: [{ required: true, message: '请选择 LLM 配置', trigger: 'change' }],
}

function openCreateDialog() {
  createForm.value = {
    pipeline_name: '',
    pipeline_mode: 'hcot',
    source_file_id: null,
    content_field: 'text',
    llm_config_id: null,
    prompt_template_id: null,
  }
  createDialogVisible.value = true
  fetchDialogData()
}

function handleSourceFileChange(fileId) {
  const selectedFile = sourceFiles.value.find(f => f.id === fileId)
  createForm.value.content_field = selectedFile?.text_field || 'text'
}

async function fetchDialogData() {
  try {
    sourceFiles.value = await getCothcotSourceFiles()
  } catch (err) {
    ElMessage.error('获取文件列表失败')
  }
  try {
    llmConfigs.value = await getLLMConfigs()
  } catch (err) {
    ElMessage.error('获取 LLM 配置失败')
  }
  try {
    const res = await listHcotPromptTemplates()
    promptTemplates.value = res.templates || []
  } catch (err) {
    // 提示词模板可选，不阻断流程
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

  createLoading.value = true
  try {
    const res = await startCothcotPipeline(createForm.value)
    ElMessage.success(`流水线已创建并启动 (ID: ${res.parent_task_id})`)
    createDialogVisible.value = false
    await fetchWorkflows()
    router.push(`/cot-hcot-workflows/${res.parent_task_id}`)
  } catch (err) {
    const detail = err.response?.data?.detail || '创建失败'
    ElMessage.error(detail)
  } finally {
    createLoading.value = false
  }
}

async function handleCreateAuto() {
  const formRef = createFormRef.value
  if (!formRef) return
  try {
    await formRef.validate()
  } catch {
    return
  }

  autoLoading.value = true
  try {
    const res = await autoRunCothcotPipeline(createForm.value)
    ElMessage.success(`一键运行已启动 (ID: ${res.parent_task_id})，共 ${res.total_steps} 步`)
    createDialogVisible.value = false
    await fetchWorkflows()
    router.push(`/cot-hcot-workflows/${res.parent_task_id}`)
  } catch (err) {
    const detail = err.response?.data?.detail || '一键运行创建失败'
    ElMessage.error(detail)
  } finally {
    autoLoading.value = false
  }
}

// --- 辅助函数 ---
function goToDetail(id) {
  router.push(`/cot-hcot-workflows/${id}`)
}

function statusTagType(s) {
  const map = { running: 'primary', completed: 'success', failed: 'danger', pending: 'info', paused: 'warning' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { running: '运行中', completed: '已完成', failed: '失败', pending: '待执行', paused: '已暂停' }
  return map[s] || s
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

onMounted(() => {
  fetchWorkflows()
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
.form-tip {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}
</style>