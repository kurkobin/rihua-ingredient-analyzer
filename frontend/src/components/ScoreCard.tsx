import { AnalysisResponse } from '../constants'

interface ScoreCardProps {
  result: AnalysisResponse
}

export default function ScoreCard({ result }: ScoreCardProps) {
  const scoreClass = result.score >= 86 ? 'good' : result.score >= 60 ? 'mid' : 'bad'

  const scoreGrade = result.score >= 86
    ? { label: '优秀', desc: '成分安全温和,推荐使用', color: '#00b894' }
    : result.score >= 76
    ? { label: '良好', desc: '成分整体不错,可放心使用', color: '#0984e3' }
    : result.score >= 60
    ? { label: '一般', desc: '部分成分需留意,按需选择', color: '#fdcb6e' }
    : { label: '不推荐', desc: '含有较多风险成分,建议谨慎', color: '#d63031' }

  return (
    <div className="score-card">
      {result.product_type && (
        <div className="product-type">📋 产品类型: {result.product_type}</div>
      )}
      <div className={`score-number ${scoreClass}`}>{result.score}</div>
      <div className="score-label">综合评分(满分100)</div>
      <div className="score-grade" style={{ color: scoreGrade.color }}>
        <span className="grade-label">{scoreGrade.label}</span>
        <span className="grade-desc">{scoreGrade.desc}</span>
      </div>
      <div className="summary">{result.summary}</div>
    </div>
  )
}
