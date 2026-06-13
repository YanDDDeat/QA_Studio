-- ============================================================
-- 专业 CoT 管线：文件存储 → 数据库存储 迁移脚本
-- 数据库: qa_gen
-- 兼容: MySQL 5.7+ / 8.0+ / RDS
-- 用法:   mysql -h <host> -u <user> -p qa_gen < migrate_professional_cot.sql
-- ============================================================

USE qa_gen;

-- -----------------------------------------------------------
-- 辅助：安全添加列（跳过已存在的列，不报错）
-- -----------------------------------------------------------
DROP PROCEDURE IF EXISTS safe_add_column;
DELIMITER //
CREATE PROCEDURE safe_add_column(
    IN tbl_name VARCHAR(128),
    IN col_name VARCHAR(128),
    IN col_def  TEXT
)
BEGIN
    DECLARE col_exists INT DEFAULT 0;
    SELECT COUNT(*) INTO col_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'qa_gen'
      AND TABLE_NAME = tbl_name
      AND COLUMN_NAME = col_name;
    IF col_exists = 0 THEN
        SET @ddl = CONCAT('ALTER TABLE ', tbl_name, ' ADD COLUMN ', col_name, ' ', col_def);
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END //
DELIMITER ;

-- -----------------------------------------------------------
-- 1. prompts 表：新增 template_id 和 prompt_key
-- -----------------------------------------------------------
CALL safe_add_column('prompts', 'template_id', "VARCHAR(128) NULL COMMENT '提示词模板包 ID'");
CALL safe_add_column('prompts', 'prompt_key',  "VARCHAR(128) NULL COMMENT '模板内 prompt 标识'");

-- 索引（不存在则创建）
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = 'qa_gen' AND TABLE_NAME = 'prompts' AND INDEX_NAME = 'idx_template_prompt');
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_template_prompt ON prompts (template_id, prompt_key)',
    'SELECT "INDEX idx_template_prompt already exists" AS msg');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- -----------------------------------------------------------
-- 2. tasks 表：新增专业 CoT 相关字段
-- -----------------------------------------------------------
CALL safe_add_column('tasks', 'input_count',         "INT DEFAULT 1 COMMENT '专业 CoT：输入文献数'");
CALL safe_add_column('tasks', 'success_count',       "INT DEFAULT 0 COMMENT '专业 CoT：成功文献数'");
CALL safe_add_column('tasks', 'failed_count',        "INT DEFAULT 0 COMMENT '专业 CoT：失败文献数'");
CALL safe_add_column('tasks', 'sample_count',        "INT DEFAULT 0 COMMENT '专业 CoT：产出样本数'");
CALL safe_add_column('tasks', 'run_extra',           "JSON NULL COMMENT '专业 CoT：扩展元数据'");
CALL safe_add_column('tasks', 'progress_label',      "VARCHAR(100) NULL COMMENT '步骤进度阶段描述'");
CALL safe_add_column('tasks', 'prompt_template_id',  "VARCHAR(128) NULL COMMENT '提示词模板 ID'");

-- -----------------------------------------------------------
-- 3. cot_samples 表：CoT 产出样本
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cot_samples (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    task_id         INT NOT NULL,
    user_id         INT NOT NULL,
    source_index    INT DEFAULT 0,
    source          VARCHAR(512) NULL,
    source_type     VARCHAR(32) DEFAULT 'unknown',
    cot_type        VARCHAR(128) NULL,
    cot_type_key    VARCHAR(64) NULL,
    input           TEXT NULL,
    chainofThought  TEXT NULL,
    output          TEXT NULL,
    evidence_trace  TEXT NULL,
    step_results    JSON NULL COMMENT '各步骤 LLM 原始返回',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_cot_task (task_id),
    INDEX idx_cot_type (cot_type_key),
    INDEX idx_cot_user (user_id),

    CONSTRAINT fk_cot_samples_task FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_cot_samples_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------
-- 4. cot_step_logs 表：每篇文献每步骤的执行日志
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cot_step_logs (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    task_id          INT NOT NULL,
    source_index     INT DEFAULT 0 COMMENT '文献序号，-1 表示 task 级别',
    step_key         VARCHAR(64) NOT NULL COMMENT 'step1_3_integrated/step4_input/step5_chain/step6_output',
    status           VARCHAR(16) DEFAULT 'pending' COMMENT 'pending/running/completed/failed/skipped',
    progress_current INT DEFAULT 0,
    progress_label   VARCHAR(256) NULL,
    cot_type         VARCHAR(128) NULL,
    cot_type_key     VARCHAR(64) NULL,
    artifact_path    VARCHAR(512) NULL,
    error_message    TEXT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_step_task (task_id, source_index, step_key),

    CONSTRAINT fk_cot_step_logs_task FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------
-- 5. professional_cot_type_stats 表：CoT 类型全局计数器
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS professional_cot_type_stats (
    cot_type_key VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(128) NOT NULL,
    count        INT DEFAULT 0 NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 清理
DROP PROCEDURE IF EXISTS safe_add_column;

-- 结果确认
SELECT '=== 迁移完成，检查新建表 ===' AS status;
SHOW TABLES LIKE 'cot_%';
SHOW TABLES LIKE 'professional_cot_type_stats';
