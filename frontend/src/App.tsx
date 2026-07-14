import { useState, useRef, useMemo, useEffect } from 'react'
import History from './History'
import IngredientSearch from './IngredientSearch'

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
  history_id?: number  // 历史记录 id(用于导出 PDF)
}

// ===== 风险等级 -> 标签样式映射 =====
const RISK_TAG: Record<string, { cls: string; label: string }> = {
  '安全': { cls: 'safe', label: '安全' },
  '注意': { cls: 'notice', label: '注意' },
  '慎用': { cls: 'caution', label: '慎用' },
  '规避': { cls: 'avoid', label: '规避' },
}

// ===== 法规来源归类规则 =====
// 把 reference 字段(自由文本)归一为若干标准来源标签,用于筛选下拉
const REFERENCE_RULES: { keyword: string; label: string }[] = [
  { keyword: '安全技术规范', label: '化妆品安全技术规范(2015版)' },
  { keyword: '已使用原料目录', label: '国家药监局已使用原料目录(2021版)' },
  { keyword: 'GB 22115', label: 'GB 22115-2008 牙膏用原料规范' },
  { keyword: 'CIR', label: 'CIR 评估' },
  { keyword: '欧盟', label: '欧盟法规' },
  { keyword: 'IFRA', label: 'IFRA 标准' },
  { keyword: 'FDA', label: 'FDA' },
  { keyword: '常用成分', label: '常用成分(无明确法规)' },
  { keyword: '暂无明确法规', label: '暂无明确法规依据' },
  { keyword: '国家非处方药', label: '国家非处方药目录' },
]

// 把一条成分的 reference 文本归一为来源标签(命中第一个规则即返回)
function classifyReference(ref: string | null): string {
  if (!ref) return '暂无明确法规依据'
  for (const rule of REFERENCE_RULES) {
    if (ref.includes(rule.keyword)) return rule.label
  }
  return '其他'
}

