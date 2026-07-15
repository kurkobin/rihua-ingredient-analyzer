import { useState } from 'react'
import {
  API_BASE,
  AnalysisResponse,
  IngredientInfo,
} from './constants'
import UploadArea from './components/UploadArea'
import ScoreCard from './components/ScoreCard'
import RiskChart from './components/RiskChart'
import Alerts from './components/Alerts'
import IngredientList from './components/IngredientList'
import IngredientDetailModal from './components/IngredientDetailModal'
import History from './History'
import IngredientSearch from './IngredientSearch'
import AllergenSettings from './AllergenSettings'
import { saveHistory, checkAllergenAlerts } from './storage'

// ===== 图片压缩 =====
// 大图片(3-4MB)直接上传会导致 OCR 超时,上传前先压缩
// 目标:长边不超过 1600px,质量 0.8,通常能压到 500KB 以内
async function compressImage(file: File): Promise<Blob> {
  const MAX_WIDTH = 1600
  const MAX_HEIGHT = 1600
  const QUALITY = 0.8

  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        let { width, height } = img
        if (width > MAX_WIDTH || height > MAX_HEIGHT) {
          const ratio = Math.min(MAX_WIDTH / width, MAX_HEIGHT / height)
          width = Math.round(width * ratio)
          height = Math.round(height * ratio)
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('无法创建 canvas 上下文'))
          return
        }
        ctx.drawImage(img, 0, 0, width, height)
        canvas.toBlob(
          (blob) => {
            if (blob) resolve(blob)
            else reject(new Error('图片压缩失败'))
          },
          'image/jpeg',
          QUALITY
        )
      }
      img.onerror = () => reject(new Error('图片加载失败'))
      img.src = e.target?.result as string
    }
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

