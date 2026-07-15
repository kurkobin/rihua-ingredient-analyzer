import { useEffect } from 'react'
import { IngredientInfo, RISK_TAG } from '../constants'

interface ModalProps {
  ingredient: IngredientInfo
  allIngredients: IngredientInfo[]
  onClose: () => void
  onSelect: (ing: IngredientInfo) => void
}

export default function IngredientDetailModal({ ingredient, allIngredients, onClose, onSelect }: ModalProps) {
  const tag = ingredient.risk_level ? RISK_TAG[ingredient.risk_level] : null

  // 同类成分推荐(同 category,排除自己,最多 8 个)
  const related = ingredient.category
    ? allIngredients.filter(
        ing => ing.category === ingredient.category && ing.name !== ingredient.name
      ).slice(0, 8)
    : []

  // 全局监听 ESC 键关闭弹窗
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // 点击遮罩关闭
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className="modal-backdrop" onClick={handleBackdropClick}>
      <div className="modal-content">
        <button className="modal-close" onClick={onClose} aria-label="关闭">
          ✕
        </button>

        <h2 className="modal-title">
          {ingredient.name}
          {!ingredient.in_database && <span className="db-badge">未入库</span>}
        </h2>

        <div className="modal-tags">
          {tag && (
            <span className={`tag tag-lg ${tag.cls}`}>{tag.label}</span>
          )}
          {ingredient.category && (
            <span className="tag tag-lg unknown">{ingredient.category}</span>
          )}
        </div>

        {ingredient.description && (
          <div className="modal-section">
            <h4>说明</h4>
            <p className="modal-desc">{ingredient.description}</p>
          </div>
        )}

        {ingredient.reference && (
          <div className="modal-section">
            <h4>📖 法规依据</h4>
            <p className="modal-ref">{ingredient.reference}</p>
          </div>
        )}

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

        {!ingredient.description && !ingredient.reference && (
          <div className="modal-section">
            <p className="modal-empty">该成分暂无详细信息</p>
          </div>
        )}
      </div>
    </div>
  )
}
