1. 已經下載的 ID/URL 就不用下載
2. 先寫 DB 最後下載 covers/{id}.jpg 
3  下載前先檢查 covers/{id}.jpg，若是有就是已下載過，SKIP
4  get_missav_titles.py [--debug] [--count n] [--threads p] [id]  id 也是 OPTIONAL, 若是沒有指定，就是從 db random 選一個開始
