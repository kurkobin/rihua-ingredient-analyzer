import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_BASE || ''

interface HistoryItem {
  id: number
  img_hash: string
  product_type: string | null
  summary: string | null
  score: number | null
  ingredient_count: number | null
  created_at: string
}

interface CompareItem {
  id: number
  product_type: string
  score: number
  pros: string[]
  cons: string[]
  ingredient_names: string[]
}

interface CompareResult {
  items: CompareItem[]
  common_ingredients: string[]
  unique_ingredients: Record<number, string[]>
}

interface Props {
  onBack: () => void
  onView: (result: string, historyId: number) => void  // 查看详情,传 result_json 和 id
}

// 格式化时间
function formatTime(iso: string): string {
  const d = new Date(iso)
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hour = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hour}:${min}`
}

// 趋势图用的短时间格式(月-日)
function formatChartTime(iso: string): string {
  const d = new Date(iso)
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

// 评分颜色
function scoreClass(score: number | null): string {
  if (score === null) return 'mid'
  if (score >= 86) return 'good'
  if (score >= 60) return 'mid'
  return 'bad'
}

function History({ onBack, onView }: Props) {
  const [list, setList] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [comparing, setComparing] = useState(false)
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null)
  // 独立的勾选模式开关(不再用 -1 哨兵)
  const [selectMode, setSelectMode] = useState(false)

  const fetchHistory = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/history`)
      if (!resp.ok) throw new Error('获取历史记录失败')
      const data: HistoryItem[] = await resp.json()
      setList(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHistory()
  }, [])

  // 趋势图数据:把 list 反转(最早→最晚),过滤无评分项
  const chartData = useMemo(() => {
    return [...list]
      .filter(item => item.score !== null)
      .reverse()  // 原本是倒序,反转成时间正序
      .map((item, idx) => ({
        idx: idx + 1,  // 序号(1,2,3...)
        score: item.score as number,
        label: formatChartTime(item.created_at),
        productType: item.product_type || '未知产品',
      }))
  }, [list])

  // 评分平均值(参考线)
  const avgScore = useMemo(() => {
    if (chartData.length === 0) return 0
    const sum = chartData.reduce((acc, d) => acc + d.score, 0)
    return Math.round(sum / chartData.length)
  }, [chartData])

  // 查看详情
  const handleView = async (id: number) => {
    // 如果在勾选模式,点击切换勾选;否则查看详情
    if (selectMode) {
      toggleSelect(id)
      return
    }
    try {
      const resp = await fetch(`${API_BASE}/api/history/${id}`)
      if (!resp.ok) throw new Error('获取详情失败')
      const detail = await resp.json()
      onView(detail.result_json, id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    }
  }

  // 切换勾选
  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        if (next.size >= 5) return prev  // 最多选 5 个
        next.add(id)
      }
      return next
    })
  }

  // 删除单条
  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('确定删除这条记录?')) return
    try {
      const resp = await fetch(`${API_BASE}/api/history/${id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('删除失败')
      setList(list.filter((item) => item.id !== id))
      setSelected((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    }
  }

  // 清空全部
  const handleClearAll = async () => {
    if (list.length === 0) return
    if (!confirm(`确定清空全部 ${list.length} 条记录?此操作不可恢复。`)) return
    try {
      const resp = await fetch(`${API_BASE}/api/history`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('清空失败')
      setList([])
      setSelected(new Set())
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    }
  }

  // 对比选中
  const handleCompare = async () => {
    if (selected.size < 2) {
      setError('请至少选择 2 条记录进行对比')
      return
    }
    setComparing(true)
    setError(null)
    try {
      const ids = Array.from(selected).join(',')
      const resp = await fetch(`${API_BASE}/api/compare?ids=${ids}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '对比失败')
      }
      const data: CompareResult = await resp.json()
      setCompareResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setComparing(false)
    }
  }

  // 退出勾选模式
  const exitSelectMode = () => {
    setSelected(new Set())
    setSelectMode(false)
    setCompareResult(null)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>历史记录</h1>
        <p>共 {list.length} 条分析记录</p>
      </header>

      <div className="history-actions">
        <button className="btn btn-secondary" onClick={onBack}>
          ← 返回
        </button>
        {selectMode && (
          <>
            <span className="select-count">已选 {selected.size}/5</span>
            <button
              className="btn btn-primary"
              onClick={handleCompare}
              disabled={comparing || selected.size < 2}
            >
              {comparing ? '对比中...' : `📊 对比 (${selected.size})`}
            </button>
            <button className="btn btn-secondary" onClick={exitSelectMode}>
              取消
            </button>
          </>
        )}
        {!selectMode && list.length > 0 && (
          <button className="btn btn-secondary" onClick={() => setSelectMode(true)}>
            📊 选择对比
          </button>
        )}
        {!selectMode && list.length > 0 && (
          <button className="btn btn-danger" onClick={handleClearAll}>
            清空全部
          </button>
        )}
      </div>

      {/* 勾选模式提示 */}
      {selectMode && !compareResult && (
        <div className="select-tip">
          点击记录进行勾选,选 2-5 条后点"对比"
        </div>
      )}

      {error && <div className="error">⚠️ {error}</div>}

      {/* 对比结果 */}
      {compareResult && (
        <CompareView result={compareResult} onClose={() => setCompareResult(null)} />
      )}

      {!compareResult && (
        <>
          {loading ? (
            <div className="loading">
              <div className="spinner" />
              <div>加载中...</div>
            </div>
          ) : list.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📋</div>
              <p>还没有分析记录</p>
              <p className="empty-tip">返回首页扫描配料表,记录会自动保存</p>
            </div>
          ) : (
            <>
              {/* 评分趋势图(2 条以上评分数据才显示) */}
              {chartData.length >= 2 && !compareResult && (
                <div className="chart-card">
                  <h3>📊 评分趋势</h3>
                  <p className="chart-summary">
                    共 {chartData.length} 次扫描 · 平均 {avgScore} 分
                  </p>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart
                      data={chartData}
                      margin={{ top: 10, right: 16, left: -16, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f2f6" />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 11, fill: '#636e72' }}
                      />
                      <YAxis
                        domain={[0, 100]}
                        ticks={[0, 20, 40, 60, 80, 100]}
                        tick={{ fontSize: 11, fill: '#636e72' }}
                      />
                      <Tooltip
                        contentStyle={{
                          fontSize: 12,
                          borderRadius: 8,
                          border: '1px solid #f1f2f6',
                        }}
                        labelStyle={{ color: '#636e72' }}
                        formatter={(value) => [`${value} 分`, '评分']}
                        labelFormatter={(label, payload) => {
                          const p = payload?.[0]?.payload as { productType?: string } | undefined
                          return p?.productType ? `${label} · ${p.productType}` : `${label}`
                        }}
                      />
                      <ReferenceLine
                        y={avgScore}
                        stroke="#fdcb6e"
                        strokeDasharray="5 5"
                        label={{ value: `均值 ${avgScore}`, fontSize: 10, fill: '#fdcb6e' }}
                      />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="#0984e3"
                        strokeWidth={2}
                        dot={{ r: 4, fill: '#0984e3' }}
                        activeDot={{ r: 6 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

            <div className="history-list">
              {list.map((item) => (
                <div
                  key={item.id}
                  className={`history-card ${selected.has(item.id) ? 'selected' : ''}`}
                  onClick={() => handleView(item.id)}
                >
                  {selectMode && (
                    <div className="history-checkbox">
                      <input
                        type="checkbox"
                        checked={selected.has(item.id)}
                        onChange={() => toggleSelect(item.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  )}
                  <div className="history-card-left">
                    <div className={`history-score ${scoreClass(item.score)}`}>
                      {item.score ?? '--'}
                    </div>
                  </div>
                  <div className="history-card-body">
                    <div className="history-product">
                      {item.product_type || '未知产品'}
                    </div>
                    <div className="history-summary">
                      {item.summary || '暂无简评'}
                    </div>
                    <div className="history-meta">
                      <span>🧪 {item.ingredient_count ?? 0} 种成分</span>
                      <span>🕐 {formatTime(item.created_at)}</span>
                    </div>
                  </div>
                  {!selectMode && (
                    <button
                      className="history-delete"
                      onClick={(e) => handleDelete(item.id, e)}
                      title="删除"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

// ===== 对比结果展示组件 =====
function CompareView({ result, onClose }: { result: CompareResult; onClose: () => void }) {
  const { items, common_ingredients, unique_ingredients } = result

  return (
    <div className="compare-view">
      <div className="compare-header">
        <h2>📊 成分对比</h2>
        <button className="btn btn-secondary" onClick={onClose}>关闭</button>
      </div>

      {/* 评分对比 */}
      <div className="compare-section">
        <h3>评分对比</h3>
        <div className="compare-scores">
          {items.map((item) => (
            <div key={item.id} className="compare-score-card">
              <div className={`history-score ${scoreClass(item.score)}`}>
                {item.score}
              </div>
              <div className="compare-product-name">{item.product_type}</div>
              <div className="compare-ingredient-count">
                {item.ingredient_names.length} 种成分
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 优缺点对比 */}
      <div className="compare-section">
        <h3>优缺点对比</h3>
        <div className="compare-pros-cons">
          {items.map((item) => (
            <div key={item.id} className="compare-pc-card">
              <h4>{item.product_type}</h4>
              <div className="compare-pros">
                <strong>✅ 优点</strong>
                <ul>
                  {item.pros.length > 0 ? (
                    item.pros.map((p, i) => <li key={i}>{p}</li>)
                  ) : (
                    <li className="muted">暂无</li>
                  )}
                </ul>
              </div>
              <div className="compare-cons">
                <strong>⚠️ 缺点</strong>
                <ul>
                  {item.cons.length > 0 ? (
                    item.cons.map((c, i) => <li key={i}>{c}</li>)
                  ) : (
                    <li className="muted">暂无</li>
                  )}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 共有成分 */}
      <div className="compare-section">
        <h3>共有成分({common_ingredients.length}种)</h3>
        <p className="compare-desc">这些产品都含有的成分</p>
        {common_ingredients.length > 0 ? (
          <div className="tag-list">
            {common_ingredients.map((name, i) => (
              <span key={i} className="ingredient-tag common">{name}</span>
            ))}
          </div>
        ) : (
          <p className="muted">无共有成分</p>
        )}
      </div>

      {/* 独有成分 */}
      <div className="compare-section">
        <h3>独有成分</h3>
        <p className="compare-desc">各自特有、其他产品没有的成分</p>
        {items.map((item) => {
          const unique = unique_ingredients[item.id] || []
          return (
            <div key={item.id} className="unique-section">
              <h4>{item.product_type}({unique.length}种)</h4>
              {unique.length > 0 ? (
                <div className="tag-list">
                  {unique.map((name, i) => (
                    <span key={i} className="ingredient-tag unique">{name}</span>
                  ))}
                </div>
              ) : (
                <p className="muted">无独有成分</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default History
