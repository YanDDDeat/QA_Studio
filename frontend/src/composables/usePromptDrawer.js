import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createPromptConfig, getPromptConfigs } from '../api'

/**
 * Reusable composable for the prompt preview + inline-edit drawer.
 *
 * @param {string}  stage           - Stage enum value, e.g. 'question_generate'
 * @param {Ref}     promptOptionsRef - ref holding the array of prompt option objects
 * @param {Ref}     formRef          - ref holding the form object (must include prompt_id, model)
 * @param {Ref}     selectedLLMConfigIdRef - ref holding the selected LLM config id
 * @returns drawer state, computed, and methods
 */
export function usePromptDrawer(stage, promptOptionsRef, formRef, selectedLLMConfigIdRef) {
  const drawerVisible = ref(true)
  const drawerContent = ref('')
  const drawerVersion = ref(null)
  const drawerCreatedAt = ref(null)
  const drawerOriginalContent = ref('')
  const saveLoading = ref(false)

  const drawerContentChanged = computed(
    () => drawerContent.value !== drawerOriginalContent.value
  )

  const nextVersion = computed(() => (drawerVersion.value ?? 0) + 1)

  // Sync drawer with the currently selected prompt
  function syncDrawerContent() {
    const pid = formRef.value.prompt_id
    const selectedPrompt = promptOptionsRef.value.find((p) => p.id === pid)
    if (selectedPrompt) {
      drawerContent.value = selectedPrompt.content || ''
      drawerVersion.value = selectedPrompt.version
      drawerCreatedAt.value = selectedPrompt.created_at
      drawerOriginalContent.value = selectedPrompt.content || ''
    } else {
      drawerContent.value = ''
      drawerVersion.value = null
      drawerCreatedAt.value = null
      drawerOriginalContent.value = ''
    }
  }

  // Watch prompt_id changes (user switches prompt in the dropdown)
  watch(() => formRef.value?.prompt_id, () => syncDrawerContent())

  // Watch promptOptions changes (initial load, refresh after save)
  watch(promptOptionsRef, () => {
    if (promptOptionsRef.value.length > 0) {
      syncDrawerContent()
    }
  })

  // Save edited content as a new version
  async function saveAsNewVersion() {
    if (!drawerContent.value) return

    saveLoading.value = true
    try {
      const payload = {
        stage,
        content: drawerContent.value,
        model: formRef.value.model,
        llm_config_id: selectedLLMConfigIdRef.value || null,
      }
      const res = await createPromptConfig(payload)

      // Refresh prompt options list
      const newPrompts = await getPromptConfigs({ stage })
      promptOptionsRef.value = Array.isArray(newPrompts) ? newPrompts : []

      // Auto-select the newly created version
      formRef.value.prompt_id = res.id

      ElMessage.success(`已保存为新版本 v${res.version}`)
    } catch (err) {
      const detail = err.response?.data?.detail || '保存失败'
      ElMessage.error(detail)
    } finally {
      saveLoading.value = false
    }
  }

  return {
    drawerVisible,
    drawerContent,
    drawerVersion,
    drawerCreatedAt,
    drawerContentChanged,
    nextVersion,
    saveLoading,
    saveAsNewVersion,
  }
}