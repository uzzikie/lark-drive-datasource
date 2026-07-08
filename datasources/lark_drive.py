import sys
from typing import Any, Generator
import requests

from dify_plugin.interfaces.datasource.online_drive import OnlineDriveDatasource
from dify_plugin.entities.datasource import (
    OnlineDriveBrowseFilesRequest,
    OnlineDriveBrowseFilesResponse,
    OnlineDriveDownloadFileRequest,
    OnlineDriveFile,
    OnlineDriveFileBucket,
    DatasourceMessage,
)


class LarkDriveDatasource(OnlineDriveDatasource):
    """飞书云盘数据源插件，支持浏览和下载飞书云盘文件。"""

    # ==========================
    # 飞书 API 端点常量
    # ==========================
    FEISHU_BASE_URL = "https://open.larksuite.com/open-apis"
    # 获取 tenant_access_token
    AUTH_URL = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
    # 浏览文件列表
    FILES_LIST_URL = f"{FEISHU_BASE_URL}/drive/v1/files"
    # 普通文件下载（需替换 {token}）
    FILE_DOWNLOAD_URL_TEMPLATE = f"{FEISHU_BASE_URL}/drive/v1/files/{{token}}/download"
    # 创建导出任务
    EXPORT_TASKS_URL = f"{FEISHU_BASE_URL}/drive/v1/export_tasks"
    # 查询导出任务结果（需替换 {ticket}）
    EXPORT_QUERY_URL_TEMPLATE = f"{FEISHU_BASE_URL}/drive/v1/export_tasks/{{ticket}}"
    # 下载导出后的文件（需替换 {file_token}）
    EXPORT_DOWNLOAD_URL_TEMPLATE = f"{FEISHU_BASE_URL}/drive/v1/export_tasks/file/{{file_token}}/download"

    def _get_access_token(self, credentials: dict) -> str:
        """使用 App ID 和 App Secret 获取飞书 tenant_access_token。

        Args:
            credentials: 包含 app_id 和 app_secret 的字典。

        Returns:
            tenant_access_token 字符串。

        Raises:
            ValueError: 当凭证缺失或请求失败时。
        """
        app_id = credentials.get("app_id")
        app_secret = credentials.get("app_secret")

        if not app_id or not app_secret:
            raise ValueError("Missing credentials: app_id and app_secret are required")

        payload = {"app_id": app_id, "app_secret": app_secret}

        print(f"DEBUG: Request URL: {self.AUTH_URL}", file=sys.stderr)
        safe_payload = {"app_id": app_id, "app_secret": "***"}
        print(f"DEBUG: Request Payload: {safe_payload}", file=sys.stderr)

        resp = requests.post(self.AUTH_URL, json=payload, timeout=30)

        print(f"DEBUG: Response Status: {resp.status_code}", file=sys.stderr)
        print(f"DEBUG: Response Body: {resp.text}", file=sys.stderr)

        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            error_msg = data.get("msg", "unknown error")
            raise ValueError(
                f"Failed to get access token: {error_msg}. "
                f"Please verify your App ID and App Secret are correct."
            )
        return data["tenant_access_token"]

    def _build_auth_headers(self, token: str) -> dict:
        """构建带有 Bearer Token 的请求头。"""
        return {"Authorization": f"Bearer {token}"}

    def _browse_files(self, request: OnlineDriveBrowseFilesRequest) -> OnlineDriveBrowseFilesResponse:
        """浏览飞书云盘文件列表。

        路径优先级：
            1. request.prefix（用户当前浏览的文件夹）
            2. credentials["default_folder_token"]（Provider 配置的默认文件夹）
            3. 不传 folder_token，访问根目录
        """
        # 从运行时上下文获取凭证
        credentials = self.runtime.credentials
        token = self._get_access_token(credentials)
        # 浏览路径优先级：用户当前路径 > Provider全局配置
        prefix = (request.prefix or credentials.get("default_folder_token", "")).strip()

        headers = self._build_auth_headers(token)

        # 统一的 API 路径，通过 folder_token 参数指定文件夹
        params = {"page_size": 50}

        # 如果 prefix 不为空，则作为 folder_token 参数
        if prefix:
            params["folder_token"] = prefix
        # 如果 prefix 为空，不传 folder_token 或传空字符串，API 会返回根目录

        if request.next_page_parameters:
            params["page_token"] = request.next_page_parameters.get("page_token", "")

        print(f"DEBUG: Browse Files Request URL: {self.FILES_LIST_URL}", file=sys.stderr)
        print(f"DEBUG: Browse Files Request Params: {params}", file=sys.stderr)
        print(f"DEBUG: Browse Files Request Headers: {headers}", file=sys.stderr)

        resp = requests.get(self.FILES_LIST_URL, headers=headers, params=params, timeout=30)

        print(f"DEBUG: Browse Files Response Status: {resp.status_code}", file=sys.stderr)
        print(f"DEBUG: Browse Files Response Headers: {dict(resp.headers)}", file=sys.stderr)
        print(f"DEBUG: Browse Files Response Body: {resp.text[:500]}", file=sys.stderr)  # 只打印前500字符

        # 如果是 404，可能是文件夹不存在，返回空列表而不是抛出异常
        if resp.status_code == 404:
            return OnlineDriveBrowseFilesResponse(
                result=[
                    OnlineDriveFileBucket(
                        files=[],
                        is_truncated=False,
                        next_page_parameters=None,
                    )
                ]
            )

        if resp.status_code != 200:
            try:
                error_msg = resp.json().get("msg", resp.text[:300])
            except ValueError:
                error_msg = resp.text[:300]
            raise ValueError(
                f"Failed to list files (HTTP {resp.status_code}): {error_msg}. "
                f"Please check: 1) App has required permissions; 2) Folder is shared with the app; 3) Folder token is valid."
            )

        data = resp.json()

        if data.get("code") != 0:
            error_msg = data.get("msg", "unknown error")
            raise ValueError(
                f"Failed to list files: {error_msg}. "
                f"Please check: 1) App has required permissions; 2) Folder is shared with the app; 3) Folder token is valid."
            )

        # 根据飞书 API 文档，响应结构是 data.files[]
        items = data.get("data", {}).get("files", [])
        files = []
        for item in items:
            file_type = item.get("type", "file")
            is_folder = file_type == "folder"

            # 获取文件大小，如果是文件夹则为 0
            size = item.get("size", 0) or 0

            # 处理快捷方式：使用目标文件的 token 和类型
            if file_type == "shortcut":
                shortcut_info = item.get("shortcut_info", {})
                file_token = shortcut_info.get("target_token", "")
                file_type = shortcut_info.get("target_type", "file")
                is_folder = file_type == "folder"
            else:
                file_token = item.get("token", "")

            # 将原始类型编码到 id 中，格式: token#type
            encoded_id = f"{file_token}#{file_type}" if not is_folder else file_token

            files.append(
                OnlineDriveFile(
                    id=encoded_id,
                    name=item.get("name", ""),
                    size=size,
                    type="folder" if is_folder else "file",
                )
            )

        is_truncated = data.get("data", {}).get("has_more", False)
        next_page_token = data.get("data", {}).get("next_page_token", "")
        next_page_params = {"page_token": next_page_token} if is_truncated and next_page_token else None

        bucket = OnlineDriveFileBucket(
            files=files,
            is_truncated=is_truncated,
            next_page_parameters=next_page_params,
        )

        return OnlineDriveBrowseFilesResponse(result=[bucket])

    def _download_file(self, request: OnlineDriveDownloadFileRequest) -> Generator[DatasourceMessage, None, None]:
        """根据文件类型选择对应的下载方式。"""
        # 从运行时上下文获取凭证
        credentials = self.runtime.credentials
        token = self._get_access_token(credentials)
        file_id = request.id

        # 解析 id：格式为 token#type 或单纯的 token（文件夹）
        if "#" in file_id:
            actual_token, file_type = file_id.rsplit("#", 1)
        else:
            actual_token = file_id
            file_type = "file"

        print(f"DEBUG: Download file_id={file_id}, actual_token={actual_token}, type={file_type}", file=sys.stderr)

        headers = self._build_auth_headers(token)

        # 获取原始文件名（从id中提取token作为文件名）
        original_name = actual_token

        # 根据文件类型选择下载方式
        if file_type in ("docx", "doc", "wiki"):
            # 飞书文档：使用导出任务导出为 docx
            yield from self._download_via_export(actual_token, file_type, "docx", headers, original_name)
        elif file_type == "sheet":
            # 电子表格：导出为 csv
            yield from self._download_via_export(actual_token, file_type, "csv", headers, original_name)
        elif file_type == "bitable":
            # 多维表格：导出为 xlsx（csv需要sub_id，xlsx不需要）
            yield from self._download_via_export(actual_token, file_type, "xlsx", headers, original_name)
        else:
            # 普通文件（PDF、图片等）：直接下载
            yield from self._download_raw_file(actual_token, headers, original_name)

    def _download_raw_file(self, token: str, headers: dict, filename: str) -> Generator[DatasourceMessage, None, None]:
        """下载普通文件（PDF、图片等）的原始二进制内容。"""
        download_url = self.FILE_DOWNLOAD_URL_TEMPLATE.format(token=token)
        resp = requests.get(download_url, headers=headers, timeout=60, allow_redirects=True)

        print(f"DEBUG: Raw file download URL: {download_url}, status: {resp.status_code}", file=sys.stderr)

        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            yield self.create_blob_message(
                resp.content,
                meta={"filename": filename, "mime_type": content_type}
            )
        else:
            raise ValueError(f"Failed to download file: {resp.status_code} - {resp.text[:200]}")

    def _guess_ext_from_content_type(self, content_type: str) -> str:
        """从Content-Type猜测文件扩展名"""
        import mimetypes
        ext = mimetypes.guess_extension(content_type)
        return ext if ext else ".bin"

    def _download_via_export(
        self, token: str, doc_type: str, file_extension: str, headers: dict, filename: str
    ) -> Generator[DatasourceMessage, None, None]:
        """通过导出任务下载飞书文档/表格。

        导出流程：
            1. 创建导出任务，获取 ticket
            2. 轮询查询导出任务状态，直到完成或失败
            3. 使用 file_token 下载导出后的文件
        """
        import time

        # 步骤一：创建导出任务
        export_payload = {
            "file_extension": file_extension,
            "token": token,
            "type": doc_type,
        }

        print(f"DEBUG: Creating export task: {export_payload}", file=sys.stderr)
        resp = requests.post(self.EXPORT_TASKS_URL, headers=headers, json=export_payload, timeout=30)

        print(f"DEBUG: Export create status: {resp.status_code}, body: {resp.text[:200]}", file=sys.stderr)

        if resp.status_code != 200:
            raise ValueError(f"Failed to create export task: {resp.status_code} - {resp.text[:200]}")

        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"Failed to create export task: {data.get('msg', '')}")

        ticket = data.get("data", {}).get("ticket")
        if not ticket:
            raise ValueError("Export task ticket not found in response")

        print(f"DEBUG: Export ticket: {ticket}", file=sys.stderr)

        # 步骤二：轮询查询导出任务结果
        result_url = self.EXPORT_QUERY_URL_TEMPLATE.format(ticket=ticket)
        file_token = None

        for attempt in range(30):  # 最多轮询30次
            result_resp = requests.get(result_url, headers=headers, params={"token": token}, timeout=30)

            print(f"DEBUG: Export query attempt {attempt + 1}, status: {result_resp.status_code}", file=sys.stderr)

            if result_resp.status_code == 200:
                result_data = result_resp.json()
                if result_data.get("code") == 0:
                    result_info = result_data.get("data", {}).get("result", {})
                    job_status = result_info.get("job_status")

                    print(f"DEBUG: Export job_status: {job_status}", file=sys.stderr)

                    if job_status == 0:  # 成功
                        file_token = result_info.get("file_token")
                        print(f"DEBUG: Export success, file_token: {file_token}", file=sys.stderr)
                        break
                    elif job_status in (1, 2):  # 初始化或处理中
                        time.sleep(1)
                        continue
                    else:  # 其他状态表示失败
                        error_msg = result_info.get("job_error_msg", "unknown error")
                        raise ValueError(f"Export task failed: job_status={job_status}, error={error_msg}")
                else:
                    raise ValueError(f"Export query failed: {result_data.get('msg', '')}")
            else:
                time.sleep(1)

        if not file_token:
            raise ValueError("Export task timed out or failed")

        # 步骤三：下载导出文件
        download_url = self.EXPORT_DOWNLOAD_URL_TEMPLATE.format(file_token=file_token)
        file_resp = requests.get(download_url, headers=headers, timeout=60)

        print(f"DEBUG: Export download status: {file_resp.status_code}", file=sys.stderr)

        if file_resp.status_code == 200:
            mime_type_map = {
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "csv": "text/csv",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            mime_type = mime_type_map.get(file_extension, "application/octet-stream")
            ext = f".{file_extension}"
            yield self.create_blob_message(
                file_resp.content,
                meta={"filename": f"{filename}.{file_extension}", "mime_type": mime_type}
            )
        else:
            raise ValueError(f"Failed to download exported file: {file_resp.status_code} - {file_resp.text[:200]}")
