# Lark Drive Datasource

Fetch documents from Lark Drive (Feishu Drive) into Dify knowledge base pipelines.

## Features

- **Browse Lark Drive files** — Connect to Lark Open Platform and browse authorized folders and files
- **Multi-format support** — Handle native Lark docs (docx), PDFs, images, spreadsheets, and more
- **Smart download** — Automatically pick the best download method per file type
- **Shortcut support** — Resolve shortcut files to their target documents

## Setup

1. Create an app on [Lark Open Platform](https://open.larksuite.com/app) and obtain **App ID** and **App Secret**.
2. Add the required API permissions (see below) and publish the app version.
3. Share the target folder with your app in Lark Drive.
4. Install this plugin in Dify and fill in the credentials.

### Required Lark API Permissions

| Scope | Permission | Purpose |
|-------|-----------|---------|
| tenant | `drive:file:readonly` | List files in Drive |
| tenant | `drive:file:download` | Download regular files |
| tenant | `drive:export:readonly` | Create and query export tasks |
| tenant | `docx:document:readonly` | Read Lark document content |
| tenant | `docs:document.content:read` | Read document body |
| tenant | `docs:document.media:download` | Download document media |
| tenant | `docs:document:export` | Export documents |
| tenant | `space:document:retrieve` | Retrieve space documents |

## Usage

1. In Dify, go to **Knowledge** → create or open a knowledge base.
2. Add a **Lark Drive** datasource node in the pipeline.
3. Browse folders, select files, and start syncing.

### Supported File Types

| File Type | Extension | Download Method |
|-----------|-----------|-----------------|
| Lark Doc | `.docx` | Export as text |
| Spreadsheet | `.sheet` | Export as CSV |
| Bitable | `.bitable` | Export as XLSX |
| Regular files | `.pdf`, `.jpg`, etc. | Direct download |

## Privacy

This plugin sends App ID, App Secret, and folder tokens to Lark Open Platform APIs. File content is streamed directly to Dify without intermediate caching. See [PRIVACY.md](./PRIVACY.md) for details.
