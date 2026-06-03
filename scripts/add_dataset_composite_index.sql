-- 为 datasets 表添加复合索引，解决慢查询全表扫描问题
-- 影响：user_id + current_stage + created_at 三列联合过滤不再扫描 310K 行
-- 预估：查询时间从 4~5秒 降至 <0.01秒

CREATE INDEX idx_datasets_user_stage_created
ON datasets (user_id, current_stage, created_at);