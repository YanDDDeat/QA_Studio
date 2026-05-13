#!/usr/bin/env python3
"""
迁移脚本：将 datasets.domain 字段从 VARCHAR(128) 改为 TEXT

原因：LLM 可能返回数组格式的 domain（如 ["单质炸药", "混合炸药"]），
     需要存储为 JSON 字符串，TEXT 类型无长度限制，更安全。

执行方式：
  docker exec -i qa-studio-db mysql -uroot -p<密码> qa_studio < scripts/migrate_domain_to_text.sql

或者直接在 MySQL 容器内执行：
  docker exec -it qa-studio-db mysql -uroot -p
  USE qa_studio;
  ALTER TABLE datasets MODIFY COLUMN domain TEXT NULL COMMENT '领域（支持JSON数组）';
"""

# SQL 语句
SQL = """
ALTER TABLE datasets MODIFY COLUMN domain TEXT NULL COMMENT '领域（支持JSON数组）';
"""

if __name__ == "__main__":
    print("=" * 60)
    print("迁移脚本：datasets.domain VARCHAR(128) -> TEXT")
    print("=" * 60)
    print()
    print("请在 MySQL 容器内执行以下 SQL：")
    print()
    print(SQL)
    print()
    print("执行命令：")
    print("  docker exec -it qa-studio-db mysql -uroot -p<密码>")
    print("  USE qa_studio;")
    print("  ALTER TABLE datasets MODIFY COLUMN domain TEXT NULL COMMENT '领域（支持JSON数组）';")
    print()
    print("或一键执行：")
    print('  docker exec -i qa-studio-db mysql -uroot -p<密码> qa_studio -e "ALTER TABLE datasets MODIFY COLUMN domain TEXT NULL COMMENT \'领域（支持JSON数组）\';"')