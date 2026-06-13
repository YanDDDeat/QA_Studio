-- QA_Studio Database Schema
-- Target: MySQL 8.x (Aliyun RDS)
-- Database: qa_gen
-- MySQL connection: 117.72.57.125:13306, root/swust
-- Generated from SQLAlchemy ORM models

-- 删除旧数据库并重新创建（全新部署）
DROP DATABASE IF EXISTS qa_gen;
CREATE DATABASE IF NOT EXISTS qa_gen
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE qa_gen;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS `users` (
    `id`         INT          NOT NULL AUTO_INCREMENT,
    `username`   VARCHAR(64)  NOT NULL,
    `password_hash` VARCHAR(256) NOT NULL,
    `created_at` DATETIME     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. 数据集表（QA问答数据）
-- ============================================================
CREATE TABLE IF NOT EXISTS `datasets` (
    `id`            INT          NOT NULL AUTO_INCREMENT,
    `user_id`       INT          NOT NULL,
    `domain`        TEXT         DEFAULT NULL COMMENT '领域（支持JSON数组）',
    `category`      VARCHAR(32)  DEFAULT NULL COMMENT '枚举: 知识问答, 逻辑生成',
    `task_type`     VARCHAR(64)  DEFAULT NULL,
    `input`         TEXT         DEFAULT NULL COMMENT '问题文本',
    `output`        TEXT         DEFAULT NULL COMMENT '答案文本',
    `cot`           TEXT         DEFAULT NULL COMMENT '推理过程',
    `corpus_cate`   INT          NOT NULL DEFAULT 1,
    `scene`         TEXT         DEFAULT NULL COMMENT '与knowledge相同',
    `Assessment`    VARCHAR(256) NOT NULL DEFAULT '' COMMENT '评估备注，固定为空',
    `source`        VARCHAR(128) DEFAULT NULL COMMENT '来源名称',
    `source_id`     VARCHAR(128) DEFAULT NULL COMMENT '来源ID',
    `source_type`   VARCHAR(32)  DEFAULT '图书' COMMENT '枚举: 图书,专利,文献,其他',
    `originContent` TEXT         DEFAULT NULL COMMENT '原始文本内容(来自输入text)',
    `knowledge`     JSON         DEFAULT NULL COMMENT '知识体系(LLM生成)',
    `difficulty`    VARCHAR(32)  DEFAULT NULL COMMENT '难度等级',
    `relevance`     INT          DEFAULT NULL COMMENT '相关性评分',
    `clarity`       INT          DEFAULT NULL COMMENT '清晰度评分',
    `reasoning`     INT          DEFAULT NULL COMMENT '推理评分',
    `terminology`   INT          DEFAULT NULL COMMENT '术语评分',
    `score`         FLOAT        DEFAULT NULL COMMENT '综合评分',
    `passed`        VARCHAR(16)  NOT NULL DEFAULT '是' COMMENT '校验通过状态',
    `step_count`    VARCHAR(32)  DEFAULT NULL,
    `extra_fields`  JSON         DEFAULT NULL COMMENT '额外字段（LLM 返回的未知字段兜底）',
    `current_stage` ENUM('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','cot_filter','dataset_split','dataset_assessment') DEFAULT 'question_generate',
    `created_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_current_stage` (`current_stage`),
    KEY `idx_passed` (`passed`),
    CONSTRAINT `fk_datasets_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. 文件表（上传文件 + 校验失败文件）
-- ============================================================
CREATE TABLE IF NOT EXISTS `files` (
    `id`            INT          NOT NULL AUTO_INCREMENT,
    `user_id`       INT          NOT NULL,
    `filename`      VARCHAR(256) NOT NULL,
    `file_type`     VARCHAR(64)  DEFAULT NULL,
    `file_path`     VARCHAR(512) NOT NULL,
    `source_stage`  ENUM('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','cot_filter','dataset_split','dataset_assessment') DEFAULT NULL COMMENT '来源阶段',
    `text_field`    VARCHAR(128) NOT NULL DEFAULT 'text' COMMENT 'JSON中文本块字段名',
    `created_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    CONSTRAINT `fk_files_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. 提示词表（每个阶段独立配置，版本化管理）
-- ============================================================
CREATE TABLE IF NOT EXISTS `prompts` (
    `id`         INT          NOT NULL AUTO_INCREMENT,
    `user_id`    INT          NOT NULL,
    `stage`      ENUM('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','cot_filter','dataset_split','dataset_assessment','cot_hcot_pipeline','professional_cot') NOT NULL,
    `version`    INT          NOT NULL DEFAULT 1 COMMENT '版本号，修改时自增',
    `name`       VARCHAR(128) DEFAULT NULL COMMENT '用户自定义名称',
    `content`    MEDIUMTEXT  NOT NULL COMMENT '提示词内容',
    `model`      VARCHAR(128) DEFAULT NULL COMMENT '选择的模型',
    `reference_fields` JSON DEFAULT NULL COMMENT '附加参考字段列表',
    `template_id` VARCHAR(128) DEFAULT NULL COMMENT '提示词模板包 ID（专业 CoT / H-CoT 分组）',
    `prompt_key`  VARCHAR(128) DEFAULT NULL COMMENT '模板内 prompt 标识',
    `created_at` DATETIME     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_stage` (`stage`),
    KEY `idx_template_prompt` (`template_id`, `prompt_key`),
    CONSTRAINT `fk_prompts_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. 任务表（Pipeline各阶段执行任务）
-- ============================================================
CREATE TABLE IF NOT EXISTS `tasks` (
    `id`              INT          NOT NULL AUTO_INCREMENT,
    `user_id`         INT          NOT NULL,
    `stage`           ENUM('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','cot_filter','dataset_split','dataset_assessment','cot_hcot_pipeline','professional_cot') NOT NULL,
    `dataset_id`      INT          DEFAULT NULL,
    `file_id`         INT          DEFAULT NULL,
    `source_file_id`  INT          DEFAULT NULL COMMENT '原始输入文件ID，用于任务恢复',
    `model`           VARCHAR(128) DEFAULT NULL,
    `prompt_id`       INT          DEFAULT NULL,
    `status`          ENUM('pending','running','paused','completed','failed') NOT NULL DEFAULT 'pending',
    `progress_current` INT         DEFAULT 0 COMMENT '当前已完成数量',
    `progress_total`  INT          DEFAULT 0 COMMENT '总数量',
    `progress_label`  VARCHAR(100) DEFAULT NULL COMMENT '步骤进度阶段描述',
    `prompt_template_id` VARCHAR(128) DEFAULT NULL COMMENT '提示词模板 ID',
    `input_count`     INT DEFAULT 1 COMMENT '专业 CoT：输入文献数',
    `success_count`   INT DEFAULT 0 COMMENT '专业 CoT：成功文献数',
    `failed_count`    INT DEFAULT 0 COMMENT '专业 CoT：失败文献数',
    `sample_count`    INT DEFAULT 0 COMMENT '专业 CoT：产出样本数',
    `run_extra`       JSON DEFAULT NULL COMMENT '专业 CoT：扩展元数据',
    `created_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_stage` (`stage`),
    KEY `idx_status` (`status`),
    CONSTRAINT `fk_tasks_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_tasks_dataset_id` FOREIGN KEY (`dataset_id`) REFERENCES `datasets` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_tasks_file_id` FOREIGN KEY (`file_id`) REFERENCES `files` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_tasks_prompt_id` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. 任务日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS `task_logs` (
    `id`          INT          NOT NULL AUTO_INCREMENT,
    `task_id`     INT          NOT NULL,
    `log_content` TEXT         DEFAULT NULL,
    `created_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_task_id` (`task_id`),
    CONSTRAINT `fk_task_logs_task_id` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 7. CoT 样本表（专业 CoT 管线产出）
-- ============================================================
CREATE TABLE IF NOT EXISTS `cot_samples` (
    `id`              INT NOT NULL AUTO_INCREMENT,
    `task_id`         INT NOT NULL,
    `user_id`         INT NOT NULL,
    `source_index`    INT DEFAULT 0,
    `source`          VARCHAR(512) DEFAULT NULL,
    `source_type`     VARCHAR(32) DEFAULT 'unknown',
    `cot_type`        VARCHAR(128) DEFAULT NULL,
    `cot_type_key`    VARCHAR(64) DEFAULT NULL,
    `input`           TEXT DEFAULT NULL,
    `chainofThought`  TEXT DEFAULT NULL,
    `output`          TEXT DEFAULT NULL,
    `evidence_trace`  TEXT DEFAULT NULL,
    `step_results`    JSON DEFAULT NULL COMMENT '各步骤 LLM 原始返回',
    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_cot_task` (`task_id`),
    KEY `idx_cot_type` (`cot_type_key`),
    KEY `idx_cot_user` (`user_id`),
    CONSTRAINT `fk_cot_samples_task_id` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cot_samples_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 8. CoT 步骤日志表（专业 CoT 管线每篇文献每步骤日志）
-- ============================================================
CREATE TABLE IF NOT EXISTS `cot_step_logs` (
    `id`               INT NOT NULL AUTO_INCREMENT,
    `task_id`          INT NOT NULL,
    `source_index`     INT DEFAULT 0 COMMENT '文献序号，-1表示run级别',
    `step_key`         VARCHAR(64) NOT NULL COMMENT 'step1_3_integrated/step4_input/step5_chain/step6_output',
    `status`           VARCHAR(16) DEFAULT 'pending' COMMENT 'pending/running/completed/failed/skipped',
    `progress_current` INT DEFAULT 0,
    `progress_label`   VARCHAR(256) DEFAULT NULL,
    `cot_type`         VARCHAR(128) DEFAULT NULL,
    `cot_type_key`     VARCHAR(64) DEFAULT NULL,
    `artifact_path`    VARCHAR(512) DEFAULT NULL,
    `error_message`    TEXT DEFAULT NULL,
    `created_at`       DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_step_task` (`task_id`, `source_index`, `step_key`),
    CONSTRAINT `fk_cot_step_logs_task_id` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- admin账号由服务启动时自动初始化（bcrypt生成真实密码hash）
-- 不要手动INSERT，否则密码hash无效
