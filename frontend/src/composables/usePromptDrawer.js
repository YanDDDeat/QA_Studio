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
  const drawerReferenceFields = ref([])
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
      drawerReferenceFields.value = selectedPrompt.reference_fields || []
    } else {
      drawerContent.value = ''
      drawerVersion.value = null
      drawerCreatedAt.value = null
      drawerOriginalContent.value = ''
      drawerReferenceFields.value = []
    }
  }

  // Watch prompt_id changes (user switches prompt in the dropdown)
  watch(() => formRef.value?.prompt_id, () => syncDrawerContent())

  // Watch promptOptions changes (initial load, refresh after save)
  watch(promptOptionsRef, () => {
    if (promptOptionsRef.value.length > 0) {
      // Auto-select default prompt if user hasn't selected one yet
      if (!formRef.value?.prompt_id) {
        const defaultPrompt = promptOptionsRef.value.find(p => p.is_default)
        if (defaultPrompt) {
          formRef.value.prompt_id = defaultPrompt.id
          // Also inherit the default prompt's LLM config and model
          if (defaultPrompt.llm_config_id && !selectedLLMConfigIdRef.value) {
            selectedLLMConfigIdRef.value = defaultPrompt.llm_config_id
          }
          if (defaultPrompt.model && !formRef.value?.model) {
            formRef.value.model = defaultPrompt.model
          }
        } else {
          formRef.value.prompt_id = promptOptionsRef.value[0].id
        }
      }
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
        reference_fields: drawerReferenceFields.value,
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
    drawerReferenceFields,
    nextVersion,
    saveLoading,
    saveAsNewVersion,
  }
}