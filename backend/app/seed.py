"""一次性数据导入脚本

把 ingredient.py 里的 INGREDIENT_DB(120 种成分)和 SYNONYMS(76 条同义词)
写入 SQLite 数据库。

用法(在 backend 目录下运行):
    python -m app.seed

特点:
- 可重复运行:先清空旧数据再导入,不会产生重复
- 导入后打印统计,方便确认
"""
from app.database import get_connection, init_db
from app.services.ingredient import INGREDIENT_DB, SYNONYMS


def seed() -> None:
    """把成分库和同义词导入数据库"""
    # 1. 确保表结构存在
    init_db()

    conn = get_connection()
    try:
        # 2. 清空旧数据(支持重复运行)
        conn.execute("DELETE FROM synonyms")
        conn.execute("DELETE FROM ingredients")

        # 3. 导入成分表
        #    用 INSERT OR IGNORE 防止意外重复(name 有 UNIQUE 约束)
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

        # 4. 导入同义词表
        #    只导入标准名在 ingredients 表里存在的同义词
        syn_count = 0
        for alias, standard_name in SYNONYMS.items():
            # 检查标准名是否存在于成分表
            exists = conn.execute(
                "SELECT 1 FROM ingredients WHERE name = ?", (standard_name,)
            ).fetchone()
            if not exists:
                print(f"  [跳过] 同义词 '{alias}' -> '{standard_name}' 标准名不存在")
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

        # 5. 打印统计
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
