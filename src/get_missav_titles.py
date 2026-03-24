#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
import sys
from collections import deque
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

REF_PATTERN = re.compile(r"https://fourhoi\.com/([^/\s\"'`<>]+)/cover-t\.jpg", re.IGNORECASE)


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        attr_map = {k.lower(): v for k, v in attrs if k and v}
        content = attr_map.get("content")
        if not content:
            return
        key = attr_map.get("property") or attr_map.get("name")
        if key:
            self.meta[key.lower()] = content


def normalize_id(value):
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        path = urlparse(value).path
        parts = [p for p in path.split("/") if p]
        if parts:
            return parts[-1]
    return value.strip()


def safe_id_for_filename(video_id):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", video_id)
    return safe or "unknown"


def fetch_text(url, timeout=30):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(content_type, errors="replace")


def fetch_bytes(url, timeout=30):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_text_with_playwright(url, timeout_ms=45000):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError(
            "Playwright is required for protected pages. Install with: uv pip install playwright playwright-stealth"
        ) from e

    stealth_cls = None
    try:
        from playwright_stealth import Stealth

        stealth_cls = Stealth
    except Exception:
        stealth_cls = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        if stealth_cls:
            stealth_cls().apply_stealth_sync(page)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            return page.content()
        finally:
            browser.close()


def fetch_page_html(url, fetch_mode):
    if fetch_mode == "http":
        return fetch_text(url)
    if fetch_mode == "playwright":
        return fetch_text_with_playwright(url)

    # auto mode:
    # - missav.ai is always protected, so go Playwright directly
    # - for other domains, try HTTP first then fallback to Playwright
    hostname = (urlparse(url).hostname or "").lower()
    if hostname == "missav.ai" or hostname.endswith(".missav.ai"):
        return fetch_text_with_playwright(url)

    try:
        return fetch_text(url)
    except HTTPError as e:
        if e.code in (401, 403, 429):
            print(f"[INFO] HTTP {e.code} for {url}, retrying with Playwright...")
            return fetch_text_with_playwright(url)
        raise
    except Exception:
        print(f"[INFO] HTTP fetch failed for {url}, retrying with Playwright...")
        return fetch_text_with_playwright(url)


def parse_page(html):
    parser = MetaParser()
    parser.feed(html)

    title = unescape(parser.meta.get("og:title", "")).strip()
    description = unescape(parser.meta.get("og:description", "")).strip()
    cover_url = unescape(parser.meta.get("og:image", "")).strip()
    keywords_raw = unescape(parser.meta.get("keywords", "")).strip()

    keywords = []
    if keywords_raw:
        keywords = [k.strip() for k in re.split(r"[,，]", keywords_raw) if k.strip()]

    refs = sorted(set(m.group(1).strip() for m in REF_PATTERN.finditer(html) if m.group(1).strip()))
    return title, description, cover_url, keywords, refs


