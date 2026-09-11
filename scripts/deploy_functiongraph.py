#!/usr/bin/env python3
"""通过华为云官方 SDK 将构建产物部署到 FunctionGraph。"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkfunctiongraph.v2 import (
    FuncCode,
    FunctionGraphClient,
    UpdateFunctionCodeRequest,
    UpdateFunctionCodeRequestBody,
)
from huaweicloudsdkfunctiongraph.v2.region.functiongraph_region import FunctionGraphRegion


REQUIRED_ENV = (
    "HUAWEICLOUD_ACCESS_KEY_ID",
    "HUAWEICLOUD_SECRET_ACCESS_KEY",
    "HUAWEICLOUD_PROJECT_ID",
    "HUAWEICLOUD_REGION",
    "FUNCTIONGRAPH_FUNCTION_URN",
)


def required_environment() -> dict[str, str]:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        raise SystemExit("缺少部署配置：" + ", ".join(missing))
    return {name: os.environ[name].strip() for name in REQUIRED_ENV}


def main() -> None:
    config = required_environment()
    package_path = Path(
        os.getenv("FUNCTIONGRAPH_PACKAGE", "build/ai-interviewer-functiongraph.zip")
    ).resolve()
    if not package_path.is_file():
        raise SystemExit(f"找不到部署包：{package_path}")

    # FunctionGraph 的 ZIP 直传接口上限为 40 MiB，提前失败比上传后报错更清楚。
    package_size = package_path.stat().st_size
    if package_size > 40 * 1024 * 1024:
        raise SystemExit(f"部署包超过 40 MiB：{package_size / 1024 / 1024:.1f} MiB")

    credentials = BasicCredentials(
        config["HUAWEICLOUD_ACCESS_KEY_ID"],
        config["HUAWEICLOUD_SECRET_ACCESS_KEY"],
        config["HUAWEICLOUD_PROJECT_ID"],
    )
    client = (
        FunctionGraphClient.new_builder()
        .with_credentials(credentials)
        .with_region(FunctionGraphRegion.value_of(config["HUAWEICLOUD_REGION"]))
        .build()
    )
    body = UpdateFunctionCodeRequestBody(
        code_type="zip",
        code_filename=package_path.name,
        func_code=FuncCode(
            file=base64.b64encode(package_path.read_bytes()).decode("ascii")
        ),
    )
    request = UpdateFunctionCodeRequest(
        function_urn=config["FUNCTIONGRAPH_FUNCTION_URN"], body=body
    )
    client.update_function_code(request)
    print(
        f"部署成功：{package_path.name}（{package_size / 1024 / 1024:.1f} MiB）"
    )


if __name__ == "__main__":
    main()
