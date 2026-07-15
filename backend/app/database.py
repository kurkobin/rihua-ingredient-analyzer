"""SQLite 数据库连接和表结构

使用 SQLite 持久化存储成分库,替代内存字典。
数据库文件: backend/ingredients.db
"""
import sqlite3
from pathlib import Path

from app.logger import logger

# 数据库文件路径: backend/ingredients.db
DB_PATH = Path(__file__).parent.parent / "ingredients.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接(每次调用创建新连接,用完即关)

    开启 WAL 模式提升并发读性能。
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # 返回字典风格的行
    # 开启 WAL 模式(提升读并发,减少锁竞争)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.OperationalError:
        pass  # 某些环境可能不支持,忽略
    return conn


def init_db() -> None:
    """初始化数据库表结构"""
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ingredients (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                category    TEXT,
                risk_level  TEXT,
                description TEXT,
                reference   TEXT
            );

            CREATE TABLE IF NOT EXISTS synonyms (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                alias         TEXT UNIQUE NOT NULL,
                standard_name TEXT NOT NULL,
                FOREIGN KEY (standard_name) REFERENCES ingredients(name)
            );

            -- 加速查询的索引
            CREATE INDEX IF NOT EXISTS idx_ingredients_name ON ingredients(name);
            CREATE INDEX IF NOT EXISTS idx_synonyms_alias ON synonyms(alias);

            -- OCR 结果缓存表(同一张图片重复上传时直接返回缓存)
            CREATE TABLE IF NOT EXISTS ocr_cache (
                img_hash   TEXT PRIMARY KEY,  -- 图片 MD5 哈希
                result_json TEXT NOT NULL,    -- 完整分析结果(JSON 字符串)
                created_at TEXT NOT NULL      -- 缓存时间(ISO 格式)
            );

            -- 分析历史记录表(用户扫过的商品记录)
            CREATE TABLE IF NOT EXISTS history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                img_hash     TEXT NOT NULL,       -- 图片 MD5(关联缓存)
                product_type TEXT,                -- 产品品类
                summary      TEXT,                -- 简评
                score        INTEGER,             -- 综合评分
                ingredient_count INTEGER,         -- 成分数
                result_json  TEXT NOT NULL,       -- 完整分析结果(JSON)
                created_at   TEXT NOT NULL        -- 分析时间(ISO 格式)
            );
            CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);

            -- 用户过敏原档案表(标记过敏成分,扫描时自动预警)
            CREATE TABLE IF NOT EXISTS allergens (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_name TEXT UNIQUE NOT NULL,  -- 过敏成分名(唯一,防重复)
                created_at      TEXT NOT NULL           -- 添加时间(ISO 格式)
            );
            CREATE INDEX IF NOT EXISTS idx_allergens_name ON allergens(ingredient_name);
            """
        )
        conn.commit()
    finally:
        conn.close()


# ===== 历史记录 CRUD =====

def add_history(
    img_hash: str,
    product_type: str,
    summary: str,
    score: int,
    ingredient_count: int,
    result_json: str,
) -> int:
    """新增一条历史记录,返回新记录 id"""
    from datetime import datetime
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO history (img_hash, product_type, summary, score,
                                 ingredient_count, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (img_hash, product_type, summary, score, ingredient_count,
             result_json, datetime.now().isoformat()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_history_list(limit: int = 50) -> list[dict]:
    """获取历史记录列表(按时间倒序,不含完整 JSON,节省传输)"""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, img_hash, product_type, summary, score,
                   ingredient_count, created_at
            FROM history
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_history_detail(history_id: int) -> dict | None:
    """获取单条历史记录详情(含完整分析结果 JSON)"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM history WHERE id = ?", (history_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_history(history_id: int) -> bool:
    """删除一条历史记录,返回是否删除成功"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM history WHERE id = ?", (history_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def clear_history() -> int:
    """清空全部历史记录,返回删除条数"""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM history")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_ingredient(name: str) -> dict | None:
    """查询单个成分(按标准名精确匹配)"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM ingredients WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_ingredient_by_alias(alias: str) -> dict | None:
    """通过同义词查询成分(返回标准成分信息)"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT i.* FROM ingredients i
            JOIN synonyms s ON s.standard_name = i.name
            WHERE s.alias = ?
            """,
            (alias,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_ingredients() -> list[dict]:
    """获取全部成分(用于调试)"""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM ingredients ORDER BY category, name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_ingredients(
    name: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
    reference_keyword: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """多条件检索成分库(法规检索页用)

    所有参数均为可选,支持任意组合:
    - name: 成分名模糊匹配(LIKE,%name%)
    - category: 分类精确匹配
    - risk_level: 风险等级精确匹配
    - reference_keyword: 法规出处关键词模糊匹配
    - limit: 返回上限,默认 100,最大 500
    """
    # 限制 limit 上限,防止一次拉太多
    limit = max(1, min(limit, 500))

    # 动态拼接 SQL 和参数
    conditions = []
    params: list = []

    if name:
        conditions.append("name LIKE ?")
        params.append(f"%{name}%")
    if category:
        conditions.append("category = ?")
        params.append(category)
    if risk_level:
        conditions.append("risk_level = ?")
        params.append(risk_level)
    if reference_keyword:
        conditions.append("reference LIKE ?")
        params.append(f"%{reference_keyword}%")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM ingredients{where_clause} ORDER BY category, name LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_ingredient_categories() -> list[str]:
    """获取全部成分分类(去重,用于检索页下拉选项)"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM ingredients "
            "WHERE category IS NOT NULL ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]
    finally:
        conn.close()


def find_ingredient(name: str) -> dict | None:
    """联合查询成分:标准名 -> 同义词 -> 同义词(小写)

    一次调用搞定三种匹配,ingredient.py 无需关心匹配细节。
    """
    conn = get_connection()
    try:
        # 1. 标准名精确匹配
        row = conn.execute(
            "SELECT * FROM ingredients WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return dict(row)

        # 2. 同义词精确匹配
        row = conn.execute(
            """
            SELECT i.* FROM ingredients i
            JOIN synonyms s ON s.standard_name = i.name
            WHERE s.alias = ?
            """,
            (name,),
        ).fetchone()
        if row:
            return dict(row)

        # 3. 同义词小写匹配(处理英文名变体,如 "Vitamin C" -> "vitamin c")
        lower = name.lower()
        row = conn.execute(
            """
            SELECT i.* FROM ingredients i
            JOIN synonyms s ON s.standard_name = i.name
            WHERE LOWER(s.alias) = ?
            """,
            (lower,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def find_ingredients_batch(names: list[str]) -> dict[str, dict]:
    """批量查询多个成分(优化 N+1 问题)

    一次连接内完成所有查询,替代循环调用 find_ingredient。
    匹配顺序:标准名 -> 同义词精确 -> 同义词小写。

    Args:
        names: 待查询的候选成分名列表

    Returns:
        dict: { 原始名: 成分信息 } 仅包含命中的项
    """
    if not names:
        return {}

    result: dict[str, dict] = {}
    conn = get_connection()
    try:
        # 用单个连接批量查询,避免重复开关连接
        for name in names:
            if name in result:
                continue  # 已命中,跳过

            # 1. 标准名精确匹配
            row = conn.execute(
                "SELECT * FROM ingredients WHERE name = ?", (name,)
            ).fetchone()
            if row:
                result[name] = dict(row)
                continue

            # 2. 同义词精确匹配
            row = conn.execute(
                """
                SELECT i.* FROM ingredients i
                JOIN synonyms s ON s.standard_name = i.name
                WHERE s.alias = ?
                """,
                (name,),
            ).fetchone()
            if row:
                result[name] = dict(row)
                continue

            # 3. 同义词小写匹配
            lower = name.lower()
            row = conn.execute(
                """
                SELECT i.* FROM ingredients i
                JOIN synonyms s ON s.standard_name = i.name
                WHERE LOWER(s.alias) = ?
                """,
                (lower,),
            ).fetchone()
            if row:
                result[name] = dict(row)

        return result
    finally:
        conn.close()


def get_cache(img_hash: str) -> str | None:
    """查询缓存:命中返回 result_json,未命中返回 None"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT result_json FROM ocr_cache WHERE img_hash = ?", (img_hash,)
        ).fetchone()
        return row["result_json"] if row else None
    finally:
        conn.close()


def set_cache(img_hash: str, result_json: str) -> None:
    """写入缓存(INSERT OR REPLACE:相同图片覆盖旧缓存)"""
    from datetime import datetime
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO ocr_cache (img_hash, result_json, created_at)
            VALUES (?, ?, ?)
            """,
            (img_hash, result_json, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


# ===== 过敏原档案 CRUD =====

def add_allergen(ingredient_name: str) -> dict | None:
    """添加过敏成分(已存在则忽略,返回该记录)"""
    from datetime import datetime
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO allergens (ingredient_name, created_at) VALUES (?, ?)",
            (ingredient_name, datetime.now().isoformat()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM allergens WHERE ingredient_name = ?", (ingredient_name,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_allergens() -> list[dict]:
    """获取全部过敏成分列表(按时间倒序)"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM allergens ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_allergen(allergen_id: int) -> bool:
    """删除一条过敏成分,返回是否删除成功"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM allergens WHERE id = ?", (allergen_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_allergen_names() -> list[str]:
    """获取全部过敏成分名列表(用于 /analyze 时快速匹配)"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ingredient_name FROM allergens"
        ).fetchall()
        return [r["ingredient_name"] for r in rows]
    finally:
        conn.close()


# 模块导入时自动初始化表结构
init_db()
