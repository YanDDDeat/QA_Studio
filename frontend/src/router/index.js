import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    redirect: '/question-generate',
    component: () => import('../views/Layout.vue'),
    children: [
      {
        path: 'text-preprocess',
        name: 'TextPreprocess',
        component: () => import('../views/TextPreprocess.vue'),
        meta: { title: '文本预处理' },
      },
      {
        path: 'cot-hcot-workflows',
        name: 'CotHcotWorkflows',
        component: () => import('../views/CotHcot/WorkflowList.vue'),
        meta: { title: 'CoT/H-CoT 标注' },
      },
      {
        path: 'cot-hcot-workflows/:id',
        name: 'CotHcotWorkflowDetail',
        component: () => import('../views/CotHcot/WorkflowDetail.vue'),
        meta: { title: '标注流水线详情' },
      },
      {
        path: 'professional-cot-runs',
        name: 'ProfessionalCotRuns',
        component: () => import('../views/CotHcot/ProfessionalCotList.vue'),
        meta: { title: '标注流水线2：专业 CoT 构建' },
      },
      {
        path: 'professional-cot-runs/:id',
        name: 'ProfessionalCotRunDetail',
        component: () => import('../views/CotHcot/ProfessionalCotDetail.vue'),
        meta: { title: '标注流水线2详情' },
      },
      {
        path: 'question-generate',
        name: 'QuestionGenerate',
        component: () => import('../views/QuestionGenerate.vue'),
        meta: { title: '问题生成', stage: 'question_generate' },
      },
      {
        path: 'knowledge-generate',
        name: 'KnowledgeGenerate',
        component: () => import('../views/KnowledgeGenerate.vue'),
        meta: { title: '知识体系生成', stage: 'knowledge_generate' },
      },
      {
        path: 'question-validate',
        name: 'QuestionValidate',
        component: () => import('../views/QuestionValidate.vue'),
        meta: { title: '问题校验', stage: 'question_validate' },
      },
      {
        path: 'answer-generate',
        name: 'AnswerGenerate',
        component: () => import('../views/AnswerGenerate.vue'),
        meta: { title: '答案生成', stage: 'answer_generate' },
      },
      {
        path: 'answer-validate',
        name: 'AnswerValidate',
        component: () => import('../views/AnswerValidate.vue'),
        meta: { title: '答案校验', stage: 'answer_validate' },
      },
      {
        path: 'data-evaluate',
        name: 'DataEvaluate',
        component: () => import('../views/DataEvaluate.vue'),
        meta: { title: '数据评估', stage: 'data_evaluate' },
      },
      {
        path: 'quality-check',
        name: 'QualityCheck',
        component: () => import('../views/QualityCheck.vue'),
        meta: { title: '质检', stage: 'quality_check' },
      },
      {
        path: 'cot-filter',
        name: 'CotFilter',
        component: () => import('../views/CotFilter.vue'),
        meta: { title: 'COT过滤', stage: 'cot_filter' },
      },
      {
        path: 'dataset-processing',
        name: 'DatasetProcessing',
        component: () => import('../views/DatasetProcessing.vue'),
        meta: { title: '测试集切分', stage: 'dataset_processing' },
      },
      {
        path: 'generic-generate',
        name: 'GenericGenerate',
        component: () => import('../views/GenericGenerate.vue'),
        meta: { title: '通用生成', stage: 'generic' },
      },
      {
        path: 'data-manage',
        name: 'DataManage',
        component: () => import('../views/DataManage.vue'),
        meta: { title: '数据管理' },
      },
      {
        path: 'config-center',
        name: 'ConfigCenter',
        component: () => import('../views/ConfigCenter.vue'),
        meta: { title: '配置中心' },
      },
      {
        path: 'file-manage',
        name: 'FileManage',
        component: () => import('../views/FileManage.vue'),
        meta: { title: '文件管理' },
      },
      {
        path: 'user-manage',
        name: 'UserManage',
        component: () => import('../views/UserManage.vue'),
        meta: { title: '用户管理' },
      },
      {
        path: 'my-tasks',
        name: 'MyTasks',
        component: () => import('../views/MyTasks.vue'),
        meta: { title: '我的任务' },
      },
      {
        path: 'json-merge-tool',
        name: 'JsonMergeTool',
        component: () => import('../views/JsonMergeTool.vue'),
        meta: { title: 'JSON 文件合并工具' },
      },
      {
        path: 'gzip-upload-test',
        name: 'GzipUploadTest',
        component: () => import('../views/GzipUploadTest.vue'),
        meta: { title: 'Gzip 压缩上传测试' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard - redirect to login if not authenticated
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router
