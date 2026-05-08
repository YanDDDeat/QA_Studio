import api from '../utils/api'

// Auth API
export function login(data) {
  return api.post('/auth/login', data)
}

export function createUser(data) {
  return api.post('/auth/create-user', data)
}

export function getMe() {
  return api.get('/auth/me')
}

export function listUsers() {
  return api.get('/auth/users')
}

// Datasets API
export function getDatasets(params) {
  return api.get('/datasets', { params })
}

export function getDataset(id) {
  return api.get(`/datasets/${id}`)
}

export function createDataset(data) {
  return api.post('/datasets', data)
}

export function updateDataset(id, data) {
  return api.put(`/datasets/${id}`, data)
}

export function deleteDataset(id) {
  return api.delete(`/datasets/${id}`)
}

// Tasks API
export function getTasks(params) {
  return api.get('/tasks', { params })
}

export function createTask(data) {
  return api.post('/tasks', data)
}

export function getTask(id) {
  return api.get(`/tasks/${id}`)
}

export function getTaskLogs(taskId, params) {
  return api.get(`/task-logs/${taskId}`, { params })
}

export function getTaskList(params) {
  return api.get('/task-logs/tasks', { params })
}

export function stopTask(taskId) {
  return api.post(`/tasks/${taskId}/stop`)
}

export function resumeTask(taskId) {
  return api.post(`/tasks/${taskId}/resume`)
}

// Stage APIs
export function startQuestionGenerate(data) {
  return api.post('/question-generate/start', data)
}

export function startKnowledgeGenerate(data) {
  return api.post('/knowledge-generate/start', data)
}

export function startQuestionValidate(data) {
  return api.post('/question-validate/start', data)
}

export function startAnswerGenerate(data) {
  return api.post('/answer-generate/start', data)
}

export function startAnswerValidate(data) {
  return api.post('/answer-validate/start', data)
}

export function startDataEvaluate(data) {
  return api.post('/data-evaluate/start', data)
}

export function getStageStatus(stage, taskId) {
  return api.get(`/${stage}/status/${taskId}`)
}

export function retryStage(stage, taskId) {
  return api.post(`/${stage}/retry/${taskId}`)
}

// Source Files API (per-stage)
export function getQuestionGenerateSourceFiles(params) {
  return api.get('/question-generate/source-files', { params })
}

export function getKnowledgeGenerateSourceFiles(params) {
  return api.get('/knowledge-generate/source-files', { params })
}

export function getQuestionValidateSourceFiles(params) {
  return api.get('/question-validate/source-files', { params })
}

export function getAnswerGenerateSourceFiles(params) {
  return api.get('/answer-generate/source-files', { params })
}

export function getAnswerValidateSourceFiles(params) {
  return api.get('/answer-validate/source-files', { params })
}

export function getDataEvaluateSourceFiles(params) {
  return api.get('/data-evaluate/source-files', { params })
}

export function getDataEvaluateReport(taskId) {
  return api.get(`/data-evaluate/report/${taskId}`)
}

// Files API
export function uploadFile(data) {
  return api.post('/files/upload', data)
}

export function getFiles(params) {
  return api.get('/files', { params })
}

export function deleteFile(id) {
  return api.delete(`/files/${id}`)
}

// Prompts API
export function getPrompts(params) {
  return api.get('/prompts', { params })
}

export function createPrompt(data) {
  return api.post('/prompts', data)
}

export function updatePrompt(id, data) {
  return api.put(`/prompts/${id}`, data)
}

// Config API
export function getStages() {
  return api.get('/config-center/stages')
}

export function getPromptConfigs(params) {
  return api.get('/config-center/prompts', { params })
}

export function getModelConfigs() {
  return api.get('/config-center/models')
}

export function createPromptConfig(data) {
  return api.post('/config-center/prompts', data)
}

export function deletePromptConfig(id) {
  return api.delete(`/config-center/prompts/${id}`)
}

export function updateModelConfig(data) {
  return api.put('/config-center/models', data)
}

// File Manage API
export function getManagedFiles(params) {
  return api.get('/file-manage', { params })
}

export function getManagedFile(id) {
  return api.get(`/file-manage/${id}`)
}

export function getManagedFileContent(id, params) {
  return api.get(`/file-manage/content/${id}`, { params })
}

export function uploadManagedFile(data) {
  return api.post('/file-manage/upload', data)
}

export function uploadMdFile(data) {
  return api.post('/file-manage/upload-md', data)
}

export function deleteManagedFile(id) {
  return api.delete(`/file-manage/${id}`)
}

export function downloadManagedFile(id, fields = null) {
  const params = { responseType: 'blob' }
  if (fields && fields.length > 0) {
    params.params = { fields: fields.join(',') }
  }
  return api.get(`/file-manage/download/${id}`, params)
}

export function mergeAndDownloadFiles(fileIds, fields = null) {
  const data = { file_ids: fileIds }
  if (fields && fields.length > 0) {
    data.fields = fields
  }
  return api.post('/file-manage/merge-download', data, { responseType: 'blob' })
}

// LLM Config API
export function getLLMConfigs() {
  return api.get('/llm-configs')
}

export function createLLMConfig(data) {
  return api.post('/llm-configs', data)
}

export function updateLLMConfig(id, data) {
  return api.put(`/llm-configs/${id}`, data)
}

export function deleteLLMConfig(id) {
  return api.delete(`/llm-configs/${id}`)
}

export function testLLMConfig(id) {
  return api.post(`/llm-configs/${id}/test`)
}

// COT Filter API
export function startCotFilter(data) {
  return api.post('/cot-filter/start', data)
}

export function getCotFilterStatus(taskId) {
  return api.get(`/cot-filter/status/${taskId}`)
}

export function getCotFilterSourceFiles(params) {
  return api.get('/cot-filter/source-files', { params })
}

// Dataset Split API
export function startDatasetSplit(data) {
  return api.post('/dataset-split/start', data)
}

export function getDatasetSplitStatus(taskId) {
  return api.get(`/dataset-split/status/${taskId}`)
}

export function getDatasetSplitSourceFiles(params) {
  return api.get('/dataset-split/source-files', { params })
}

// Dataset Assessment API
export function startDatasetAssessment(data) {
  return api.post('/dataset-assessment/start', data)
}

export function getDatasetAssessmentStatus(taskId) {
  return api.get(`/dataset-assessment/status/${taskId}`)
}

export function getDatasetAssessmentSourceFiles(params) {
  return api.get('/dataset-assessment/source-files', { params })
}

// Prompts for Assessment stage
export function getAssessmentPrompts(params) {
  return api.get('/prompts', { params })
}