import { useState, useEffect } from 'react'
import {
  getAllergens, addAllergen, removeAllergen,
  type AllergenItem,
} from './storage'

// 过敏原档案现在存本地 localStorage,不再调用后端接口
// 后端 analyze 接口不再做过敏原检查,改由前端在拿到结果后本地检查

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
  const [inputName, setInputName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refreshList = () => {
    setAllergens(getAllergens())
  }

  useEffect(() => {
    refreshList()
  }, [])

  // 添加过敏成分
  const handleAdd = (name: string) => {
    const trimmed = name.trim()
    if (!trimmed) return
    setError(null)
    const newItem = addAllergen(trimmed)
    if (!newItem) {
      setError(`"${trimmed}" 已在列表中`)
      return
    }
    setInputName('')
    refreshList()
  }

  // 删除过敏成分
  const handleDelete = (id: number) => {
    removeAllergen(id)
    refreshList()
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
              if (e.key === 'Enter') handleAdd(inputName)
            }}
          />
          <button
            className="btn btn-primary"
            onClick={() => handleAdd(inputName)}
            disabled={!inputName.trim()}
          >
            添加
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
        {allergens.length === 0 ? (
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
          <li>数据存储在你的浏览器本地,不会上传到云端,仅你可见</li>
          <li>清除浏览器缓存或更换设备后,数据将丢失</li>
          <li>可以随时删除已标记的过敏成分</li>
        </ul>
      </div>
    </div>
  )
}

export default AllergenSettings
