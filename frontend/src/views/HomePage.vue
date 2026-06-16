<template>
  <div class="home-page">
    <!-- 顶部导航栏 -->
    <header class="home-nav">
      <div class="nav-inner">
        <a href="/" class="nav-brand">
          <svg viewBox="0 0 32 32" width="28" height="28" class="nav-logo">
            <rect x="2" y="2" width="28" height="28" rx="8" fill="none" stroke="currentColor" stroke-width="2.5"/>
            <text x="16" y="22" text-anchor="middle" font-size="14" font-weight="800" fill="currentColor" font-family="sans-serif">QA</text>
          </svg>
          <span class="nav-title">QA Studio</span>
        </a>
        <nav class="nav-links">
          <a href="https://gitee.com/yandddeeat/qa_gen" target="_blank" class="nav-link">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="margin-right:4px">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            Gitee
          </a>
        </nav>
      </div>
    </header>

    <!-- 粒子背景 -->
    <canvas ref="bgCanvas" class="bg-canvas"></canvas>

    <!-- Hero 区域 -->
    <section class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title">
          <span class="gradient-text">QA Studio</span>
        </h1>
        <p class="hero-tagline">以质量为中心的 AI 数据生成平台</p>
        <p class="hero-subtitle">好数据，好模型</p>
        <div class="hero-actions">
          <button class="btn-primary" @click="goLogin">开始使用</button>
          <a class="btn-secondary" href="https://gitee.com/yandddeeat/qa_gen" target="_blank">
            Gitee →
          </a>
        </div>
      </div>
    </section>

    <!-- 特性卡片 -->
    <section class="features-section">
      <div class="features-container">
        <div class="feature-card" v-for="f in features" :key="f.title">
          <span class="feature-icon">{{ f.icon }}</span>
          <h3 class="feature-title">{{ f.title }}</h3>
          <p class="feature-desc">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="home-footer">
      <p>Powered by Vue 3 & Element Plus</p>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const bgCanvas = ref(null)

const features = [
  { icon: '🧠', title: '智能生成', desc: '基于 LLM 自动生成高质量 QA 问答对，支持多种生成策略' },
  { icon: '🔍', title: '多级校验', desc: '问题校验、答案校验、CoT 质检，层层把关数据质量' },
  { icon: '⚙️', title: '流水线引擎', desc: '可视化流水线配置，从文本预处理到数据集导出全流程覆盖' },
  { icon: '📊', title: '数据评估', desc: '自动评估生成数据的多样性、一致性和覆盖度指标' },
  { icon: '🎯', title: 'CoT 标注', desc: '支持单/多 CoT 标注和 H-CoT 提示词模板管理' },
  { icon: '📦', title: '一键导出', desc: '支持多种格式导出，无缝对接模型训练流程' },
]

function goLogin() {
  router.push('/login')
}

