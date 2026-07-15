/**
 * 本地存储工具模块
 *
 * 用于在浏览器 localStorage 中管理历史记录和过敏原档案。
 * 数据完全存储在用户设备上,不上传后端,实现用户数据隔离。
 *
 * 注意:localStorage 容量约 5-10MB,历史记录过多时需清理。
 */

import type { AnalysisResponse, IngredientInfo, AllergenAlert } from './constants'

// ===== 历史记录 =====

export interface HistoryItem {
  id: number
  img_hash: string
  product_type: string | null
  summary: string | null
  score: number | null
  ingredient_count: number | null
  created_at: string
  result_json: string  // 完整分析结果(用于查看详情)
}

const HISTORY_KEY = 'ingredient_history'
const HISTORY_MAX = 100  // 最多保留 100 条

/** 读取所有历史记录(按时间倒序) */
export function getHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return []
    const list: HistoryItem[] = JSON.parse(raw)
    return list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  } catch {
    return []
  }
}

/** 添加一条历史记录 */
export function addHistory(item: Omit<HistoryItem, 'id' | 'created_at'>): HistoryItem {
  const list = getHistory()
  const newItem: HistoryItem = {
    ...item,
    id: Date.now(),  // 用时间戳作为唯一 id
    created_at: new Date().toISOString(),
  }
  const next = [newItem, ...list].slice(0, HISTORY_MAX)  // 限制最多 100 条
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
  return newItem
}

/** 删除单条历史记录 */
export function removeHistory(id: number): void {
  const list = getHistory()
  const next = list.filter(item => item.id !== id)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
}

/** 清空全部历史记录 */
export function clearHistory(): void {
  localStorage.removeItem(HISTORY_KEY)
}

/** 根据 id 获取历史记录详情 */
export function getHistoryById(id: number): HistoryItem | null {
  const list = getHistory()
  return list.find(item => item.id === id) || null
}

// ===== 过敏原档案 =====

export interface AllergenItem {
  id: number
  ingredient_name: string
  created_at: string
}

const ALLERGEN_KEY = 'ingredient_allergens'

/** 读取所有过敏原 */
export function getAllergens(): AllergenItem[] {
  try {
    const raw = localStorage.getItem(ALLERGEN_KEY)
    if (!raw) return []
    return JSON.parse(raw)
  } catch {
    return []
  }
}

/** 添加过敏原(去重,返回新增项或已存在的项) */
export function addAllergen(name: string): AllergenItem | null {
  const trimmed = name.trim()
  if (!trimmed) return null
  const list = getAllergens()
  // 去重检查
  if (list.some(a => a.ingredient_name === trimmed)) {
    return null
  }
  const newItem: AllergenItem = {
    id: Date.now(),
    ingredient_name: trimmed,
    created_at: new Date().toISOString(),
  }
  const next = [...list, newItem]
  localStorage.setItem(ALLERGEN_KEY, JSON.stringify(next))
  return newItem
}

/** 删除过敏原 */
export function removeAllergen(id: number): void {
  const list = getAllergens()
  const next = list.filter(a => a.id !== id)
  localStorage.setItem(ALLERGEN_KEY, JSON.stringify(next))
}

/** 获取过敏原名称列表(用于扫描时检查) */
export function getAllergenNames(): string[] {
  return getAllergens().map(a => a.ingredient_name)
}

// ===== 便利函数(供 App.tsx 直接调用) =====

/** 保存分析结果到历史记录 */
export function saveHistory(result: AnalysisResponse): void {
  addHistory({
    img_hash: '',  // 本地存储不依赖图片哈希
    product_type: result.product_type || null,
    summary: result.summary || null,
    score: result.score,
    ingredient_count: result.ingredients.length,
    result_json: JSON.stringify(result),
  })
}

/** 检查成分列表中是否包含用户过敏原,返回预警列表 */
export function checkAllergenAlerts(ingredients: IngredientInfo[]): AllergenAlert[] {
  const allergenNames = getAllergenNames()
  if (allergenNames.length === 0) return []
  const alerts: AllergenAlert[] = []
  for (const ing of ingredients) {
    if (allergenNames.some(name => ing.name.includes(name) || name.includes(ing.name))) {
      alerts.push({ ingredient_name: ing.name })
    }
  }
  return alerts
}
