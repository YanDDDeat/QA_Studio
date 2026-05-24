<template>
  <el-dialog
    :model-value="visible"
    :title="dialogTitle"
    width="480px"
    :close-on-click-modal="false"
    @update:model-value="handleVisibleChange"
  >
    <el-form label-width="80px" v-loading="loading">
      <el-form-item v-if="stageLabel" label="阶段">
        <el-tag type="info">{{ stageLabel }}</el-tag>
      </el-form-item>
      <el-form-item label="LLM配置">
        <el-select
          v-model="llmConfigId"
          placeholder="选择LLM配置"
          style="width: 100%"
          filterable
          clearable
          @change="handleLLMConfigChange"
        >
          <el-option
            v-for="cfg in llmConfigs"
            :key="cfg.id"
            :label="cfg.name + (cfg.is_global ? ' (全局)' : ' (我的)')"
            :value="cfg.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="模型">
        <el-select
          v-model="model"
          placeholder="请选择模型"
          style="width: 100%"
          filterable
          clearable
          :disabled="!llmConfigId"
        >
          <el-option v-for="m in modelOptions" :key="m" :label="m" :value="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="提示词">
        <el-select
          v-model="promptId"
          placeholder="选择提示词"
          style="width: 100%"
          filterable
          clearable
        >
          <el-option
            v-for="p in promptOptions"
            :key="p.id"
            :label="p.name || `v${p.version}`"
            :value="p.id"
          >
            <span>{{ p.name || `v${p.version}` }}{{ p.is_default ? '(默认)' : '' }}</span>
          </el-option>
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleVisibleChange(false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        确认{{ action === 'retry' ? '重试' : '恢复' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { getPromptConfigs, getLLMConfigs } from '../api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  action: { type: String, default: 'resume' }, // 'resume' | 'retry'
  task: { type: Object, default: null },
  stage: { type: String, default: '' },
})

const emit = defineEmits(['update:visible', 'confirm'])

// ---------- 阶段标签映射（仅用于弹窗显示） ----------
const STAGE_LABELS = {
  question_generate: '问题生成',
  knowledge_generate: '知识体系',
  question_validate: '问题校验',
  answer_generate: '答案生成',
  answer_validate: '答案校验',
  data_evaluate: '数据评估',
  cot_filter: 'COT过滤',
  dataset_split: '数据集切分',
  dataset_assessment: '评分标准生成',
}

const stageLabel = computed(() => {
  const key = props.stage || props.task?.stage
  if (!key) return ''
  return STAGE_LABELS[key] || key
})

const dialogTitle = computed(() => (props.action === 'retry' ? '重试任务配置' : '恢复任务配置'))

// ---------- 弹窗状态 ----------
const llmConfigs = ref([])
const promptOptions = ref([])
const promptId = ref(null)
const model = ref('')
const llmConfigId = ref(null)
const loading = ref(false)
const submitting = ref(false)

const modelOptions = computed(() => {
  const cfg = llmConfigs.value.find(c => c.id === llmConfigId.value)
  return cfg ? (cfg.models || []) : []
})

function handleLLMConfigChange(cfgId) {
  const cfg = llmConfigs.value.find(c => c.id === cfgId)
  model.value = cfg?.default_model || ''
}

function handleVisibleChange(val) {
  emit('update:visible', val)
}

async function loadOptions() {
  loading.value = true
  try {
    const stageKey = props.stage || props.task?.stage || ''
    const [promptRes, llmRes] = await Promise.all([
      stageKey ? getPromptConfigs({ stage: stageKey }) : Promise.resolve([]),
      getLLMConfigs(),
    ])
    promptOptions.value = Array.isArray(promptRes) ? promptRes : []
    llmConfigs.value = Array.isArray(llmRes) ? llmRes : []
  } catch {
    promptOptions.value = []
    llmConfigs.value = []
  } finally {
    loading.value = false
  }
}

function initFromTask() {
  const t = props.task || {}
  promptId.value = t.prompt_id ?? null
  model.value = t.model || ''
  // 优先使用 task.llm_config_id；如果没有则根据 model 反查
  if (t.llm_config_id != null) {
    llmConfigId.value = t.llm_config_id
  } else if (t.model) {
    const matched = llmConfigs.value.find(c => (c.models || []).includes(t.model))
    llmConfigId.value = matched ? matched.id : null
  } else {
    llmConfigId.value = null
  }
}

// 监听 visible：打开时加载数据并回填默认值
watch(
  () => props.visible,
  async (v) => {
    if (!v) return
    // 先按 task 初始化（即便 llmConfigs 还没拿到，至少 model/prompt 能回填）
    initFromTask()
    await loadOptions()
    // 选项加载完成后再次校准 llmConfigId（依赖 llmConfigs 反查）
    initFromTask()
  }
)

async function submit() {
  const t = props.task || {}
  const data = {}
  // 仅在用户改动时下发；llm_config_id 只要有选就下发（与 MyTasks 原行为一致）
  if (promptId.value && promptId.value !== t.prompt_id) {
    data.prompt_id = promptId.value
  }
  if (model.value && model.value !== t.model) {
    data.model = model.value
  }
  if (llmConfigId.value) {
    data.llm_config_id = llmConfigId.value
  }

  submitting.value = true
  try {
    emit('confirm', data)
    emit('update:visible', false)
  } finally {
    submitting.value = false
  }
}
</script>