def save_debug_html(base_dir, article_id, html):
    debug_dir = os.path.join(base_dir, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    safe_id = safe_id_for_filename(article_id)
    path = os.path.join(debug_dir, f"debug_missing_{safe_id}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def cover_filename(article_id):
    safe_id = safe_id_for_filename(article_id)
    return f"{safe_id}.jpg"


def cover_full_path(base_dir, article_id):
    covers_dir = os.path.join(base_dir, "covers")
    os.makedirs(covers_dir, exist_ok=True)
    return os.path.join(covers_dir, cover_filename(article_id))


def download_cover_jpg(base_dir, article_id, cover_url):
    if not cover_url:
        return None

    full_path = cover_full_path(base_dir, article_id)
    if os.path.exists(full_path):
        return cover_filename(article_id)

    try:
        data = fetch_bytes(cover_url)
        with open(full_path, "wb") as f:
            f.write(data)
        return cover_filename(article_id)
    except Exception as e:
        print(f"[WARN] Cover download failed for {article_id}: {e}")
        return None


def get_sqlite_db_path(base_dir):
    default_db_path = os.path.join(base_dir, "missav_title.db")
    return os.getenv("MISSAV_DB_PATH", default_db_path)


def connect_sqlite(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            keywords TEXT,
            cover TEXT
        );

        CREATE TABLE IF NOT EXISTS article_refs (
            from_article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
            to_article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
            PRIMARY KEY (from_article_id, to_article_id)
        );

        CREATE INDEX IF NOT EXISTS idx_refs_to ON article_refs(to_article_id);
        """
    )


def is_article_downloaded(conn, article_id):
    row = conn.execute(
        """
        SELECT 1
        FROM articles
        WHERE id = ?
          AND (
            description IS NOT NULL
            OR keywords IS NOT NULL
            OR (title IS NOT NULL AND title <> id)
          )
        LIMIT 1
        """,
        (article_id,),
    ).fetchone()
    return row is not None


def get_ref_ids(conn, from_id):
    rows = conn.execute(
        "SELECT to_article_id FROM article_refs WHERE from_article_id = ?",
        (from_id,),
    ).fetchall()
    return [r[0] for r in rows if r and r[0]]


def pick_random_seed(conn):
    # Prefer unresolved placeholder rows first, then any existing id.
    row = conn.execute(
        """
        SELECT id
        FROM articles
        WHERE description IS NULL
          AND keywords IS NULL
          AND (title = id OR title IS NULL)
        ORDER BY RANDOM()
        LIMIT 1
        """
    ).fetchone()
    if row:
        return row[0]

    row = conn.execute("SELECT id FROM articles ORDER BY RANDOM() LIMIT 1").fetchone()
    if row:
        return row[0]
    return None


def upsert_article(conn, article_id, title, description, keywords, cover):
    conn.execute(
        """
        INSERT INTO articles (id, title, description, keywords, cover)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE
        SET title = excluded.title,
            description = excluded.description,
            keywords = excluded.keywords,
            cover = excluded.cover
        """,
        (article_id, title, description, json.dumps(keywords, ensure_ascii=False), cover),
    )


def insert_refs(conn, from_id, to_ids):
    if not to_ids:
        return
    for to_id in to_ids:
        if to_id == from_id:
            continue
        conn.execute(
            """
            INSERT INTO articles (id, title)
            VALUES (?, ?)
            ON CONFLICT (id) DO NOTHING
            """,
            (to_id, to_id),
        )
        conn.execute(
            """
            INSERT INTO article_refs (from_article_id, to_article_id)
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
            """,
            (from_id, to_id),
        )


def crawl_single(seed_id, limit_count, debug_flag, fetch_mode):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = get_sqlite_db_path(base_dir)

    with connect_sqlite(db_path) as conn:
        ensure_schema(conn)
        print(f"[INFO] SQLite DB: {db_path}")

        queue = deque([seed_id])
        discovered = {seed_id}
        downloaded = 0
        skip_downloaded = 0

        while queue and downloaded < limit_count:
            article_id = queue.popleft()

            if is_article_downloaded(conn, article_id):
                skip_downloaded += 1
                refs_from_db = get_ref_ids(conn, article_id)
                for ref_id in refs_from_db:
                    if ref_id not in discovered:
                        discovered.add(ref_id)
                        queue.append(ref_id)
                print(f"[SKIP] Already downloaded: {article_id}")
                continue

            try:
                url = f"https://missav.ai/ja/{article_id}"
                print(f"[INFO] Fetching {url}")
                html = fetch_page_html(url, fetch_mode=fetch_mode)

                if debug_flag:
                    debug_path = save_debug_html(base_dir, article_id, html)
                    print(f"[DEBUG] Saved HTML: {debug_path}")

                title, description, cover_url, keywords, refs = parse_page(html)
                if not title:
                    title = article_id

                # 1) Write DB first
                planned_cover = cover_filename(article_id) if cover_url else None
                upsert_article(conn, article_id, title, description, keywords, planned_cover)
                insert_refs(conn, article_id, refs)
                conn.commit()

                # 2) Then download cover if not already downloaded
                if cover_url:
                    cover_path = cover_full_path(base_dir, article_id)
                    if os.path.exists(cover_path):
                        print(f"[SKIP] Cover exists: {cover_path}")
                    else:
                        saved_cover = download_cover_jpg(base_dir, article_id, cover_url)
                        if saved_cover:
                            print(f"[INFO] Cover saved: {saved_cover}")

                for ref_id in refs:
                    if ref_id not in discovered:
                        discovered.add(ref_id)
                        queue.append(ref_id)

                downloaded += 1
                print(
                    f"[INFO] Saved article={article_id}, refs={len(refs)}, "
                    f"progress={downloaded}/{limit_count}"
                )
            except Exception as e:
                print(f"[WARN] Failed {article_id}: {e}")

        print(f"[DONE] Downloaded {downloaded} article(s), skipped {skip_downloaded} already-downloaded.")


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Crawl MissAV metadata into SQLite."
    )
    parser.add_argument(
        "id",
        nargs="?",
        help="Seed video id or URL (optional). If omitted, pick one random id from DB.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Maximum number of new pages to download (default: 20)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save fetched HTML to debug/debug_missing_{id}.html",
    )
    parser.add_argument(
        "--fetch-mode",
        choices=["auto", "http", "playwright"],
        default="auto",
        help="Fetch engine: auto(default), http only, or playwright only",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = get_sqlite_db_path(base_dir)
    with connect_sqlite(db_path) as conn:
        ensure_schema(conn)
        seed_raw = args.id
        if not seed_raw:
            seed_raw = pick_random_seed(conn)
            if not seed_raw:
                print("[ERROR] No id provided and DB is empty. Please pass an id.")
                sys.exit(1)
            print(f"[INFO] Picked random seed from DB: {seed_raw}")

    seed_id = normalize_id(seed_raw)
    if not seed_id:
        print("[ERROR] Seed id is empty.")
        sys.exit(1)
    if args.count <= 0:
        print("[ERROR] --count must be > 0")
        sys.exit(1)

    crawl_single(
        seed_id=seed_id,
        limit_count=args.count,
        debug_flag=args.debug,
        fetch_mode=args.fetch_mode,
    )


if __name__ == "__main__":
    main()
