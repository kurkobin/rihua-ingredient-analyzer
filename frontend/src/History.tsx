import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import {
  getHistory, removeHistory, clearHistory, getHistoryById,
  type HistoryItem,
} from './storage'

// 历史记录现在存本地 localStorage,不再调用后端接口
// 对比功能改为前端本地计算(不再依赖后端 /api/compare)

interface CompareItemData {
  id: number
  product_type: string
  score: number
  pros: string[]
  cons: string[]
  ingredient_names: string[]
}

interface CompareResult {
  items: CompareItemData[]
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

// 本地计算对比结果
function computeCompare(items: HistoryItem[]): CompareResult {
  // 解析每条记录的 result_json,提取成分名、优缺点
  const parsed: CompareItemData[] = items.map(item => {
    try {
      const data = JSON.parse(item.result_json)
      return {
        id: item.id,
        product_type: item.product_type || '未知产品',
        score: item.score ?? 0,
        pros: data.pros || [],
        cons: data.cons || [],
        ingredient_names: (data.ingredients || []).map((ing: { name: string }) => ing.name),
      }
    } catch {
      return {
        id: item.id,
        product_type: item.product_type || '未知产品',
        score: item.score ?? 0,
        pros: [],
        cons: [],
        ingredient_names: [],
      }
    }
  })

  // 计算共有成分(所有产品都含有的)
  const nameSets = parsed.map(p => new Set(p.ingredient_names))
  let common: string[] = []
  if (nameSets.length > 0) {
    common = [...nameSets[0]].filter(name => nameSets.every(s => s.has(name)))
  }

  // 计算独有成分(只出现在自己,不在其他产品中)
  const unique: Record<number, string[]> = {}
  parsed.forEach((p, idx) => {
    const otherNames = new Set<string>()
    nameSets.forEach((s, i) => {
      if (i !== idx) s.forEach(n => otherNames.add(n))
    })
    unique[p.id] = p.ingredient_names.filter((n: string) => !otherNames.has(n))
  })

  return { items: parsed, common_ingredients: common, unique_ingredients: unique }
}

function History({ onBack, onView }: Props) {
  const [list, setList] = useState<HistoryItem[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [comparing, setComparing] = useState(false)
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null)
  const [selectMode, setSelectMode] = useState(false)

  const refreshList = () => {
    setList(getHistory())
  }

  useEffect(() => {
    refreshList()
  }, [])

  // 趋势图数据:把 list 反转(最早→最晚),过滤无评分项
  const chartData = useMemo(() => {
    return [...list]
      .filter(item => item.score !== null)
      .reverse()
      .map((item, idx) => ({
        idx: idx + 1,
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
  const handleView = (id: number) => {
    if (selectMode) {
      toggleSelect(id)
      return
    }
    const detail = getHistoryById(id)
    if (detail) {
      onView(detail.result_json, id)
    }
  }

  // 切换勾选
  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        if (next.size >= 5) return prev
        next.add(id)
      }
      return next
    })
  }

  // 删除单条
  const handleDelete = (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('确定删除这条记录?')) return
    removeHistory(id)
    refreshList()
    setSelected(prev => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  // 清空全部
  const handleClearAll = () => {
    if (list.length === 0) return
    if (!confirm(`确定清空全部 ${list.length} 条记录?此操作不可恢复。`)) return
    clearHistory()
    setList([])
    setSelected(new Set())
  }

  // 对比选中(本地计算,不再调用后端)
  const handleCompare = () => {
    if (selected.size < 2) return
    setComparing(true)
    try {
      const selectedItems = list.filter(item => selected.has(item.id))
      const result = computeCompare(selectedItems)
      setCompareResult(result)
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
        <p>共 {list.length} 条分析记录 · 数据存储在本地浏览器</p>
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

      {selectMode && !compareResult && (
        <div className="select-tip">
          点击记录进行勾选,选 2-5 条后点"对比"
        </div>
      )}

      {/* 对比结果 */}
      {compareResult && (
        <CompareView result={compareResult} onClose={() => setCompareResult(null)} />
      )}

      {!compareResult && (
        <>
          {list.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📋</div>
              <p>还没有分析记录</p>
              <p className="empty-tip">返回首页扫描配料表,记录会自动保存到本地</p>
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
