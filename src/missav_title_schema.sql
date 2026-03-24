CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    cover TEXT,
    dislike INTEGER NOT NULL DEFAULT 0
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