// ===== 主组件 =====
function App() {
  const [image, setImage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState<'home' | 'history' | 'search' | 'allergen'>('home')
  const [selectedIngredient, setSelectedIngredient] = useState<IngredientInfo | null>(null)

  // 选择图片
  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError('请上传图片文件')
      return
    }
    const reader = new FileReader()
    reader.onload = (e) => {
      setImage(e.target?.result as string)
      setResult(null)
      setError(null)
    }
    reader.readAsDataURL(file)
  }

  // 调用后端分析
  const handleAnalyze = async () => {
    if (!image) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(image)
      const originalBlob = await res.blob()
      const file = new File([originalBlob], 'upload.jpg', { type: originalBlob.type })

      let compressedBlob: Blob
      try {
        compressedBlob = await compressImage(file)
      } catch {
        compressedBlob = originalBlob
      }

      const formData = new FormData()
      formData.append('image', compressedBlob, 'upload.jpg')

      const resp = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData,
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || `请求失败(${resp.status})`)
      }
      const data: AnalysisResponse = await resp.json()

      // 前端做过敏原检查(基于本地 localStorage)
      const allergenAlerts = checkAllergenAlerts(data.ingredients)
      data.allergen_alerts = allergenAlerts

      // 保存到本地历史记录
      saveHistory(data)

      setResult(data)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '未知错误'
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        setError('网络连接失败,请检查网络或稍后重试')
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  // 查看历史详情
  const handleViewHistory = (resultJson: string, historyId: number) => {
    try {
      const data: AnalysisResponse = JSON.parse(resultJson)
      data.history_id = historyId
      setResult(data)
      setImage(null)
      setError(null)
      setPage('home')
    } catch {
      setError('无法加载历史记录详情')
    }
  }

  // 导出 PDF 报告
  const handleExportPDF = async () => {
    if (!result) return
    try {
      const resp = await fetch(`${API_BASE}/api/report/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(result),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '导出失败')
      }
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = '成分分析报告.pdf'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : '导出失败')
    }
  }

  // 历史记录页
  if (page === 'history') {
    return <History onBack={() => setPage('home')} onView={handleViewHistory} />
  }

  // 法规检索页
  if (page === 'search') {
    return <IngredientSearch onBack={() => setPage('home')} />
  }

  // 过敏原设置页
  if (page === 'allergen') {
    return <AllergenSettings onBack={() => setPage('home')} />
  }

  return (
    <div className="app">
      <header className="header">
        <h1>成分扫一扫</h1>
        <p>上传商品配料表图片,看清商品真实的样子</p>
      </header>

      {/* 顶部导航 */}
      <div className="topbar">
        <button className="link-btn" onClick={() => setPage('history')}>
          📋 历史记录
        </button>
        <button className="link-btn" onClick={() => setPage('search')}>
          🔍 法规检索
        </button>
        <button className="link-btn" onClick={() => setPage('allergen')}>
          ⚠️ 过敏原
        </button>
      </div>

      {/* 产品理念横幅(仅首页未分析时显示) */}
      {!result && !loading && (
        <>
          <div className="hero-banner">
            <div className="hero-slogan">看清商品真实的样子</div>
            <div className="hero-desc">
              帮你识别 264 种成分,做出明智选择。拍照上传配料表,
              30 秒看懂优缺点、风险预警与替代建议。
            </div>
          </div>

          <div className="stats-cards">
            <div className="stat-card">
              <div className="stat-number">264</div>
              <div className="stat-label">种成分收录</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">8</div>
              <div className="stat-label">大法规来源</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">10</div>
              <div className="stat-label">类产品覆盖</div>
            </div>
          </div>
        </>
      )}

      {/* 上传区 */}
      <UploadArea image={image} onFile={handleFile} />

      {/* 分析按钮 */}
      <button
        className="btn btn-primary"
        onClick={handleAnalyze}
        disabled={!image || loading}
      >
        {loading ? '分析中...' : '开始分析'}
      </button>

      {/* 错误提示 */}
      {error && <div className="error">⚠️ {error}</div>}

      {/* 加载状态 */}
      {loading && (
        <div className="loading">
          <div className="spinner" />
          <div className="loading-steps">
            <div>正在压缩图片...</div>
            <div>正在 OCR 识别文字...</div>
            <div>正在分析成分...</div>
          </div>
          <div className="loading-tip">分析约需 10-30 秒,请耐心等待</div>
        </div>
      )}

      {/* 分析结果 */}
      {result && !loading && (
        <div className="result">
          <ScoreCard result={result} />
          <RiskChart result={result} />

          {/* 优缺点 */}
          <div className="pros-cons">
            <div className="card pros">
              <h3>✅ 优点</h3>
              {result.pros.length > 0 ? (
                <ul>
                  {result.pros.map((p, i) => <li key={i}>{p}</li>)}
                </ul>
              ) : (
                <div style={{ color: '#b2bec3', fontSize: 14 }}>暂未发现明显优点</div>
              )}
            </div>
            <div className="card cons">
              <h3>⚠️ 缺点</h3>
              {result.cons.length > 0 ? (
                <ul>
                  {result.cons.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              ) : (
                <div style={{ color: '#b2bec3', fontSize: 14 }}>未发现明显缺点</div>
              )}
            </div>
          </div>

          {/* 智能预警区 */}
          <Alerts result={result} onManageAllergens={() => setPage('allergen')} />

          {/* 成分列表 */}
          <IngredientList result={result} onSelect={setSelectedIngredient} />

          {/* OCR 原文 */}
          <div className="ocr-text">
            <h3>识别原文</h3>
            <pre>{result.ocr_text}</pre>
          </div>

          {/* 导出 PDF */}
          <button
            className="btn btn-primary"
            onClick={handleExportPDF}
            style={{ marginTop: 16 }}
          >
            📄 导出 PDF 报告
          </button>
        </div>
      )}

      {/* 成分详情弹窗 */}
      {selectedIngredient && result && (
        <IngredientDetailModal
          ingredient={selectedIngredient}
          allIngredients={result.ingredients}
          onClose={() => setSelectedIngredient(null)}
          onSelect={(ing) => setSelectedIngredient(ing)}
        />
      )}

      {/* 页脚 */}
      <footer className="footer">
        <div className="footer-section">
          <h4>📚 数据来源</h4>
          <p>《化妆品安全技术规范》(2015版)、《牙膏用原料规范》GB 22115-2008、CIR 评估报告、IFRA 标准、欧盟化妆品法规</p>
        </div>
        <div className="footer-section">
          <h4>⚠️ 免责声明</h4>
          <p>本工具分析结果仅供参考,不替代专业医疗建议。成分风险等级基于公开法规和评估数据,实际使用感受因人而异。如有严重过敏史,请咨询专业医生。</p>
        </div>
        <div className="footer-bottom">
          <span>成分扫一扫 · 日化洗护成分分析工具</span>
          <a
            href="https://github.com/kurkobin/rihua-ingredient-analyzer"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-link"
          >
            🐙 GitHub 仓库
          </a>
        </div>
      </footer>
    </div>
  )
}

export default App
