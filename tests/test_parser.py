"""Tests for imageporter.core.parser module."""

from __future__ import annotations

import unittest

from imageporter.core.parser import (
    dedup_keep_order,
    normalize_image_identity,
    parse_multiline_images,
    validate_image_name,
)


class TestParseMultilineImages(unittest.TestCase):
    def test_basic(self):
        raw = "nginx\nredis\npostgres"
        self.assertEqual(parse_multiline_images(raw), ["nginx", "redis", "postgres"])

    def test_strips_whitespace(self):
        self.assertEqual(parse_multiline_images("  nginx  \n  redis  "), ["nginx", "redis"])

    def test_skips_empty_lines(self):
        self.assertEqual(parse_multiline_images("nginx\n\n\nredis\n\n"), ["nginx", "redis"])

    def test_skips_comment_lines(self):
        raw = "# comment\nnginx\n# another\nredis"
        self.assertEqual(parse_multiline_images(raw), ["nginx", "redis"])

    def test_strips_inline_comments(self):
        raw = "nginx:latest # web server\nredis:7 # cache"
        self.assertEqual(parse_multiline_images(raw), ["nginx:latest", "redis:7"])

    def test_empty_input(self):
        self.assertEqual(parse_multiline_images(""), [])

    def test_only_comments(self):
        self.assertEqual(parse_multiline_images("# a\n# b\n"), [])

    def test_complex_image_names(self):
        raw = "ghcr.io/owner/repo:v1.2.3\nregistry.example.com:5000/app:latest"
        self.assertEqual(
            parse_multiline_images(raw),
            ["ghcr.io/owner/repo:v1.2.3", "registry.example.com:5000/app:latest"],
        )


class TestDedupKeepOrder(unittest.TestCase):
    def test_no_duplicates(self):
        self.assertEqual(dedup_keep_order(["a", "b", "c"]), ["a", "b", "c"])

    def test_removes_duplicates_keeps_first(self):
        self.assertEqual(dedup_keep_order(["a", "b", "a", "c", "b"]), ["a", "b", "c"])

    def test_empty(self):
        self.assertEqual(dedup_keep_order([]), [])

    def test_all_same(self):
        self.assertEqual(dedup_keep_order(["x", "x", "x"]), ["x"])

    def test_preserves_order(self):
        items = ["nginx", "redis", "nginx", "postgres", "redis", "mysql"]
        self.assertEqual(dedup_keep_order(items), ["nginx", "redis", "postgres", "mysql"])


class TestValidateImageName(unittest.TestCase):
    def _assert_valid(self, image: str):
        ok, msg = validate_image_name(image)
        self.assertTrue(ok, f"{image!r} should be valid, got: {msg}")

    def _assert_invalid(self, image: str):
        ok, _ = validate_image_name(image)
        self.assertFalse(ok, f"{image!r} should be invalid")

    def test_valid_simple(self):
        for img in ["nginx", "nginx:latest", "nginx:1.25", "ubuntu", "python:3.12-slim"]:
            self._assert_valid(img)

    def test_valid_with_registry(self):
        for img in [
            "ghcr.io/owner/repo",
            "ghcr.io/owner/repo:v1.2.3",
            "registry.example.com:5000/app:latest",
            "mcr.microsoft.com/dotnet/sdk:8.0",
        ]:
            self._assert_valid(img)

    def test_empty(self):
        ok, msg = validate_image_name("")
        self.assertFalse(ok)
        self.assertIn("为空", msg)

    def test_contains_space(self):
        ok, msg = validate_image_name("nginx latest")
        self.assertFalse(ok)
        self.assertIn("空格", msg)

    def test_too_long(self):
        ok, msg = validate_image_name("a" * 257)
        self.assertFalse(ok)
        self.assertIn("过长", msg)

    def test_invalid_formats(self):
        for img in ["NGINX", "nginx::latest", ":latest"]:
            self._assert_invalid(img)

    def test_whitespace_stripped(self):
        ok, _ = validate_image_name("  nginx  ")
        self.assertTrue(ok)


class TestNormalizeImageIdentity(unittest.TestCase):
    def test_equivalent_official_images(self):
        """H-1：官方镜像的各种简写应规范化为同一身份。"""
        base = "docker.io/library/nginx:latest"
        for img in ("nginx", "nginx:latest", "library/nginx", "docker.io/nginx", "NGINX"):
            self.assertEqual(normalize_image_identity(img), base, img)

    def test_namespace_images(self):
        base = "docker.io/user/app:latest"
        for img in ("user/app", "user/app:latest"):
            self.assertEqual(normalize_image_identity(img), base)

    def test_explicit_registry_preserved(self):
        cases = {
            "ghcr.io/owner/repo": "ghcr.io/owner/repo:latest",
            "ghcr.io/owner/repo:v1": "ghcr.io/owner/repo:v1",
            "registry.example.com:5000/app:latest": "registry.example.com:5000/app:latest",
            "localhost/app": "localhost/app:latest",
            "localhost:5000/app": "localhost:5000/app:latest",
        }
        for img, expected in cases.items():
            self.assertEqual(normalize_image_identity(img), expected, img)

    def test_tags_preserved(self):
        self.assertEqual(normalize_image_identity("nginx:1.25"), "docker.io/library/nginx:1.25")
        self.assertEqual(normalize_image_identity("ubuntu:22.04"), "docker.io/library/ubuntu:22.04")

    def test_digest_references(self):
        digest = "sha256:" + "a" * 64
        self.assertEqual(normalize_image_identity(f"nginx@{digest}"), f"docker.io/library/nginx@{digest}")
        self.assertNotIn(":latest@", normalize_image_identity(f"nginx@{digest}"))

    def test_tagged_digest_preserved(self):
        digest = "sha256:" + "b" * 64
        self.assertEqual(
            normalize_image_identity(f"nginx:1.25@{digest}"),
            f"docker.io/library/nginx:1.25@{digest}",
        )

    def test_empty(self):
        self.assertEqual(normalize_image_identity(""), "")
        self.assertEqual(normalize_image_identity("  "), "")

    def test_lowercased(self):
        self.assertEqual(normalize_image_identity("GHCr.io/Owner/Repo"), "ghcr.io/owner/repo:latest")


if __name__ == "__main__":
    unittest.main()
