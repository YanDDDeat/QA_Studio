<template>
  <div class="page-container">
    <h2 class="page-title">单COT提示词模板管理</h2>

    <!-- 顶部：模板选择 + 操作按钮 -->
    <el-card class="top-card">
      <div class="template-selector-row">
        <div class="selector-left">
          <span class="selector-label">当前模板：</span>
          <el-select
            v-model="selectedTemplateId"
            placeholder="选择模板包"
            style="width: 300px"
            @change="handleTemplateChange"
          >
            <el-option-group label="系统模板">
              <el-option
                v-for="t in systemTemplates"
                :key="t.template_id"
                :label="t.name + (t.is_default ? '（我的默认）' : '')"
                :value="t.template_id"
              />
            </el-option-group>
            <el-option-group label="我的模板" v-if="userTemplates.length">
              <el-option
                v-for="t in userTemplates"
                :key="t.template_id"
                :label="t.name + (t.is_default ? '（我的默认）' : '')"
                :value="t.template_id"
              />
            </el-option-group>
          </el-select>
        </div>
        <div class="selector-actions">
          <el-button type="primary" plain @click="handleDuplicate" :disabled="!selectedTemplateId">
            <el-icon><CopyDocument /></el-icon>
            复制为我的模板
          </el-button>
          <el-button plain @click="handleSetDefault" :disabled="!selectedTemplateId || currentManifest?.is_default">
            <el-icon><Star /></el-icon>
            设为我的默认
          </el-button>
          <el-button plain @click="handleRename" v-if="currentManifest?.can_edit" :disabled="!currentManifest?.can_edit">
            <el-icon><Edit /></el-icon>
            重命名
          </el-button>
          <el-button plain type="danger" @click="handleDelete" v-if="currentManifest?.can_delete" :disabled="!currentManifest?.can_delete">
            <el-icon><Delete /></el-icon>
            删除
          </el-button>
        </div>
      </div>
      <div class="template-meta" v-if="currentManifest">
        <el-descriptions :column="4" size="small">
          <el-descriptions-item label="模板 ID">{{ currentManifest.template_id }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ currentManifest.is_system ? '系统内置' : '用户自定义' }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ currentManifest.version }}</el-descriptions-item>
          <el-descriptions-item label="被使用次数">{{ currentManifest.used_count || 0 }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <!-- 左右布局：树 + 编辑区 -->
    <div class="main-layout" v-loading="treeLoading">
      <!-- 左侧树 -->
      <el-card class="left-panel">
        <template #header>
          <span>Prompt 结构（{{ promptCount }} 项）</span>
        </template>
        <el-tree
          ref="treeRef"
          :data="promptTree"
          :props="treeProps"
          node-key="id"
          highlight-current
          default-expand-all
          @node-click="handleNodeClick"
        >
          <template #default="{ node, data }">
            <span class="tree-node-label">
              <el-icon v-if="data.is_prompt" size="14"><Document /></el-icon>
              <el-icon v-else size="14"><Folder /></el-icon>
              {{ data.label }}
            </span>
          </template>
        </el-tree>
      </el-card>

      <!-- 右侧编辑区 -->
      <el-card class="right-panel">
        <template #header>
          <span v-if="selectedPrompt">
            {{ selectedPromptBreadcrumb }}
          </span>
          <span v-else class="empty-header">请从左侧选择一个 Prompt 查看</span>
        </template>

        <div v-if="selectedPrompt" class="prompt-editor-area">
          <!-- Prompt 信息头 -->
          <div class="prompt-meta-bar">
            <span class="prompt-key-badge">{{ selectedPrompt.prompt_key }}</span>
            <el-tag v-if="currentManifest?.is_system" type="info" size="small">系统模板 - 只读</el-tag>
            <el-tag v-else-if="currentManifest?.can_edit" type="success" size="small">可编辑</el-tag>
            <el-tag v-else type="warning" size="small">只读</el-tag>
            <span v-if="promptContentModified" class="modified-badge">
              <el-icon><Warning /></el-icon>
              内容已修改
            </span>
          </div>

          <!-- 编辑器 -->
          <div class="editor-wrapper" v-loading="promptLoading">
            <el-input
              v-if="currentManifest?.can_edit"
              v-model="editedContent"
              type="textarea"
              :rows="20"
              resize="vertical"
              placeholder="Prompt 内容"
              class="prompt-textarea"
            />
            <div v-else class="prompt-readonly-view">
              <pre>{{ promptData?.content || '' }}</pre>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="prompt-actions" v-if="currentManifest?.can_edit">
            <el-button type="primary" :loading="saveLoading" :disabled="!promptContentModified" @click="handleSavePrompt">
              <el-icon><Check /></el-icon>
              保存
            </el-button>
            <el-button plain @click="handleRestoreDefault" :loading="restoreLoading">
              <el-icon><RefreshLeft /></el-icon>
              恢复该项默认
            </el-button>
          </div>

          <!-- 变量说明 -->
          <el-alert
            v-if="variableHint"
            type="info"
            :closable="false"
            style="margin-top: 12px"
          >
            <template #title>
              <span>变量说明：{{ variableHint }}</span>
            </template>
          </el-alert>

          <!-- 已使用提示 -->
          <el-alert
            v-if="currentManifest?.used_count > 0 && currentManifest?.can_edit"
            type="warning"
            :closable="false"
            style="margin-top: 12px"
          >
            <template #title>
              <span>该模板已被 {{ currentManifest.used_count }} 个历史任务使用。继续修改不会影响历史任务，因为任务已保存提示词快照。</span>
            </template>
          </el-alert>
        </div>

        <div v-else class="empty-editor">
          <el-empty description="请从左侧结构树中选择一个 Prompt 项" />
        </div>
      </el-card>
    </div>

    <!-- 复制弹窗 -->
    <el-dialog v-model="duplicateDialogVisible" title="复制为我的模板" width="420px" :close-on-click-modal="false" destroy-on-close>
      <el-form ref="duplicateFormRef" :model="duplicateForm" :rules="duplicateRules" label-width="100px">
        <el-form-item label="新模板名称" prop="name">
          <el-input v-model="duplicateForm.name" placeholder="例如：我的自定义模板" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="duplicateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="duplicateLoading" @click="handleDuplicateConfirm">确认复制</el-button>
      </template>
    </el-dialog>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="renameDialogVisible" title="重命名模板" width="420px" :close-on-click-modal="false" destroy-on-close>
      <el-form ref="renameFormRef" :model="renameForm" :rules="renameRules" label-width="100px">
        <el-form-item label="新名称" prop="name">
          <el-input v-model="renameForm.name" placeholder="输入新的模板名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="renameLoading" @click="handleRenameConfirm">确认重命名</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CopyDocument, Star, Edit, Delete, Document, Folder,
  Check, RefreshLeft, Warning,
} from '@element-plus/icons-vue'
import {
  listProfessionalCotPromptTemplates,
  getProfessionalCotPromptTemplate,
  duplicateProfessionalCotPromptTemplate,
  renameProfessionalCotPromptTemplate,
  setDefaultProfessionalCotPromptTemplate,
  deleteProfessionalCotPromptTemplate,
  getProfessionalCotPromptItem,
  updateProfessionalCotPromptItem,
  restoreDefaultProfessionalCotPromptItem,
} from '../../api'

