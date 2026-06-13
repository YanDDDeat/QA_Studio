/*
 Navicat Premium Data Transfer

 Source Server         : 192.168.217.62
 Source Server Type    : MySQL
 Source Server Version : 80046
 Source Host           : localhost:13306
 Source Schema         : qa_gen

 Target Server Type    : MySQL
 Target Server Version : 80046
 File Encoding         : 65001

 Date: 13/06/2026 23:57:15
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for cot_samples
-- ----------------------------
DROP TABLE IF EXISTS `cot_samples`;
CREATE TABLE `cot_samples`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` int NOT NULL,
  `user_id` int NOT NULL,
  `source_index` int NULL DEFAULT 0,
  `source` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `source_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'unknown',
  `cot_type` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `cot_type_key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `input` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `chainofThought` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `output` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `evidence_trace` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `step_results` json NULL COMMENT '各步骤 LLM 原始返回',
  `created_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_cot_task`(`task_id`) USING BTREE,
  INDEX `idx_cot_type`(`cot_type_key`) USING BTREE,
  INDEX `idx_cot_user`(`user_id`) USING BTREE,
  CONSTRAINT `cot_samples_ibfk_1` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `cot_samples_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for cot_step_logs
-- ----------------------------
DROP TABLE IF EXISTS `cot_step_logs`;
CREATE TABLE `cot_step_logs`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` int NOT NULL,
  `source_index` int NULL DEFAULT 0 COMMENT '文献序号，-1 表示 task 级别',
  `step_key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'step1_3_integrated/step4_input/step5_chain/step6_output',
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'pending',
  `progress_current` int NULL DEFAULT 0,
  `progress_label` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `cot_type` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `cot_type_key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `artifact_path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_step_task`(`task_id`, `source_index`, `step_key`) USING BTREE,
  CONSTRAINT `cot_step_logs_ibfk_1` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for datasets
-- ----------------------------
DROP TABLE IF EXISTS `datasets`;
CREATE TABLE `datasets`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `domain` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL COMMENT 'é¢†åŸŸï¼ˆæ”¯æŒJSONæ•°ç»„ï¼‰',
  `category` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `task_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `input` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `output` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `cot` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `corpus_cate` int NOT NULL,
  `scene` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `Assessment` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `source_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `source_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `originContent` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `knowledge` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `step_count` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `extra_fields` json NULL,
  `difficulty` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `relevance` int NULL DEFAULT NULL,
  `clarity` int NULL DEFAULT NULL,
  `reasoning` int NULL DEFAULT NULL,
  `terminology` int NULL DEFAULT NULL,
  `score` float NULL DEFAULT NULL,
  `passed` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `current_stage` enum('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','quality_check','cot_filter','dataset_split','dataset_assessment','generic') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` datetime(0) NULL DEFAULT NULL,
  `updated_at` datetime(0) NULL DEFAULT NULL,
  `file_id` int NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_datasets_user_id`(`user_id`) USING BTREE,
  INDEX `ix_datasets_file_id`(`file_id`) USING BTREE,
  INDEX `idx_datasets_user_stage_created`(`user_id`, `current_stage`, `created_at`) USING BTREE,
  CONSTRAINT `datasets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_datasets_file_id` FOREIGN KEY (`file_id`) REFERENCES `files` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1700065 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for files
-- ----------------------------
DROP TABLE IF EXISTS `files`;
CREATE TABLE `files`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `filename` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `file_path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_stage` enum('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','quality_check','cot_filter','dataset_split','dataset_assessment','generic') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `text_field` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(0) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_files_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `files_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1462 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for llm_configs
-- ----------------------------
DROP TABLE IF EXISTS `llm_configs`;
CREATE TABLE `llm_configs`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NULL DEFAULT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `base_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `api_key` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `proxy` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `models` json NOT NULL,
  `default_model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(0) NULL DEFAULT NULL,
  `updated_at` datetime(0) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_llm_configs_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `fk_llm_configs_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 24 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for professional_cot_type_stats
-- ----------------------------
DROP TABLE IF EXISTS `professional_cot_type_stats`;
CREATE TABLE `professional_cot_type_stats`  (
  `cot_type_key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `count` int NOT NULL DEFAULT 0,
  PRIMARY KEY (`cot_type_key`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for prompts
-- ----------------------------
DROP TABLE IF EXISTS `prompts`;
CREATE TABLE `prompts`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NULL DEFAULT NULL,
  `stage` enum('question_generate','knowledge_generate','answer_generate','answer_validate','question_validate','data_evaluate','dataset_assessment','quality_check','cot_quality_check','cot_hcot','professional_cot','generic_generate','generic') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'question_generate',
  `version` int NOT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `content` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'æç¤ºè¯å†…å®¹',
  `model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` datetime(0) NULL DEFAULT NULL,
  `llm_config_id` int NULL DEFAULT NULL,
  `is_default` tinyint(1) NOT NULL DEFAULT 0,
  `reference_fields` json NULL COMMENT 'é™„åŠ å‚è€ƒå­—æ®µåˆ—è¡¨',
  `template_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '提示词模板包 ID',
  `prompt_key` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '模板内 prompt 标识',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_prompts_user_id`(`user_id`) USING BTREE,
  INDEX `ix_prompts_llm_config_id`(`llm_config_id`) USING BTREE,
  INDEX `idx_template_prompt`(`template_id`, `prompt_key`) USING BTREE,
  CONSTRAINT `fk_prompts_llm_config_id` FOREIGN KEY (`llm_config_id`) REFERENCES `llm_configs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `prompts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 257 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for task_logs
-- ----------------------------
DROP TABLE IF EXISTS `task_logs`;
CREATE TABLE `task_logs`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` int NOT NULL,
  `log_content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` datetime(0) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_task_logs_task_id`(`task_id`) USING BTREE,
  CONSTRAINT `task_logs_ibfk_1` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1688029 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for tasks
-- ----------------------------
DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `stage` enum('question_generate','knowledge_generate','answer_generate','answer_validate','question_validate','data_evaluate','dataset_assessment','quality_check','cot_quality_check','cot_hcot','professional_cot','generic_generate','generic','text_preprocess','dataset_split','cot_filter') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'question_generate',
  `dataset_id` int NULL DEFAULT NULL,
  `file_id` int NULL DEFAULT NULL,
  `source_file_id` int NULL DEFAULT NULL COMMENT 'åŽŸå§‹è¾“å…¥æ–‡ä»¶IDï¼Œç”¨äºŽä»»åŠ¡æ¢å¤',
  `model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `prompt_id` int NULL DEFAULT NULL,
  `status` enum('pending','running','completed','failed','paused') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `progress_current` int NULL DEFAULT NULL,
  `progress_total` int NULL DEFAULT NULL,
  `created_at` datetime(0) NULL DEFAULT NULL,
  `updated_at` datetime(0) NULL DEFAULT NULL,
  `input_count` int NULL DEFAULT 1 COMMENT '专业 CoT：输入文献数',
  `success_count` int NULL DEFAULT 0 COMMENT '专业 CoT：成功文献数',
  `failed_count` int NULL DEFAULT 0 COMMENT '专业 CoT：失败文献数',
  `sample_count` int NULL DEFAULT 0 COMMENT '专业 CoT：产出样本数',
  `run_extra` json NULL COMMENT '专业 CoT：扩展元数据',
  `progress_label` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '步骤进度阶段描述',
  `prompt_template_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '提示词模板 ID',
  `parent_task_id` int NULL DEFAULT NULL COMMENT '子步骤链接到父流水线',
  `pipeline_mode` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'hcot or cot',
  `pipeline_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '流水线名称',
  `step_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '步骤标识',
  `chunk_index` int NULL DEFAULT NULL COMMENT 'chunk 序号',
  `l0_question_index` int NULL DEFAULT NULL COMMENT 'L0 总问题序号',
  `total_chunks` int NULL DEFAULT NULL COMMENT '流水线总 chunk 数',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `dataset_id`(`dataset_id`) USING BTREE,
  INDEX `file_id`(`file_id`) USING BTREE,
  INDEX `prompt_id`(`prompt_id`) USING BTREE,
  INDEX `ix_tasks_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `tasks_ibfk_2` FOREIGN KEY (`dataset_id`) REFERENCES `datasets` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `tasks_ibfk_3` FOREIGN KEY (`file_id`) REFERENCES `files` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `tasks_ibfk_4` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 927 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(0) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `ix_users_username`(`username`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 16 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Procedure structure for safe_add_column
-- ----------------------------
DROP PROCEDURE IF EXISTS `safe_add_column`;
delimiter ;;
CREATE PROCEDURE `safe_add_column`(IN tbl_name VARCHAR(128),
    IN col_name VARCHAR(128),
    IN col_def  TEXT)
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
END
;;
delimiter ;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- Prompt Seed Data (professional_cot templates)
-- ============================================================

USE qa_gen;

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域专业 CoT 数据构建专家。请阅读我提供的完整文献内容，先提取关键实验信息，再判断该文献适合构建 10 类 CoT 中的哪些类型。

重要要求：
1. 只基于输入文献中的证据，不凭常识补全。
2. 不要直接生成最终 CoT 样本。
3. 不要生成训练 input、chainofThought 或 output。
4. 优先依据结果与讨论、实验部分、图表、表征数据和补充信息。
5. 不要只根据摘要判断。
6. 博士论文中优先使用作者自己的实验章节，不把综述章节当作实验事实。
7. 如果证据不足以支持某类 CoT，请标记为 not_build。

输入：
source_id: <文献编号、题名、DOI、章节编号或内部编号，可为空>
source_type: <research_paper / phd_thesis / unknown>
full_literature:
<在这里粘贴完整文献内容>

请只输出以下 JSON，不要输出其他解释：

{
  "source_id": "...",
  "source_type": "research_paper / phd_thesis / unknown",
  "literature_usability": {
    "decision": "yes / partial / no",
    "reason": "简要说明该文献是否适合构建 CoT",
    "usable_parts": ["可用章节、图表、实验部分或补充信息位置"]
  },
  "key_information": {
    "research_object": "具体材料、分子、体系或研究对象",
    "research_goal": "文献想提升、解释、筛选、优化或验证的核心目标",
    "baseline_or_problem": "基准样品、原始体系、空白组或待解决短板",
    "key_variables": [
      "被改变的结构、组成、配方、工艺、条件或候选对象"
    ],
    "control_or_comparison_samples": [
      "对照样品、系列样品、候选对象、失败样品或商业对照"
    ],
    "performance_metrics": [
      "性能指标、单位和测试条件"
    ],
    "main_observed_results": [
      "主要实验结果、趋势或性能对比，只写事实"
    ],
    "mechanism_or_explanation": [
      "有表征、计算或对照证据支撑的机制解释"
    ],
    "process_or_recipe_information": [
      "关键工艺条件、配方组分、比例、浓度、温度、时间、溶剂、pH 等"
    ],
    "failure_or_limitations": [
      "失败现象、副作用、负例、条件限制或文献未解决问题"
    ],
    "evidence_locations": [
      "支撑上述信息的章节、图、表或补充信息位置"
    ]
  },
  "cot_type_judgement": [
    {
      "cot_type": "性能提升路径 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "为什么可构建或不可构建",
      "key_evidence": ["支撑该判断的关键证据"],
      "missing_or_risky_evidence": ["缺失证据或构建风险"]
    },
    {
      "cot_type": "构效关系 / 结构-性能关系 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "候选分子 / 材料优选决策 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "反事实结构改造 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "失败原因诊断 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "多目标约束优化 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "机理到设计策略迁移 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "实验条件 / 制备工艺优化 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "实验方案生成 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "实验设计配方 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    }
  ],
  "recommended_next_action": {
    "priority_cot_types": ["优先构建的 CoT 类型"],
    "types_to_skip": ["不建议构建的 CoT 类型"],
    "notes_for_next_step": "进入后续 input 构建时需要保留的关键边界、条件或风险"
  }
}

判定参考：
- 性能提升路径：需要有基准短板、改性变量、性能提升和机制证据。
- 构效关系：需要有同系列样品、系统变量和性能趋势。
- 候选优选：需要有多个候选对象和可比较指标。
- 反事实结构改造：需要有可替换结构变量、相似对照或趋势证据。
- 失败原因诊断：需要有失败样品、性能下降、副作用或失效证据。
- 多目标约束优化：需要有两个及以上目标，并体现冲突或折中。
- 机理到设计策略迁移：需要有已验证机制和可调控变量。
- 实验条件 / 工艺优化：需要有工艺参数变化范围、性能响应趋势和最优窗口。
- 实验方案生成：需要有明确目标、候选变量、对照逻辑和验证方法。
- 实验设计配方：需要有配方组分、比例/浓度范围、工艺条件和性能反馈。', 'system_default_v1', 'common.step1_3',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“性能提升路径 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
性能提升路径 CoT

生成要求：
1. input 必须表现为“针对体系 X 的性能短板，如何提出提升性能 Z 的路径”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. input 必须包含具体研究对象或材料/分子/催化/储能/吸附/传感体系 X。
4. input 必须包含当前性能短板、性能基线或待突破的问题，例如活性不足、选择性低、循环稳定性差、容量衰减、传输受限、能量密度不足、感度偏高、产率低、响应慢等。
5. input 必须包含目标性能指标 Z，并尽量保留必要单位、测试条件或评价场景。
6. input 必须包含至少一个限制性能提升的瓶颈线索，例如电子结构不匹配、活性位点不足、界面传输慢、孔道扩散受限、结构稳定性差、副反应多、结晶/形貌不理想、组分比例不合理等。
7. input 必须包含可调控因素，例如结构单元、取代基、掺杂元素、缺陷浓度、晶相、形貌、孔结构、界面层、负载量、组分比例、制备条件或后处理条件。
8. 如果有性能趋势、对照样品、失败条件、最优窗口或机制线索，应写入 input，但不得把最终提升路径直接写成答案。
9. input 应要求模型提出性能提升路径、说明每条路径对应的瓶颈和作用机制、判断潜在副作用，并给出验证指标。
10. 不要把任务写成“选择哪个候选最好”；如果核心任务是候选排序，应转入“候选分子 / 材料优选决策 CoT”。
11. 不要把任务写成完整实验步骤设计；如果核心任务是实验分组、操作流程和对照设置，应转入“实验方案生成 CoT”。
12. 不要把任务限定为单一反事实替换；如果核心任务是“A 替换为 B 后性能如何变化”，应转入“反事实结构改造 CoT”。
13. 如果缺少研究体系、目标性能或可调控因素，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 体系当前在性能 Z 上存在短板，主要表现为 A；已有信息提示该短板可能与 B 瓶颈有关，可调控因素包括 C、D 和 E。请围绕目标性能 Z 提出可行的性能提升路径，说明每条路径对应的限制因素、预期作用机制、潜在副作用、优先级和验证指标。”

请按以下 JSON 输出：

{
  "cot_type": "性能提升路径 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "current_performance_gap": "当前性能短板或性能基线",
    "target_performance": "目标性能指标 Z",
    "bottleneck_clues": [
      "限制性能提升的瓶颈线索"
    ],
    "adjustable_factors": [
      "可调控结构、组成、界面、工艺或测试因素"
    ],
    "known_trends_or_comparisons": [
      "可用于构建提升路径的趋势、对照或机制线索"
    ],
    "constraints": [
      "稳定性、安全性、成本、可制备性、测试条件或适用范围"
    ],
    "required_task": "提出性能提升路径 / 解释作用机制 / 判断副作用 / 给出优先级和验证指标"
  },
  "evidence_used": [
    "用于生成 input 的关键信息，保留体系、性能短板、可调控因素、趋势、机制或约束"
  ],
  "quality_check": {
    "is_specific": true,
    "has_research_system": true,
    "has_current_performance_gap": true,
    "has_target_performance": true,
    "has_bottleneck_clues": true,
    "has_adjustable_factors": true,
    "asks_for_improvement_paths": true,
    "asks_for_mechanism_and_side_effects": true,
    "asks_for_priority_and_validation": true,
    "does_not_turn_into_candidate_selection": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_turn_into_counterfactual_modification": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'performance_improvement.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“性能提升路径 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
性能提升路径 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的“性能提升路径”生成。
3. 必须先明确目标性能 Z、当前短板和需要突破的性能边界。
4. 必须把性能 Z 拆解为若干影响通道，例如活性位点、电子结构、传质/传输、界面接触、相稳定性、孔结构、结晶质量、缺陷结构、副反应、力学稳定性、热稳定性或安全性。
5. 必须判断哪些通道更可能是主导瓶颈，并说明判断逻辑。
6. 必须把主导瓶颈映射到可调控因素，例如组成调节、结构改造、掺杂/取代、缺陷调控、形貌控制、界面工程、孔道调控、工艺窗口优化、后处理或复合策略。
7. 必须形成至少一条核心提升路径，并可根据证据强度形成辅助路径或备选路径。
8. 每条路径都必须说明“针对的瓶颈 -> 调控手段 -> 结构/过程变化 -> 性能提升方向”的因果链或条件性关联链。
9. 必须分析潜在副作用和折中关系，例如提升活性但降低稳定性、增加缺陷但引入副反应、改善传输但降低密度、提高反应性但增加安全风险等。
10. 必须给出路径优先级判断，说明优先推进哪条路径以及原因。
11. 必须给出验证建议，包括关键表征、性能测试、对照样品、稳定性测试或计算模拟。
12. 不要引入文献没有支撑的新变量、新机制、新数值或新性能结论。
13. 如果证据只支持相关性，不要写成确定因果，应使用“可能”“倾向于”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源。
17. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
18. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据改写为性能事实、瓶颈判断、结构/过程影响和专业推断。
19. 不要使用“根据已有数据”“对照实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
20. 不要生成最终 output。

推荐推理步骤结构：
1. 明确目标性能、当前短板和提升目标。
2. 拆解性能 Z 的关键决定因素。
3. 识别最可能限制性能提升的主导瓶颈。
4. 将瓶颈映射到可调控结构、组成、界面、工艺或测试因素。
5. 构建核心提升路径，并说明其作用机制。
6. 构建辅助或备选提升路径，并说明适用场景。
7. 分析路径之间的副作用、折中关系和边界条件。
8. 给出优先级排序和验证指标。

请按以下 JSON 输出：

{
  "cot_type": "性能提升路径 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留体系、性能短板、变量、趋势、机制或约束；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、测试条件、调控范围、性能指标、证据强度或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_target_performance": true,
    "has_performance_gap": true,
    "decomposes_performance_factors": true,
    "identifies_main_bottleneck": true,
    "maps_bottleneck_to_adjustable_factors": true,
    "proposes_core_improvement_path": true,
    "proposes_auxiliary_or_alternative_paths": true,
    "links_path_to_mechanism": true,
    "mentions_tradeoffs_and_side_effects": true,
    "prioritizes_paths": true,
    "includes_validation_metrics": true,
    "keeps_uncertainty": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'performance_improvement.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“性能提升路径 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
性能提升路径 CoT

生成要求：
1. output 必须直接回答 input 中提出的性能提升路径任务，开头即说明该体系应优先突破的性能短板和推荐提升路径，不能用“综上”“总体来看”“可以从多个方面优化”等泛泛开场。
2. output 必须紧扣“性能提升路径”任务，不要答成实验方案、配方设计、工艺优化或泛泛机理解释。回答重点应是“性能短板 -> 主导瓶颈 -> 调控手段 -> 结构/过程变化 -> 性能收益 -> 风险与验证”。
3. 如果 input 或 chainofThought 没有明确目标性能、性能短板、可调控变量、机制依据或验证指标，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成提升路径。
4. output 应比单句建议更详细，必须给出可执行、可验证的分层提升路径；但不要生成完整实验分组、详细操作流程或配方矩阵。
5. 必须给出总体提升思路，说明当前性能短板应优先从哪些主导瓶颈入手突破，不能只写“通过结构优化提升性能”。
6. 必须给出至少一条优先路径；如果证据支持，可给出辅助路径或备选路径。不要为了显得完整而强行生成多条路径，证据只支持一条时应集中写清楚这一条。
7. 每条路径都必须包含：针对的瓶颈、关键调控手段、预期结构/组成/界面/传输/反应过程变化、预期性能收益、潜在副作用和验证方法。
8. 每个关键判断都必须绑定具体材料体系、性能指标、结构因素、工艺变量、组分变量或机制通道，不能只写“改善结构”“增强稳定性”“提高活性”“促进协同作用”“实现综合性能提升”等空泛表达。
9. 必须说明路径优先级及理由。优先级理由应基于主导瓶颈对应性、机制证据强弱、调控可行性、副作用大小或验证可操作性，不能只写“因此优先推荐”。
10. 如果某条路径可能提升目标性能但牺牲稳定性、安全性、选择性、传输、加工性、相容性或其他指标，必须明确说明折中关系，不能只保留有利结论。
11. 潜在副作用和适用边界必须具体到结构、组分、界面、传输、反应过程、稳定性、测试条件或应用场景层面，不能只写“存在一定风险”“仍需进一步优化”。
12. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于验证哪个瓶颈、结构变化、机制通道、性能收益或副作用是否被抑制。
13. 必须给出成功判据或验证指标，例如目标性能变化、结构表征信号、稳定性指标、对照样品差异、失效现象是否被抑制或副作用是否处于可接受范围。
14. output 应按清晰顺序组织，建议采用“总体提升思路 -> 优先路径 -> 辅助/备选路径 -> 路径优先级理由 -> 风险与边界 -> 验证方式与成功判据”的结构，避免把结论、原因、风险和验证混在一起。
15. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“可实现综合性能提升”等。若表达意义，必须落到具体性能、机制、路径或应用边界上。
16. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新实验条件、新测试指标或新结论。
17. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该条件范围内”“需要进一步验证”等限定表达。
18. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
19. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
20. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该体系的性能提升应优先从 B 瓶颈入手。优先路径是通过 C 调控手段改善 M 结构/过程，使目标性能 Z 得到提升；该路径优先于其他方向，是因为它直接对应当前主导瓶颈，且副作用更容易通过 R 表征和 S 性能测试验证。辅助路径可围绕 D 变量展开，用于进一步缓解 N 限制，但需要关注 P 副作用，例如稳定性下降、传输受阻或安全性变差。判断该路径有效的标准是 Z 指标出现预期改善，M 结构/过程信号得到确认，同时 P 风险没有超过可接受范围。该判断只适用于 Q 体系、条件或变量范围内，超出该边界需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "性能提升路径 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少目标性能、性能短板、可调控变量、机制依据、风险信息或验证指标"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "target_performance": "需要提升的目标性能",
    "main_performance_bottleneck": "当前优先突破的性能短板或主导瓶颈",
    "overall_strategy": "总体性能提升思路，必须说明从哪些瓶颈入手以及为什么",
    "prioritized_improvement_paths": [
      {
        "priority": "优先 / 辅助 / 备选",
        "path_name": "路径名称，必须反映真实调控对象或机制通道",
        "target_bottleneck": "该路径针对的性能瓶颈",
        "key_adjustment": "关键调控手段，必须来自 input 或 chainofThought",
        "expected_structure_or_process_change": "预期结构、组成、界面、传输或反应过程变化",
        "expected_performance_benefit": "预期性能收益或变化方向",
        "priority_reason": "为什么该路径优先、辅助或备选，必须绑定瓶颈对应性、机制证据、风险或验证可行性",
        "potential_side_effects": [
          "潜在副作用、折中关系或风险，必须具体到结构、过程、性能或应用边界"
        ],
        "validation_methods": [
          {
            "method": "表征、测试、对照或计算方法",
            "validation_target": "验证哪个瓶颈、结构变化、机制、性能收益或副作用",
            "success_signal": "什么结果支持该路径有效"
          }
        ]
      }
    ],
    "recommended_sequence": [
      "建议优先验证和推进的路径顺序，以及排序理由"
    ],
    "success_criteria": [
      "判断性能提升路径有效的关键指标或判据"
    ],
    "boundary_conditions": [
      "适用条件、体系边界、不确定性或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留体系、性能短板、变量、趋势、机制或约束；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_performance_improvement_task": true,
    "does_not_repeat_chain": true,
    "has_target_performance": true,
    "has_main_performance_bottleneck": true,
    "has_overall_strategy": true,
    "has_prioritized_paths": true,
    "path_names_are_specific": true,
    "each_path_has_bottleneck": true,
    "each_path_has_adjustment": true,
    "each_path_has_mechanism": true,
    "each_path_has_expected_benefit": true,
    "each_path_has_priority_reason": true,
    "mentions_specific_tradeoffs_and_side_effects": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "has_success_criteria": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'performance_improvement.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“构效关系 / 结构-性能关系 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、control_or_comparison_samples、performance_metrics、main_observed_results、cot_type_judgement>

目标 CoT 类型：
构效关系 / 结构-性能关系 CoT

生成要求：
1. input 必须表现为“归纳结构/组成变量与性能之间关系”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含同一可比系列样品或同一体系下的变量系列。
4. 必须包含被系统改变的结构、组成、形貌、晶相、缺陷、官能团、取代基、孔结构、掺杂比例或配方变量。
5. 必须包含目标性能指标 Z，并保留必要单位和测试条件。
6. 必须包含性能随变量变化的趋势，例如升高、降低、先升后降、存在最优点、平台期、异常点等。
7. 如果存在异常样品或非线性趋势，应写入 input，并要求解释。
8. input 应要求模型归纳结构-性能关系，说明主导因素、趋势原因和适用边界。
9. 不要在 input 中直接给出最终结构-性能规则。
10. 不要把候选优选任务混入本类 input；如果主要任务是“选哪个样品最好”，应转入候选优选 CoT。
11. 如果缺少可比系列样品、系统变量或性能趋势，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“给定 X 系列样品的对比结果，主要结构/组成变量 Y 从 A 到 B 逐步变化，目标性能 Z 呈现某种趋势，其中样品 S 可能是异常点或最优点。请归纳 Y 与 Z 之间的结构-性能关系，解释趋势形成原因，并说明该规则的适用边界。”

请按以下 JSON 输出：

{
  "cot_type": "构效关系 / 结构-性能关系 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "series_system": "同一可比系列样品或体系",
    "structure_or_composition_variable": "被系统改变的变量 Y",
    "variable_range_or_levels": "变量范围或样品水平",
    "target_performance": "性能指标 Z",
    "performance_trend": "性能随变量变化的趋势",
    "anomalies_or_optimum": ["异常点、最优点或非线性趋势"],
    "required_task": "归纳结构-性能关系 / 解释趋势 / 说明异常点 / 给出边界"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留样品系列、变量、性能指标、趋势或条件"
  ],
  "quality_check": {
    "is_specific": true,
    "has_comparable_series": true,
    "has_systematic_variable": true,
    "has_performance_metric": true,
    "has_performance_trend": true,
    "asks_for_structure_property_rule": true,
    "asks_for_boundary_conditions": true,
    "does_not_turn_into_candidate_selection": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'structure_property.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“构效关系 / 结构-性能关系 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、control_or_comparison_samples、performance_metrics、main_observed_results、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
构效关系 / 结构-性能关系 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的结构-性能规则形成。
3. 必须先确认样品是否属于同一可比系列。
4. 必须识别被系统改变的结构、组成、形貌、晶相、缺陷、孔结构、官能团、取代基或比例变量。
5. 必须归纳性能随变量变化的趋势。
6. 必须判断主导性能变化的结构因素。
7. 如果存在异常点、平台期、最优点或非线性趋势，必须解释其可能原因。
8. 必须说明该结构-性能关系的适用边界，不能写成普适规律。
9. 必须给出进一步验证该关系的表征、性能测试或计算方法。
10. 不能引入文献没有支撑的新变量、新机制或新性能结论。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据转写为系列事实、变量关系、性能趋势和专业判断。
17. 不要使用“根据已有数据”“对比实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 确认样品属于同一可比系列。
2. 找出被系统改变的结构或组成变量。
3. 比较性能随变量变化的趋势。
4. 判断主导性能变化的结构因素。
5. 解释异常点、最优点或非线性趋势。
6. 形成结构-性能关系规则。
7. 判断规则适用边界。
8. 给出进一步验证方法。

请按以下 JSON 输出：

{
  "cot_type": "构效关系 / 结构-性能关系 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留样品系列、变量、性能指标、趋势、异常点或条件；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的样品系列、变量范围、测试条件或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "confirms_comparable_series": true,
    "identifies_systematic_variable": true,
    "has_performance_trend": true,
    "identifies_dominant_structure_factor": true,
    "handles_anomaly_or_nonlinearity": true,
    "forms_structure_property_rule": true,
    "keeps_boundary_conditions": true,
    "includes_validation_methods": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'structure_property.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“构效关系 / 结构-性能关系 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
构效关系 / 结构-性能关系 CoT

生成要求：
1. output 必须直接回答 input 中提出的结构-性能关系归纳任务，开头即给出“结构/组成变量 Y 与性能指标 Z 的关系判断”，不能用“综上”“总体来看”“可以从多个方面分析”等泛泛开场。
2. output 必须紧扣“构效关系 / 结构-性能关系”任务，不要答成候选优选、性能提升路径、实验方案或泛泛机理解释。回答重点应是“同系列样品 -> 主变量变化 -> 性能响应趋势 -> 主导结构因素 -> 规则边界”。
3. 如果 input 或 chainofThought 没有明确样品系列、结构/组成变量、性能指标或可归纳趋势，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行总结构效规律。
4. 必须明确说明样品是否属于可比较系列，以及主要变量是什么。若变量不单一或存在多因素耦合，output 必须说明该规则只能作为趋势性判断，不能写成单变量确定因果。
5. 必须明确给出变量 Y 的变化方向和性能 Z 的响应趋势，例如升高、降低、先升后降、存在最优点、平台期、阈值效应或异常点，不能只写“二者有关”“存在影响”“表现更好”。
6. 每个关键结论都必须绑定具体结构因素、性能指标和趋势方向，不能只写“优化结构”“改善性能”“增强稳定性”“构效关系明显”等空泛表达。
7. 必须说明主导性能变化的结构因素，并解释该结构因素如何影响传输、界面、活性位点、缺陷、孔结构、晶相、稳定性、反应过程或其他与性能相关的机制通道。
8. 如果存在异常点、最优点或非线性趋势，output 必须说明可能原因；如果没有足够证据解释，应明确写“异常点原因需要进一步验证”，不要补写无依据机制。
9. 必须保留适用边界和不确定性，说明该规则适用于哪个样品系列、变量范围、测试条件或体系边界，不能把特定系列规律写成普适规律。
10. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认结构变量变化、验证性能趋势、解释异常点或排除其他变量干扰。
11. output 应按清晰顺序组织，建议采用“关系结论 -> 变量与性能趋势 -> 主导结构因素/机制解释 -> 异常点或最优点 -> 适用边界 -> 验证方式”的结构，避免把结论、原因、风险和验证混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“说明材料具有优异性能”等。若表达意义，必须落到具体结构变量、性能指标或应用边界上。
13. 不要为了显得完整而强行生成复杂规律。如果证据只支持简单单调趋势，应集中写清楚该趋势；如果证据不足以判断趋势，应在 missing_information 或 applicability_boundary 中说明。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新性能指标或新性能结论。
15. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该系列中”“在该变量范围内”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“对比实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“在该系列样品中，结构/组成变量 Y 是影响性能 Z 的关键因素。随着 Y 从 A 向 B 变化，Z 呈现升高/降低/先升后降/平台期/最优点趋势，说明 Y 主要通过 M 结构或过程通道影响 Z。若 Y 继续偏离合适范围，可能出现 N 副作用或异常表现，使 Z 不再继续改善。因此，该结构-性能规则只适用于 Q 样品系列、变量范围或测试条件内，不能直接外推到其他体系。后续应通过 R 表征确认 Y 的结构变化，通过 S 性能测试复核 Z 的趋势，并通过 T 对照或计算排除其他变量干扰。”

请按以下 JSON 输出：

{
  "cot_type": "构效关系 / 结构-性能关系 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少样品系列、结构变量、性能指标、趋势证据或边界条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "comparability_statement": "样品是否属于可比较系列，以及是否存在多变量耦合或干扰",
    "structure_property_rule": "核心结构-性能关系规则",
    "variable_trend": "结构/组成变量的变化方向或范围",
    "performance_trend": "性能指标的变化趋势",
    "dominant_structure_factor": "主导性能变化的结构因素",
    "mechanism_to_performance_link": "结构因素如何通过具体机制通道影响性能",
    "anomaly_or_optimum_explanation": "异常点、最优点、平台期或非线性趋势解释；证据不足时说明需要进一步验证",
    "applicability_boundary": [
      "该规则适用的样品系列、变量范围、测试条件、体系边界或不确定性"
    ],
    "validation_methods": [
      {
        "method": "表征、性能测试、对照或计算方法",
        "validation_target": "验证哪个结构变量、性能趋势、机制解释、异常点或干扰因素",
        "success_signal": "什么结果支持该结构-性能关系成立"
      }
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留样品系列、变量、性能指标、趋势、异常点或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_structure_property_task": true,
    "has_comparability_statement": true,
    "has_structure_property_rule": true,
    "has_variable_trend": true,
    "has_performance_trend": true,
    "identifies_dominant_structure_factor": true,
    "links_structure_factor_to_performance": true,
    "handles_anomaly_or_optimum": true,
    "keeps_boundary_conditions": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "does_not_turn_into_candidate_selection": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'structure_property.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“候选分子 / 材料优选决策 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output，也不要提前给出最终推荐候选。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

目标 CoT 类型：
候选分子 / 材料优选决策 CoT

生成要求：
1. input 必须表现为一个具体候选优选任务，而不是泛泛比较。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含明确应用场景或选择目标，例如电池电极、催化反应、吸附分离、含能材料、药物分子、涂层、聚合物体系等。
4. 必须包含至少 2 个候选对象，优先包含 3 个或以上候选对象。
5. 候选对象必须是具体分子、材料、样品、配方、结构或工艺路线，不要只写宽泛类别。
6. 必须包含可比较指标，例如活性、选择性、稳定性、容量、能量密度、安全性、感度、成本、合成难度、环境适应性、循环寿命、可加工性等。
7. 必须说明指标优先级或应用约束。如果文献中没有显式优先级，应根据应用场景给出“当前场景下更应优先考虑的指标”，并标注为场景约束，而不是绝对规律。
8. input 应呈现候选之间的优缺点差异，但不要直接写“最佳候选是 A”。
9. input 应要求模型做出选择，并说明理由、风险和条件变化下选择是否会改变。
10. 最终 input 中不要使用“候选 A / 候选 B / 候选 C”这类占位符，除非原始样品名称本身就是 A、B、C。
11. 不要写成“候选A（化合物3）”“候选B（样品 S2）”这类占位符-真实名称混合表达；应直接使用真实名称，例如“化合物 3”“样品 S2”“Ni-Fe-LDH-2”。
12. 如果需要提高可读性，可以写“化合物 3、化合物 5 和化合物 7 三个候选物”，不要额外引入 A/B/C 映射。
13. “实测密度”“理论密度”“计算能量”等术语只有在它们本身是评价指标时才保留；不要写成“文献实测”“报道实测”等来源化表达。
14. 如果候选数量不足、缺少可比较指标、没有应用场景或无法判断优先级，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“针对 X 应用场景，需要在化合物 3、化合物 5 和化合物 7 中选择更合适的材料/分子。已知化合物 3 在指标 P 上表现较好但存在 Q 风险，化合物 5 在稳定性或安全性上更优但关键性能较弱，化合物 7 在综合性能上较均衡。当前场景更重视 P 和 R，同时要求 Q 风险可控。请判断应优先选择哪个候选，并说明理由、潜在风险以及在指标优先级变化时选择是否会改变。”

请按以下 JSON 输出：

{
  "cot_type": "候选分子 / 材料优选决策 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "application_scenario": "具体应用场景或选择目标",
    "decision_goal": "需要做出的选择，例如选择最适合的材料/分子/样品/配方/路线",
    "candidate_objects": [
      {
        "candidate_name": "真实候选名称，例如化合物 3、样品 S2 或 Ni-Fe-LDH-2",
        "known_advantages": ["可写入 input 的优势"],
        "known_limitations": ["可写入 input 的短板或风险"],
        "key_metrics": ["该候选涉及的关键指标"]
      }
    ],
    "evaluation_metrics": [
      {
        "metric": "评价指标",
        "priority": "high / medium / low / scenario_dependent",
        "preferred_direction": "higher_is_better / lower_is_better / balanced / condition_dependent",
        "condition_or_unit": "单位、测试条件或应用约束"
      }
    ],
    "application_constraints": [
      "成本、安全性、稳定性、可合成性、环境条件、工艺兼容性、法规或使用场景限制"
    ],
    "required_task": "选择候选 / 说明理由 / 判断风险 / 讨论优先级变化时选择是否改变"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留候选名称、指标、条件、数值或对比关系"
  ],
  "quality_check": {
    "is_specific": true,
    "has_application_scenario": true,
    "has_at_least_two_candidates": true,
    "uses_real_candidate_names": true,
    "does_not_use_placeholder_candidate_labels": true,
    "does_not_mix_placeholder_and_real_names": true,
    "has_comparable_metrics": true,
    "has_metric_priority_or_constraints": true,
    "shows_candidate_tradeoffs": true,
    "does_not_reveal_final_choice": true,
    "asks_for_reasoned_selection": true,
    "asks_for_risk_or_boundary": true,
    "avoids_source_mention": true
  }
}', 'system_default_v1', 'candidate_selection.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“候选分子 / 材料优选决策 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
候选分子 / 材料优选决策 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的最终候选推荐。
3. 必须明确应用场景和选择目标，例如特定反应、器件、材料体系、配方体系或使用环境。
4. 必须识别候选对象，并确认它们是否处于同一可比任务或同一评价框架下。
5. 必须明确评价指标及其优先级，例如活性、选择性、容量、稳定性、安全性、成本、可合成性、循环寿命、感度、可加工性等。
6. 必须分别分析每个候选对象的优势、短板和风险。
7. 必须区分“关键指标优势”和“可接受短板”；不能只因某一单项指标最高就直接推荐。
8. 必须判断是否存在硬约束或不可接受风险，例如安全性不足、稳定性太差、不可合成、成本过高或应用条件不匹配。
9. 必须进行多指标权衡，并形成候选优先级或候选排序的推理依据。
10. 必须说明如果应用场景或指标优先级发生变化，候选选择是否可能改变。
11. 必须给出后续需要补充验证的性能测试、稳定性测试、成本/安全评估或可制备性验证。
12. 不能引入文献没有支撑的新候选、新指标、新数值或新风险。
13. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源，例如“（图 2）”“（表 1）”“（文献报道）”。
17. 可以使用 input 中已经给出的候选名称、指标、数值和条件，但表达方式应改为任务事实，不要说明其来自文献。
18. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
19. chainofThought 还必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据转写为候选对象的性能事实、约束条件和决策依据。
20. 不要使用“对比实验表明”“根据已有数据”“结果显示”“数据说明”“从表中可以看出”“已有研究证明”等证据过程表达。
21. 推荐使用内化表达，例如：
    - 不写：“对比实验表明，候选 A 的稳定性最高。”
    - 改写：“候选 A 的主要优势在于稳定性更好，更适合稳定性优先的场景。”
    - 不写：“表中数据显示候选 B 的活性最高。”
    - 改写：“候选 B 在活性指标上更突出，但需要同时评估其稳定性和安全性是否满足场景要求。”
    - 不写：“根据数据，候选 C 是最优。”
    - 改写：“如果当前场景更重视综合平衡而非单项极值，候选 C 可能更符合整体约束。”
22. 不要生成最终 output 段落。

推荐推理步骤结构：
1. 明确应用场景和选择目标。
2. 确认可比较候选对象及其评价框架。
3. 确定评价指标优先级和硬约束。
4. 分别分析各候选的优势、短板和风险。
5. 判断候选短板是否会触发不可接受风险。
6. 进行多指标权衡，形成候选排序或优先选择依据。
7. 分析指标优先级变化时选择是否会改变。
8. 给出后续需要补充验证的指标和边界条件。

请按以下 JSON 输出：

{
  "cot_type": "候选分子 / 材料优选决策 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留候选名称、指标、条件、数值、单位或证据位置；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的应用场景、测试条件、指标优先级、材料体系或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_application_scenario": true,
    "has_candidate_objects": true,
    "confirms_candidate_comparability": true,
    "has_metric_priority": true,
    "compares_advantages_and_limitations": true,
    "handles_tradeoffs": true,
    "checks_unacceptable_risks": true,
    "considers_priority_change": true,
    "includes_followup_validation": true,
    "avoids_single_metric_overdecision": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'candidate_selection.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“候选分子 / 材料优选决策 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
候选分子 / 材料优选决策 CoT

生成要求：
1. output 必须直接回答 input 中提出的候选优选任务，开头即给出推荐候选、条件性推荐或候选排序，不能用“综上”“总体来看”“可以从多个方面考虑”等泛泛开场。
2. output 必须紧扣“候选分子 / 材料优选决策”任务，不要答成性能提升路径、构效关系、实验方案或泛泛材料评价。回答重点应是“应用场景 -> 指标优先级 -> 候选对比 -> 推荐结论 -> 风险与边界”。
3. 如果 input 或 chainofThought 没有明确应用场景、候选对象、评价指标或可比较依据，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行推荐。
4. 必须明确给出推荐候选；如果证据不足以唯一推荐，应给出条件性推荐或候选排序，并说明不同条件下选择如何改变。
5. 推荐理由必须基于应用场景下的指标优先级，而不是简单说“综合性能最好”。必须说明哪些指标是首要指标，哪些指标是约束、风险或次级目标。
6. 每个关键判断都必须绑定具体候选、评价指标、优势、短板或风险，不能只写“性能优异”“稳定性较好”“更适合应用”“综合表现突出”等空泛表达。
7. 不能只依据单一最高指标做选择，除非 input 明确该指标是唯一关键指标。若某候选单项指标更突出但存在关键短板，output 必须说明其为什么不作为首选。
8. 必须说明非推荐候选为什么不是首选，包括违反关键约束、关键指标不足、风险更高、适用场景不匹配或证据不足等具体原因。
9. 被推荐候选的风险和边界必须具体到性能、稳定性、安全性、成本、可制备性、相容性、加工性或应用场景层面，不能只写“存在一定风险”或“仍需优化”。
10. 后续验证必须说明验证目标和成功信号，不能只罗列测试名称。例如应说明该测试用于确认哪个关键指标、风险、稳定性、安全性、成本或可制备性问题。
11. output 应按清晰顺序组织，建议采用“推荐结论 -> 指标优先级 -> 候选对比 -> 非首选原因 -> 选择可能改变的条件 -> 后续验证 -> 适用边界”的结构，避免把结论、理由、风险和验证混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“综合性能优异”等。若表达意义，必须落到具体场景、指标或约束上。
13. 不要为了显得完整而强行生成新的候选、指标或排序。如果证据只支持两个候选对比，就只比较这两个候选；如果证据不足，应在 missing_information 或 boundary_conditions 中说明。
14. 不要引入 input 和 chainofThought 中没有出现的新候选、新指标、新数值、新风险、新机制、新应用场景或新结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定结论，必须保留“在当前场景下”“更倾向于”“若优先级改变”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“对比实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“在当前 X 应用场景下，优先推荐候选 A。该选择的关键依据是当前场景更重视 P 和 Q 指标，而 A 在这两个核心指标上更符合要求，同时 R 风险处于可接受或可验证范围。候选 B 虽然在 M 指标上更突出，但受 N 短板限制，不宜作为首选；候选 C 的优势是 O，但在当前指标优先级下不足以抵消其 P 或 Q 方面的不足。如果应用场景转为更重视 M、成本、安全性或可制备性，候选排序可能改变。后续应通过 S 测试确认 A 的关键性能，通过 T 稳定性/安全性/成本/可制备性验证排查主要风险。该推荐仅适用于当前 X 场景和指标优先级内。”

请按以下 JSON 输出：

{
  "cot_type": "候选分子 / 材料优选决策 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少应用场景、候选对象、评价指标、优先级、风险信息或可比较证据"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "application_context": "当前应用场景或使用条件",
    "recommended_candidate": "推荐候选；如果无法唯一推荐，写条件性推荐或排序",
    "recommendation_type": "single_best / conditional_best / ranked_candidates / insufficient_evidence",
    "metric_priority": [
      {
        "metric": "评价指标或约束",
        "priority": "核心指标 / 硬约束 / 次级指标 / 风险项",
        "reason": "为什么该指标在当前场景下重要"
      }
    ],
    "core_decision_basis": [
      "推荐候选的核心依据，必须对应应用场景、指标优先级和候选差异"
    ],
    "candidate_tradeoff_summary": [
      {
        "candidate": "候选名称",
        "main_advantages": ["主要优势，必须绑定具体指标或场景"],
        "main_limitations": ["主要短板、风险或证据缺口"],
        "decision_role": "首选 / 备选 / 特定条件下更优 / 不推荐",
        "reason_for_role": "为什么承担该决策角色"
      }
    ],
    "unacceptable_or_manageable_risks": [
      "不可接受风险，或可接受但需要验证的风险"
    ],
    "when_choice_may_change": [
      "如果应用场景、指标优先级或约束条件改变，选择可能如何变化"
    ],
    "followup_validation": [
      {
        "method": "性能测试、稳定性测试、安全性验证、成本评估、可制备性验证、相容性评价或其他方法",
        "validation_target": "验证哪个关键指标、风险或选择依据",
        "success_signal": "什么结果支持该候选作为首选"
      }
    ],
    "boundary_conditions": [
      "该推荐成立的应用场景、测试条件、指标优先级、材料体系边界或不确定性"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留候选名称、指标、条件、数值、单位或证据位置；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_candidate_selection_task": true,
    "has_application_context": true,
    "has_recommended_candidate": true,
    "has_decision_basis": true,
    "uses_metric_priority": true,
    "compares_non_selected_candidates": true,
    "explains_why_others_are_not_first_choice": true,
    "does_not_overuse_single_metric": true,
    "mentions_specific_risks": true,
    "mentions_when_choice_changes": true,
    "includes_followup_validation": true,
    "validation_methods_have_targets_and_success_signals": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'candidate_selection.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“反事实结构改造 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
反事实结构改造 CoT

生成要求：
1. input 必须表现为“如果将结构因素 A 替换/改造为 B，会如何影响性能 Z”的反事实任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含具体研究对象或材料/分子体系 X。
4. 必须包含原始结构因素 A，例如官能团、金属中心、掺杂元素、晶相、缺陷浓度、侧链长度、配位环境、孔结构、界面层等。
5. 必须包含拟替换、增加、减少或改造的结构因素 B。
6. 必须包含目标性能 Z，例如活性、选择性、稳定性、容量、感度、密度、吸附能力、传输性能、能垒、溶解性等。
7. 如果有相似对照样品、系列趋势或已知副作用，应写入 input。
8. input 应要求模型预测性能变化方向，说明原因、潜在副作用和验证方法。
9. 不要在 input 中直接给出最终预测答案。
10. 如果缺少原结构因素、拟改造因素或目标性能，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 材料/分子原本具有结构因素 A，该因素与性能 Z 的表现有关。若将 A 替换/调控为 B，B 在电子效应、空间位阻、配位能力、界面作用或传输特性上与 A 存在差异。请预测目标性能 Z 可能如何变化，并说明原因、潜在副作用和验证方法。”

请按以下 JSON 输出：

{
  "cot_type": "反事实结构改造 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "original_structure_factor": "A",
    "counterfactual_modification": "B",
    "target_performance": "Z",
    "known_role_of_original_factor": "A 的作用",
    "expected_difference_between_A_and_B": ["电子、空间、界面、传输、吸附、稳定性等差异"],
    "possible_side_effects": ["潜在副作用或风险"],
    "required_task": "预测性能变化 / 解释原因 / 判断副作用 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留结构因素、相似对照、性能趋势、机制或风险"
  ],
  "quality_check": {
    "is_specific": true,
    "has_original_structure_factor": true,
    "has_counterfactual_modification": true,
    "has_target_performance": true,
    "has_known_role_or_comparison_basis": true,
    "asks_for_prediction": true,
    "asks_for_side_effects": true,
    "asks_for_validation_methods": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'counterfactual_modification.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“反事实结构改造 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
反事实结构改造 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的性能变化预测。
3. 必须识别原结构因素 A 的作用。
4. 必须分析拟改造因素 B 与 A 的差异，例如电子效应、空间位阻、极性、配位能力、离子半径、界面作用、孔结构、疏水性、缺陷稳定性等。
5. 必须推断 B 替代或调控 A 后对结构、电子、界面、传输、吸附或稳定性的影响。
6. 必须连接这些影响与目标性能 Z。
7. 必须判断性能变化方向：提升、下降、存在折中或不确定。
8. 必须说明潜在副作用或风险。
9. 必须给出验证建议，例如结构表征、性能测试、对照样品、计算模拟或原位表征。
10. 不能引入文献没有支撑的新变量、新机制或新性能结论。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据转写为结构事实、变量差异、机制影响和专业判断。
17. 不要使用“根据已有数据”“对照实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 识别原结构因素 A 及其作用。
2. 分析拟改造因素 B 与 A 的关键差异。
3. 推断 B 对结构、电子、界面、传输或吸附过程的影响。
4. 连接这些影响与目标性能 Z。
5. 预测性能变化方向，并保留不确定性。
6. 判断可能的副作用或折中关系。
7. 给出验证建议。
8. 说明适用边界和后续优化方向。

请按以下 JSON 输出：

{
  "cot_type": "反事实结构改造 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留结构因素、相似对照、性能趋势、机制或风险；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、替换范围、测试条件、结构相似性或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_original_structure_factor": true,
    "has_counterfactual_modification": true,
    "compares_A_and_B": true,
    "links_structure_change_to_mechanism": true,
    "predicts_performance_direction": true,
    "keeps_uncertainty": true,
    "mentions_side_effects": true,
    "includes_validation_methods": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'counterfactual_modification.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“反事实结构改造 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
反事实结构改造 CoT

生成要求：
1. output 必须直接回答 input 中提出的反事实结构改造任务，开头即说明“将结构因素 A 替换/调控为 B 后，目标性能 Z 更可能提升、下降、出现折中或仍不确定”，不能用“综上”“总体来看”“可以从多个方面分析”等泛泛开场。
2. output 必须紧扣反事实结构改造任务，不要答成普通性能提升、实验方案生成或泛泛结构优化建议。回答重点应是“结构改造前后差异 -> 机制变化 -> 性能变化方向 -> 风险与验证”。
3. 如果 input 或 chainofThought 没有明确原结构因素 A、替换/调控因素 B、目标性能 Z 或可支撑的机制依据，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要补写无依据预测。
4. 性能变化方向必须与证据强度匹配。若证据只支持趋势或相关性，应写“可能提升/可能下降/存在折中/需要验证”，不能写成确定因果；若证据不足以判断方向，应明确输出“不确定”。
5. 每个关键判断都必须绑定具体对象、结构差异、机制通道和性能结果，不能只写“改善结构”“增强性能”“调控电子结构”“提高稳定性”等空泛表达。
6. 核心原因必须写成清楚的机制链条：B 与 A 的关键差异是什么，该差异如何影响结构、电子、界面、传输、吸附、反应过程或稳定性，进而为什么会影响目标性能 Z。
7. 如果结构替换会带来正负并存的影响，output 必须明确说明折中关系。例如某一性能可能提升，但稳定性、传输、选择性、加工性或安全性可能受到影响，不能只保留有利结论。
8. 潜在副作用或风险必须具体到结构、组分、界面、反应过程、传输路径、稳定性或应用场景层面，不能只写“存在一定风险”“可能需要进一步优化”。
9. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认结构替换是否发生、机制通道是否改变、目标性能是否按预测方向变化，或副作用是否出现。
10. output 应按清晰顺序组织，建议采用“预测结论 -> 结构差异 -> 机制影响 -> 性能后果 -> 副作用/边界 -> 验证方式”的结构，避免把结论、原因、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“可实现性能优化”等。若表达意义，必须落到具体性能、机制或应用边界上。
12. 不要为了显得完整而强行生成多个改造方向。若 input 只提出一个 A 到 B 的反事实改造，应集中回答该改造；若存在多个备选改造，必须逐一说明各自依据和不确定性。
13. 不要生成完整实验方案；本步骤输出的是反事实结构改造判断和验证方向，不是详细操作流程。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新候选结构或新实验条件。
15. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
16. output 应完成证据内化，不要出现“对照实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
17. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“将结构因素 A 替换/调控为 B 后，目标性能 Z 更可能提升/下降/出现折中/仍不确定。关键原因是 B 相比 A 改变了 M 结构或过程，使 N 机制通道发生变化，从而影响 Z；但这种改造也可能带来 P 副作用，例如影响稳定性、传输、选择性、加工性或安全性。因此，该判断只适用于 Q 条件或当前设计空间内，不能直接外推到其他体系。后续应通过 R 表征确认结构替换及其作用，通过 S 性能测试判断 Z 是否按预测方向变化，并通过 T 对照或稳定性评价排查 P 风险。”

请按以下 JSON 输出：

{
  "cot_type": "反事实结构改造 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少原结构因素、替换因素、目标性能、机制依据或验证条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "counterfactual_change": {
      "original_factor": "原结构因素 A",
      "modified_factor": "替换/调控因素 B",
      "target_performance": "目标性能 Z"
    },
    "predicted_performance_change": "提升 / 下降 / 折中 / 不确定",
    "core_reason": "性能变化的核心原因，必须写清楚 A 与 B 的差异及其机制后果",
    "affected_mechanism_or_property": [
      "被影响的结构、电子、界面、传输、吸附、反应过程、稳定性或其他机制因素"
    ],
    "mechanism_to_performance_link": "结构改造如何通过具体机制通道影响目标性能",
    "potential_side_effects": [
      "可能副作用、折中关系或风险，必须具体到结构、过程、性能或应用边界"
    ],
    "validation_methods": [
      {
        "method": "表征、测试、对照或计算方法",
        "validation_target": "验证哪个结构变化、机制影响、性能趋势或副作用",
        "success_signal": "什么结果支持该预测或提示该预测不成立"
      }
    ],
    "uncertainty_and_boundary": [
      "不确定性、适用条件、设计空间边界或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留结构因素、相似对照、性能趋势、机制或风险；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_counterfactual_task": true,
    "has_original_and_modified_factors": true,
    "has_target_performance": true,
    "has_predicted_performance_change": true,
    "has_core_reason": true,
    "links_structure_change_to_mechanism": true,
    "links_mechanism_to_performance": true,
    "mentions_specific_side_effects": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "keeps_uncertainty": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'counterfactual_modification.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“失败原因诊断 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、failure_or_limitations、cot_type_judgement>

目标 CoT 类型：
失败原因诊断 CoT

生成要求：
1. input 必须表现为具体失败诊断任务，而不是泛泛讨论。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含研究对象 X。
4. 必须包含原始设计意图，例如希望通过 Y 改性、掺杂、替换、配方、工艺或结构调控提升性能 Z。
5. 必须包含实际失败信号，例如性能没有提升、反而下降、稳定性变差、选择性下降、结构坍塌、副反应增强、循环衰减、产率降低、不可重复等。
6. 如果有成功样品、失败样品、基准样品或对照样品之间的差异，应写入 input。
7. 如果有表征或测试异常，例如晶相变化、形貌破坏、阻抗升高、活性位点减少、杂相生成、孔结构塌陷、吸附过强、溶解性变差等，应写入 input。
8. input 应要求模型诊断可能失败原因，并提出修正方向和验证方法。
9. 不要在 input 中直接写出最终失败原因。
10. 如果没有明确失败现象、负例或失败信号，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“研究者原本希望通过 Y 策略改善 X 体系的 Z 性能，但实际结果显示性能没有提升或反而下降，同时出现 A、B 等异常信号；与成功样品或基准样品相比，失败样品在 M、N 方面存在差异。请诊断可能失败原因，并提出后续修正方向和验证方法。”

请按以下 JSON 输出：

{
  "cot_type": "失败原因诊断 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_object": "X",
    "original_design_intent": "原始设计意图",
    "target_performance": "Z",
    "expected_positive_effect": "预期正向作用",
    "actual_failure_signal": "实际失败表现",
    "comparison_samples": ["成功样品、失败样品、基准样品或对照样品"],
    "diagnostic_clues": ["表征、测试、结构或性能异常线索"],
    "required_task": "诊断失败原因 / 提出修正方向 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留设计意图、失败信号、样品差异、异常表征或测试条件"
  ],
  "quality_check": {
    "is_specific": true,
    "has_design_intent": true,
    "has_failure_signal": true,
    "has_target_performance": true,
    "has_comparison_or_diagnostic_clues": true,
    "asks_for_failure_diagnosis": true,
    "asks_for_correction_strategy": true,
    "asks_for_validation_method": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'failure_diagnosis.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“失败原因诊断 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、failure_or_limitations、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
失败原因诊断 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的失败原因判断和修正建议。
3. 必须明确原始设计意图和预期正向作用。
4. 必须识别实际失败信号和失败程度。
5. 必须比较失败样品与成功样品、基准样品或对照样品之间的关键差异。
6. 必须把差异映射到可能失效环节，例如结构破坏、活性位点失效、传输受阻、界面恶化、相分离、副反应、过量添加、结晶失败、热/光/化学稳定性不足等。
7. 必须推断最可能的失败原因，并保留不确定性。
8. 必须提出修正策略，例如降低掺杂量、改变工艺窗口、调整组分比例、改善分散、避免副反应、优化后处理或增加保护措施。
9. 必须给出验证方法，例如结构表征、性能复测、稳定性测试、对照实验、原位表征、计算验证等。
10. 不能引入文献没有支撑的新变量、新机制或新实验条件。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为失败现象、样品差异、失效环节和专业判断。
17. 不要使用“根据已有数据”“失败实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 明确原始设计意图和目标性能。
2. 识别实际失败信号和失败程度。
3. 比较失败样品与成功/基准/对照样品的关键差异。
4. 将这些差异映射到可能失效环节。
5. 判断最可能的失败原因，并说明不确定性。
6. 提出针对性的修正策略。
7. 设计验证失败原因的实验或表征方法。
8. 说明结论边界和后续迭代方向。

请按以下 JSON 输出：

{
  "cot_type": "失败原因诊断 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留失败信号、样品差异、表征或测试条件；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、样品范围、测试条件、失败类型或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_design_intent": true,
    "has_failure_signal": true,
    "compares_failed_and_control_samples": true,
    "maps_differences_to_failure_link": true,
    "infers_likely_failure_reason": true,
    "keeps_uncertainty": true,
    "has_correction_strategy": true,
    "has_validation_methods": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'failure_diagnosis.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“失败原因诊断 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
失败原因诊断 CoT

生成要求：
1. output 必须直接回答 input 中提出的失败诊断任务，开头即给出最可能失败原因、优先怀疑原因或条件性诊断结论，不能用“综上”“总体来看”“可能需要从多个方面分析”等泛泛开场。
2. output 必须紧扣“失败原因诊断”任务，不要答成普通性能提升、工艺优化、实验方案或泛泛改进建议。回答重点应是“原始设计意图 -> 实际失败信号 -> 失效环节 -> 根因判断 -> 修正策略 -> 验证方式”。
3. 如果 input 或 chainofThought 没有明确失败现象、预期目标、样品差异、异常信号或可支撑的诊断依据，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行诊断。
4. 必须给出最可能失败原因；如果证据不足，应写成“优先怀疑原因”或“可能原因”，并标明置信度。不能把证据不足的判断写成确定根因。
5. 每个失败原因都必须对应具体失败信号、样品差异、性能下降、结构异常、界面问题、副反应、稳定性问题或工艺失控现象，不能只写“结构不稳定”“反应不充分”“性能下降明显”等空泛表达。
6. 必须说明失败原因与实际失败信号之间的对应关系：该原因为什么能解释观测到的异常，不能只给结论不解释诊断依据。
7. 如果存在多个可能原因，必须给出优先级或排查顺序，并说明为什么某一原因优先怀疑，其他原因属于备选或待排查。
8. 修正策略必须针对具体失效环节，说明要调整什么变量、抑制什么副作用、恢复什么结构/过程或改善什么性能通道，不能只写“优化工艺”“改善结构”“进一步调控条件”等泛泛建议。
9. 必须说明修正策略的潜在风险或边界。例如修正某个副作用时是否可能牺牲活性、稳定性、选择性、传输、加工性或安全性。
10. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认哪个失败原因、排除哪个备选原因、验证哪个修正策略，以及什么结果支持或否定该诊断。
11. output 应按清晰顺序组织，建议采用“诊断结论 -> 失败信号对应关系 -> 备选原因/排查顺序 -> 修正策略 -> 验证方式 -> 边界与不确定性”的结构，避免把结论、原因、修正和验证混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“需要进一步系统优化”等。若表达后续意义，必须落到具体失效环节、修正变量或验证指标上。
13. 不要为了显得完整而强行生成多个失败原因。如果 input 和 chainofThought 只支持一个主要原因，应集中写清楚该原因；如果证据不足，应在 missing_information 或 remaining_uncertainties 中说明。
14. 不要生成完整实验方案；本步骤输出的是失败诊断、修正方向和验证路径，不是详细操作流程。
15. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新失败原因、新实验条件或新性能结论。
16. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“优先怀疑”“可能”“更倾向于”“需要进一步验证”等限定表达。
17. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
18. output 应完成证据内化，不要出现“失败实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
19. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该失败优先怀疑由 A 失效环节引起。A 能同时解释 B 失败信号和 C 样品差异：它会导致 D 结构/过程异常，进而削弱目标性能 Z。备选原因 E 也需要排查，但目前它只能解释部分信号，优先级低于 A。修正时应针对 A 调整 F 变量或降低 G 副作用，预期恢复 H 过程或抑制 I 失效表现；但该策略可能带来 J 风险。后续应通过 K 表征确认 A 是否存在，通过 L 性能测试判断修正后 Z 是否恢复，并通过 M 对照排除 E 原因。该诊断仅适用于 Q 条件或当前样品范围内，超出该边界需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "失败原因诊断 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少失败现象、预期目标、样品差异、异常信号、诊断依据或验证条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "original_intent": "原始设计意图或预期目标",
    "observed_failure": "实际失败现象或异常信号",
    "likely_failure_reasons": [
      {
        "reason": "最可能失败原因或优先怀疑原因",
        "confidence": "high / medium / low",
        "linked_failure_signals": ["该原因能解释的失败信号、样品差异或异常表现"],
        "diagnostic_logic": "该原因为什么能解释这些失败信号"
      }
    ],
    "alternative_causes_or_exclusion_order": [
      {
        "cause": "备选失败原因或待排查原因",
        "priority": "高 / 中 / 低",
        "reason": "为什么需要排查，或为什么不是首要原因"
      }
    ],
    "core_diagnostic_basis": [
      "失败原因与样品差异、异常信号、性能下降或失效环节之间的核心逻辑"
    ],
    "correction_strategies": [
      {
        "strategy": "修正策略",
        "targeted_failure_link": "该策略针对哪个失效环节或失败原因",
        "expected_effect": "预期恢复或改善什么结构、过程、性能通道或失效表现",
        "potential_tradeoff_or_risk": "该修正可能带来的副作用、折中关系或边界"
      }
    ],
    "validation_methods": [
      {
        "method": "表征、测试、对照或计算方法",
        "validation_target": "用于验证哪个失败原因、排除哪个备选原因或验证哪个修正策略",
        "success_signal": "什么信号说明诊断成立、修正有效或该原因应被排除"
      }
    ],
    "remaining_uncertainties": [
      "仍需保留的不确定性、证据缺口或待排查因素"
    ],
    "boundary_conditions": [
      "该诊断成立的体系、条件、样品范围、测试边界或适用条件"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留失败信号、样品差异、表征或测试条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_failure_diagnosis_task": true,
    "has_original_intent": true,
    "has_observed_failure": true,
    "has_likely_failure_reason": true,
    "links_reason_to_failure_signal": true,
    "has_diagnostic_logic": true,
    "handles_alternative_causes_or_exclusion_order": true,
    "has_correction_strategy": true,
    "correction_strategy_targets_failure_link": true,
    "mentions_specific_tradeoffs_or_risks": true,
    "has_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "keeps_uncertainty": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'failure_diagnosis.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“多目标约束优化 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
多目标约束优化 CoT

生成要求：
1. input 必须表现为“在多个性能目标和约束条件下，如何确定最优方案、最优窗口或合理折中”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含具体研究对象或材料/分子/工艺/配方/器件体系 X。
4. 必须包含至少两个目标性能或评价指标，例如活性与稳定性、容量与倍率、能量密度与安全性、产率与纯度、密度与感度、吸附容量与选择性、强度与韧性、效率与成本等。
5. 必须明确每个指标的优化方向，例如越高越好、越低越好、需控制在某范围内、需超过阈值或不能低于基线。
6. 必须包含至少一个硬约束，例如安全上限、稳定性下限、成本限制、结构保持要求、产率阈值、纯度要求、测试条件、工艺可行性或法规/应用场景约束。
7. 可以包含软目标或优先级，例如在满足安全和稳定性的前提下优先提高性能、在性能接近时优先选择低成本或易制备路线。
8. 必须包含可调控变量、候选方案或设计空间，例如组分比例、掺杂量、反应条件、配方比例、候选分子、孔结构、界面层、晶相、缺陷浓度或后处理方式。
9. 如果目标之间存在冲突或折中，应写入 input，例如提高活性可能降低稳定性、提高密度可能增加感度、增加缺陷可能提升容量但降低循环寿命。
10. input 应要求模型区分硬约束和软目标，筛除不可行方案，分析折中关系，并给出推荐方案或优化窗口。
11. 不要在 input 中直接给出最终最优方案或最终排序结论。
12. 不要把任务写成单一指标的候选优选；如果只有一个目标且没有约束，应转入“候选分子 / 材料优选决策 CoT”或“性能提升路径 CoT”。
13. 不要把任务写成完整实验步骤设计；如果核心任务是实验分组和操作流程，应转入“实验方案生成 CoT”。
14. 如果缺少多个目标、约束条件或可调控设计空间，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 体系需要在目标 Z1、Z2 和 Z3 之间进行优化，其中 Z1 越高越好，Z2 需要低于/高于阈值 A，Z3 作为稳定性或安全性硬约束必须满足 B。可调控变量包括 C、D 和 E，不同变量可能带来性能收益与副作用之间的折中。请区分硬约束和软目标，筛选可行方案，分析目标冲突，并给出最合理的优化窗口或推荐方案及其验证指标。”

请按以下 JSON 输出：

{
  "cot_type": "多目标约束优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "optimization_variables_or_design_space": [
      "可调控变量、候选方案或可搜索设计空间"
    ],
    "objectives": [
      {
        "metric": "目标性能指标",
        "optimization_direction": "越高越好 / 越低越好 / 控制在范围内 / 达到阈值",
        "target_or_threshold": "目标值、阈值、范围或相对要求",
        "priority": "高 / 中 / 低 / 未明确"
      }
    ],
    "hard_constraints": [
      "必须满足的约束条件"
    ],
    "soft_preferences": [
      "满足硬约束后的偏好或次级目标"
    ],
    "tradeoff_relations": [
      "目标之间或变量与性能之间的冲突/折中关系"
    ],
    "required_task": "区分硬约束和软目标 / 筛选可行域 / 分析折中 / 给出推荐方案或优化窗口 / 给出验证指标"
  },
  "evidence_used": [
    "用于生成 input 的关键信息，保留体系、变量、多个目标、约束、趋势、冲突或边界"
  ],
  "quality_check": {
    "is_specific": true,
    "has_research_system": true,
    "has_multiple_objectives": true,
    "has_optimization_directions": true,
    "has_hard_constraints": true,
    "has_design_space_or_variables": true,
    "has_tradeoff_relations": true,
    "distinguishes_hard_constraints_and_soft_goals": true,
    "asks_for_feasible_solution": true,
    "asks_for_tradeoff_analysis": true,
    "asks_for_validation_metrics": true,
    "does_not_include_final_decision": true,
    "does_not_turn_into_single_metric_selection": true,
    "does_not_turn_into_experimental_plan": true,
    "avoids_source_mention": true
  }
}', 'system_default_v1', 'multi_objective_optimization.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“多目标约束优化 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
多目标约束优化 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的多目标约束优化决策。
3. 必须明确所有目标指标，并说明每个指标的优化方向和重要性。
4. 必须区分硬约束和软目标：硬约束用于筛除不可行方案，软目标用于在可行方案中排序和折中。
5. 必须先判断哪些方案、条件或设计变量水平满足硬约束，哪些应被排除或谨慎处理。
6. 必须分析目标之间的冲突关系，例如提升一个指标是否会牺牲另一个指标，以及该冲突来自结构、组成、界面、传输、稳定性、安全性、成本或工艺可行性的哪一类原因。
7. 必须识别可能的折中解、可行窗口或 Pareto 倾向方案，但不要使用证据不支持的数学优化术语或虚构权重。
8. 必须说明推荐方案或优化窗口为什么在多个目标之间更均衡，而不是只在单一指标上最好。
9. 必须说明被排除或降级方案的原因，例如违反硬约束、虽然某一性能高但副作用过大、稳定性不足、制备不可行或风险过高。
10. 必须保留不确定性；如果证据只支持相关性，不要写成确定因果。
11. 必须给出验证建议，包括关键性能复测、稳定性/安全性评价、结构表征、对照样品或边界条件验证。
12. 不要引入文献没有支撑的新变量、新机制、新数值、新候选方案或新性能结论。
13. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
14. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
15. 不要在 chainofThought 中用括号标注证据来源。
16. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
17. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据改写为目标要求、可行性判断、性能折中和专业推断。
18. 不要使用“根据已有数据”“对照实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
19. 不要生成最终 output。

推荐推理步骤结构：
1. 明确研究体系、设计空间和所有目标指标。
2. 统一各指标优化方向，区分越高越好、越低越好、阈值约束和范围约束。
3. 划分硬约束与软目标，并说明硬约束的筛选作用。
4. 筛选满足硬约束的可行方案或可行窗口。
5. 分析可行方案内部的目标冲突和折中关系。
6. 判断最均衡的推荐方案、窗口或策略，并说明优先级。
7. 说明被排除或降级方案的原因。
8. 给出验证指标、风险点和适用边界。

请按以下 JSON 输出：

{
  "cot_type": "多目标约束优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留体系、变量、多个目标、约束、趋势、冲突或边界；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、设计空间、指标阈值、测试条件、证据强度或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_multiple_objectives": true,
    "normalizes_objective_directions": true,
    "distinguishes_hard_constraints_and_soft_goals": true,
    "screens_feasible_space": true,
    "analyzes_tradeoffs": true,
    "identifies_balanced_solution_or_window": true,
    "does_not_optimize_single_metric_only": true,
    "explains_rejected_or_downgraded_options": true,
    "mentions_risks_and_side_effects": true,
    "includes_validation_methods": true,
    "keeps_uncertainty": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'multi_objective_optimization.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“多目标约束优化 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
多目标约束优化 CoT

生成要求：
1. output 必须直接回答 input 中提出的多目标约束优化任务，开头即给出推荐方案、推荐候选、推荐配方、推荐工艺窗口或推荐设计方向，不能用“综上”“总体来看”“可以从多个方面考虑”等泛泛开场。
2. 推荐内容必须与 input 中的设计空间一致。如果 input 要求选择候选，则给出推荐候选；如果 input 要求优化配方、工艺或结构，则给出对应的配方、工艺窗口或结构设计方向，不要答成其他任务类型。
3. output 必须紧扣“多目标约束优化”的核心：说明推荐方案如何同时处理硬约束和多个软目标，而不是只解释单一性能为什么提升。
4. 每个关键判断都必须绑定具体对象、目标指标、约束条件、冲突关系或调控变量，不能只写“综合性能更好”“实现性能平衡”“优化结构”“提升稳定性”等空泛表达。
5. 必须说明硬约束是否满足，以及哪些方案因违反硬约束、风险过高或证据不足而不应优先选择。
6. 必须说明软目标之间的主要冲突和取舍，并解释推荐方案为什么是更合理的折中解，而不是单一指标最优解。
7. 如果某个备选方案在单一指标上更优，但会损害其他目标、违反约束或增加风险，output 必须明确指出其不作为首选的原因。
8. 风险、边界和不确定性必须具体到结构、组分、工艺、性能或应用场景层面，不能只写“存在一定风险”“仍需进一步优化”“受条件限制”。
9. 验证方式必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于验证哪个目标、约束、折中判断或失效风险，以及什么结果支持推荐方案成立。
10. output 应按清晰顺序组织，建议采用“推荐结论 -> 硬约束检查 -> 软目标折中逻辑 -> 降级或排除方案 -> 验证方式 -> 适用边界”的结构，避免把结论、原因、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“实现综合性能提升”等。若表达意义，必须落到具体目标、机制、约束或应用边界上。
12. 不要为了显得完整而强行生成多个备选方案。如果 input 和 chainofThought 只支持一个推荐方向，应集中写清楚该方向；信息不足时，在 missing_information 或 boundary_conditions 中说明缺口。
13. 不要生成完整实验方案；本步骤输出的是优化决策和验证方向，不是详细操作流程。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新候选方案或新实验条件。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该条件范围内”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“优先推荐 A 方案/窗口作为该多目标约束下的折中解。该方案首先满足 B、C 等硬约束，因此没有触及必须排除的安全、稳定性、可加工性或适用条件边界；在软目标上，它牺牲/限制了 Z1 的单项最大化，但换来了 Z2 和 Z3 的更稳定表现，因此比单独追求 Z1 的 D 方案更适合作为首选。D 方案虽然在 Z1 上更突出，但会带来 E 风险或削弱 F 目标，适合作为降级方案或暂不推荐。后续应通过 G 测试验证目标 Z1，通过 H 表征确认约束 B，通过 I 稳定性/安全性评价确认折中是否成立。该判断仅适用于 Q 条件或当前设计空间内，超出该范围需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "多目标约束优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "recommended_solution_or_window": "推荐方案、候选、配方、工艺窗口或设计方向",
    "objective_satisfaction_summary": [
      {
        "metric": "目标指标",
        "judgement": "满足 / 部分满足 / 不满足 / 需要验证",
        "reason": "判断理由，必须绑定具体变量、目标、约束或风险"
      }
    ],
    "hard_constraints_check": [
      {
        "constraint": "硬约束",
        "status": "满足 / 不满足 / 需要验证",
        "impact_on_decision": "该约束如何影响推荐、降级或排除"
      }
    ],
    "tradeoff_rationale": "推荐方案在多个目标之间形成合理折中的原因，必须说明目标冲突和取舍逻辑",
    "rejected_or_lower_priority_options": [
      {
        "option": "被排除或降级的方案",
        "reason": "违反约束、风险过高、证据不足、单一指标好但综合不均衡等原因"
      }
    ],
    "validation_methods": [
      {
        "method": "表征、性能测试、稳定性/安全性评价、对照或计算方法",
        "validation_target": "验证哪个目标、约束、折中判断或风险",
        "success_signal": "什么结果支持推荐方案有效"
      }
    ],
    "boundary_conditions": [
      "适用条件、测试边界、设计空间边界、不确定性或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留体系、变量、多个目标、约束、趋势、冲突或边界；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "does_not_repeat_chain": true,
    "has_recommended_solution_or_window": true,
    "matches_input_design_space": true,
    "checks_hard_constraints": true,
    "summarizes_objective_satisfaction": true,
    "explains_tradeoff_rationale": true,
    "mentions_rejected_or_lower_priority_options": true,
    "does_not_optimize_single_metric_only": true,
    "has_specific_risks_and_boundaries": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "has_success_criteria": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'multi_objective_optimization.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“机理到设计策略迁移 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
机理到设计策略迁移 CoT

生成要求：
1. input 必须表现为“基于已知机制提出设计策略”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含研究对象或体系 X。
4. 必须包含已知机制 M，例如活性位点调控、界面阻抗降低、离子传输增强、载流子分离、缺陷调控、吸附能调节、疏水性增强、晶相稳定、分子构象变化等。
5. 必须包含目标性能 Z 或进一步优化目标。
6. 必须包含机制 M 对应的可调控设计变量，例如组分、缺陷、晶相、界面、孔结构、官能团、侧链、金属中心、溶剂环境、配位结构等。
7. input 应要求模型基于机制 M 推导可迁移设计策略，而不是只解释原体系为什么有效。
8. input 应要求说明策略适用条件、潜在风险和验证方法。
9. 不要在 input 中直接给出最终设计策略答案。
10. 如果缺少明确机制或机制缺少证据支撑，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“已知 X 体系的性能提升主要来自机制 M，该机制与变量 A、B、C 的调控有关。现在希望进一步提升目标性能 Z，并避免问题 R。请基于机制 M 提出可迁移的设计策略，说明应优先调控哪些变量、为什么这些变量可能有效、适用边界是什么，以及需要通过哪些实验或计算验证。”

请按以下 JSON 输出：

{
  "cot_type": "机理到设计策略迁移 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "known_mechanism": "M",
    "target_performance": "Z",
    "current_limitation_or_goal": "当前短板或进一步优化目标",
    "controllable_design_variables": ["A", "B", "C"],
    "potential_risks_or_boundaries": ["策略迁移时需要注意的风险或边界"],
    "required_task": "基于机制提出设计策略 / 判断适用条件 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留机制、变量、性能指标、验证方法或边界条件"
  ],
  "quality_check": {
    "is_specific": true,
    "has_known_mechanism": true,
    "has_target_performance": true,
    "has_controllable_variables": true,
    "asks_for_design_strategy_transfer": true,
    "asks_for_boundary_conditions": true,
    "asks_for_validation_methods": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'mechanism_to_design.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“机理到设计策略迁移 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
机理到设计策略迁移 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的设计策略形成。
3. 必须先明确已知机制 M 及其作用对象。
4. 必须识别机制 M 对应的可调控变量，例如结构、组分、缺陷、晶相、界面、孔结构、官能团、金属中心、侧链、溶剂环境等。
5. 必须分析每个变量如何影响机制 M，以及机制 M 如何影响目标性能 Z。
6. 必须从机制 M 迁移得到新的设计策略，而不是只复述原体系结论。
7. 必须判断策略适用条件和不适用场景。
8. 必须识别潜在副作用，例如稳定性下降、传输受阻、活性与选择性冲突、合成难度增加、安全性降低、成本升高等。
9. 必须给出验证策略，例如结构表征、性能测试、原位表征、动力学实验、稳定性测试或计算验证。
10. 不能引入文献没有支撑的新机制、新变量或新性能结论。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何验证得到，而要把证据转写为机制事实、变量关系、条件约束和专业判断。
17. 不要使用“根据已有数据”“机理表征表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 提取已知机制 M 及其作用对象。
2. 判断 M 对应哪些可调控设计变量。
3. 分析这些变量如何影响 M。
4. 连接 M 与目标性能 Z。
5. 从 M 迁移得到新的设计策略。
6. 判断策略适用条件和潜在副作用。
7. 给出验证策略和关键指标。
8. 说明边界条件和下一轮优化方向。

请按以下 JSON 输出：

{
  "cot_type": "机理到设计策略迁移 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留机制、变量、性能指标、验证方法或边界；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、机制适用范围、测试条件或应用场景"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_known_mechanism": true,
    "maps_mechanism_to_variables": true,
    "links_variables_to_target_performance": true,
    "derives_new_design_strategy": true,
    "has_applicability_boundary": true,
    "identifies_potential_side_effects": true,
    "includes_validation_strategy": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'mechanism_to_design.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“机理到设计策略迁移 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
机理到设计策略迁移 CoT

生成要求：
1. output 必须直接回答 input 中提出的设计策略迁移任务，开头即给出推荐设计策略或策略优先级，不能用“综上”“总体来看”“可以从多个方面考虑”等泛泛开场。
2. output 必须紧扣“机理到设计策略迁移”任务，不要答成普通机理解释、性能提升路径、实验方案或泛泛优化建议。回答重点应是“已知机理 M -> 可调变量 -> 设计策略 -> 目标性能路径 -> 适用边界与验证”。
3. 如果 input 或 chainofThought 没有明确已知机理、目标性能、可调变量或可迁移设计空间，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成设计策略。
4. 必须给出明确的设计策略，而不是只重复机制解释。每条策略都应说明要调控什么变量、为什么该变量对应已知机理、预期通过什么路径影响目标性能。
5. 每个关键判断都必须绑定具体机理、变量、设计动作和性能结果，不能只写“优化结构”“调控界面”“增强活性”“提升稳定性”“改善传输”等空泛表达。
6. 机制迁移必须有边界。output 必须说明该策略适用于哪些结构、组分、反应条件、性能目标或应用场景，不能把特定体系中的机理直接写成普适设计规律。
7. 如果策略可能同时带来正向作用和副作用，output 必须明确说明折中关系。例如增强活性可能损害稳定性，提高传输可能影响结构完整性，增加活性位点可能引入副反应。
8. 如果存在多个策略，必须给出优先级及理由。优先级理由应基于机理对应性、变量可控性、风险大小、验证可行性或对目标性能的直接影响，不能只写“因此优先推荐”。
9. 后续验证必须说明验证目标和成功信号，不能只罗列表征、测试或计算方法。例如应说明该方法用于验证机制是否被增强、变量是否被成功调控、目标性能是否按预期变化或副作用是否可控。
10. output 应按清晰顺序组织，建议采用“设计策略结论 -> 机制依据 -> 可调变量 -> 性能路径 -> 策略优先级 -> 风险边界 -> 验证方式”的结构，避免把结论、机制、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“可实现性能优化”等。若表达意义，必须落到具体机制、变量、性能或应用边界上。
12. 不要为了显得完整而强行生成多个策略。如果 input 和 chainofThought 只支持一个主要策略，应集中写清楚该策略；如果证据不足，应在 missing_information 或 applicability_boundary 中说明。
13. 不要生成完整实验方案；本步骤输出的是设计策略迁移结果和验证方向，不是详细操作流程。
14. 不要引入 input 和 chainofThought 中没有出现的新机制、新变量、新数值、新材料、新设计方向或新性能结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该机制成立的条件下”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“机理表征表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“基于机制 M，优先采用 A 设计策略。该策略的核心不是单纯提高某一指标，而是通过调控变量 C 和 D 来增强/抑制 E 过程，从而改善目标性能 Z。A 策略优先于 B 策略，是因为它与 M 的对应关系更直接，且更容易通过 R 表征和 S 性能测试验证；B 策略可作为补充，但需要关注 G 副作用。该迁移判断仅适用于具备 F 条件的体系，若结构环境、反应条件或目标性能发生变化，需要重新验证机制 M 是否仍然主导性能变化。后续应通过 H 表征确认变量 C/D 是否被调控，通过 I 测试判断 Z 是否按预期改善，并通过 J 稳定性或计算验证排查 G 风险。”

请按以下 JSON 输出：

{
  "cot_type": "机理到设计策略迁移 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少已知机理、目标性能、可调变量、迁移对象、边界条件或验证依据"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "source_mechanism": "用于迁移的已知机理 M",
    "target_performance": "希望改善或调控的目标性能 Z",
    "recommended_design_strategies": [
      {
        "strategy": "推荐设计策略",
        "target_variables": ["应调控的变量"],
        "mechanism_basis": "该策略对应的机制依据，必须说明变量如何映射到已知机理",
        "expected_performance_pathway": "变量如何通过机制通道影响目标性能",
        "potential_risks": ["潜在副作用、折中关系或限制"]
      }
    ],
    "priority_order": [
      {
        "strategy": "策略名称",
        "priority": "优先 / 辅助 / 备选",
        "reason": "优先级理由，必须绑定机理对应性、变量可控性、风险或验证可行性"
      }
    ],
    "validation_methods": [
      {
        "method": "实验、表征、测试或计算方法",
        "validation_target": "验证哪个机制、变量、性能路径或副作用",
        "success_signal": "什么结果说明策略有效或提示策略不成立"
      }
    ],
    "applicability_boundary": [
      "策略适用的体系、结构、条件、性能目标、应用边界或不确定性"
    ],
    "fallback_or_next_iteration": [
      "如果首选策略效果不足，下一步如何调整；必须基于已有机制和变量，不得新增无依据方向"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留机制、变量、性能指标、验证方法或边界；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_mechanism_to_design_task": true,
    "has_source_mechanism": true,
    "has_target_performance": true,
    "has_design_strategy": true,
    "does_not_only_repeat_mechanism": true,
    "has_mechanism_basis": true,
    "has_target_variables": true,
    "links_strategy_to_performance": true,
    "has_priority_order_when_multiple_strategies": true,
    "has_applicability_boundary": true,
    "mentions_specific_risks": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "does_not_repeat_chain": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'mechanism_to_design.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“实验条件 / 制备工艺优化 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information 和 cot_type_judgement>

目标 CoT 类型：
实验条件 / 制备工艺优化 CoT

生成要求：
1. input 必须表现为具体工艺优化问题，而不是完整实验方案设计任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含具体研究对象 X。
4. 必须包含明确工艺变量 Y，例如温度、时间、溶剂、pH、气氛、前驱体比例、煅烧条件、结晶条件、光照波长、光照功率等。
5. 必须包含变量范围、变量水平或至少两个可比较条件。
6. 必须包含目标性能 Z 或评价指标，例如容量、效率、选择性、稳定性、转化率、产率、过电位、半衰期等。
7. 如果存在“先升后降”“过低不足”“过高副作用”“某一窗口最优”等趋势，应写入 input。
8. 如果存在结构、形貌、晶相、缺陷、界面、孔结构、光谱特征或传输行为等线索，可作为背景写入 input。
9. input 应要求模型解释性能趋势、判断工艺窗口、说明副作用和提出验证方法。
10. 不要在 input 中直接给出最终原因、完整答案或完整实验方案。
11. 不要要求“设计实验分组、对照设置、完整实验方案”；这属于实验方案生成 CoT。
12. 如果缺少明确工艺变量、变量范围或性能趋势，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 材料/体系在工艺条件 Y 从 A 到 B 变化时，目标性能 Z 呈现某种趋势；相关表征显示结构因素 M、N 也随 Y 发生变化。请解释该性能趋势，判断合理的工艺优化窗口，并说明过低或过高条件的副作用以及需要的验证方法。”

请按以下 JSON 输出：

{
  "cot_type": "实验条件 / 制备工艺优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_object": "X",
    "process_variable": "Y",
    "variable_range_or_levels": "A 到 B，或具体条件列表",
    "target_performance": "Z",
    "observed_trend": "性能变化趋势",
    "structure_or_process_clues": ["可用于后续推理的结构、表征、机制或过程线索"],
    "low_or_high_condition_risks": ["过低或过高条件下的风险"],
    "required_task": "解释趋势 / 判断工艺窗口 / 说明副作用 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留变量、数值、单位、条件或对比关系"
  ],
  "quality_check": {
    "is_specific": true,
    "has_process_variable": true,
    "has_variable_range_or_levels": true,
    "has_performance_metric": true,
    "has_trend_or_comparison": true,
    "asks_for_process_window": true,
    "asks_for_side_effects": true,
    "asks_for_validation": true,
    "does_not_turn_into_experimental_plan": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'process_optimization.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“实验条件 / 制备工艺优化 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
实验条件 / 制备工艺优化 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的工艺窗口判断。
3. 必须明确工艺优化目标和目标性能指标。
4. 必须识别核心工艺变量、变量范围或条件水平。
5. 必须说明目标性能随工艺变量变化的趋势。
6. 必须分析工艺变量如何影响结构、形貌、晶相、缺陷、界面、孔结构、光谱特征、传输行为或其他相关因素。
7. 必须把结构/过程变化与性能趋势建立联系。
8. 必须判断最优工艺窗口或最佳条件的依据。
9. 必须说明过低或过高条件可能带来的副作用。
10. 必须给出需要的表征、性能测试或稳定性验证方法。
11. 不能引入文献没有支撑的新变量、新机制或新实验条件。
12. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
13. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
14. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“图 2a”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
15. 不要在 chainofThought 中用括号标注证据来源，例如“（图 2a）”“（文献报道 8.3%）”“（见表 1）”。
16. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
17. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为体系事实、变量关系、条件约束和专业判断。
18. 不要使用“根据已有数据”“根据已有筛选”“筛选实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”“已有案例证明”等证据过程表达。
19. 不要生成完整实验方案，不要写 output。

推荐推理步骤结构：
1. 明确工艺优化任务和目标性能。
2. 识别核心工艺变量及其变化范围。
3. 总结性能随工艺变量变化的趋势。
4. 分析工艺变量对结构、形貌、晶相、缺陷或界面等因素的影响。
5. 解释这些结构或过程变化如何影响目标性能。
6. 判断最优工艺窗口或最佳条件的证据基础。
7. 说明过低或过高条件下的副作用。
8. 给出后续需要的表征和性能验证方法。

请按以下 JSON 输出：

{
  "cot_type": "实验条件 / 制备工艺优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留变量、数值、单位、条件、图表或章节位置；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的实验条件、测试条件、材料体系或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_process_variable": true,
    "has_performance_trend": true,
    "links_structure_or_process_to_performance": true,
    "identifies_optimal_window": true,
    "mentions_low_or_high_condition_side_effects": true,
    "includes_validation_methods": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'process_optimization.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验条件 / 制备工艺优化 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验条件 / 制备工艺优化 CoT

生成要求：
1. output 必须直接回答 input 中提出的工艺优化任务，开头即给出推荐工艺窗口、最佳条件或优化方向，不能用“综上”“总体来看”“可以从多个方面优化”等泛泛开场。
2. output 必须紧扣“实验条件 / 制备工艺优化”任务，不要答成实验方案生成、配方设计、性能提升路径或泛泛工艺建议。回答重点应是“工艺变量 -> 结构/过程响应 -> 性能趋势 -> 推荐窗口 -> 过低/过高副作用 -> 验证方式”。
3. 如果 input 或 chainofThought 没有明确工艺变量、目标性能、性能趋势、结构/过程变化或可判断的边界条件，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行给出工艺窗口。
4. 必须给出推荐工艺窗口、最佳条件或合理优化方向。若没有明确数值范围，不能编造具体数值，只能使用低/中/高、偏低/适中/偏高、相对窗口或“需要先补充范围验证”的表述。
5. 每个关键判断都必须绑定具体工艺变量、结构/过程变化、性能指标和趋势方向，不能只写“优化工艺”“改善结构”“提高性能”“条件更合适”等空泛表达。
6. 必须说明该窗口成立的核心依据：工艺变量如何影响形貌、晶相、缺陷、孔结构、界面、传输、反应过程、稳定性或其他结构/过程因素，并进一步影响目标性能。
7. 必须分别说明过低条件和过高条件可能导致的问题。如果 input 和 chainofThought 只支持其中一侧风险，应明确写出另一侧风险证据不足，不要补写无依据副作用。
8. 如果性能趋势是先升后降、平台期、阈值效应或非线性变化，output 必须说明趋势含义和可能的结构/过程原因；如果只能判断相关性，应保留限定表达。
9. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认目标结构是否形成、工艺副作用是否被抑制、性能是否稳定达到窗口判断，或过低/过高条件是否被排除。
10. output 应按清晰顺序组织，建议采用“推荐窗口 -> 核心依据 -> 过低风险 -> 过高风险 -> 验证方式 -> 适用边界”的结构，避免把窗口、原因、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“进一步优化工艺参数”等。若表达方案价值，必须落到具体工艺变量、结构响应、性能指标或风险控制上。
12. 不要为了显得完整而强行生成多个工艺变量或优化方向。如果 input 和 chainofThought 只支持一个变量，应集中写清楚该变量；证据不足时，应在 missing_information 或 boundary_conditions 中说明。
13. 不要生成完整实验方案；本步骤输出的是工艺窗口判断和验证方向，不是详细操作流程或分组方案。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新实验条件、新测试指标或新结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该条件范围内”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该体系应优先将工艺变量 Y 控制在 A 条件或 A-B 窗口内。该窗口的依据是 Y 在该范围内能够促进 M 结构/过程形成，同时避免 N 副作用，使目标性能 Z 更稳定地改善。若 Y 偏低，可能导致 P 问题，例如目标结构形成不足、传输受限或反应不充分；若 Y 偏高，可能引发 Q 问题，例如结构破坏、副反应增加、稳定性下降或加工性变差。后续应通过 R 表征确认 M 是否形成，通过 S 性能测试判断 Z 是否稳定改善，并通过 T 稳定性或对照验证排除过低/过高条件带来的副作用。该判断只适用于当前体系和已给定变量范围，超出该范围需要重新筛选。”

请按以下 JSON 输出：

{
  "cot_type": "实验条件 / 制备工艺优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少工艺变量、变量范围、目标性能、性能趋势、结构/过程响应、过低/过高风险或验证条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "process_variable": "需要优化的工艺变量",
    "recommended_process_window": "推荐工艺窗口、最佳条件或优化方向；无明确数值时不得编造具体数值",
    "core_rationale": "支持该窗口的核心依据，必须说明工艺变量如何影响结构/过程并进一步影响目标性能",
    "structure_or_process_response": [
      "工艺变量变化引起的形貌、晶相、缺陷、孔结构、界面、传输、反应过程、稳定性或其他响应"
    ],
    "performance_trend": "目标性能随工艺变量变化的趋势，例如升高、降低、先升后降、平台期、阈值效应或不确定",
    "low_condition_risk": {
      "risk": "过低条件的风险或副作用；证据不足时说明缺口",
      "affected_structure_or_performance": "该风险影响的结构、过程或性能"
    },
    "high_condition_risk": {
      "risk": "过高条件的风险或副作用；证据不足时说明缺口",
      "affected_structure_or_performance": "该风险影响的结构、过程或性能"
    },
    "validation_methods": [
      {
        "method": "表征、性能测试、稳定性验证、对照或计算方法",
        "validation_target": "验证哪个工艺窗口、结构/过程响应、性能趋势或副作用",
        "success_signal": "什么结果支持该工艺窗口有效"
      }
    ],
    "boundary_conditions": [
      "适用条件、体系边界、变量范围、测试条件、不确定性或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留图表、章节、变量、数值、单位或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_process_optimization_task": true,
    "does_not_repeat_chain": true,
    "has_process_variable": true,
    "has_recommended_process_window": true,
    "avoids_fabricated_conditions": true,
    "has_core_rationale": true,
    "links_process_to_structure_or_process_response": true,
    "links_response_to_performance": true,
    "has_performance_trend": true,
    "mentions_low_or_high_condition_side_effects": true,
    "low_high_risks_are_specific": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'process_optimization.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“实验方案生成 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information 和 cot_type_judgement>

目标 CoT 类型：
实验方案生成 CoT

生成要求：
1. input 必须表现为一个具体实验方案设计任务，而不是泛泛建议。
2. input 中不要出现“根据文献”“本文报道”“作者发现”等文献来源表达。
3. 必须包含研究对象 X。
4. 必须包含实验目标，例如提升性能 Z、验证机制 M、比较候选策略、优化体系短板等。
5. 必须包含当前短板或待验证问题。
6. 应包含可调控变量，例如结构变量、组分变量、工艺变量、配方变量或候选材料。
7. 应要求设计实验分组、对照组、关键变量、表征方法和性能测试。
8. 如果有已知风险、边界条件或失败信号，应写入 input，要求方案中规避或验证。
9. 不要在 input 中直接给出实验方案细节答案。
10. 如果缺少研究目标、可调变量或验证方法，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“针对 X 体系当前存在的 A 短板，希望提升或验证目标 Z。可调控变量包括 B、C、D，并需要通过 M 类表征和 P 类性能测试判断效果。请设计一套实验方案，包括实验分组、对照设置、关键变量、验证方法和成功判据。”

请按以下 JSON 输出：

{
  "cot_type": "实验方案生成 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_object": "X",
    "experiment_goal": "提升性能 / 验证机制 / 比较策略 / 优化短板",
    "current_problem_or_shortcoming": "A",
    "candidate_variables": ["B", "C", "D"],
    "suggested_controls_or_comparisons": ["空白组、对照组、变量组、最佳样品或失败样品"],
    "validation_methods": ["表征方法、性能测试或计算验证"],
    "success_metrics": ["用于判断实验是否成功的指标"],
    "risk_or_boundary": ["需要规避或验证的风险与边界"],
    "required_task": "设计实验方案 / 设置对照 / 指定验证方法 / 定义成功判据"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留图表、章节、条件或数值"
  ],
  "quality_check": {
    "is_specific": true,
    "has_experiment_goal": true,
    "has_candidate_variables": true,
    "asks_for_controls": true,
    "asks_for_validation": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'experimental_plan.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“实验方案生成 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output，也不要直接写完整实验方案。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
实验方案生成 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中“完整实验方案”的形成。
3. 必须明确实验目标，例如提升转化率、提升分离产率、获得高纯度产物、验证结构或评估稳定性。
4. 必须识别当前体系短板和已知风险，例如产率低、半衰期短、逆向转化、降解、分离困难或无效条件。
5. 必须识别可调控变量，并按变量类型分层，例如溶剂、波长、功率、时间、浓度、温度、后处理和反溶剂。
6. 必须说明为什么需要设置对照组，包括原料对照、暗对照、空白/基准对照、失败条件对照和候选条件对照。
7. 必须说明变量筛选应采用分阶段、单因素优先的逻辑，避免多变量同时变化导致归因困难。
8. 必须把每类变量与评价指标对应起来，例如转化率、分离产率、半衰期、纯度、结构表征和稳定性。
9. 必须说明表征和测试方法各自验证什么，例如 UV-Vis 验证光异构化趋势，NMR 验证结构和纯度，IR/Raman 验证振动指纹，半衰期测试验证稳定性。
10. 必须形成成功判据的推理依据，例如无降解、转化率提高、分离产率提高、结构可确证、稳定性满足最低要求。
11. 必须说明风险规避逻辑，例如避光、快速后处理、避免过高功率、避免无效溶剂、验证过低功率不足等。
12. 不能引入文献没有支撑的新变量、新机制或新实验条件。
13. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“图 2a”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源，例如“（图 2a）”“（文献报道 8.3%）”“（见表 1）”。
17. 可以使用 input 中已经给出的数值、条件和现象，但表达方式应改为任务事实，例如“当前分离产率较低，仅为 8.3%”，不要写“文献报道仅 8.3%”。
18. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
19. chainofThought 还必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为体系本身的事实、变量关系、条件约束和专业判断。
20. 不要使用“根据已有数据”“根据已有筛选”“筛选实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”“已有案例证明”等证据过程表达。
21. 推荐使用内化表达，例如：
    - 不写：“溶剂筛选实验表明，DMSO 是有效溶剂。”
    - 改写：“在该体系中，DMSO 更适合作为异构化反应介质，而水主要受限于后续分离，甲醇中的异构化响应较弱。”
    - 不写：“功率筛选结果显示 10 W 会破坏骨架。”
    - 改写：“过高光功率存在骨架破坏风险，过低功率则不足以维持高比例目标产物。”
22. 不要生成最终实验方案，不要写 output。

推荐推理步骤结构：
1. 明确实验方案要解决的核心目标和评价指标。
2. 识别当前体系的主要短板和必须规避的失败条件。
3. 将可调控变量分层，并确定优先筛选顺序。
4. 设计对照逻辑，说明每类对照用于排除或验证什么。
5. 规划分阶段变量筛选思路，避免多因素混杂。
6. 将表征方法和性能测试指标匹配到具体验证目标。
7. 推导成功判据和淘汰判据。
8. 说明风险规避、边界条件和下一轮迭代优化逻辑。

请按以下 JSON 输出：

{
  "cot_type": "实验方案生成 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留变量、数值、单位、条件、图表或章节位置；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的实验条件、测试条件、材料体系或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_experiment_goal": true,
    "has_current_shortcoming": true,
    "has_candidate_variables": true,
    "has_control_logic": true,
    "has_stagewise_screening_strategy": true,
    "matches_methods_to_validation_targets": true,
    "has_success_and_rejection_criteria": true,
    "has_risk_control_logic": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'experimental_plan.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验方案生成 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验方案生成 CoT

生成要求：
1. output 必须直接回答 input 中提出的实验方案设计任务，开头即说明实验目标和总体方案，不要用“综上”“总体来看”“可以从多个方面开展”等泛泛开场。
2. output 必须紧扣“实验方案生成”任务，不要答成普通机理解释、性能提升路径、候选优选或泛泛优化建议。回答重点应是“实验目标 -> 变量与对照 -> 分阶段实验 -> 表征/测试 -> 成功与淘汰判据 -> 风险与迭代”。
3. 如果 input 或 chainofThought 没有明确实验目标、研究对象、可调变量、评价指标、必要对照或验证方法，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成完整实验方案。
4. output 必须是可执行的实验方案，但不要写成详细操作规程。应明确分组逻辑、变量筛选顺序、评价指标和判定规则，不需要写逐步称量、仪器参数、操作时长等 input 和 chainofThought 中没有提供的细节。
5. 实验分组必须服务于 input 的目标。对照组应按任务需要设置，不能机械加入无关的空白对照、暗对照、阳性组或失败组；每个组都必须说明条件、目的、评价指标和保留/淘汰规则。
6. 每个关键实验组都必须绑定具体问题：验证哪个变量、排除哪个干扰、确认哪个机制、比较哪个性能或识别哪个失败风险，不能只写“用于对比”“用于验证效果”等空泛表述。
7. 变量筛选必须有顺序和理由。优先先筛选最影响目标性能或风险最大的变量，再做组合验证；如果变量之间存在耦合，应说明为什么不能只做单因素结论。
8. 表征方法和性能测试必须说明验证目标和成功信号，不能只罗列方法名称。例如应说明该方法验证结构是否形成、界面是否改善、目标性能是否提升、稳定性是否达标或副反应是否被抑制。
9. 成功判据、失败判据和回退条件必须具体到结构、性能、稳定性、安全性、可重复性、对照差异或风险信号，不能只写“性能较好”“结果稳定”“需要进一步优化”。
10. 风险控制策略必须对应 input 或 chainofThought 中已有的失败条件、副作用或不确定性，说明如何规避、识别或淘汰，不能新增无依据风险。
11. output 应按清晰顺序组织，建议采用“总体实验策略 -> 实验分组 -> 变量筛选计划 -> 表征与测试 -> 成功/淘汰判据 -> 风险控制 -> 迭代计划 -> 适用边界”的结构，避免把分组、目的、测试和判据混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“系统开展实验验证”等。若表达方案价值，必须落到具体目标、变量、判据或风险控制上。
13. 不要为了显得完整而强行生成过多实验组或变量。如果 input 和 chainofThought 只支持有限变量，应围绕这些变量设计方案；证据不足时，应在 missing_information 或 boundary_conditions 中说明。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新实验条件、新测试指标或新结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把实验方案写成验证确定因果，应保留“用于判断”“用于筛查”“需要进一步确认”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“根据已有数据”“结果显示”“实验表明”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该实验方案应围绕 X 目标展开，先建立 A 基准组确认原始体系表现，再设置 B 变量筛选组判断关键调控因素对 Z 性能的影响，最后用 C 组合验证组确认最有效策略是否稳定成立。分组中，A 组用于提供基准对照，B 组用于比较变量 Y 的不同水平或条件，C 组用于验证优选变量组合；每组都应以 P 性能、Q 结构信号和 R 稳定性/风险信号作为判据。若 B 组出现 S 失败信号，应回退调整 Y 或排除该条件；若 C 组仅提升单一指标但引入 T 副作用，则不应进入后续优化。该方案只适用于当前 X 体系和已给定变量范围，超出该设计空间需要重新设定对照和评价指标。”

请按以下 JSON 输出：

{
  "cot_type": "实验方案生成 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少实验目标、研究对象、可调变量、评价指标、对照逻辑、验证方法或风险条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终实验方案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "experimental_goal": "实验要解决的具体问题或要验证的目标性能",
    "overall_experimental_strategy": "总体实验设计策略和阶段划分",
    "experimental_groups": [
      {
        "group_name": "实验组或对照组名称",
        "group_type": "baseline / blank_control / dark_control / positive_condition / failure_control / variable_screening / combined_validation / other_relevant_control",
        "conditions": ["该组的关键实验条件，必须来自 input 或 chainofThought"],
        "purpose": "该组用于验证什么变量、排除什么干扰、比较什么性能或识别什么风险",
        "evaluation_metrics": ["该组需要观察或测试的指标"],
        "decision_rule": "如何根据结果判断保留、淘汰、回退或进入下一阶段"
      }
    ],
    "variable_screening_plan": [
      {
        "stage": "筛选阶段名称",
        "variable": "本阶段筛选的变量",
        "screening_reason": "为什么优先筛选该变量",
        "levels_or_conditions": ["变量水平或实验条件；不得新增无依据条件"],
        "fixed_conditions": ["本阶段保持不变的条件"],
        "evaluation_metrics": ["本阶段评价指标"],
        "decision_rule": "进入下一阶段、回退或淘汰的判据"
      }
    ],
    "characterization_and_tests": [
      {
        "method": "表征、测试或计算方法",
        "validation_target": "该方法验证哪个结构、机制、性能、稳定性、对照差异或风险",
        "success_signal": "什么信号说明实验有效或该条件应被保留"
      }
    ],
    "success_criteria": [
      "判断实验成功的具体判据，必须对应目标性能、结构信号、稳定性、可重复性或风险抑制"
    ],
    "rejection_or_failure_criteria": [
      "判断实验失败、淘汰条件或需要回退优化的判据"
    ],
    "risk_control_strategy": [
      "针对已知失败条件、副作用或不稳定性的规避、识别和验证策略"
    ],
    "iteration_plan": [
      "如果某阶段不达标，下一轮如何调整变量、对照或验证方式；不得新增无依据方向"
    ],
    "boundary_conditions": [
      "该实验方案成立的体系、变量范围、测试范围、适用条件或不确定性"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留图表、章节、变量、数值、单位或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_experimental_plan_task": true,
    "is_detailed_experimental_plan": true,
    "has_experimental_goal": true,
    "has_overall_strategy": true,
    "has_experimental_groups": true,
    "groups_are_relevant_to_input": true,
    "has_control_groups_when_needed": true,
    "has_variable_screening_plan": true,
    "screening_order_has_reason": true,
    "matches_methods_to_validation_targets": true,
    "validation_methods_have_targets_and_success_signals": true,
    "has_success_criteria": true,
    "has_rejection_or_failure_criteria": true,
    "has_risk_control_strategy": true,
    "has_iteration_plan": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'experimental_plan.step6',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“实验设计配方 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、recipe_components、process_or_recipe_information、cot_type_judgement>

目标 CoT 类型：
实验设计配方 CoT

生成要求：
1. input 必须表现为具体配方设计任务，而不是泛泛实验建议。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含研究体系 X，例如电解液、浆料、涂层、催化剂、聚合物、复合材料、凝胶、前驱体体系、药物分子配方等。
4. 必须包含配方设计目标 Z，例如提升容量、稳定性、选择性、安全性、机械强度、溶解度、成膜性、能量密度、分散性或可加工性。
5. 必须包含关键组分及其作用，例如活性组分、溶剂、添加剂、粘结剂、前驱体、交联剂、载体、盐、填料、助剂等。
6. 必须包含可调配方变量，例如质量比、摩尔比、浓度、添加剂含量、负载量、溶剂比例、固含量或组分梯度。
7. 如果文献信息中有明确比例、浓度或范围，应保留单位和条件。
8. 如果没有明确比例或浓度，不能编造数值；可以要求设计低/中/高梯度或在已有安全范围内筛选。
9. 必须包含评价指标和成功判据，例如目标性能、稳定性、重复性、纯度、分散性、黏度、成膜质量、安全性等。
10. 如果存在过量添加、副反应、相分离、稳定性下降、黏度过高、性能下降等风险，应写入 input。
11. input 应要求模型给出基础配方、变量矩阵、筛选逻辑、淘汰准则和下一轮优化方向。
12. 不要在 input 中直接给出最终配方答案。
13. 如果缺少配方组分、可调比例/浓度或性能反馈，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“需要为 X 体系设计一组实验配方，以优化目标性能 Z。已知关键组分包括 A、B、C，其中 A 主要负责 P，B 影响 Q，C 可能改善 R，但过量 C 会带来 S 风险。可调因素包括 A:B 比例、C 含量、溶剂比例和处理条件。请给出合理的基础配方、单因素梯度、组合优化配方、成功判据和淘汰准则。”

请按以下 JSON 输出：

{
  "cot_type": "实验设计配方 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "recipe_system": "X",
    "recipe_design_goal": "Z",
    "base_recipe_or_reference": "已有基础配方、基准配方或参考体系",
    "key_components": [
      {
        "component": "组分名称",
        "role": "该组分在配方中的作用"
      }
    ],
    "adjustable_recipe_variables": [
      "可调比例、浓度、负载量、添加剂含量、溶剂比例、固含量等"
    ],
    "known_ranges_or_levels": [
      "已知比例、浓度、单位或低/中/高梯度"
    ],
    "performance_metrics": [
      "用于评价配方效果的指标"
    ],
    "risks_or_side_effects": [
      "过量、缺失、比例不当或工艺不兼容带来的风险"
    ],
    "required_task": "设计基础配方 / 单因素梯度 / 组合优化矩阵 / 成功判据 / 淘汰准则"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留组分、比例、浓度、单位、性能趋势或风险"
  ],
  "quality_check": {
    "is_specific": true,
    "has_recipe_system": true,
    "has_recipe_design_goal": true,
    "has_key_components": true,
    "has_adjustable_recipe_variables": true,
    "has_performance_metrics": true,
    "mentions_ranges_or_says_no_fabrication": true,
    "asks_for_recipe_matrix": true,
    "asks_for_success_and_rejection_criteria": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}', 'system_default_v1', 'recipe_design.step4',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“实验设计配方 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output，也不要直接给出完整配方表。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、recipe_components、process_or_recipe_information、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
实验设计配方 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的配方矩阵和筛选方案。
3. 必须明确配方设计目标和评价指标。
4. 必须识别关键组分及其作用。
5. 必须区分配方变量和工艺变量；本类推理重点是组分比例、浓度、负载量、添加剂含量、溶剂比例、固含量等配方因素。
6. 必须说明为什么需要基础配方、单因素梯度和组合优化配方。
7. 必须根据已有证据设定安全变量范围；没有数值范围时，只能使用低/中/高梯度或条件性范围，不能编造具体数值。
8. 必须说明每个变量变化可能影响的性能、结构或工艺适配性。
9. 必须说明过量添加、比例失衡、相分离、副反应、稳定性下降或可加工性变差等风险。
10. 必须推导成功判据和淘汰判据。
11. 必须说明下一轮优化如何根据第一轮结果调整配方。
12. 不能引入文献没有支撑的新组分、新比例、新浓度、新机制或新风险。
13. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源。
17. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
18. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为配方事实、组分作用、变量关系、条件约束和专业判断。
19. 不要使用“根据已有数据”“配方筛选实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
20. 不要生成最终配方表，不要写 output。

推荐推理步骤结构：
1. 明确配方设计目标和成功评价指标。
2. 识别基础配方、关键组分及其功能角色。
3. 区分主变量、辅助变量和固定条件。
4. 设定可接受的变量范围或低/中/高梯度。
5. 规划单因素梯度，判断每个变量要验证的问题。
6. 规划组合优化逻辑，避免变量混杂。
7. 推导成功判据、淘汰判据和风险控制逻辑。
8. 给出下一轮精细化优化方向。

请按以下 JSON 输出：

{
  "cot_type": "实验设计配方 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留组分、比例、浓度、单位、性能趋势或风险；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的配方体系、组分范围、工艺条件、测试条件或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_recipe_goal": true,
    "has_key_components_and_roles": true,
    "distinguishes_recipe_variables_from_process_variables": true,
    "has_variable_ranges_or_gradients": true,
    "plans_single_factor_screening": true,
    "plans_combination_optimization": true,
    "has_success_and_rejection_criteria": true,
    "handles_overdose_or_imbalance_risks": true,
    "avoids_fabricated_ratios": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}', 'system_default_v1', 'recipe_design.step5',
'{"schema_version":"1.0"}', NOW(), 0);

INSERT INTO prompts (user_id, stage, version, name, content, template_id, prompt_key, reference_fields, created_at, is_default)
VALUES (NULL, 'professional_cot', 1, '系统默认模板 v1',
'你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验设计配方 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验设计配方 CoT

生成要求：
1. output 必须直接回答 input 中提出的配方设计任务，开头即说明配方目标、基础配方思路和核心筛选变量，不能用“综上”“总体来看”“可以从多个方面优化”等泛泛开场。
2. output 必须紧扣“实验设计配方”任务，不要答成普通实验方案、性能提升路径、工艺优化或泛泛配方建议。回答重点应是“配方目标 -> 组分作用 -> 单因素梯度 -> 组合优化矩阵 -> 评价与淘汰判据 -> 风险控制 -> 下一轮优化”。
3. 如果 input 或 chainofThought 没有明确配方目标、组分、可调变量、评价指标或可用范围，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成配方矩阵。
4. output 必须给出可执行的基础配方、变量筛选逻辑和配方矩阵，但不要写成无依据的操作规程。不得补写 input 和 chainofThought 中没有提供的称量、浓度、温度、时间、溶剂或处理条件。
5. 如果 input 或 chainofThought 中有明确数值范围、比例、浓度、单位或条件，应保持一致；如果没有明确数值范围，不能编造具体比例或浓度，只能使用低/中/高梯度、相对比例、条件性建议或“需要先确定范围”的表述。
6. 每个关键组分都必须说明作用和风险，至少说明它影响什么结构、过程、性能、稳定性、加工性、相容性或安全性，不能只写“提高性能”“改善体系”“增强稳定性”等空泛表达。
7. 每个单因素梯度必须说明筛选变量、保持不变的条件、验证目的、评价指标和进入下一阶段或淘汰的规则，不能只列出梯度名称。
8. 组合优化矩阵必须建立在单因素筛选逻辑上，说明为什么组合这些变量、预期解决什么问题，以及如何判断组合是否优于基础配方。
9. 成功判据和淘汰判据必须具体到目标性能、稳定性、加工性、相分离、副反应、可重复性、对照差异或风险信号，不能只写“性能更好”“结果稳定”“不满足要求则淘汰”。
10. 风险控制策略必须对应配方中的具体问题，例如过量添加、比例失衡、相分离、副反应、稳定性下降、加工性变差、相容性不足或安全性风险，不能只写“需要控制风险”。
11. 下一轮优化方向必须基于当前筛选结果可能出现的情况，说明缩小哪个范围、细化哪个比例、保留哪个变量或补充哪个验证，不能新增无依据组分或方向。
12. output 应按清晰顺序组织，建议采用“基础配方 -> 组分作用 -> 单因素梯度 -> 组合优化矩阵 -> 评价指标 -> 成功/淘汰判据 -> 风险控制 -> 下一轮优化 -> 适用边界”的结构，避免把组分、变量、判据和风险混在一起。
13. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“系统优化配方性能”等。若表达方案价值，必须落到具体组分、变量、性能或风险控制上。
14. 不要为了显得完整而强行生成过多配方组或组合矩阵。如果 input 和 chainofThought 只支持有限变量，应围绕这些变量设计；证据不足时，应在 missing_information 或 boundary_conditions 中说明。
15. 不要引入 input 和 chainofThought 中没有出现的新组分、新比例、新浓度、新机制、新材料、新实验条件、新测试指标或新结论。
16. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把配方设计写成确定最优方案，应保留“用于筛查”“优先验证”“可能更合适”“需要进一步确认”等限定表达。
17. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
18. output 应完成证据内化，不要出现“配方筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
19. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该配方设计应以 X 体系的 Z 性能为目标，先建立包含 A、B、C 组分的基础配方，其中 A 负责……，B 负责……，C 负责……。第一轮采用单因素梯度筛选关键变量 Y，在其他组分和处理条件保持不变的前提下比较低/中/高或已给定范围，判断 Y 对 Z、稳定性和加工性的影响；进入下一轮的条件是 P 指标改善且不出现 Q 风险。第二轮将单因素中表现较好的 Y 与 W 变量组合，形成小规模组合矩阵，用于判断二者是否存在协同或比例失衡。若出现相分离、副反应、稳定性下降或加工性变差，应淘汰该配方组或回退到较低水平。下一轮优化应围绕保留组进一步缩小比例范围，并补充 R 测试确认长期稳定性或可重复性。该方案只适用于当前组分体系和已给定变量范围，不能直接外推到其他配方体系。”

请按以下 JSON 输出：

{
  "cot_type": "实验设计配方 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少配方目标、基础组分、可调变量、范围信息、评价指标、风险条件或边界条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终配方设计与筛选方案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "recipe_goal": "配方设计要优化或验证的具体目标",
    "base_recipe": {
      "description": "基础配方或基准配方",
      "fixed_components": ["固定组分及作用"],
      "initial_conditions": ["已有比例、浓度、处理条件；无明确数值时写条件性描述，不得编造"]
    },
    "component_roles": [
      {
        "component": "组分名称",
        "role": "该组分在结构、过程、性能、稳定性、加工性、相容性或安全性中的作用",
        "risk_if_too_low_or_too_high": "过低或过高的具体风险"
      }
    ],
    "single_factor_gradient": [
      {
        "variable": "单因素变量",
        "levels_or_range": ["具体水平、范围或低/中/高梯度；不得新增无依据数值"],
        "fixed_conditions": ["保持不变的配方或工艺条件"],
        "purpose": "该梯度用于验证什么变量作用或风险",
        "evaluation_metrics": ["评价指标"],
        "decision_rule": "保留、淘汰、回退或进入组合优化的判据"
      }
    ],
    "combination_optimization_matrix": [
      {
        "recipe_group": "组合优化组名称",
        "combined_variables": ["组合变量"],
        "design_logic": "为什么组合这些变量，预期解决什么问题或验证什么协同/冲突",
        "evaluation_metrics": ["评价指标"],
        "decision_rule": "判断是否优于基础配方、是否淘汰或是否进入下一轮的标准"
      }
    ],
    "success_criteria": [
      "判断配方成功的具体判据，必须对应目标性能、稳定性、加工性、相容性、可重复性或风险抑制"
    ],
    "rejection_criteria": [
      "判断配方失败、淘汰或需要回退的具体判据"
    ],
    "risk_control_strategy": [
      "针对过量、比例失衡、副反应、相分离、稳定性下降、加工性变差、相容性不足或安全性问题的控制策略"
    ],
    "next_iteration_plan": [
      "下一轮优化如何缩小范围、细化比例、保留变量或增加验证；不得新增无依据方向"
    ],
    "boundary_conditions": [
      "该配方方案成立的体系、组分范围、测试条件、变量空间或适用边界"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留组分、比例、浓度、单位、性能趋势或风险；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_recipe_design_task": true,
    "is_actionable_recipe_design": true,
    "has_recipe_goal": true,
    "has_base_recipe": true,
    "has_component_roles": true,
    "component_roles_are_specific": true,
    "has_single_factor_gradient": true,
    "single_factor_gradient_has_decision_rules": true,
    "has_combination_optimization_matrix": true,
    "combination_matrix_has_design_logic": true,
    "has_success_criteria": true,
    "has_rejection_criteria": true,
    "handles_specific_risks": true,
    "has_next_iteration_plan": true,
    "avoids_fabricated_ratios": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
', 'system_default_v1', 'recipe_design.step6',
'{"schema_version":"1.0"}', NOW(), 0);