// 粒子动画
onMounted(() => {
  const canvas = bgCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')

  function resize() {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  const particles = []
  const count = 50
  for (let i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 2 + 0.5,
      opacity: Math.random() * 0.4 + 0.15,
    })
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i]
      p.x += p.vx
      p.y += p.vy
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1

      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(129, 140, 248, ${p.opacity})`
      ctx.fill()

      for (let j = i + 1; j < particles.length; j++) {
        const p2 = particles[j]
        const dx = p.x - p2.x
        const dy = p.y - p2.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 130) {
          ctx.beginPath()
          ctx.moveTo(p.x, p.y)
          ctx.lineTo(p2.x, p2.y)
          ctx.strokeStyle = `rgba(129, 140, 248, ${0.06 * (1 - dist / 130)})`
          ctx.lineWidth = 0.5
          ctx.stroke()
        }
      }
    }
    requestAnimationFrame(draw)
  }
  draw()
})
</script>

<style>
/* 全局重置 */
html, body {
  margin: 0;
  padding: 0;
  background: #0f0c29;
}

.home-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
  color: #fff;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  position: relative;
}

/* ========== 顶部导航栏 ========== */
.home-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  backdrop-filter: blur(16px);
  background: rgba(15, 12, 41, 0.75);
  border-bottom: 1px solid rgba(139, 92, 246, 0.12);
}

.nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 2rem;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: #fff;
  font-weight: 600;
  font-size: 1.05rem;
}

.nav-logo {
  opacity: 0.9;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.nav-link {
  display: flex;
  align-items: center;
  color: #94a3b8;
  text-decoration: none;
  font-size: 0.9rem;
  transition: color 0.2s;
}

.nav-link:hover {
  color: #c4b5fd;
}

/* ========== 粒子背景 ========== */
.bg-canvas {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}

/* ========== Hero ========== */
.hero-section {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  text-align: center;
  padding: 6rem 2rem 4rem;
}

.hero-content {
  max-width: 600px;
}

.gradient-text {
  background: linear-gradient(135deg, #a78bfa 0%, #818cf8 40%, #6366f1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-title {
  font-size: 4.5rem;
  font-weight: 800;
  margin: 0;
  letter-spacing: -0.03em;
  line-height: 1.15;
  opacity: 0;
  animation: fadeInUp 0.8s ease forwards;
}

.hero-tagline {
  font-size: 1.4rem;
  color: #c4b5fd;
  margin: 1.25rem 0 0.5rem;
  font-weight: 500;
  opacity: 0;
  animation: fadeInUp 0.8s ease 0.15s forwards;
}

.hero-subtitle {
  font-size: 1rem;
  color: #94a3b8;
  margin: 0 0 2.5rem;
  opacity: 0;
  animation: fadeInUp 0.8s ease 0.3s forwards;
}

.hero-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  opacity: 0;
  animation: fadeInUp 0.8s ease 0.45s forwards;
}

.btn-primary {
  background: linear-gradient(135deg, #6366f1, #818cf8);
  color: #fff;
  border: none;
  padding: 0.8rem 2.5rem;
  border-radius: 10px;
  font-size: 1.05rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.06);
  color: #c4b5fd;
  border: 1px solid rgba(139, 92, 246, 0.25);
  padding: 0.8rem 2rem;
  border-radius: 10px;
  font-size: 1.05rem;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.3s;
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(139, 92, 246, 0.4);
  transform: translateY(-2px);
}

/* ========== 特性 ========== */
.features-section {
  position: relative;
  z-index: 1;
  padding: 2rem 2rem 6rem;
  max-width: 1100px;
  margin: 0 auto;
}

.features-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
}

.feature-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(139, 92, 246, 0.1);
  border-radius: 14px;
  padding: 1.75rem 1.5rem;
  transition: all 0.3s;
}

.feature-card:hover {
  border-color: rgba(139, 92, 246, 0.3);
  background: rgba(255, 255, 255, 0.07);
  transform: translateY(-3px);
}

.feature-icon {
  font-size: 1.8rem;
  display: block;
  margin-bottom: 0.75rem;
}

.feature-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: #e2e8f0;
  margin: 0 0 0.4rem;
}

.feature-desc {
  font-size: 0.875rem;
  color: #94a3b8;
  line-height: 1.6;
  margin: 0;
}

/* ========== Footer ========== */
.home-footer {
  position: relative;
  z-index: 1;
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.85rem;
  border-top: 1px solid rgba(139, 92, 246, 0.08);
}

.home-footer p {
  margin: 0;
}

/* ========== 动画 ========== */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ========== 响应式 ========== */
@media (max-width: 640px) {
  .hero-title { font-size: 2.8rem; }
  .hero-tagline { font-size: 1.1rem; }
  .hero-subtitle { font-size: 0.9rem; }
  .hero-actions { flex-direction: column; align-items: center; }
  .features-container { grid-template-columns: 1fr; }
  .nav-inner { padding: 0 1rem; }
}
</style>
