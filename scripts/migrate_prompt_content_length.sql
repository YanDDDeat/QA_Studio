-- 迁移脚本：将 prompts.content 字段从 TEXT 改为 MEDIUMTEXT
-- 
-- 原因：提示词内容可能很长（如包含完整知识体系表），TEXT 类型最大 64KB，
--       MEDIUMTEXT 最大 16MB，足够存储大型提示词。
--
-- 执行方式：
--   docker exec -i qa-studio-db mysql -uroot -p<密码> qa_studio < scripts/migrate_prompt_content_length.sql
--
-- 或直接执行：
--   docker exec -i qa-studio-db mysql -uroot -p<密码> qa_studio -e "ALTER TABLE prompts MODIFY COLUMN content MEDIUMTEXT NOT NULL COMMENT '提示词内容';"

ALTER TABLE prompts MODIFY COLUMN content MEDIUMTEXT NOT NULL COMMENT '提示词内容';