// ===== 主组件 =====
function App() {
  const [image, setImage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // 页面切换:home=首页扫描,history=历史记录,search=法规检索
  const [page, setPage] = useState<'home' | 'history' | 'search'>('home')

  // ===== 成分筛选状态(结果页) =====
  const [filterRisk, setFilterRisk] = useState<string>('all')  // 风险等级
  const [filterCategory, setFilterCategory] = useState<string>('all')  // 成分分类
  const [filterReference, setFilterReference] = useState<string>('all')  // 法规来源
  const [onlyInDb, setOnlyInDb] = useState<boolean>(false)  // 仅入库成分

  // 成分详情弹窗:选中的成分(null=关闭)
  const [selectedIngredient, setSelectedIngredient] = useState<IngredientInfo | null>(null)

  // 从当前结果中动态提取「分类」和「法规来源」选项
  const categoryOptions = useMemo(() => {
    if (!result) return [] as string[]
    const set = new Set<string>()
    result.ingredients.forEach(ing => {
      if (ing.category) set.add(ing.category)
    })
    return Array.from(set).sort()
  }, [result])

  const referenceOptions = useMemo(() => {
    if (!result) return [] as string[]
    const set = new Set<string>()
    result.ingredients.forEach(ing => {
      set.add(classifyReference(ing.reference))
    })
    return Array.from(set).sort()
  }, [result])

  // 过滤后的成分列表
  const filteredIngredients = useMemo(() => {
    if (!result) return [] as IngredientInfo[]
    return result.ingredients.filter(ing => {
      // 仅入库成分
      if (onlyInDb && !ing.in_database) return false
      // 风险等级
      if (filterRisk !== 'all' && ing.risk_level !== filterRisk) return false
      // 成分分类
      if (filterCategory !== 'all' && ing.category !== filterCategory) return false
      // 法规来源
      if (filterReference !== 'all') {
        const refLabel = classifyReference(ing.reference)
        if (refLabel !== filterReference) return false
      }
      return true
    })
  }, [result, onlyInDb, filterRisk, filterCategory, filterReference])

  // 新结果返回时重置筛选器
  const resetFilters = () => {
    setFilterRisk('all')
    setFilterCategory('all')
    setFilterReference('all')
    setOnlyInDb(false)
  }

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
      resetFilters()  // 新结果重置筛选状态
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

  // 查看历史详情(从历史记录页返回时,把 JSON 解析成结果展示)
  const handleViewHistory = (resultJson: string, historyId: number) => {
    try {
      const data: AnalysisResponse = JSON.parse(resultJson)
      data.history_id = historyId  // 补上 history_id 供导出 PDF
      setResult(data)
      resetFilters()  // 重置筛选状态
      setImage(null)
      setError(null)
      setPage('home')
    } catch {
      setError('无法加载历史记录详情')
    }
  }

  // 导出 PDF 报告
  const handleExportPDF = async () => {
    if (!result?.history_id) {
      setError('无法导出:缺少历史记录 ID')
      return
    }
    try {
      const resp = await fetch(`${API_BASE}/api/report/${result.history_id}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '导出失败')
      }
      // 触发浏览器下载
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      // 从响应头获取文件名,或用默认名
      const disposition = resp.headers.get('Content-Disposition') || ''
      const filenameMatch = disposition.match(/filename\*=UTF-8''(.+)/)
      const filename = filenameMatch
        ? decodeURIComponent(filenameMatch[1])
        : '成分分析报告.pdf'
      a.download = filename
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

  return (
    <div className="app">
      <header className="header">
        <h1>成分扫一扫</h1>
        <p>上传商品配料表图片,看清商品真实的样子</p>
      </header>

      {/* 顶部导航:历史记录 + 法规检索 */}
      <div className="topbar">
        <button className="link-btn" onClick={() => setPage('history')}>
          📋 历史记录
        </button>
        <button className="link-btn" onClick={() => setPage('search')}>
          🔍 法规检索
        </button>
      </div>

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

            {/* 筛选条 */}
            <div className="filter-bar">
              <div className="filter-item">
                <label>风险等级</label>
                <select
                  value={filterRisk}
                  onChange={(e) => setFilterRisk(e.target.value)}
                >
                  <option value="all">全部</option>
                  <option value="安全">安全</option>
                  <option value="注意">注意</option>
                  <option value="慎用">慎用</option>
                  <option value="规避">规避</option>
                </select>
              </div>
              <div className="filter-item">
                <label>成分分类</label>
                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                >
                  <option value="all">全部</option>
                  {categoryOptions.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              <div className="filter-item">
                <label>法规来源</label>
                <select
                  value={filterReference}
                  onChange={(e) => setFilterReference(e.target.value)}
                >
                  <option value="all">全部</option>
                  {referenceOptions.map(ref => (
                    <option key={ref} value={ref}>{ref}</option>
                  ))}
                </select>
              </div>
              <div className="filter-item filter-checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={onlyInDb}
                    onChange={(e) => setOnlyInDb(e.target.checked)}
                  />
                  仅入库成分
                </label>
              </div>
            </div>

            {/* 筛选计数 */}
            <div className="filter-count">
              显示 {filteredIngredients.length} / 共 {result.ingredients.length} 项
            </div>

            {/* 过滤后成分列表 */}
            {filteredIngredients.map((ing) => {
              const tag = ing.risk_level ? RISK_TAG[ing.risk_level] : null
              return (
                <div
                  className="ingredient-item ingredient-clickable"
                  key={ing.name}
                  onClick={() => setSelectedIngredient(ing)}
                >
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
            {filteredIngredients.length === 0 && (
              <div className="filter-empty">没有符合筛选条件的成分</div>
            )}
          </div>

          {/* OCR 原文 */}
          <div className="ocr-text">
            <h3>识别原文</h3>
            <pre>{result.ocr_text}</pre>
          </div>

          {/* 导出 PDF */}
          {result.history_id && (
            <button
              className="btn btn-primary"
              onClick={handleExportPDF}
              style={{ marginTop: 16 }}
            >
              📄 导出 PDF 报告
            </button>
          )}
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
    </div>
  )
}

// ===== 成分详情弹窗组件 =====
interface ModalProps {
  ingredient: IngredientInfo
  allIngredients: IngredientInfo[]
  onClose: () => void
  onSelect: (ing: IngredientInfo) => void
}

function IngredientDetailModal({ ingredient, allIngredients, onClose, onSelect }: ModalProps) {
  const tag = ingredient.risk_level ? RISK_TAG[ingredient.risk_level] : null

  // 同类成分推荐(同 category,排除自己,最多 8 个)
  const related = ingredient.category
    ? allIngredients.filter(
        ing => ing.category === ingredient.category && ing.name !== ingredient.name
      ).slice(0, 8)
    : []

  // 全局监听 ESC 键关闭弹窗(不依赖焦点位置)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // 点击遮罩关闭(仅当点击的是 backdrop 本身而非内部内容)
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className="modal-backdrop"
      onClick={handleBackdropClick}
    >
      <div className="modal-content">
        {/* 关闭按钮 */}
        <button className="modal-close" onClick={onClose} aria-label="关闭">
          ✕
        </button>

        {/* 成分名 */}
        <h2 className="modal-title">
          {ingredient.name}
          {!ingredient.in_database && <span className="db-badge">未入库</span>}
        </h2>

        {/* 标签区 */}
        <div className="modal-tags">
          {tag && (
            <span className={`tag tag-lg ${tag.cls}`}>{tag.label}</span>
          )}
          {ingredient.category && (
            <span className="tag tag-lg unknown">{ingredient.category}</span>
          )}
        </div>

        {/* 描述 */}
        {ingredient.description && (
          <div className="modal-section">
            <h4>说明</h4>
            <p className="modal-desc">{ingredient.description}</p>
          </div>
        )}

        {/* 法规依据 */}
        {ingredient.reference && (
          <div className="modal-section">
            <h4>📖 法规依据</h4>
            <p className="modal-ref">{ingredient.reference}</p>
          </div>
        )}

        {/* 同类成分 */}
        {related.length > 0 && (
          <div className="modal-section">
            <h4>同类成分({ingredient.category})</h4>
            <div className="modal-related">
              {related.map(ing => {
                const rtag = ing.risk_level ? RISK_TAG[ing.risk_level] : null
                return (
                  <button
                    key={ing.name}
                    className="related-chip"
                    onClick={() => onSelect(ing)}
                  >
                    <span className="related-name">{ing.name}</span>
                    {rtag && <span className={`related-risk ${rtag.cls}`}>{rtag.label}</span>}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* 无信息提示 */}
        {!ingredient.description && !ingredient.reference && (
          <div className="modal-section">
            <p className="modal-empty">该成分暂无详细信息</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
