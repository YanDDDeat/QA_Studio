<template>
  <el-dialog
    :model-value="visible"
    title="导出字段选择"
    width="640px"
    :close-on-click-modal="false"
    @close="$emit('cancel')"
  >
    <div class="field-select-container">
      <!-- Top-level fields group -->
      <div class="field-group">
        <div class="group-header">
          <span class="group-title">顶层字段</span>
          <el-checkbox
            :model-value="isAllTopLevelChecked"
            :indeterminate="isTopLevelIndeterminate"
            @change="toggleAllTopLevel"
          >
            全选 / 取消全选
          </el-checkbox>
        </div>
        <div class="checkbox-grid">
          <el-checkbox
            v-for="field in fields.topLevel"
            :key="field"
            :model-value="selectedFields.includes(field)"
            @change="toggleField(field, $event)"
          >
            {{ field }}
          </el-checkbox>
        </div>
      </div>

      <!-- Extra sub-fields group -->
      <div v-if="fields.extra.length > 0" class="field-group">
        <div class="group-header">
          <span class="group-title">extra 子字段</span>
          <el-checkbox
            :model-value="isAllExtraChecked"
            :indeterminate="isExtraIndeterminate"
            @change="toggleAllExtra"
          >
            全选 / 取消全选
          </el-checkbox>
        </div>
        <div class="checkbox-grid">
          <el-checkbox
            v-for="field in fields.extra"
            :key="'extra.' + field"
            :model-value="selectedFields.includes('extra.' + field)"
            @change="toggleField('extra.' + field, $event)"
          >
            extra.{{ field }}
          </el-checkbox>
        </div>
      </div>
    </div>

    <template #footer>
      <span class="selected-count">已选 {{ selectedFields.length }} 个字段</span>
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" @click="$emit('confirm', sortByDefaultOrder(selectedFields))">确认导出</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  fields: {
    type: Object,
    default: () => ({ topLevel: [], extra: [] }),
  },
  defaultFields: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['confirm', 'cancel'])

// Selected fields list (includes both top-level names and "extra.xxx" for extra sub-fields)
const selectedFields = ref([])

// Case-insensitive default matching — output follows defaultFields order
function matchDefaults() {
  const topLowerMap = new Map(props.fields.topLevel.map(f => [f.toLowerCase(), f]))
  const extraLowerMap = new Map(props.fields.extra.map(f => [f.toLowerCase(), f]))
  const matched = []
  for (const df of props.defaultFields) {
    const lower = df.toLowerCase()
    if (topLowerMap.has(lower)) {
      matched.push(topLowerMap.get(lower))
    } else if (extraLowerMap.has(lower)) {
      matched.push('extra.' + extraLowerMap.get(lower))
    }
  }
  return matched
}

// Sort selectedFields by defaultFields order, unmatched fields go to the end
function sortByDefaultOrder(fields) {
  const orderMap = new Map(props.defaultFields.map((f, i) => [f.toLowerCase(), i]))
  return [...fields].sort((a, b) => {
    const keyA = a.startsWith('extra.') ? a.slice(6) : a
    const keyB = b.startsWith('extra.') ? b.slice(6) : b
    const idxA = orderMap.has(keyA.toLowerCase()) ? orderMap.get(keyA.toLowerCase()) : Infinity
    const idxB = orderMap.has(keyB.toLowerCase()) ? orderMap.get(keyB.toLowerCase()) : Infinity
    return idxA - idxB
  })
}

// Reset selection when dialog opens with new fields
watch(() => props.visible, (val) => {
  if (val) {
    selectedFields.value = matchDefaults()
  }
})

// Top-level select-all logic
const isAllTopLevelChecked = computed(() => {
  if (props.fields.topLevel.length === 0) return false
  return props.fields.topLevel.every(f => selectedFields.value.includes(f))
})

const isTopLevelIndeterminate = computed(() => {
  const checked = props.fields.topLevel.filter(f => selectedFields.value.includes(f)).length
  return checked > 0 && checked < props.fields.topLevel.length
})

function toggleAllTopLevel(val) {
  if (val) {
    // Add all top-level fields (don't add duplicates)
    for (const f of props.fields.topLevel) {
      if (!selectedFields.value.includes(f)) {
        selectedFields.value.push(f)
      }
    }
  } else {
    // Remove all top-level fields
    selectedFields.value = selectedFields.value.filter(f => !props.fields.topLevel.includes(f))
  }
}

// Extra select-all logic
const isAllExtraChecked = computed(() => {
  if (props.fields.extra.length === 0) return false
  return props.fields.extra.every(f => selectedFields.value.includes('extra.' + f))
})

const isExtraIndeterminate = computed(() => {
  const checked = props.fields.extra.filter(f => selectedFields.value.includes('extra.' + f)).length
  return checked > 0 && checked < props.fields.extra.length
})

function toggleAllExtra(val) {
  if (val) {
    for (const f of props.fields.extra) {
      const key = 'extra.' + f
      if (!selectedFields.value.includes(key)) {
        selectedFields.value.push(key)
      }
    }
  } else {
    selectedFields.value = selectedFields.value.filter(f => !f.startsWith('extra.'))
  }
}

// Toggle individual field
function toggleField(field, val) {
  if (val) {
    if (!selectedFields.value.includes(field)) {
      selectedFields.value.push(field)
    }
  } else {
    selectedFields.value = selectedFields.value.filter(f => f !== field)
  }
}
</script>

<style scoped>
.field-select-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field-group {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.group-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.checkbox-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}

.checkbox-grid .el-checkbox {
  min-width: 120px;
}

.selected-count {
  color: #909399;
  font-size: 13px;
  margin-right: 16px;
}
</style>