// ---------- 模板列表 ----------
const templatesData = ref(null)
const systemTemplates = computed(() =>
  (templatesData.value?.templates || []).filter(t => t.is_system)
)
const userTemplates = computed(() =>
  (templatesData.value?.templates || []).filter(t => !t.is_system)
)
const selectedTemplateId = ref('')
const currentManifest = computed(() =>
  (templatesData.value?.templates || []).find(t => t.template_id === selectedTemplateId.value)
)

async function fetchTemplates() {
  try {
    const res = await listProfessionalCotPromptTemplates()
    templatesData.value = res
    // 默认选中用户默认模板或系统默认模板
    const defaultId = res.effective_default_template_id || res.system_template_id
    if (!selectedTemplateId.value || !(res.templates || []).find(t => t.template_id === selectedTemplateId.value)) {
      selectedTemplateId.value = defaultId
    }
  } catch (err) {
    ElMessage.error('获取模板列表失败')
  }
}

// ---------- 模板详情 & 树 ----------
const treeLoading = ref(false)
const promptTree = ref([])
const promptCount = ref(0)
const treeProps = { children: 'children', label: 'label' }
const treeRef = ref(null)

async function fetchTemplateDetail() {
  if (!selectedTemplateId.value) return
  treeLoading.value = true
  try {
    const res = await getProfessionalCotPromptTemplate(selectedTemplateId.value)
    promptTree.value = res.tree || []
    promptCount.value = res.prompt_count || 0
  } catch (err) {
    ElMessage.error('获取模板详情失败')
  } finally {
    treeLoading.value = false
  }
}

