# 飞书云盘数据源插件

从飞书云盘获取文档并导入 Dify 知识库流水线。

## 功能特性

- **浏览云盘文件**：连接飞书开放平台，浏览授权范围内的文件夹和文件
- **多格式支持**：支持飞书原生文档、PDF、图片、电子表格等多种类型
- **智能下载**：根据文件类型自动选择最佳下载方式
- **快捷方式兼容**：正确处理云盘中的快捷方式文件

## 配置步骤

1. 在[飞书开放平台](https://open.feishu.cn/app)创建应用，获取 **App ID** 和 **App Secret**
2. 添加所需 API 权限并发布应用版本
3. 在飞书云盘中将目标文件夹共享给应用
4. 在 Dify 中安装插件并填写凭证

### 所需飞书 API 权限

| 权限 | 用途 |
|------|------|
| `drive:file:readonly` | 读取云盘文件列表 |
| `drive:file:download` | 下载普通文件 |
| `drive:export:readonly` | 创建和查询导出任务 |
| `docx:document:readonly` | 读取飞书文档内容 |
| `docs:document.content:read` | 读取文档正文 |
| `docs:document.media:download` | 下载文档媒体资源 |
| `docs:document:export` | 导出文档 |
| `space:document:retrieve` | 检索空间文档 |

## 使用方式

1. 在 Dify 中进入**知识库**→创建或打开知识库
2. 在流水线中添加**飞书云盘**数据源节点
3. 浏览文件夹，选择文件，开始同步

### 支持的文件类型

| 文件类型 | 扩展名 | 下载方式 |
|---------|--------|---------|
| 飞书文档 | `.docx` | 导出为文本 |
| 电子表格 | `.sheet` | 导出为 CSV |
| 多维表格 | `.bitable` | 导出为 XLSX |
| 普通文件 | `.pdf`, `.jpg` 等 | 直接下载 |

## 隐私说明

本插件将 App ID、App Secret 和文件夹 Token 发送至飞书开放平台 API。文件内容直接流式传输至 Dify，不做中间缓存。详见 [PRIVACY.md](../PRIVACY.md)。
