-- ============================================================
-- 专业 CoT 管线：文件存储 → 数据库存储 迁移脚本
-- 数据库: qa_gen
-- 兼容: MySQL 5.7+ / 8.0+ / RDS
-- 用法:   mysql -h <host> -u <user> -p qa_gen < migrate_professional_cot.sql
-- 注意:   如遇 "Duplicate column" 错误，说明列已存在，忽略继续即可
-- ============================================================

USE qa_gen;

-- -----------------------------------------------------------
-- 1. prompts 表：新增 template_id 和 prompt_key
-- -----------------------------------------------------------
ALTER TABLE prompts ADD COLUMN template_id VARCHAR(128) NULL COMMENT '提示词模板包 ID';
ALTER TABLE prompts ADD COLUMN prompt_key  VARCHAR(128) NULL COMMENT '模板内 prompt 标识';
CREATE INDEX idx_template_prompt ON prompts (template_id, prompt_key);

-- -----------------------------------------------------------
-- 2. tasks 表：新增专业 CoT 相关字段
-- -----------------------------------------------------------
ALTER TABLE tasks ADD COLUMN input_count        INT DEFAULT 1 COMMENT '专业 CoT：输入文献数';
ALTER TABLE tasks ADD COLUMN success_count      INT DEFAULT 0 COMMENT '专业 CoT：成功文献数';
ALTER TABLE tasks ADD COLUMN failed_count       INT DEFAULT 0 COMMENT '专业 CoT：失败文献数';
ALTER TABLE tasks ADD COLUMN sample_count       INT DEFAULT 0 COMMENT '专业 CoT：产出样本数';
ALTER TABLE tasks ADD COLUMN run_extra          JSON NULL COMMENT '专业 CoT：扩展元数据';
ALTER TABLE tasks ADD COLUMN progress_label     VARCHAR(100) NULL COMMENT '步骤进度阶段描述';
ALTER TABLE tasks ADD COLUMN prompt_template_id VARCHAR(128) NULL COMMENT '提示词模板 ID';

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

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------
-- 4. cot_step_logs 表：每篇文献每步骤的执行日志
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cot_step_logs (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    task_id          INT NOT NULL,
    source_index     INT DEFAULT 0 COMMENT '文献序号，-1 表示 task 级别',
    step_key         VARCHAR(64) NOT NULL COMMENT 'step1_3_integrated/step4_input/step5_chain/step6_output',
    status           VARCHAR(16) DEFAULT 'pending',
    progress_current INT DEFAULT 0,
    progress_label   VARCHAR(256) NULL,
    cot_type         VARCHAR(128) NULL,
    cot_type_key     VARCHAR(64) NULL,
    artifact_path    VARCHAR(512) NULL,
    error_message    TEXT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_step_task (task_id, source_index, step_key),

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------
-- 5. professional_cot_type_stats 表：CoT 类型全局计数器
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS professional_cot_type_stats (
    cot_type_key VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(128) NOT NULL,
    count        INT DEFAULT 0 NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 结果确认
SELECT '=== 迁移完成 ===' AS status;
SHOW TABLES LIKE 'cot_%';
