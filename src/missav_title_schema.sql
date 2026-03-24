CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    keywords TEXT, -- JSON array string, e.g. ["tag1","tag2"]
    cover TEXT
);

CREATE TABLE IF NOT EXISTS article_refs (
    from_article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
    to_article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
    PRIMARY KEY (from_article_id, to_article_id)
);

CREATE INDEX IF NOT EXISTS idx_refs_to ON article_refs(to_article_id);
