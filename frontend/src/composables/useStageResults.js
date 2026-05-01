/**
 * Composable for stage-page result area (lazy-loaded datasets).
 *
 * Each stage page calls useStageResults(stageName, fileId, columns)
 * and gets all reactive state + methods needed for the collapsible
 * result card at the bottom of the page.
 *
 * Priority for fileId: task output file > manually selected file
 */
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import katex from 'katex'
import { getDatasets } from '../api'

// Truncate threshold for long text in table cells
const TRUNCATE_LIMIT = 80

export function useStageResults(stageName, fileIdRef, columns, taskInfoRef) {
  // ---- State ----
  const resultsData = ref([])
  const resultsTotal = ref(0)
  const resultsLoading = ref(false)
  const resultsPage = ref(1)
  const detailVisible = ref(false)
  const detailRecord = ref(null)

  // Resolve file_id: task output > manually selected
  const effectiveFileId = computed(() => {
    if (taskInfoRef && taskInfoRef.value && taskInfoRef.value.file_id) {
      return taskInfoRef.value.file_id
    }
    return fileIdRef.value
  })

  // ---- Methods ----

  async function loadResults() {
    const fileId = effectiveFileId.value
    if (!fileId) {
      ElMessage.warning('暂无可查看的结果文件')
      return
    }
    resultsLoading.value = true
    try {
      const res = await getDatasets({
        file_id: fileId,
        current_stage: stageName,
        page: resultsPage.value,
        page_size: 10,
      })
      resultsData.value = res.items || []
      resultsTotal.value = res.total || 0
    } catch (err) {
      ElMessage.error('加载结果失败')
      resultsData.value = []
      resultsTotal.value = 0
    } finally {
      resultsLoading.value = false
    }
  }

  function handleResultsPageChange(page) {
    resultsPage.value = page
    loadResults()
  }

  function showDetail(row) {
    detailRecord.value = row
    detailVisible.value = true
  }

  function truncateText(text) {
    if (!text) return '-'
    if (typeof text !== 'string') {
      try {
        text = JSON.stringify(text)
      } catch {
        text = String(text)
      }
    }
    if (text.length > TRUNCATE_LIMIT) {
      return text.substring(0, TRUNCATE_LIMIT) + '...'
    }
    return text
  }

  // ---- LaTeX rendering (same logic as DataManage.vue) ----

  function renderLatex(text) {
    if (!text) return ''
    let html = text

    html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
      try {
        return katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false })
      } catch {
        return match
      }
    })

    html = html.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
      try {
        return katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false })
      } catch {
        return match
      }
    })

    return html
  }

  function escapeHtml(text) {
    if (!text) return ''
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  function renderContent(text) {
    if (!text) return '<span class="empty-field">-</span>'
    let html = escapeHtml(text)
    html = renderLatex(html)
    html = html.replace(/\n/g, '<br>')
    return html
  }

  function renderKnowledge(knowledge) {
    if (!knowledge) return '<span class="empty-field">-</span>'
    if (typeof knowledge === 'string') return renderContent(knowledge)
    try {
      const formatted = JSON.stringify(knowledge, null, 2)
      return '<pre class="knowledge-json">' + escapeHtml(formatted) + '</pre>'
    } catch {
      return String(knowledge)
    }
  }

  return {
    resultsData,
    resultsTotal,
    resultsLoading,
    resultsPage,
    detailVisible,
    detailRecord,
    effectiveFileId,
    columns,
    loadResults,
    handleResultsPageChange,
    showDetail,
    truncateText,
    renderContent,
    renderKnowledge,
  }
}