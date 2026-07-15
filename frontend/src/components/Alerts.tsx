import { AnalysisResponse } from '../constants'

interface AlertsProps {
  result: AnalysisResponse
  onManageAllergens: () => void
}

export default function Alerts({ result, onManageAllergens }: AlertsProps) {
  return (
    <>
      {/* 成分相互作用预警 */}
      {result.interactions && result.interactions.length > 0 && (
        <div className="alert-section alert-interactions">
          <h3>⚠️ 成分相互作用预警</h3>
          <p className="alert-desc">以下成分组合同时使用可能产生不良反应</p>
          {result.interactions.map((w, i) => (
            <div key={i} className={`alert-item alert-severity-${w.severity === '高' ? 'high' : 'mid'}`}>
              <div className="alert-title">
                <span className="alert-pair">{w.ingredient_a}</span>
                <span className="alert-plus">+</span>
                <span className="alert-pair">{w.ingredient_b}</span>
                <span className={`alert-badge alert-badge-${w.severity === '高' ? 'high' : 'mid'}`}>{w.severity}风险</span>
              </div>
              <div className="alert-reason">{w.reason}</div>
            </div>
          ))}
        </div>
      )}

      {/* 过敏原预警 */}
      {result.allergen_alerts && result.allergen_alerts.length > 0 && (
        <div className="alert-section alert-allergens">
          <h3>🚫 过敏原预警</h3>
          <p className="alert-desc">该产品含有你标记的过敏成分</p>
          {result.allergen_alerts.map((a, i) => (
            <div key={i} className="alert-item alert-allergen-item">
              <span className="allergen-name">{a.ingredient_name}</span>
              <button className="link-btn-sm" onClick={onManageAllergens}>
                管理过敏原
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 成分替代建议 */}
      {result.alternatives && result.alternatives.length > 0 && (
        <div className="alert-section alert-alternatives">
          <h3>💡 更温和的替代建议</h3>
          <p className="alert-desc">以下成分有更温和的替代选择</p>
          {result.alternatives.map((alt, i) => (
            <div key={i} className="alert-item alert-alt-item">
              <div className="alt-original">{alt.original}</div>
              <div className="alt-reason">{alt.reason}</div>
              <div className="alt-suggestions">
                <span className="alt-label">建议替代:</span>
                {alt.alternatives.map(name => (
                  <span key={name} className="alt-chip">{name}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
