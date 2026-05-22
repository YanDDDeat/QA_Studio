<template>
  <div class="page-container">
    <h2>配置中心</h2>

    <!-- Top-level tabs: LLM配置 / 提示词配置 -->
    <el-tabs v-model="mainTab" type="border-card">
      <!-- LLM 配置 Tab -->
      <el-tab-pane label="LLM 配置" name="llm">
        <div v-loading="llmLoading">
          <!-- Built-in templates -->
          <div v-if="globalConfigs.length > 0" class="template-section">
            <h3 class="section-title">内置模板</h3>
            <div class="template-cards">
              <el-card
                v-for="cfg in globalConfigs"
                :key="cfg.id"
                shadow="hover"
                class="template-card"
              >
                <div class="template-name">{{ cfg.name }}</div>
                <div class="template-info">
                  <div class="info-row">
                    <span class="info-label">Endpoint:</span>
                    <span class="info-value">{{ cfg.base_url }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">默认模型:</span>
                    <span class="info-value">{{ cfg.default_model }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">支持模型:</span>
                    <span class="info-value">{{ (cfg.models || []).join(', ') }}</span>
                  </div>
                </div>
                <div class="template-actions">
                  <el-button type="primary" size="small" @click="openUseTemplateDialog(cfg)">
                    使用此模板
                  </el-button>
                </div>
              </el-card>
            </div>
          </div>

          <!-- Config list table -->
          <div class="config-list-section">
            <div class="list-header">
              <h3 class="section-title">配置列表</h3>
              <el-button type="primary" @click="openCreateDialog()">新建空白配置</el-button>
            </div>

            <el-table :data="llmConfigs" stripe style="width: 100%">
              <el-table-column prop="name" label="配置名" min-width="140" />
              <el-table-column prop="base_url" label="Base URL" min-width="200" show-overflow-tooltip />
              <el-table-column label="模型数" width="80" align="center">
                <template #default="{ row }">
                  {{ (row.models || []).length }}
                </template>
              </el-table-column>
              <el-table-column prop="default_model" label="默认模型" min-width="140" />
              <el-table-column label="归属" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.is_global" type="warning" size="small">全局</el-tag>
                  <el-tag v-else type="success" size="small">我的</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="220" align="center">
                <template #default="{ row }">
                  <el-button
                    v-if="!row.is_global || isAdmin"
                    type="text"
                    size="small"
                    @click="openEditDialog(row)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    v-if="!row.is_global || isAdmin"
                    type="text"
                    size="small"
                    style="color: #f56c6c"
                    @click="handleDeleteLLMConfig(row)"
                  >
                    删除
                  </el-button>
                  <el-button
                    type="text"
                    size="small"
                    style="color: #409eff"
                    @click="handleTestLLMConfig(row)"
                    :loading="testLoadingMap[row.id]"
                  >
                    测试连接
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-empty v-if="llmConfigs.length === 0 && !llmLoading" description="暂无LLM配置" />
          </div>
        </div>

        <!-- Use template dialog -->
        <el-dialog
          v-model="useTemplateVisible"
          title="使用此模板"
          width="500px"
          destroy-on-close
        >
          <el-form :model="useTemplateForm" label-width="100px">
            <el-form-item label="配置名">
              <el-input v-model="useTemplateForm.name" placeholder="给配置取一个自定义名称" />
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="useTemplateForm.base_url" disabled />
            </el-form-item>
            <el-form-item label="默认模型">
              <el-input v-model="useTemplateForm.default_model" disabled />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="useTemplateForm.api_key" placeholder="请输入API Key" show-password />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="useTemplateVisible = false">取消</el-button>
            <el-button type="primary" :loading="dialogLoading" @click="handleUseTemplate">创建</el-button>
          </template>
        </el-dialog>

        <!-- Create / Edit config dialog -->
        <el-dialog
          v-model="configDialogVisible"
          :title="isEditing ? '编辑配置' : '新建配置'"
          width="560px"
          destroy-on-close
        >
          <el-form :model="configForm" label-width="100px">
            <el-form-item label="配置名">
              <el-input v-model="configForm.name" placeholder="请输入配置名" />
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="configForm.base_url" placeholder="请输入OpenAI兼容的Endpoint URL" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="configForm.api_key" placeholder="请输入API Key" show-password />
            </el-form-item>
            <el-form-item label="代理地址">
              <el-input v-model="configForm.proxy" placeholder="可选，如 http://host:port（无需代理请留空）" />
            </el-form-item>
            <el-form-item label="模型列表">
              <div class="model-list-editor">
                <div class="model-list-inputs">
                  <div v-for="(m, idx) in configForm.models" :key="idx" class="model-item-row">
                    <el-input v-model="configForm.models[idx]" placeholder="模型名" style="width: 240px" />
                    <el-button type="danger" text size="small" @click="removeModelItem(idx)">
                      删除
                    </el-button>
                  </div>
                </div>
                <el-button type="primary" size="small" @click="addModelItem">添加模型</el-button>
              </div>
            </el-form-item>
            <el-form-item label="默认模型">
              <el-select v-model="configForm.default_model" placeholder="请选择默认模型" style="width: 100%">
                <el-option
                  v-for="m in configForm.models"
                  :key="m"
                  :label="m"
                  :value="m"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="isAdmin" label="全局共享">
              <el-switch v-model="configForm.is_global" active-text="全局" inactive-text="私有" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="configDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="dialogLoading" @click="handleSaveLLMConfig">
              {{ isEditing ? '保存' : '创建' }}
            </el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- 提示词配置 Tab -->
      <el-tab-pane label="提示词配置" name="prompt">
        <el-tabs v-model="activeStage" type="border-card" @tab-change="handlePromptTabChange">
          <el-tab-pane
            v-for="stage in stages"
            :key="stage.value"
            :label="stage.label"
            :name="stage.value"
          >
            <div class="stage-config" v-loading="paneLoading">
              <!-- LLM config selector (two-level) -->
              <div class="config-row">
                <span class="config-label">LLM配置 / 模型</span>
                <div class="llm-select-row">
                  <el-select
                    v-model="promptLLMConfigId"
                    placeholder="选择LLM配置"
                    style="width: 260px"
                    filterable
                    @change="handlePromptLLMConfigChange"
                  >
                    <el-option
                      v-for="cfg in llmConfigs"
                      :key="cfg.id"
                      :label="cfg.name + (cfg.is_global ? ' (全局)' : ' (我的)')"
                      :value="cfg.id"
                    />
                  </el-select>
                  <el-select
                    v-model="promptModel"
                    placeholder="选择模型"
                    style="width: 200px; margin-left: 12px"
                    :disabled="!promptLLMConfigId"
                  >
                    <el-option
                      v-for="m in promptModelOptions"
                      :key="m"
                      :label="m"
                      :value="m"
                    />
                  </el-select>
                </div>
              </div>

              <!-- Prompt editor -->
              <div class="config-row prompt-editor">
                <span class="config-label">Prompt内容</span>
                <el-input
                  v-model="editableContent"
                  type="textarea"
                  :rows="8"
                  placeholder="请输入Prompt内容"
                  resize="vertical"
                />
              </div>

              <!-- Save button -->
              <div class="config-row actions">
                <el-button
                  type="primary"
                  :loading="saveLoading"
                  :disabled="!contentChanged"
                  @click="handleSavePrompt"
                >
                  保存为新版本
                </el-button>
                <el-tag v-if="contentChanged" type="info" size="small">
                  内容已修改，保存将创建新版本 (v{{ nextVersion }})
                </el-tag>
                <el-tag v-if="!contentChanged && hasLatestPrompt" type="success" size="small">
                  当前内容未修改
                </el-tag>
              </div>

              <!-- Version history -->
              <div class="version-history" v-if="versionHistory.length > 0">
                <el-divider content-position="left">版本历史</el-divider>
                <el-timeline>
                  <el-timeline-item
                    v-for="ver in versionHistory"
                    :key="ver.id"
                    :timestamp="formatTime(ver.created_at)"
                    placement="top"
                  >
                    <el-card shadow="hover" class="version-card">
                      <div class="version-header">
                        <el-tag :type="ver.is_default ? 'warning' : (ver.version === latestVersion ? 'primary' : 'info')" size="small">
                          {{ ver.name || `v${ver.version}` }}
                        </el-tag>
                        <el-tag v-if="ver.is_default" type="warning" size="small">默认</el-tag>
                        <span v-if="ver.model" class="version-model">{{ ver.model }}</span>
                        <span v-if="ver.llm_config_name" class="version-llm">{{ ver.llm_config_name }}</span>
                        <el-button
                          v-if="ver.version !== latestVersion && !ver.is_default"
                          type="text"
                          size="small"
                          @click="handleViewVersion(ver)"
                        >
                          查看内容
                        </el-button>
                        <el-button
                          v-if="!ver.is_default"
                          type="text"
                          size="small"
                          style="color: #f56c6c"
                          @click="handleDeleteVersion(ver)"
                        >
                          删除
                        </el-button>
                        <el-tag v-if="ver.version === latestVersion" type="success" size="small">
                          当前版本
                        </el-tag>
                      </div>
                      <div v-if="viewingVersionId === ver.id" class="version-content-preview">
                        <pre class="prompt-preview">{{ ver.content }}</pre>
                        <el-button type="text" size="small" @click="viewingVersionId = null">关闭</el-button>
                      </div>
                    </el-card>
                  </el-timeline-item>
                </el-timeline>
              </div>

              <el-empty v-if="versionHistory.length === 0 && !paneLoading" description="暂无Prompt配置，请输入内容并保存" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>

      <!-- 系统设置 Tab (仅管理员可见) -->
      <el-tab-pane label="系统设置" name="system" v-if="isAdmin">
        <el-card>
          <template #header>
            <span>运行参数</span>
          </template>
          <el-form label-width="160px" style="max-width: 500px;">
            <el-form-item label="LLM 并发线程数">
              <el-input-number
                v-model="systemConfig.llm_thread_pool_size"
                :min="1"
                :max="100"
                :step="1"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="systemConfigSaving" @click="handleSaveSystemConfig">保存</el-button>
            </el-form-item>
            <el-alert
              title="修改后需重启后端服务才能生效"
              type="info"
              :closable="false"
              show-icon
              style="margin-top: 10px;"
            />
          </el-form>
        </el-card>

        <el-divider />
        <h4>运行中任务</h4>
        <el-table
          :data="runningTasks"
          style="width: 100%; margin-top: 10px;"
          v-loading="runningTasksLoading"
          empty-text="暂无运行中的任务"
        >
          <el-table-column prop="username" label="用户" width="100" />
          <el-table-column prop="stage" label="阶段" width="140" />
          <el-table-column prop="model" label="模型" width="160" />
          <el-table-column label="进度" width="180">
            <template #default="{ row }">
              <el-progress
                :percentage="row.progress_total ? Math.round(row.progress_current / row.progress_total * 100) : 0"
                :format="() => `${row.progress_current}/${row.progress_total}`"
              />
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getStages,
  getPromptConfigs,
  getModelConfigs,
  createPromptConfig,
  deletePromptConfig,
  updateModelConfig,
  getLLMConfigs,
  createLLMConfig,
  updateLLMConfig,
  deleteLLMConfig,
  testLLMConfig,
  getSystemConfig,
  updateSystemConfig,
  getRunningTasks,
} from '../api'

// ----- Admin detection -----
const isAdmin = computed(() => localStorage.getItem('username') === 'admin')

// ----- Main tab state -----
const mainTab = ref('llm')

// ----- LLM Config state -----
const llmConfigs = ref([])
const globalConfigs = computed(() => llmConfigs.value.filter(c => c.is_global))
const llmLoading = ref(false)
const testLoadingMap = ref({})
const dialogLoading = ref(false)

// ----- System config state -----
const systemConfig = ref({ llm_thread_pool_size: 20 })
const systemConfigSaving = ref(false)

// ----- Running tasks state (admin) -----
const runningTasks = ref([])
const runningTasksLoading = ref(false)
let runningTasksTimer = null

// ----- Use template dialog -----
const useTemplateVisible = ref(false)
const useTemplateForm = ref({
  name: '',
  base_url: '',
  default_model: '',
  api_key: '',
  template_id: null,
})

// ----- Create/Edit config dialog -----
const configDialogVisible = ref(false)
const isEditing = ref(false)
const editingConfigId = ref(null)
const configForm = ref({
  name: '',
  base_url: '',
  api_key: '',
  proxy: '',
  models: [],
  default_model: '',
  is_global: false,
})

// ----- Prompt tab state -----
const stages = ref([])
const activeStage = ref('question_generate')
const modelOptions = ref([])

// Per-stage data
const stageDataMap = ref({})
const paneLoading = ref(false)
const saveLoading = ref(false)
const viewingVersionId = ref(null)

// Prompt LLM config (two-level dropdown in prompt tab)
const promptLLMConfigs = ref([])
const promptLLMConfigId = ref(null)
const promptModel = ref('')
const promptModelOptions = computed(() => {
  const cfg = llmConfigs.value.find(c => c.id === promptLLMConfigId.value)
  return cfg ? (cfg.models || []) : []
})

// Current stage computed accessors
const currentStageData = computed(() => stageDataMap.value[activeStage.value] || {})
const versionHistory = computed(() => currentStageData.value.versions || [])
const latestVersion = computed(() => {
  const versions = versionHistory.value
  return versions.length > 0 ? versions[0].version : 0
})
const hasLatestPrompt = computed(() => versionHistory.value.length > 0)
const nextVersion = computed(() => latestVersion.value + 1)

const editableContent = ref('')
const currentModel = ref('')
const originalContent = ref('')

const contentChanged = computed(() => editableContent.value !== originalContent.value)

function initStageData(stageValue) {
  if (!stageDataMap.value[stageValue]) {
    stageDataMap.value[stageValue] = { versions: [] }
  }
}

// ----- LLM Config operations -----
async function fetchLLMConfigs() {
  llmLoading.value = true
  try {
    const res = await getLLMConfigs()
    llmConfigs.value = Array.isArray(res) ? res : []
  } catch (err) {
    ElMessage.error('获取LLM配置失败')
    llmConfigs.value = []
  } finally {
    llmLoading.value = false
  }
}

function openUseTemplateDialog(cfg) {
  useTemplateForm.value = {
    name: cfg.name + ' (我的)',
    base_url: cfg.base_url,
    default_model: cfg.default_model,
    api_key: '',
    template_id: cfg.id,
  }
  useTemplateVisible.value = true
}

async function handleUseTemplate() {
  if (!useTemplateForm.value.api_key.trim()) {
    ElMessage.warning('请输入API Key')
    return
  }
  if (!useTemplateForm.value.name.trim()) {
    ElMessage.warning('请输入配置名')
    return
  }

  dialogLoading.value = true
  try {
    const template = llmConfigs.value.find(c => c.id === useTemplateForm.value.template_id)
    await createLLMConfig({
      name: useTemplateForm.value.name.trim(),
      base_url: useTemplateForm.value.base_url,
      api_key: useTemplateForm.value.api_key,
      models: template ? template.models : [],
      default_model: useTemplateForm.value.default_model,
      is_global: false,
    })
    ElMessage.success('配置已创建')
    useTemplateVisible.value = false
    await fetchLLMConfigs()
  } catch (err) {
    const detail = err.response?.data?.detail || '创建配置失败'
    ElMessage.error(detail)
  } finally {
    dialogLoading.value = false
  }
}

function openCreateDialog() {
  isEditing.value = false
  editingConfigId.value = null
  configForm.value = {
    name: '',
    base_url: '',
    api_key: '',
    proxy: '',
    models: [],
    default_model: '',
    is_global: false,
  }
  configDialogVisible.value = true
}

function openEditDialog(cfg) {
  isEditing.value = true
  editingConfigId.value = cfg.id
  configForm.value = {
    name: cfg.name,
    base_url: cfg.base_url,
    api_key: cfg.api_key || '',
    proxy: cfg.proxy || '',
    models: [...(cfg.models || [])],
    default_model: cfg.default_model,
    is_global: cfg.is_global || false,
  }
  configDialogVisible.value = true
}

function addModelItem() {
  configForm.value.models.push('')
}

function removeModelItem(idx) {
  configForm.value.models.splice(idx, 1)
  // If the removed model was the default_model, clear it
  if (configForm.value.default_model === configForm.value.models[idx]) {
    configForm.value.default_model = ''
  }
}

async function handleSaveLLMConfig() {
  // Validation
  if (!configForm.value.name.trim()) {
    ElMessage.warning('请输入配置名')
    return
  }
  if (!configForm.value.base_url.trim()) {
    ElMessage.warning('请输入Base URL')
    return
  }
  if (!configForm.value.api_key.trim()) {
    ElMessage.warning('请输入API Key')
    return
  }
  const validModels = configForm.value.models.filter(m => m.trim())
  if (validModels.length === 0) {
    ElMessage.warning('请至少添加一个模型')
    return
  }
  if (!configForm.value.default_model) {
    ElMessage.warning('请选择默认模型')
    return
  }

  dialogLoading.value = true
  try {
    const payload = {
      name: configForm.value.name.trim(),
      base_url: configForm.value.base_url.trim(),
      api_key: configForm.value.api_key.trim(),
      proxy: configForm.value.proxy.trim() || null,
      models: validModels,
      default_model: configForm.value.default_model,
      is_global: configForm.value.is_global,
    }

    if (isEditing.value) {
      await updateLLMConfig(editingConfigId.value, payload)
      ElMessage.success('配置已更新')
    } else {
      await createLLMConfig(payload)
      ElMessage.success('配置已创建')
    }
    configDialogVisible.value = false
    await fetchLLMConfigs()
  } catch (err) {
    const detail = err.response?.data?.detail || (isEditing.value ? '更新配置失败' : '创建配置失败')
    ElMessage.error(detail)
  } finally {
    dialogLoading.value = false
  }
}

async function handleDeleteLLMConfig(cfg) {
  try {
    await ElMessageBox.confirm(
      `确定删除配置 "${cfg.name}" 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteLLMConfig(cfg.id)
    ElMessage.success('已删除')
    await fetchLLMConfigs()
  } catch (err) {
    const detail = err.response?.data?.detail || '删除失败'
    ElMessage.error(detail)
  }
}

async function handleTestLLMConfig(cfg) {
  testLoadingMap.value[cfg.id] = true
  try {
    const res = await testLLMConfig(cfg.id)
    if (res.ok) {
      const replyPreview = res.reply ? res.reply.substring(0, 50) : ''
      ElMessage.success(
        `连接成功! 延迟: ${res.latency_ms}ms, 回复: ${replyPreview}${res.reply && res.reply.length > 50 ? '...' : ''}`
      )
    } else {
      ElMessage.error(`连接失败: ${res.error || '未知错误'}`)
    }
  } catch (err) {
    const detail = err.response?.data?.detail || '测试连接请求失败'
    ElMessage.error(detail)
  } finally {
    testLoadingMap.value[cfg.id] = false
  }
}

// ----- Prompt tab LLM config dropdown -----
function handlePromptLLMConfigChange(configId) {
  const cfg = llmConfigs.value.find(c => c.id === configId)
  if (cfg) {
    promptModel.value = cfg.default_model || ''
  } else {
    promptModel.value = ''
  }
}

// ----- Prompt tab operations (preserved from original) -----
async function fetchStagesAndModels() {
  try {
    const stageRes = await getStages()
    stages.value = stageRes || []
    if (stages.value.length > 0) {
      activeStage.value = stages.value[0].value
    }
  } catch (err) {
    ElMessage.error('获取阶段信息失败')
  }

  try {
    const modelRes = await getModelConfigs()
    modelOptions.value = modelRes.models || []
  } catch (err) {
    ElMessage.error('获取模型列表失败')
  }
}

async function fetchPromptsForStage(stage) {
  paneLoading.value = true
  try {
    const res = await getPromptConfigs({ stage })
    const versions = (res || []).filter(p => p.stage === stage)
    initStageData(stage)
    stageDataMap.value[stage].versions = versions

    // Set editable content to latest version
    if (versions.length > 0) {
      editableContent.value = versions[0].content
      originalContent.value = versions[0].content
      // Restore LLM config and model from latest prompt
      if (versions[0].llm_config_id) {
        promptLLMConfigId.value = versions[0].llm_config_id
        promptModel.value = versions[0].model || ''
      } else {
        promptLLMConfigId.value = null
        promptModel.value = versions[0].model || ''
      }
    } else {
      editableContent.value = ''
      originalContent.value = ''
      promptLLMConfigId.value = null
      promptModel.value = ''
    }
    viewingVersionId.value = null
  } catch (err) {
    const detail = err.response?.data?.detail || '获取Prompt配置失败'
    ElMessage.error(detail)
  } finally {
    paneLoading.value = false
  }
}

function handlePromptTabChange(tab) {
  fetchPromptsForStage(tab)
}

async function handleSavePrompt() {
  if (!editableContent.value.trim()) {
    ElMessage.warning('Prompt内容不能为空')
    return
  }

  let promptName = ''
  try {
    const { value } = await ElMessageBox.prompt('请输入版本名称', '保存新版本', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：增加难度评估、优化COT格式',
    })
    promptName = value?.trim() || ''
  } catch {
    return
  }

  saveLoading.value = true
  try {
    const payload = {
      stage: activeStage.value,
      content: editableContent.value.trim(),
      model: promptModel.value || modelOptions.value[0] || null,
      name: promptName || null,
    }
    // Add llm_config_id if selected
    if (promptLLMConfigId.value) {
      payload.llm_config_id = promptLLMConfigId.value
    }
    await createPromptConfig(payload)
    ElMessage.success(`已保存为新版本: ${promptName || 'v' + nextVersion.value}`)
    await fetchPromptsForStage(activeStage.value)
  } catch (err) {
    const detail = err.response?.data?.detail || '保存Prompt失败'
    ElMessage.error(detail)
  } finally {
    saveLoading.value = false
  }
}

function handleViewVersion(ver) {
  viewingVersionId.value = ver.id
}

async function handleDeleteVersion(ver) {
  try {
    await ElMessageBox.confirm(
      `确定删除 v${ver.version} 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deletePromptConfig(ver.id)
    ElMessage.success('已删除')
    await fetchPromptsForStage(activeStage.value)
  } catch (err) {
    const detail = err.response?.data?.detail || '删除失败'
    ElMessage.error(detail)
  }
}

function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ----- System config operations -----
async function fetchSystemConfig() {
  try {
    const res = await getSystemConfig()
    systemConfig.value = res
  } catch (e) {
    console.error('获取系统配置失败', e)
  }
}

async function handleSaveSystemConfig() {
  systemConfigSaving.value = true
  try {
    await updateSystemConfig(systemConfig.value)
    ElMessage.success('配置已保存，重启后端后生效')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    systemConfigSaving.value = false
  }
}

async function fetchRunningTasks() {
  runningTasksLoading.value = true
  try {
    const res = await getRunningTasks()
    runningTasks.value = Array.isArray(res) ? res : []
  } catch (e) {
    // 非管理员静默失败
  } finally {
    runningTasksLoading.value = false
  }
}

// ----- Lifecycle -----
onMounted(async () => {
  const tasks = [fetchLLMConfigs(), fetchStagesAndModels()]
  if (isAdmin.value) {
    tasks.push(fetchSystemConfig())
  }
  await Promise.all(tasks)
  if (isAdmin.value) {
    fetchRunningTasks()
    runningTasksTimer = setInterval(fetchRunningTasks, 5000)
  }
  // Load prompts for the first stage
  if (activeStage.value) {
    await fetchPromptsForStage(activeStage.value)
  }
})

onUnmounted(() => {
  if (runningTasksTimer) {
    clearInterval(runningTasksTimer)
    runningTasksTimer = null
  }
})
</script>

<style scoped>
.page-container {}
.page-container h2 {
  margin-bottom: 16px;
}

/* LLM Config Tab styles */
.template-section {
  margin-bottom: 24px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}
.template-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.template-card {
  width: 340px;
  flex-shrink: 0;
}
.template-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}
.template-info {
  font-size: 13px;
  color: #606266;
}
.info-row {
  display: flex;
  margin-bottom: 4px;
}
.info-label {
  color: #909399;
  min-width: 80px;
}
.info-value {
  color: #303133;
}
.template-actions {
  margin-top: 12px;
  text-align: right;
}

.config-list-section {
  margin-top: 4px;
}
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

/* Model list editor */
.model-list-editor {
  width: 100%;
}
.model-list-inputs {
  margin-bottom: 8px;
}
.model-item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

/* Prompt Tab styles */
.stage-config {
  padding: 8px 0;
}
.config-row {
  margin-bottom: 16px;
}
.config-label {
  display: block;
  font-weight: 600;
  margin-bottom: 8px;
  color: #303133;
}
.llm-select-row {
  display: flex;
  align-items: center;
}
.prompt-editor .config-label {
  margin-bottom: 6px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.version-history {
  margin-top: 24px;
}
.version-card {
  max-width: 700px;
}
.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.version-model {
  font-size: 13px;
  color: #909399;
}
.version-llm {
  font-size: 13px;
  color: #409eff;
}
.version-content-preview {
  margin-top: 8px;
}
.prompt-preview {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
}
</style>