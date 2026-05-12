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
    `domain`        VARCHAR(128) DEFAULT NULL,
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
    `stage`      ENUM('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','cot_filter','dataset_split','dataset_assessment') NOT NULL,
    `version`    INT          NOT NULL DEFAULT 1 COMMENT '版本号，修改时自增',
    `content`    MEDIUMTEXT  NOT NULL COMMENT '提示词内容',
    `model`      VARCHAR(128) DEFAULT NULL COMMENT '选择的模型',
    `created_at` DATETIME     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_stage` (`stage`),
    CONSTRAINT `fk_prompts_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. 任务表（Pipeline各阶段执行任务）
-- ============================================================
CREATE TABLE IF NOT EXISTS `tasks` (
    `id`              INT          NOT NULL AUTO_INCREMENT,
    `user_id`         INT          NOT NULL,
    `stage`           ENUM('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','cot_filter','dataset_split','dataset_assessment') NOT NULL,
    `dataset_id`      INT          DEFAULT NULL,
    `file_id`         INT          DEFAULT NULL,
    `model`           VARCHAR(128) DEFAULT NULL,
    `prompt_id`       INT          DEFAULT NULL,
    `status`          ENUM('pending','running','completed','failed') NOT NULL DEFAULT 'pending',
    `progress_current` INT         DEFAULT 0 COMMENT '当前已完成数量',
    `progress_total`  INT          DEFAULT 0 COMMENT '总数量',
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

-- admin账号由服务启动时自动初始化（bcrypt生成真实密码hash）
-- 不要手动INSERT，否则密码hash无效