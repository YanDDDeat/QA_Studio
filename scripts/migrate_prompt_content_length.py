#!/usr/bin/env python3
"""
迁移脚本：将 prompts.content 字段从 TEXT 改为 MEDIUMTEXT

原因：提示词内容可能很长（如包含完整知识体系表），TEXT 类型最大 64KB，
     MEDIUMTEXT 最大 16MB，足够存储大型提示词。

执行方式：
  docker exec -i qa-studio-db mysql -uroot -p<密码> qa_studio < scripts/migrate_prompt_content_length.sql

或者直接在 MySQL 容器内执行：
  docker exec -it qa-studio-db mysql -uroot -p
  USE qa_studio;
  ALTER TABLE prompts MODIFY COLUMN content MEDIUMTEXT NOT NULL COMMENT '提示词内容';
"""

# SQL 语句
SQL = """
ALTER TABLE prompts MODIFY COLUMN content MEDIUMTEXT NOT NULL COMMENT '提示词内容';
"""

if __name__ == "__main__":
    print("=" * 60)
    print("迁移脚本：prompts.content TEXT -> MEDIUMTEXT")
    print("=" * 60)
    print()
    print("请在 MySQL 容器内执行以下 SQL：")
    print()
    print(SQL)
    print()
    print("执行命令：")
    print("  docker exec -it qa-studio-db mysql -uroot -p<密码>")
    print("  USE qa_studio;")
    print("  ALTER TABLE prompts MODIFY COLUMN content MEDIUMTEXT NOT NULL COMMENT '提示词内容';")
    print()
    print("或一键执行：")
    print("  docker exec -i qa-studio-db mysql -uroot -p<密码> qa_studio -e \"ALTER TABLE prompts MODIFY COLUMN content MEDIUMTEXT NOT NULL COMMENT '提示词内容';\"")