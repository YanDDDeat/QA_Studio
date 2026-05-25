import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadManagedFile } from '../api'

/**
 * Reusable composable for the file upload dialog on stage pages.
 *
 * Provides the dialog state, upload form, file selection handling,
 * submission logic, and post-upload refresh + auto-select behavior.
 *
 * @param {Function} fetchFileOptionsFn - The stage's fetchFileOptions function.
 *                                        Must return void; it updates the
 *                                        page's fileOptions ref internally.
 * @param {Ref}      formRef             - ref holding the form object (must include file_id)
 * @returns upload dialog state and methods
 */
export function useFileUpload(fetchFileOptionsFn, formRef) {
  const uploadVisible = ref(false)
  const uploadLoading = ref(false)
  const uploadFileList = ref([])
  const uploadForm = ref({ text_field: 'text' })

  // ----- File selection handling -----
  function handleUploadFileChange(file, fileList) {
    uploadFileList.value = fileList
  }

  function handleUploadFileRemove(file, fileList) {
    uploadFileList.value = fileList
  }

  function handleUploadExceed() {
    ElMessage.warning('只能上传一个文件，请先移除已选文件')
  }

  // ----- Open dialog -----
  function openUploadDialog() {
    uploadFileList.value = []
    uploadForm.value = { text_field: 'text' }
    uploadVisible.value = true
  }

  // ----- Submit upload -----
  async function submitUpload() {
    if (uploadFileList.value.length === 0) {
      ElMessage.warning('请先选择要上传的文件')
      return
    }

    uploadLoading.value = true
    const formData = new FormData()
    formData.append('text_field', uploadForm.value.text_field)
    formData.append('files', uploadFileList.value[0].raw)

    try {
      const res = await uploadManagedFile(formData)

      // The API returns { uploaded: [{id, filename, ...}], errors: [...] }
      const uploaded = res.uploaded || []
      const errors = res.errors || []

      if (uploaded.length > 0) {
        ElMessage.success(`文件上传成功`)
      }
      if (errors.length > 0) {
        const msg = errors.map(e => `${e.filename}: ${e.error}`).join('\n')
        ElMessage.error(`上传失败: ${msg}`)
      }

      // Close dialog
      uploadVisible.value = false

      // Refresh file options
      await fetchFileOptionsFn()

      // Auto-select the newly uploaded file
      if (uploaded.length > 0) {
        formRef.value.file_id = uploaded[0].id
      }
    } catch (err) {
      // Surface the most useful info: the backend detail if present, otherwise
      // the HTTP status (e.g. "上传失败 (HTTP 400)" — a 400 with empty body
      // usually means Starlette rejected the multipart before our handler).
      const detail = err.response?.data?.detail
      const status = err.response?.status
      const msg = detail
        ? `上传失败: ${detail}`
        : status
          ? `上传失败 (HTTP ${status})${err.message ? ' ' + err.message : ''}`
          : `上传失败: ${err.message || '未知错误'}`
      ElMessage.error(msg)
    } finally {
      uploadLoading.value = false
    }
  }

  return {
    uploadVisible,
    uploadLoading,
    uploadFileList,
    uploadForm,
    handleUploadFileChange,
    handleUploadFileRemove,
    handleUploadExceed,
    openUploadDialog,
    submitUpload,
  }
}