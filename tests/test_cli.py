"""bt_search.cli 的纯逻辑测试：parse_indices 与输出函数。"""

from __future__ import annotations

import io
import unittest

from bt_search.cli import parse_indices, print_download_links_batch, print_resource_table
from bt_search.scraper import DownloadLink, ResourceItem


class TestParseIndices(unittest.TestCase):
    def test_single_and_list(self):
        self.assertEqual(parse_indices("1", 10), [1])
        self.assertEqual(parse_indices("1,3", 10), [1, 3])

    def test_ranges(self):
        self.assertEqual(parse_indices("1-3", 10), [1, 2, 3])
        self.assertEqual(parse_indices("1,3-5,7", 10), [1, 3, 4, 5, 7])
        # 反向区间自动交换
        self.assertEqual(parse_indices("3-1", 10), [1, 2, 3])

    def test_all(self):
        self.assertEqual(parse_indices("all", 3), [1, 2, 3])
        self.assertEqual(parse_indices("ALL", 2), [1, 2])

    def test_quit_and_empty(self):
        for raw in ("", "q", "quit", "exit"):
            self.assertEqual(parse_indices(raw, 10), [], raw)

    def test_invalid_returns_empty(self):
        self.assertEqual(parse_indices("abc", 10), [])
        self.assertEqual(parse_indices("1,a", 10), [])

    def test_out_of_range_and_duplicates(self):
        self.assertEqual(parse_indices("0,11", 10), [])
        self.assertEqual(parse_indices("2,2,2-3", 10), [2, 3])


class TestPrintDownloadLinksBatch(unittest.TestCase):
    def test_magnet_only_goes_to_stdout(self):
        pairs = [
            (DownloadLink(tdown_id="1", magnet="magnet:?xt=urn:btih:aaa"),
             ResourceItem(tdown_id="1", title="有磁力的")),
            (DownloadLink(tdown_id="2"),
             ResourceItem(tdown_id="2", title="没磁力的")),
        ]
        out, err = io.StringIO(), io.StringIO()
        print_download_links_batch(pairs, True, file=out, err=err)
        self.assertEqual(out.getvalue().strip(), "magnet:?xt=urn:btih:aaa")
        self.assertIn("没磁力的", err.getvalue())

    def test_full_output_includes_thunder_and_extras(self):
        link = DownloadLink(
            tdown_id="1",
            magnet="magnet:?xt=urn:btih:aaa",
            thunder="/dlt/1.html",
            extras=["https://pan.example.com/x"],
        )
        out = io.StringIO()
        print_download_links_batch([(link, ResourceItem(tdown_id="1", title="t"))],
                                   False, file=out, err=io.StringIO())
        text = out.getvalue()
        self.assertIn("magnet:?xt=urn:btih:aaa", text)
        self.assertIn("/dlt/1.html", text)
        self.assertIn("https://pan.example.com/x", text)


class TestPrintResourceTable(unittest.TestCase):
    def test_rows_have_index_title_size_downloads(self):
        resources = [
            ResourceItem(tdown_id="1", title="版本甲", size="8GB", downloads="100"),
            ResourceItem(tdown_id="2", title="版本乙"),
        ]
        out = io.StringIO()
        print_resource_table(resources, file=out)
        text = out.getvalue()
        self.assertIn("[1]", text)
        self.assertIn("版本甲", text)
        self.assertIn("8GB", text)
        self.assertIn("[2]", text)
        # 缺失字段用 "-" 占位
        self.assertIn("-", text)


if __name__ == "__main__":
    unittest.main()
