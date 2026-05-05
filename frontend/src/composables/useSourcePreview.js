/**
 * Composable for source file preview (read-only JSON content viewer).
 *
 * Usage:
 *   const { sourceData, sourceTotal, sourceLoading, sourcePage, loadSourcePreview, handleSourcePageChange, sourceFileName } = useSourcePreview(fileIdRef, fileOptionsRef)
 *
 * Place a <el-card class="source-preview-card"> in the template that calls loadSourcePreview on demand.
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getManagedFileContent } from '../api'
import { FIELD_LABELS, LONG_TEXT_FIELDS, META_FIELDS } from '../utils/fieldLabels'

export function useSourcePreview(fileIdRef, fileOptionsRef) {
  const sourceData = ref([])
  const sourceTotal = ref(0)
  const sourceLoading = ref(false)
  const sourcePage = ref(1)
  const sourceDetailVisible = ref(false)
  const sourceDetailRecord = ref(null)

  const sourceFileName = computed(() => {
    const id = fileIdRef.value
    if (!id || !fileOptionsRef.value) return ''
    const f = fileOptionsRef.value.find(f => f.id === id)
    return f ? f.filename : ''
  })

  const sourceColumns = computed(() => {
    if (sourceData.value.length === 0) return []
    const first = sourceData.value[0]
    if (!first || typeof first !== 'object') return []
    return Object.keys(first).map(key => ({
      prop: key,
      label: FIELD_LABELS[key] || key,
      width: key === 'id' ? 55 : undefined,
      minWidth: 100,
    }))
  })

  async function loadSourcePreview() {
    const fileId = fileIdRef.value
    if (!fileId) {
      ElMessage.warning('请先选择文件')
      return
    }
    sourceLoading.value = true
    try {
      const res = await getManagedFileContent(fileId, {
        page: sourcePage.value,
        page_size: 10,
      })
      sourceData.value = res.preview || []
      sourceTotal.value = res.total_records || 0
    } catch (err) {
      ElMessage.error('加载源文件失败')
      sourceData.value = []
      sourceTotal.value = 0
    } finally {
      sourceLoading.value = false
    }
  }

  function handleSourcePageChange(page) {
    sourcePage.value = page
    loadSourcePreview()
  }

  function showSourceDetail(row) {
    sourceDetailRecord.value = row
    sourceDetailVisible.value = true
  }

  const sourceMetaFields = computed(() => {
    if (!sourceDetailRecord.value) return []
    return META_FIELDS.filter(k => sourceDetailRecord.value[k] != null)
  })
  const sourceLongTextFields = computed(() => {
    if (!sourceDetailRecord.value) return []
    return LONG_TEXT_FIELDS.filter(k => sourceDetailRecord.value[k])
  })

  function renderContent(text) {
    if (!text) return '-'
    if (typeof text !== 'string') {
      try { text = JSON.stringify(text) } catch { text = String(text) }
    }
    return text.replace(/\n/g, '<br>')
  }

  return {
    sourceData,
    sourceTotal,
    sourceLoading,
    sourcePage,
    sourceFileName,
    sourceColumns,
    sourceDetailVisible,
    sourceDetailRecord,
    sourceMetaFields,
    sourceLongTextFields,
    loadSourcePreview,
    handleSourcePageChange,
    showSourceDetail,
    renderContent,
  }
}
