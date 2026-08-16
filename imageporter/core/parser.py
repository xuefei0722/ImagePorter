"""
Parser and validator functions for Docker image handling.
"""

from __future__ import annotations

import re

_IMAGE_NAME_RE = re.compile(
    r'^(?:(?P<registry>[a-zA-Z0-9][\w.\-]*(?::\d+)?)/)?'
    r'(?P<name>[a-z0-9]+(?:[._/\-][a-z0-9]+)*)'
    r'(?::(?P<tag>[\w][\w.\-]{0,127}))?'
    r'(?:@(?P<digest>sha256:[a-fA-F0-9]{64}))?$'
)

_DEFAULT_REGISTRY = "docker.io"
_OFFICIAL_NAMESPACE = "library"
_DEFAULT_TAG = "latest"


def parse_multiline_images(raw_text: str) -> list[str]:
    images = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if line:
            images.append(line)
    return images


def dedup_keep_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def validate_image_name(image: str) -> tuple[bool, str]:
    """验证 Docker 镜像名称格式。"""
    if not image:
        return False, "为空"
    image = image.strip()
    if " " in image:
        return False, "包含空格"
    if len(image) > 256:
        return False, "名称过长 (>256 字符)"
    if not _IMAGE_NAME_RE.match(image):
        return False, "格式不符合 Docker 镜像命名规范"
    return True, ""


def normalize_image_identity(image: str) -> str:
    """返回镜像的规范化身份，用于等价去重。

    规则：统一小写；补全隐式 registry（docker.io）与官方镜像命名空间
    （library）；无 tag 且无 digest 时补默认 :latest。

    等价示例：nginx ≡ nginx:latest ≡ library/nginx ≡ docker.io/nginx
    → docker.io/library/nginx:latest
    """
    s = image.strip().lower()
    if not s:
        return s

    if "@" in s:
        base, digest = s.split("@", 1)
        suffix = f"@{digest}"
    else:
        base, suffix = s, ""

    head, sep, rest = base.partition("/")
    is_registry = bool(sep) and ("." in head or ":" in head or head == "localhost")
    if not sep:
        base = f"{_DEFAULT_REGISTRY}/{_OFFICIAL_NAMESPACE}/{head}"
    elif not is_registry:
        base = f"{_DEFAULT_REGISTRY}/{base}"
    elif head == _DEFAULT_REGISTRY and rest.count("/") == 0:
        # docker.io/nginx 与 nginx 指向同一官方镜像，统一补 library 命名空间
        base = f"{head}/{_OFFICIAL_NAMESPACE}/{rest}"

    if not suffix and ":" not in base.rsplit("/", 1)[-1]:
        base = f"{base}:{_DEFAULT_TAG}"
    return base + suffix
