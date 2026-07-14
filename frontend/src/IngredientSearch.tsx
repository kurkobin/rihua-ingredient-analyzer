import { useState, useEffect, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || ''

// ===== 类型定义 =====
interface IngredientSearchItem {
  id: number
  name: string
  category: string | null
  risk_level: string | null
  description: string | null
  reference: string | null
}

interface SearchResponse {
  total: number
  items: IngredientSearchItem[]
  categories: string[]
}

interface Props {
  onBack: () => void
}

// 风险等级 -> 标签样式(复用 App.tsx 的样式约定)
const RISK_TAG: Record<string, { cls: string; label: string }> = {
  '安全': { cls: 'safe', label: '安全' },
  '注意': { cls: 'notice', label: '注意' },
  '慎用': { cls: 'caution', label: '慎用' },
  '规避': { cls: 'avoid', label: '规避' },
}

function IngredientSearch({ onBack }: Props) {
  // 筛选状态
  const [keyword, setKeyword] = useState('')  // 成分名关键词
  const [category, setCategory] = useState('all')  // 分类
  const [riskLevel, setRiskLevel] = useState('all')  // 风险等级
  const [refKeyword, setRefKeyword] = useState('')  // 法规关键词

  // 数据
  const [results, setResults] = useState<IngredientSearchItem[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)  // 是否已搜索过(控制空状态提示)

  // 搜索函数(接收可选参数,避免闭包陈旧状态问题)
  const doSearch = useCallback(async (opts?: {
    name?: string
    category?: string
    riskLevel?: string
    refKeyword?: string
  }) => {
    setLoading(true)
    setError(null)
    try {
      // 优先用传入参数,否则用当前 state(用于按钮点击/回车)
      const n = opts?.name ?? keyword
      const c = opts?.category ?? category
      const r = opts?.riskLevel ?? riskLevel
      const ref = opts?.refKeyword ?? refKeyword

      // 拼 query string,空值不传
      const params = new URLSearchParams()
      if (n.trim()) params.set('name', n.trim())
      if (c !== 'all') params.set('category', c)
      if (r !== 'all') params.set('risk_level', r)
      if (ref.trim()) params.set('reference', ref.trim())
      params.set('limit', '200')  // 检索页允许更多结果

      const resp = await fetch(`${API_BASE}/api/ingredients/search?${params.toString()}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || `请求失败(${resp.status})`)
      }
      const data: SearchResponse = await resp.json()
      setResults(data.items)
      setTotal(data.total)
      setCategories(data.categories)
      setSearched(true)
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
  }, [keyword, category, riskLevel, refKeyword])

  // 首次加载:拉一次全量 + 获取分类列表
  useEffect(() => {
    doSearch({ name: '', category: 'all', riskLevel: 'all', refKeyword: '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 重置筛选(直接用空参数查询,避开 setState 异步问题)
  const handleReset = () => {
    setKeyword('')
    setCategory('all')
    setRiskLevel('all')
    setRefKeyword('')
    doSearch({ name: '', category: 'all', riskLevel: 'all', refKeyword: '' })
  }

  // 回车搜索
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') doSearch()
  }

  return (
    <div className="app">
      <header className="header">
        <h1>法规检索</h1>
        <p>查询成分库 {total} 条成分的分类、风险等级和法规依据</p>
      </header>

      <div className="topbar">
        <button className="link-btn" onClick={onBack}>
          ← 返回首页
        </button>
      </div>

      {/* 搜索区 */}
      <div className="search-box">
        <div className="search-row">
          <input
            type="text"
            placeholder="成分名(如:水杨酸、PPD)"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <input
            type="text"
            placeholder="法规关键词(如:安全技术规范、CIR)"
            value={refKeyword}
            onChange={(e) => setRefKeyword(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className="search-row">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="all">全部分类</option>
            {categories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
          <select
            value={riskLevel}
            onChange={(e) => setRiskLevel(e.target.value)}
          >
            <option value="all">全部风险等级</option>
            <option value="安全">安全</option>
            <option value="注意">注意</option>
            <option value="慎用">慎用</option>
            <option value="规避">规避</option>
          </select>
          <button className="btn btn-primary" onClick={() => doSearch()} disabled={loading}>
            {loading ? '搜索中...' : '🔍 搜索'}
          </button>
          <button className="btn btn-secondary" onClick={handleReset}>
            重置
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && <div className="error">⚠️ {error}</div>}

      {/* 结果计数 */}
      <div className="search-count">
        {loading ? '搜索中...' : `共 ${results.length} 条结果`}
      </div>

      {/* 结果列表 */}
      <div className="ingredient-list">
        {results.map(ing => {
          const tag = ing.risk_level ? RISK_TAG[ing.risk_level] : null
          return (
            <div className="ingredient-item" key={ing.id}>
              <div className="ingredient-detail">
                <div className="ingredient-name">{ing.name}</div>
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
        {searched && !loading && results.length === 0 && !error && (
          <div className="filter-empty">没有符合条件的成分</div>
        )}
      </div>
    </div>
  )
}

export default IngredientSearch
