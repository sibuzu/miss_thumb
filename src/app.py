import argparse
from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for
import math
import os
import sqlite3


app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COVERS_DIR = os.path.join(BASE_DIR, "covers")
DB_PATH = os.getenv("MISSAV_DB_PATH", os.path.join(BASE_DIR, "missav_title.db"))
PER_PAGE = 24

DOWNLOADED_WHERE = """
(
    a.description IS NOT NULL
    OR EXISTS (SELECT 1 FROM article_tags at WHERE at.article_id = a.id)
    OR (a.title IS NOT NULL AND a.title <> a.id)
)
"""


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            cover TEXT
        );

        CREATE TABLE IF NOT EXISTS article_refs (
            from_article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
            to_article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
            PRIMARY KEY (from_article_id, to_article_id)
        );

        CREATE INDEX IF NOT EXISTS idx_refs_to ON article_refs(to_article_id);

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS article_tags (
            article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (article_id, tag_id)
        );

        CREATE INDEX IF NOT EXISTS idx_article_tags_article ON article_tags(article_id);
        CREATE INDEX IF NOT EXISTS idx_article_tags_tag ON article_tags(tag_id);
        """
    )
    cols = conn.execute("PRAGMA table_info(articles)").fetchall()
    col_names = {c["name"] for c in cols}
    if "dislike" not in col_names:
        conn.execute("ALTER TABLE articles ADD COLUMN dislike INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def allow_dislike():
    return bool(app.config.get("SHOW_DISLIKE", False))


def cover_src(filename):
    if not filename:
        return None
    full_path = os.path.join(COVERS_DIR, filename)
    if not os.path.exists(full_path):
        return None
    return url_for("cover_file", filename=filename)


def normalize_article_row(row):
    item = dict(row)
    item["keywords_list"] = item.get("keywords_list", [])
    item["cover_url"] = cover_src(item.get("cover"))
    item["dislike"] = bool(item.get("dislike", 0))
    return item


@app.route("/covers/<path:filename>")
def cover_file(filename):
    return send_from_directory(COVERS_DIR, filename)


@app.route("/")
def index():
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    page = max(page, 1)
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()

    with get_db_connection() as conn:
        ensure_schema(conn)
        where_clauses = [DOWNLOADED_WHERE]
        params = []

        if not allow_dislike():
            where_clauses.append("COALESCE(a.dislike, 0) = 0")

        if q:
            like_q = f"%{q}%"
            where_clauses.append(
                """
                (
                    a.id LIKE ? COLLATE NOCASE
                    OR a.description LIKE ? COLLATE NOCASE
                    OR EXISTS (
                        SELECT 1
                        FROM article_tags at
                        JOIN tags t ON t.id = at.tag_id
                        WHERE at.article_id = a.id
                          AND t.name LIKE ? COLLATE NOCASE
                    )
                )
                """
            )
            params.extend([like_q, like_q, like_q])

        if tag:
            where_clauses.append(
                """
                EXISTS (
                    SELECT 1
                    FROM article_tags at
                    JOIN tags t ON t.id = at.tag_id
                    WHERE at.article_id = a.id
                      AND t.name = ? COLLATE NOCASE
                )
                """
            )
            params.append(tag)

        where_sql = " AND ".join(f"({w})" for w in where_clauses)

        count_row = conn.execute(
            f"SELECT COUNT(*) AS total FROM articles a WHERE {where_sql}",
            params,
        ).fetchone()
        total_items = int(count_row["total"] if count_row else 0)
        total_pages = max(1, math.ceil(total_items / PER_PAGE))

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * PER_PAGE
        rows = conn.execute(
            f"""
            SELECT a.id, a.title, a.cover, COALESCE(a.dislike, 0) AS dislike
            FROM articles a
            WHERE {where_sql}
            ORDER BY a.id COLLATE NOCASE ASC
            LIMIT ? OFFSET ?
            """,
            [*params, PER_PAGE, offset],
        ).fetchall()

        tag_where = [DOWNLOADED_WHERE]
        tag_params = []
        if not allow_dislike():
            tag_where.append("COALESCE(a.dislike, 0) = 0")
        tag_where_sql = " AND ".join(f"({w})" for w in tag_where)
        tag_rows = conn.execute(
            f"""
            SELECT t.name, COUNT(*) AS cnt
            FROM tags t
            JOIN article_tags at ON at.tag_id = t.id
            JOIN articles a ON a.id = at.article_id
            WHERE {tag_where_sql}
            GROUP BY t.id, t.name
            ORDER BY cnt DESC, t.name COLLATE NOCASE ASC
            """,
            tag_params,
        ).fetchall()

    articles = [normalize_article_row(r) for r in rows]
    hot_tags = [{"name": r["name"], "count": int(r["cnt"])} for r in tag_rows]

    return render_template(
        "index.html",
        articles=articles,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        q=q,
        active_tag=tag,
        hot_tags=hot_tags,
    )


@app.route("/article/<article_id>")
def article_detail(article_id):
    with get_db_connection() as conn:
        ensure_schema(conn)
        article_row = conn.execute(
            """
            SELECT id, title, description, cover, COALESCE(dislike, 0) AS dislike
            FROM articles
            WHERE id = ?
            """,
            (article_id,),
        ).fetchone()
        if not article_row:
            abort(404)
        if bool(article_row["dislike"]) and not allow_dislike():
            abort(404)

        ref_dislike_filter = "" if allow_dislike() else " AND COALESCE(a.dislike, 0) = 0 "
        refs_rows = conn.execute(
            """
            SELECT
                a.id,
                a.title,
                a.cover,
                COALESCE(a.dislike, 0) AS dislike,
                CASE WHEN (
                    a.description IS NOT NULL
                    OR EXISTS (SELECT 1 FROM article_tags at WHERE at.article_id = a.id)
                    OR (a.title IS NOT NULL AND a.title <> a.id)
                ) THEN 1 ELSE 0 END AS is_downloaded
            FROM article_refs r
            JOIN articles a ON a.id = r.to_article_id
            WHERE r.from_article_id = ? {ref_dislike_filter}
            ORDER BY is_downloaded DESC, a.id COLLATE NOCASE ASC
            """.replace("{ref_dislike_filter}", ref_dislike_filter),
            (article_id,),
        ).fetchall()

        keyword_rows = conn.execute(
            """
            SELECT t.name
            FROM article_tags at
            JOIN tags t ON t.id = at.tag_id
            WHERE at.article_id = ?
            ORDER BY t.name COLLATE NOCASE ASC
            """,
            (article_id,),
        ).fetchall()

    article = normalize_article_row(article_row)
    article["keywords_list"] = [r["name"] for r in keyword_rows]
    refs = [normalize_article_row(r) for r in refs_rows]

    return render_template("article.html", article=article, refs=refs, show_dislike=allow_dislike())


@app.post("/article/<article_id>/dislike")
def set_article_dislike(article_id):
    dislike = 1 if request.form.get("dislike") == "on" else 0
    with get_db_connection() as conn:
        ensure_schema(conn)
        exists = conn.execute("SELECT 1 FROM articles WHERE id = ?", (article_id,)).fetchone()
        if not exists:
            abort(404)
        conn.execute("UPDATE articles SET dislike = ? WHERE id = ?", (dislike, article_id))
        conn.commit()
    if dislike and not allow_dislike():
        return redirect(url_for("index"))
    return redirect(url_for("article_detail", article_id=article_id))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MissAV library web app.")
    parser.add_argument(
        "--dislike",
        action="store_true",
        help="Show disliked articles in list/ref pages.",
    )
    args = parser.parse_args()
    app.config["SHOW_DISLIKE"] = bool(args.dislike)
    print("Starting server at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
