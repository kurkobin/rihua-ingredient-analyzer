import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { useMemo } from 'react'
import { AnalysisResponse } from '../constants'

interface RiskChartProps {
  result: AnalysisResponse
}

export default function RiskChart({ result }: RiskChartProps) {
  const riskDistribution = useMemo(() => {
    const counts: Record<string, number> = { 安全: 0, 注意: 0, 慎用: 0, 规避: 0 }
    result.ingredients.forEach(ing => {
      if (ing.risk_level && counts[ing.risk_level] !== undefined) {
        counts[ing.risk_level]++
      }
    })
    return [
      { name: '安全', value: counts['安全'], color: '#00b894' },
      { name: '注意', value: counts['注意'], color: '#fdcb6e' },
      { name: '慎用', value: counts['慎用'], color: '#e17055' },
      { name: '规避', value: counts['规避'], color: '#d63031' },
    ].filter(item => item.value > 0)
  }, [result])

  if (riskDistribution.length === 0) return null

  return (
    <div className="risk-chart-card">
      <h3>📊 成分风险分布</h3>
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
            >
              {riskDistribution.map((entry, idx) => (
                <Cell key={idx} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => [`${value} 项`, '数量']} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
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
