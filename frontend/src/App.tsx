import { useState, useRef } from 'react'

// ===== API 基础地址 =====
// 本地开发:走 Vite 代理(相对路径 /api)
// 生产环境(Vercel):直接调用 Render 后端地址
const API_BASE = import.meta.env.VITE_API_BASE || ''

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
        // 计算缩放比例
        let { width, height } = img
        if (width > MAX_WIDTH || height > MAX_HEIGHT) {
          const ratio = Math.min(MAX_WIDTH / width, MAX_HEIGHT / height)
          width = Math.round(width * ratio)
          height = Math.round(height * ratio)
        }

        // 用 canvas 压缩
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

// ===== 类型定义 =====
interface IngredientInfo {
  name: string
  category: string | null
  risk_level: string | null
  description: string | null
  in_database: boolean
  reference: string | null
}

interface AnalysisResponse {
  ocr_text: string
  ingredients: IngredientInfo[]
  pros: string[]
  cons: string[]
  score: number
  summary: string
  product_type: string
}

// ===== 风险等级 -> 标签样式映射 =====
const RISK_TAG: Record<string, { cls: string; label: string }> = {
  '安全': { cls: 'safe', label: '安全' },
  '注意': { cls: 'notice', label: '注意' },
  '慎用': { cls: 'caution', label: '慎用' },
  '规避': { cls: 'avoid', label: '规避' },
}

// ===== 主组件 =====
function App() {
  const [image, setImage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  // 拖拽上传
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  // 调用后端分析
  const handleAnalyze = async () => {
    if (!image) return
    setLoading(true)
    setError(null)
    try {
      // base64 转 File,然后压缩
      const res = await fetch(image)
      const originalBlob = await res.blob()
      const file = new File([originalBlob], 'upload.jpg', { type: originalBlob.type })

      // 压缩图片(大图压缩后避免 OCR 超时)
      let compressedBlob: Blob
      try {
        compressedBlob = await compressImage(file)
      } catch {
        // 压缩失败时回退到原图
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
      setResult(data)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '未知错误'
      // 友好提示网络错误
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        setError('网络连接失败,请检查网络或稍后重试')
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  // 评分颜色
  const scoreClass = result
    ? result.score >= 86 ? 'good' : result.score >= 60 ? 'mid' : 'bad'
    : 'mid'

  return (
    <div className="app">
      <header className="header">
        <h1>成分扫一扫</h1>
        <p>上传商品配料表图片,看清商品真实的样子</p>
      </header>

      {/* 上传区 */}
      <div
        className={`upload-area ${image ? 'has-image' : ''}`}
        onClick={() => fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
      >
        {image ? (
          <img src={image} alt="配料表预览" />
        ) : (
          <>
            <div className="upload-icon">📷</div>
            <div className="upload-tip">点击或拖拽上传配料表图片</div>
          </>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleInputChange}
          style={{ display: 'none' }}
        />
      </div>

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
          {/* 产品品类 + 评分卡片 */}
          <div className="score-card">
            {result.product_type && (
              <div className="product-type">📋 产品类型: {result.product_type}</div>
            )}
            <div className={`score-number ${scoreClass}`}>{result.score}</div>
            <div className="score-label">综合评分(满分100)</div>
            <div className="summary">{result.summary}</div>
          </div>

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

          {/* 成分列表(显示全部) */}
          <div className="ingredient-list">
            <h3>成分列表(共{result.ingredients.length}项)</h3>
            {result.ingredients.map((ing, i) => {
              const tag = ing.risk_level ? RISK_TAG[ing.risk_level] : null
              return (
                <div className="ingredient-item" key={i}>
                  <div className="ingredient-detail">
                    <div className="ingredient-name">
                      {ing.name}
                      {!ing.in_database && <span className="db-badge">未入库</span>}
                    </div>
                    {ing.description && (
                      <div className="ingredient-desc">{ing.description}</div>
                    )}
                    {ing.reference && (
                      <div className="ingredient-ref">📖 {ing.reference}</div>
                    )}
                  </div>
                  <div className="ingredient-meta">
                    {ing.category && (
                      <span className="tag unknown">{ing.category}</span>
                    )}
                    {tag && (
                      <span className={`tag ${tag.cls}`}>{tag.label}</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* OCR 原文 */}
          <div className="ocr-text">
            <h3>识别原文</h3>
            <pre>{result.ocr_text}</pre>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