function handleTemplateChange() {
  selectedPrompt.value = null
  promptData.value = null
  editedContent.value = ''
  fetchTemplateDetail()
}

// ---------- Prompt 内容 ----------
const selectedPrompt = ref(null)
const promptData = ref(null)
const promptLoading = ref(false)
const editedContent = ref('')
const saveLoading = ref(false)
const restoreLoading = ref(false)

const promptContentModified = computed(() =>
  editedContent.value !== (promptData.value?.content || '')
)

const selectedPromptBreadcrumb = computed(() => {
  if (!selectedPrompt.value) return ''
  const parts = []
  if (selectedPrompt.value.cot_type_name) {
    parts.push(selectedPrompt.value.cot_type_name)
  }
  parts.push(selectedPrompt.value.label)
  return parts.join(' / ')
})

const variableHint = computed(() => {
  if (!selectedPrompt.value) return ''
  const key = selectedPrompt.value.prompt_key
  if (key.startsWith('common.step1_3')) return 'paper_text：输入的论文原文；source_id/source_label：文献来源标识'
  if (key.includes('.step4')) return 'step1_3_result：融合节点输出的文献可用性、关键信息和 CoT 类型路由结果'
  if (key.includes('.step5')) return 'step1_3_result：融合节点输出结果；step4：Step 4 生成的 input'
  if (key.includes('.step6')) return 'step4, step5：前两步的输出结果'
  return ''
})

function handleNodeClick(data) {
  if (!data.is_prompt) {
    selectedPrompt.value = null
    promptData.value = null
    editedContent.value = ''
    return
  }
  selectedPrompt.value = data
  fetchPromptContent()
}

async function fetchPromptContent() {
  if (!selectedTemplateId.value || !selectedPrompt.value?.prompt_key) return
  promptLoading.value = true
  try {
    const res = await getProfessionalCotPromptItem(selectedTemplateId.value, selectedPrompt.value.prompt_key)
    promptData.value = res
    editedContent.value = res.content || ''
  } catch (err) {
    ElMessage.error('获取 Prompt 内容失败')
    promptData.value = null
    editedContent.value = ''
  } finally {
    promptLoading.value = false
  }
}

async function handleSavePrompt() {
  if (!selectedTemplateId.value || !selectedPrompt.value?.prompt_key) return
  if (!editedContent.value.trim()) {
    ElMessage.warning('Prompt 内容不能为空')
    return
  }
  saveLoading.value = true
  try {
    const res = await updateProfessionalCotPromptItem(
      selectedTemplateId.value,
      selectedPrompt.value.prompt_key,
      { content: editedContent.value }
    )
    promptData.value = res
    editedContent.value = res.content || ''
    ElMessage.success('保存成功')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function handleRestoreDefault() {
  if (!selectedTemplateId.value || !selectedPrompt.value?.prompt_key) return
  restoreLoading.value = true
  try {
    const res = await restoreDefaultProfessionalCotPromptItem(
      selectedTemplateId.value,
      selectedPrompt.value.prompt_key
    )
    promptData.value = res
    editedContent.value = res.content || ''
    ElMessage.success('已恢复为默认内容')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '恢复默认失败')
  } finally {
    restoreLoading.value = false
  }
}

// ---------- 模板操作 ----------
const duplicateDialogVisible = ref(false)
const duplicateLoading = ref(false)
const duplicateFormRef = ref(null)
const duplicateForm = ref({ name: '' })
const duplicateRules = {
  name: [{ required: true, message: '请输入新模板名称', trigger: 'blur' }],
}

function handleDuplicate() {
  if (!selectedTemplateId.value) return
  const currentName = currentManifest.value?.name || ''
  duplicateForm.value = { name: currentName + '（副本）' }
  duplicateDialogVisible.value = true
}

async function handleDuplicateConfirm() {
  const formRef = duplicateFormRef.value
  if (!formRef) return
  try {
    await formRef.validate()
  } catch { return }
  duplicateLoading.value = true
  try {
    await duplicateProfessionalCotPromptTemplate(selectedTemplateId.value, { name: duplicateForm.value.name })
    ElMessage.success('模板复制成功')
    duplicateDialogVisible.value = false
    await fetchTemplates()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '复制失败')
  } finally {
    duplicateLoading.value = false
  }
}

