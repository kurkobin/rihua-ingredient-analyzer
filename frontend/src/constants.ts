// 共享常量和工具函数(供 App.tsx 及各子组件使用)

// API 基础地址:本地开发走 Vite 代理(相对路径 /api),生产环境用环境变量
export const API_BASE = import.meta.env.VITE_API_BASE || ''

// 风险等级 -> 标签样式映射
export const RISK_TAG: Record<string, { cls: string; label: string }> = {
  '安全': { cls: 'safe', label: '安全' },
  '注意': { cls: 'notice', label: '注意' },
  '慎用': { cls: 'caution', label: '慎用' },
  '规避': { cls: 'avoid', label: '规避' },
}

// 法规来源归类规则
const REFERENCE_RULES: { keyword: string; label: string }[] = [
  { keyword: '安全技术规范', label: '化妆品安全技术规范(2015版)' },
  { keyword: '已使用原料目录', label: '国家药监局已使用原料目录(2021版)' },
  { keyword: 'GB 22115', label: 'GB 22115-2008 牙膏用原料规范' },
  { keyword: 'CIR', label: 'CIR 评估' },
  { keyword: '欧盟', label: '欧盟法规' },
  { keyword: 'IFRA', label: 'IFRA 标准' },
  { keyword: 'FDA', label: 'FDA' },
  { keyword: '常用成分', label: '常用成分(无明确法规)' },
  { keyword: '暂无明确法规', label: '暂无明确法规依据' },
  { keyword: '国家非处方药', label: '国家非处方药目录' },
]

// 把 reference 文本归一为来源标签
export function classifyReference(ref: string | null): string {
  if (!ref) return '暂无明确法规依据'
  for (const rule of REFERENCE_RULES) {
    if (ref.includes(rule.keyword)) return rule.label
  }
  return '其他'
}

// 类型定义(共享)
export interface IngredientInfo {
  name: string
  category: string | null
  risk_level: string | null
  description: string | null
  in_database: boolean
  reference: string | null
}

export interface InteractionWarning {
  ingredient_a: string
  ingredient_b: string
  reason: string
  severity: string
}

export interface AllergenAlert {
  ingredient_name: string
}

export interface AlternativeSuggestion {
  original: string
  reason: string
  alternatives: string[]
}

export interface AnalysisResponse {
  ocr_text: string
  ingredients: IngredientInfo[]
  pros: string[]
  cons: string[]
  score: number
  summary: string
  product_type: string
  history_id?: number
  interactions?: InteractionWarning[]
  allergen_alerts?: AllergenAlert[]
  alternatives?: AlternativeSuggestion[]
}
