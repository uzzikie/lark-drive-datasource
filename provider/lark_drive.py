from collections.abc import Mapping
from typing import Any
import requests

from dify_plugin.interfaces.datasource import DatasourceProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class LarkDriveProvider(DatasourceProvider):
    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        try:
            app_id = credentials.get("app_id")
            app_secret = credentials.get("app_secret")
            if not app_id or not app_secret:
                raise ValueError("App ID and App Secret are required")
            
            # 1. 获取 Access Token
            resp = requests.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                error_msg = data.get("msg", "unknown error")
                raise ValueError(
                    f"Failed to get access token: {error_msg}. "
                    f"Please verify your App ID and App Secret are correct."
                )
            
            token = data["tenant_access_token"]
            
            # 2. 尝试列出根目录，验证权限并获取可用文件夹
            headers = {"Authorization": f"Bearer {token}"}
            root_url = "https://open.larksuite.com/open-apis/drive/v1/files"
            root_params = {"page_size": 10}
            
            root_resp = requests.get(root_url, headers=headers, params=root_params, timeout=30)
            
            if root_resp.status_code == 200:
                root_data = root_resp.json()
                if root_data.get("code") == 0:
                    # 根据飞书 API 文档，响应结构是 data.files[]
                    items = root_data.get("data", {}).get("files", [])
                    if items:
                        # 返回成功信息，包含可用文件夹列表
                        folder_names = [item.get("name", "") for item in items[:5]]
                        print(f"✓ Successfully connected to Lark Drive. Found {len(items)} folders in root.", flush=True)
                        print(f"  Available folders: {', '.join(folder_names)}", flush=True)
                        return
            
            # 如果根目录访问失败，仍然认为凭证有效（可能只是没有根目录权限）
            print("✓ Credentials validated successfully (root directory access may be limited).", flush=True)
            
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