async function handleSetDefault() {
  if (!selectedTemplateId.value) return
  if (currentManifest.value?.is_default) {
    ElMessage.info('该模板已是您的默认模板')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定将「${currentManifest.value?.name}」设为您的默认模板？新建任务时将默认使用此模板。`,
      '设为默认模板',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return }
  try {
    await setDefaultProfessionalCotPromptTemplate(selectedTemplateId.value)
    ElMessage.success('已设为默认模板')
    await fetchTemplates()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '设为默认失败')
  }
}

const renameDialogVisible = ref(false)
const renameLoading = ref(false)
const renameFormRef = ref(null)
const renameForm = ref({ name: '' })
const renameRules = {
  name: [{ required: true, message: '请输入新名称', trigger: 'blur' }],
}

function handleRename() {
  if (!currentManifest.value?.can_edit) return
  renameForm.value = { name: currentManifest.value?.name || '' }
  renameDialogVisible.value = true
}

async function handleRenameConfirm() {
  const formRef = renameFormRef.value
  if (!formRef) return
  try {
    await formRef.validate()
  } catch { return }
  renameLoading.value = true
  try {
    await renameProfessionalCotPromptTemplate(selectedTemplateId.value, { name: renameForm.value.name })
    ElMessage.success('重命名成功')
    renameDialogVisible.value = false
    await fetchTemplates()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '重命名失败')
  } finally {
    renameLoading.value = false
  }
}

async function handleDelete() {
  if (!currentManifest.value?.can_delete) return
  try {
    await ElMessageBox.confirm(
      `确定删除模板「${currentManifest.value?.name}」？该操作不可恢复。`,
      '删除模板',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  try {
    await deleteProfessionalCotPromptTemplate(selectedTemplateId.value)
    ElMessage.success('模板已删除')
    selectedTemplateId.value = ''
    selectedPrompt.value = null
    promptData.value = null
    editedContent.value = ''
    await fetchTemplates()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '删除失败')
  }
}

// ---------- 生命周期 ----------
onMounted(async () => {
  await fetchTemplates()
  await fetchTemplateDetail()
})
</script>

<style scoped>
.page-container {
  max-width: 1400px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

/* 顶部卡片 */
.top-card {
  margin-bottom: 16px;
}
.template-selector-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.selector-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.selector-label {
  font-weight: 600;
  color: #303133;
}
.selector-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.template-meta {
  margin-top: 12px;
}

/* 左右布局 */
.main-layout {
  display: flex;
  gap: 16px;
  min-height: 600px;
}
.left-panel {
  width: 280px;
  flex-shrink: 0;
}
.left-panel :deep(.el-card__body) {
  max-height: 600px;
  overflow-y: auto;
}
.right-panel {
  flex: 1;
  min-width: 0;
}
.tree-node-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

/* Prompt 编辑区 */
.prompt-editor-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.prompt-meta-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.prompt-key-badge {
  background: #f0f2f5;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #909399;
  font-family: Consolas, Monaco, monospace;
}
.modified-badge {
  color: #e6a23c;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 2px;
}
.editor-wrapper {
  flex: 1;
}
.prompt-textarea :deep(.el-textarea__inner) {
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.prompt-readonly-view {
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 16px;
  max-height: 500px;
  overflow-y: auto;
}
.prompt-readonly-view pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  color: #303133;
}
.prompt-actions {
  display: flex;
  gap: 8px;
}

.empty-header {
  color: #909399;
}
.empty-editor {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}
</style>