"""数据导入脚本

把 ingredient.py 里的 INGREDIENT_DB 和 SYNONYMS 写入 SQLite 数据库。

用法(在 backend 目录下运行):
    python -m app.seed            # 强制清空并重新导入(手动运行)
    # 应用启动时会自动调用 seed_if_empty(),仅在表为空时导入

特点:
- seed():清空旧数据再导入,支持重复运行(手动运行)
- seed_if_empty():仅当 ingredients 表为空时才导入(启动时自动调用)
"""
from app.database import get_connection, init_db
from app.services.ingredient import INGREDIENT_DB, SYNONYMS


def _import_data(conn) -> tuple[int, int]:
    """把 INGREDIENT_DB 和 SYNONYMS 导入数据库(不清空,用 INSERT OR IGNORE)

    Returns:
        (成分数, 同义词数)
    """
    ing_count = 0
    for name, info in INGREDIENT_DB.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO ingredients
                (name, category, risk_level, description, reference)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                info.get("category", ""),
                info.get("risk_level", ""),
                info.get("description", ""),
                info.get("reference", ""),
            ),
        )
        ing_count += 1

    syn_count = 0
    for alias, standard_name in SYNONYMS.items():
        exists = conn.execute(
            "SELECT 1 FROM ingredients WHERE name = ?", (standard_name,)
        ).fetchone()
        if not exists:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO synonyms (alias, standard_name)
            VALUES (?, ?)
            """,
            (alias, standard_name),
        )
        syn_count += 1

    conn.commit()
    return ing_count, syn_count


def seed_if_empty() -> bool:
    """应用启动时调用:仅当 ingredients 表为空时才导入数据。

    Returns:
        True 表示执行了导入,False 表示表已有数据(跳过)
    """
    init_db()
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
        if count > 0:
            print(f"[seed] 成分库已有 {count} 条数据,跳过初始化")
            return False

        print("[seed] 成分库为空,开始导入种子数据...")
        ing_count, syn_count = _import_data(conn)
        total_ing = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
        total_syn = conn.execute("SELECT COUNT(*) FROM synonyms").fetchone()[0]
        print("=" * 50)
        print("[seed] 成分库导入完成")
        print(f"  成分总数: {total_ing} 条")
        print(f"  同义词数: {total_syn} 条")
        print("=" * 50)
        return True
    finally:
        conn.close()


def seed() -> None:
    """手动运行:强制清空并重新导入(支持重复运行)"""
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM synonyms")
        conn.execute("DELETE FROM ingredients")
        ing_count, syn_count = _import_data(conn)
        total_ing = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
        total_syn = conn.execute("SELECT COUNT(*) FROM synonyms").fetchone()[0]
        print("=" * 50)
        print("成分库导入完成")
        print(f"  成分总数: {total_ing} 条")
        print(f"  同义词数: {total_syn} 条")
        print("=" * 50)
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
