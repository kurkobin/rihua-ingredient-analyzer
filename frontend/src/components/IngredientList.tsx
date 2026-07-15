import { useMemo, useState } from 'react'
import { AnalysisResponse, IngredientInfo, RISK_TAG, classifyReference } from '../constants'

interface IngredientListProps {
  result: AnalysisResponse
  onSelect: (ing: IngredientInfo) => void
}

export default function IngredientList({ result, onSelect }: IngredientListProps) {
  const [filterRisk, setFilterRisk] = useState<string>('all')
  const [filterCategory, setFilterCategory] = useState<string>('all')
  const [filterReference, setFilterReference] = useState<string>('all')
  const [onlyInDb, setOnlyInDb] = useState<boolean>(false)

  const categoryOptions = useMemo(() => {
    const set = new Set<string>()
    result.ingredients.forEach(ing => {
      if (ing.category) set.add(ing.category)
    })
    return Array.from(set).sort()
  }, [result])

  const referenceOptions = useMemo(() => {
    const set = new Set<string>()
    result.ingredients.forEach(ing => {
      set.add(classifyReference(ing.reference))
    })
    return Array.from(set).sort()
  }, [result])

  const filteredIngredients = useMemo(() => {
    return result.ingredients.filter(ing => {
      if (onlyInDb && !ing.in_database) return false
      if (filterRisk !== 'all' && ing.risk_level !== filterRisk) return false
      if (filterCategory !== 'all' && ing.category !== filterCategory) return false
      if (filterReference !== 'all') {
        const refLabel = classifyReference(ing.reference)
        if (refLabel !== filterReference) return false
      }
      return true
    })
  }, [result, onlyInDb, filterRisk, filterCategory, filterReference])

  return (
    <div className="ingredient-list">
      <h3>成分列表(共{result.ingredients.length}项)</h3>

      {/* 筛选条 */}
      <div className="filter-bar">
        <div className="filter-item">
          <label>风险等级</label>
          <select value={filterRisk} onChange={(e) => setFilterRisk(e.target.value)}>
            <option value="all">全部</option>
            <option value="安全">安全</option>
            <option value="注意">注意</option>
            <option value="慎用">慎用</option>
            <option value="规避">规避</option>
          </select>
        </div>
        <div className="filter-item">
          <label>成分分类</label>
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
            <option value="all">全部</option>
            {categoryOptions.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
        <div className="filter-item">
          <label>法规来源</label>
          <select value={filterReference} onChange={(e) => setFilterReference(e.target.value)}>
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
            onClick={() => onSelect(ing)}
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
  )
}
