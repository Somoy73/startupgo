import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from scraper import PublicPageFetcher, ScraperError


class Handler(BaseHTTPRequestHandler):
    FILES = {"/a.pdf": ("application/pdf", b"%PDF-1.7 fake"), "/page": ("text/html", b"<p>hi</p>")}

    def do_GET(self):
        content_type, body = self.FILES[self.path]
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetchFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_returns_the_content_type_and_bytes(self):
        self.assertEqual(PublicPageFetcher(delay=0).fetch_file(f"{self.base}/a.pdf"), ("application/pdf", b"%PDF-1.7 fake"))

    def test_refuses_html_and_files_over_the_size_limit(self):
        fetcher = PublicPageFetcher(delay=0)
        with self.assertRaisesRegex(ScraperError, "unsupported content type"):
            fetcher.fetch_file(f"{self.base}/page")
        with self.assertRaisesRegex(ScraperError, "larger than"):
            fetcher.fetch_file(f"{self.base}/a.pdf", max_bytes=5)


if __name__ == "__main__":
    unittest.main()
