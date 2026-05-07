# 需求：JSON文件合并导出

## 背景
用户经常需要将多个 JSON 数据集文件合并为一个大文件再下载使用，目前只能逐个下载后手动合并，效率低。

## 功能描述
在现有文件管理页面（`/file-manage`）上增加多选 + 合并下载功能。

## 详细规则

### 后端
- 新增 `POST /api/file-manage/merge-download` 接口
- 请求体：`{"file_ids": [1, 2, 3, ...]}`，至少 2 个文件
- 逻辑：
  1. 校验所有 file_id 属于当前用户
  2. 逐个读取 JSON 文件内容
  3. 每个文件内容必须是 JSON 数组，取其全部元素
  4. 将所有文件的数组元素拼接为大数组
  5. 写入临时文件，返回 FileResponse 下载
- 合并后的文件名：`merged_{N}files_{timestamp}.json`
- 非 JSON 文件跳过并提示
- 内容是对象（dict）的文件包装为单元素数组再合并

### 前端
- 文件列表表格新增复选框列（`el-table` 的 `selection` 列）
- 表头右侧新增「合并下载」按钮，选中 ≥ 2 个文件时可用
- 点击后调用后端合并接口，接收 blob 触发浏览器下载
- 合并后文件名由后端 Content-Disposition 决定

## UI 变更
- `FileManage.vue`：表格加 `type="selection"` 列 + 表头加「合并下载」按钮
- `api/index.js`：新增 `mergeAndDownloadFiles` 函数

## 接口变更
- 新增：`POST /api/file-manage/merge-download`（需认证）
