import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { useMemo, useState } from 'react'
import { AnalysisResponse, RISK_TAG } from '../constants'

interface RiskChartProps {
  result: AnalysisResponse
}

// 自定义 Tooltip:鼠标悬停时显示该风险等级下的具体成分名称
function CustomTooltip({ active, payload }: {
  active?: boolean
  payload?: Array<{
    payload: { name: string; value: number; color: string; ingredients: string[] }
  }>
}) {
  if (!active || !payload || payload.length === 0) return null
  const data = payload[0].payload
  return (
    <div className="risk-tooltip">
      <div className="risk-tooltip-header">
        <span className="risk-tooltip-dot" style={{ background: data.color }}></span>
        <strong>{data.name}</strong>
        <span className="risk-tooltip-count">({data.value} 项)</span>
      </div>
      {data.ingredients.length > 0 && (
        <div className="risk-tooltip-list">
          {data.ingredients.map((name, i) => (
            <div key={i} className="risk-tooltip-item">{name}</div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function RiskChart({ result }: RiskChartProps) {
  const [selectedRisk, setSelectedRisk] = useState<string | null>(null)

  // 饼图数据(附带该风险等级下的成分名称列表)
  const riskDistribution = useMemo(() => {
    const groups: Record<string, string[]> = { 安全: [], 注意: [], 慎用: [], 规避: [] }
    result.ingredients.forEach(ing => {
      if (ing.risk_level && groups[ing.risk_level]) {
        groups[ing.risk_level].push(ing.name)
      }
    })
    return [
      { name: '安全', value: groups['安全'].length, color: '#00b894', ingredients: groups['安全'] },
      { name: '注意', value: groups['注意'].length, color: '#fdcb6e', ingredients: groups['注意'] },
      { name: '慎用', value: groups['慎用'].length, color: '#e17055', ingredients: groups['慎用'] },
      { name: '规避', value: groups['规避'].length, color: '#d63031', ingredients: groups['规避'] },
    ].filter(item => item.value > 0)
  }, [result])

  if (riskDistribution.length === 0) return null

  // 点击饼图扇区,展开/收起该风险等级的成分列表(手机端友好)
  const handleClick = (name: string) => {
    setSelectedRisk(selectedRisk === name ? null : name)
  }

  return (
    <div className="risk-chart-card">
      <h3>📊 成分风险分布</h3>
      <p className="risk-chart-hint">点击扇区可查看具体成分</p>
      <div className="risk-chart-wrapper">
        <ResponsiveContainer width="100%" height={240}>
          <PieChart>
            <Pie
              data={riskDistribution}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label={(entry) => `${entry.name} ${entry.value}`}
              onClick={(entry) => entry.name && handleClick(entry.name)}
            >
              {riskDistribution.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.color}
                  style={{ cursor: 'pointer' }}
                  opacity={selectedRisk && selectedRisk !== entry.name ? 0.4 : 1}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* 点击扇区后展开的成分列表 */}
      {selectedRisk && (
        <div className="risk-detail-panel">
          <div className="risk-detail-header">
            <h4>
              <span
                className="risk-detail-dot"
                style={{ background: riskDistribution.find(r => r.name === selectedRisk)?.color }}
              ></span>
              {selectedRisk} 成分({riskDistribution.find(r => r.name === selectedRisk)?.value} 项)
            </h4>
            <button className="risk-detail-close" onClick={() => setSelectedRisk(null)}>✕</button>
          </div>
          <div className="risk-detail-chips">
            {riskDistribution.find(r => r.name === selectedRisk)?.ingredients.map(name => (
              <span key={name} className={`risk-chip ${RISK_TAG[selectedRisk]?.cls || ''}`}>
                {name}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="risk-chart-legend">
        {riskDistribution.map(item => (
          <span key={item.name} className="legend-item">
            <span className="legend-dot" style={{ background: item.color }}></span>
            {item.name}: {item.value} 项
          </span>
        ))}
      </div>
    </div>
  )
}
