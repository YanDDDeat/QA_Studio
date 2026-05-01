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