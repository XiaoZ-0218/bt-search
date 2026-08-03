"""bt_search.lang 的关键词拆解与简繁回退计划测试。"""

from __future__ import annotations

import unittest

from bt_search.lang import (
    build_search_plan,
    split_tokens,
    to_traditional,
    try_simplified,
    try_traditional,
)


class TestSplitTokens(unittest.TestCase):
    def test_split_on_space_and_punct(self):
        self.assertEqual(split_tokens("夜王 黄子华"), ["夜王", "黄子华"])
        self.assertEqual(split_tokens("a，b、c"), ["a", "b", "c"])

    def test_dedup_and_single_char_filter(self):
        self.assertEqual(split_tokens("甲甲 甲甲 乙乙"), ["甲甲", "乙乙"])
        # 单字中文与标点被过滤；单个 ASCII 字母/数字保留
        self.assertEqual(split_tokens("甲 乙"), [])
        self.assertEqual(split_tokens("x · y"), ["x", "y"])

    def test_empty(self):
        self.assertEqual(split_tokens(""), [])


class TestConversion(unittest.TestCase):
    def test_to_traditional(self):
        self.assertEqual(to_traditional("阿凡达"), "阿凡達")

    def test_try_traditional_none_for_english(self):
        self.assertIsNone(try_traditional("avatar"))

    def test_try_simplified_none_for_simplified(self):
        self.assertIsNone(try_simplified("阿凡达"))
        self.assertEqual(try_simplified("阿凡達"), "阿凡达")


class TestBuildSearchPlan(unittest.TestCase):
    def test_english_single_word_only_original(self):
        self.assertEqual(build_search_plan("avatar"), [("avatar", "原词")])

    def test_empty(self):
        self.assertEqual(build_search_plan(""), [])
        self.assertEqual(build_search_plan("   "), [])

    def test_plan_order_split_then_traditional(self):
        plan = build_search_plan("夜王 黄子华")
        queries = [q for q, _ in plan]
        self.assertEqual(queries[0], "夜王 黄子华")
        # 拆词紧跟原词
        self.assertIn("夜王", queries[1:3])
        self.assertIn("黄子华", queries[1:3])
        # 整句繁体 + 繁体拆词都在计划里
        self.assertIn(to_traditional("夜王 黄子华"), queries)
        self.assertIn(to_traditional("夜王"), queries)

    def test_no_duplicate_queries(self):
        plan = build_search_plan("阿凡达")
        queries = [q for q, _ in plan]
        self.assertEqual(len(queries), len(set(queries)))


if __name__ == "__main__":
    unittest.main()
