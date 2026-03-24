1. write get_missav_titles.py [--debug] [--count n] [--threads p] [id]

2. debug_missing_{id}.html 放在 debug/debug_missing_{id}.html
   有一個 DEBUG_FLAG --debug 可以快速切換，是不是要產生 debug html

3.  產生一個 SQLite missav_title db, 
-- 主表
CREATE TABLE articles (
    id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    keywords TEXT[], 
    cover VARCHAR(50)
);

-- 引用中間表 (自關聯多對多)
CREATE TABLE article_refs (
    from_article_id VARCHAR(50) REFERENCES articles(id) ON DELETE CASCADE,
    to_article_id VARCHAR(50) REFERENCES articles(id) ON DELETE CASCADE,
    PRIMARY KEY (from_article_id, to_article_id)
);

-- 建立索引以加速「誰引用了我」的查詢
CREATE INDEX idx_refs_to ON article_refs(to_article_id);

4. 由 id 開始 download 第一個 HTML，然後 將 
 <meta property="og:title" content="..."> => title
 <meta property="og:description" content="..."> => description
 <meta property="og:image" content="https://fourhoi.com/hunta-881/cover-n.jpg"> =>
 將影像 存在 covers/{id}.jpg (or .png)
 <meta name="keywords" content="平田司, たむらあゆむ, ..."> => split and keywords list

5. find https://fourhoi.com/{ref_id}/cover-t.jpg => from_article_id = {id}  to_article_id = {ref_id}

6. 用廣度優先，由 to_article_id 且還沒有DOWNLOAD 的找下一個 id html，goto 4 直到 --count n,  --count n (default 20) 

        
        