<template>
  <div class="prompt-preview">
    <!-- Format hint for this stage -->
    <div v-if="formatHint && version != null" class="format-hint">
      <el-collapse>
        <el-collapse-item :title="'本阶段期望LLM返回格式：' + formatHint.type" name="format">
          <div class="hint-type-desc">{{ formatHint.typeDesc }}</div>
          <table class="hint-table">
            <thead>
              <tr><th>字段名</th><th>说明</th><th>是否必须</th></tr>
            </thead>
            <tbody>
              <tr v-for="f in formatHint.fields" :key="f.name">
                <td class="field-name">{{ f.name }}</td>
                <td>{{ f.desc }}</td>
                <td>
                  <el-tag v-if="f.required" size="small" type="danger">必须</el-tag>
                  <el-tag v-else size="small" type="info">可选</el-tag>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="formatHint.example" class="hint-example">
            <span class="hint-label">示例：</span>
            <pre class="hint-code">{{ formatHint.example }}</pre>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <div v-if="version != null" class="preview-content">
      <div class="preview-header">
        <el-tag size="small" type="primary">版本 v{{ version }}</el-tag>
        <span class="preview-time">{{ timeLabel }}</span>
      </div>
      <el-input
        :model-value="content"
        type="textarea"
        :autosize="{ minRows: 6, maxRows: 18 }"
        class="preview-textarea"
        @update:model-value="$emit('update:content', $event)"
      />
      <div class="preview-footer">
        <el-button
          type="primary"
          :loading="saveLoading"
          :disabled="!contentChanged"
          size="small"
          @click="$emit('save')"
        >
          保存为新版本 (v{{ nextVersion }})
        </el-button>
      </div>
    </div>
    <div v-else class="preview-empty">
      <el-icon :size="32"><Document /></el-icon>
      <p>请先选择一个提示词</p>
    </div>
  </div>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'
import { computed } from 'vue'

const STAGE_FORMAT_HINTS = {
  question_generate: {
    type: 'JSON数组',
    typeDesc: '模型应返回一个列表，每条包含至少一个问答对',
    fields: [
      { name: 'input', desc: '问题内容', required: true },
      { name: 'output', desc: '标准答案', required: true },
      { name: 'domain', desc: '学科领域', required: false },
      { name: 'category', desc: '知识类别', required: false },
      { name: 'task_type', desc: '题目类型（简答/判断等）', required: false },
      { name: 'cot', desc: '推理/思维链过程', required: false },
    ],
    example: '[{"input": "什么是AI?", "output": "AI是...", "domain": "计算机", "task_type": "简答"}]',
  },
  knowledge_generate: {
    type: 'JSON对象',
    typeDesc: '模型应返回单个对象，包含结构化知识体系',
    fields: [
      { name: 'knowledge', desc: '知识体系（嵌套结构或列表）', required: true },
      { name: 'domain', desc: '学科领域', required: false },
      { name: 'category', desc: '知识类别', required: false },
    ],
    example: '{"knowledge": [{"topic": "AI基础", "points": ["定义", "分类"]}], "domain": "计算机"}',
  },
  question_validate: {
    type: 'JSON对象',
    typeDesc: '模型应返回单个对象，判断问题是否合格',
    fields: [
      { name: 'passed', desc: '是否通过（"是" 或 "否"）', required: true },
      { name: 'reason', desc: '校验原因说明', required: true },
      { name: 'validation_result', desc: '校验结果详情', required: false },
    ],
    example: '{"passed": "是", "reason": "问题表述清晰，符合要求"}',
  },
  answer_generate: {
    type: 'JSON对象',
    typeDesc: '模型应返回单个对象，包含生成的答案',
    fields: [
      { name: 'output', desc: '标准答案内容', required: true },
      { name: 'cot', desc: '推理/思维链过程', required: false },
      { name: 'step_count', desc: '推理步骤数', required: false },
    ],
    example: '{"output": "AI是计算机科学的一个分支...", "cot": "首先...然后...", "step_count": 3}',
  },
  answer_validate: {
    type: 'JSON对象',
    typeDesc: '模型应返回单个对象，判断答案是否合格',
    fields: [
      { name: 'passed', desc: '是否通过（"是" 或 "否"）', required: true },
      { name: 'reason', desc: '校验原因说明', required: true },
      { name: 'validation_result', desc: '校验结果详情', required: false },
    ],
    example: '{"passed": "是", "reason": "答案完整准确"}',
  },
  data_evaluate: {
    type: 'JSON对象',
    typeDesc: '模型应返回单个对象，包含各项评分',
    fields: [
      { name: 'score', desc: '综合评分（0-100）', required: true },
      { name: 'difficulty', desc: '难度等级', required: false },
      { name: 'relevance', desc: '相关性评分', required: false },
      { name: 'clarity', desc: '清晰度评分', required: false },
      { name: 'reasoning', desc: '推理质量评分', required: false },
      { name: 'terminology', desc: '术语准确性评分', required: false },
    ],
    example: '{"score": 85, "difficulty": "中等", "relevance": 90, "clarity": 80}',
  },
  dataset_assessment: {
    type: 'JSON对象',
    typeDesc: '模型应返回单个对象，包含评分标准',
    fields: [
      { name: 'Assessment', desc: '评分细则字符串（总分100分）', required: true },
    ],
    example: '{"Assessment": "评分点1(30分): 满分标准xxx / 失分规则xxx\\n评分点2(70分): ..."}',
  },
}

const props = defineProps({
  version: { type: [Number, null], default: null },
  content: { type: String, default: '' },
  timeLabel: { type: String, default: '' },
  contentChanged: { type: Boolean, default: false },
  nextVersion: { type: Number, default: 1 },
  saveLoading: { type: Boolean, default: false },
  stage: { type: String, default: '' },
})

const formatHint = computed(() => STAGE_FORMAT_HINTS[props.stage] || null)

defineEmits(['update:content', 'save'])
</script>

<style scoped>
.prompt-preview {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  min-height: 200px;
  display: flex;
  flex-direction: column;
}
.format-hint .el-collapse {
  border: none;
  margin-bottom: 12px;
}
.format-hint .el-collapse-item__header {
  font-size: 13px;
  color: #e6a23c;
  font-weight: 600;
}
.hint-type-desc {
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}
.hint-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 8px;
}
.hint-table th {
  background: #fff;
  padding: 6px 10px;
  font-size: 12px;
  color: #909399;
  text-align: left;
  border-bottom: 1px solid #ebeef5;
}
.hint-table td {
  padding: 4px 10px;
  font-size: 13px;
  border-bottom: 1px solid #ebeef5;
}
.hint-table .field-name {
  font-weight: 600;
  color: #303133;
  font-family: 'Consolas', monospace;
}
.hint-label {
  color: #909399;
  font-size: 13px;
}
.hint-code {
  background: #fff;
  border-radius: 4px;
  padding: 8px;
  font-size: 12px;
  font-family: 'Consolas', monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 4px 0 0 0;
  color: #303133;
}

.preview-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.preview-time {
  color: #909399;
  font-size: 13px;
}

.preview-textarea :deep(.el-textarea__inner) {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #fff;
  border-radius: 4px;
  overflow-y: auto;
}

.preview-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 1px solid #e4e7ed;
}

.preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: #909399;
}

.preview-empty p {
  font-size: 14px;
}
</style>