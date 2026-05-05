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

export function useSourcePreview(fileIdRef, fileOptionsRef) {
  const sourceData = ref([])
  const sourceTotal = ref(0)
  const sourceLoading = ref(false)
  const sourcePage = ref(1)

  const sourceFileName = computed(() => {
    const id = fileIdRef.value
    if (!id || !fileOptionsRef.value) return ''
    const f = fileOptionsRef.value.find(f => f.id === id)
    return f ? f.filename : ''
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
      sourceData.value = res.items || []
      sourceTotal.value = res.total || 0
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

  return {
    sourceData,
    sourceTotal,
    sourceLoading,
    sourcePage,
    sourceFileName,
    loadSourcePreview,
    handleSourcePageChange,
  }
}
