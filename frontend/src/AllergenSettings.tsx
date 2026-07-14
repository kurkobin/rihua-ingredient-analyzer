import { useState, useEffect, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || ''

// 过敏原项
interface AllergenItem {
  id: number
  ingredient_name: string
  created_at: string
}

// 常见过敏成分快捷选项
const COMMON_ALLERGENS = [
  '香精', '乙醇', '变性乙醇', '对羟基苯甲酸甲酯', '对羟基苯甲酸乙酯',
  '对羟基苯甲酸丙酯', '对羟基苯甲酸丁酯', '甲基异噻唑啉酮', '甲基氯异噻唑啉酮',
  '月桂醇硫酸酯钠', '月桂醇聚醚硫酸酯钠', '丙二醇', '苯甲醇', '异丙醇',
  '咪唑烷基脲', '脱氢乙酸', '视黄醇', '水杨酸', '果酸',
]

interface Props {
  onBack: () => void
}

function AllergenSettings({ onBack }: Props) {
  const [allergens, setAllergens] = useState<AllergenItem[]>([])
  const [loading, setLoading] = useState(true)
  const [inputName, setInputName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  // 获取过敏原列表
  const fetchAllergens = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/allergens`)
      if (!resp.ok) throw new Error('获取失败')
      const data = await resp.json()
      setAllergens(data.items)
    } catch {
      setError('获取过敏原列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAllergens()
  }, [fetchAllergens])

  // 添加过敏成分
  const handleAdd = async (name: string) => {
    const trimmed = name.trim()
    if (!trimmed) return
    setAdding(true)
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/allergens`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ingredient_name: trimmed }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '添加失败')
      }
      setInputName('')
      await fetchAllergens()
    } catch (e) {
      setError(e instanceof Error ? e.message : '添加失败')
    } finally {
      setAdding(false)
    }
  }

  // 删除过敏成分
  const handleDelete = async (id: number) => {
    try {
      const resp = await fetch(`${API_BASE}/api/allergens/${id}`, {
        method: 'DELETE',
      })
      if (!resp.ok) throw new Error('删除失败')
      setAllergens(prev => prev.filter(a => a.id !== id))
    } catch {
      setError('删除失败')
    }
  }

  // 已添加的成分名集合(用于快捷按钮禁用)
  const addedNames = new Set(allergens.map(a => a.ingredient_name))

  // 过滤已添加的快捷选项
  const availableCommon = COMMON_ALLERGENS.filter(n => !addedNames.has(n))

  return (
    <div className="app">
      <header className="header">
        <h1>过敏原档案</h1>
        <p>标记你的过敏成分,扫描时自动预警</p>
      </header>

      <div className="topbar">
        <button className="link-btn" onClick={onBack}>
          ← 返回首页
        </button>
      </div>

      {/* 添加区 */}
      <div className="allergen-add-section">
        <div className="allergen-input-row">
          <input
            type="text"
            className="allergen-input"
            placeholder="输入成分名(如:香精)"
            value={inputName}
            onChange={(e) => setInputName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !adding) handleAdd(inputName)
            }}
            disabled={adding}
          />
          <button
            className="btn btn-primary"
            onClick={() => handleAdd(inputName)}
            disabled={!inputName.trim() || adding}
          >
            {adding ? '添加中...' : '添加'}
          </button>
        </div>

        {/* 快捷添加 */}
        {availableCommon.length > 0 && (
          <div className="allergen-quick">
            <div className="allergen-quick-label">常见过敏成分(点击快速添加):</div>
            <div className="allergen-quick-chips">
              {availableCommon.map(name => (
                <button
                  key={name}
                  className="allergen-quick-chip"
                  onClick={() => handleAdd(name)}
                  disabled={adding}
                >
                  + {name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && <div className="error">⚠️ {error}</div>}

      {/* 列表区 */}
      <div className="allergen-list-section">
        <h3>已标记的过敏成分({allergens.length})</h3>
        {loading ? (
          <div className="allergen-empty">加载中...</div>
        ) : allergens.length === 0 ? (
          <div className="allergen-empty">
            还没有标记过敏成分<br />
            <span className="allergen-empty-hint">添加后,扫描产品时会自动检测并预警</span>
          </div>
        ) : (
          <div className="allergen-list">
            {allergens.map(a => (
              <div key={a.id} className="allergen-list-item">
                <div className="allergen-item-info">
                  <span className="allergen-item-name">{a.ingredient_name}</span>
                  <span className="allergen-item-time">
                    {new Date(a.created_at).toLocaleDateString('zh-CN')}
                  </span>
                </div>
                <button
                  className="allergen-delete-btn"
                  onClick={() => handleDelete(a.id)}
                  aria-label="删除"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 说明 */}
      <div className="allergen-tips">
        <h4>💡 使用说明</h4>
        <ul>
          <li>添加过敏成分后,每次扫描产品时会自动检测是否含有该成分</li>
          <li>支持精确匹配成分名(如"香精"只匹配"香精",不匹配"薄荷油")</li>
          <li>数据存储在本地浏览器关联的设备上,不会上传到云端</li>
          <li>可以随时删除已标记的过敏成分</li>
        </ul>
      </div>
    </div>
  )
}

export default AllergenSettings
