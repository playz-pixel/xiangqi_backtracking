
# Cờ Tướng bằng Backtracking — Python + Flask + SVG

Bài tập lớn môn Trí tuệ nhân tạo: chương trình mô phỏng cờ tướng, người chơi Đỏ đấu với AI Đen.

## 1. Công nghệ

- Python 3.10+
- Flask
- HTML/CSS/JavaScript
- SVG để vẽ bàn cờ và quân cờ
- AI: Backtracking đệ quy theo Minimax + Alpha-Beta pruning
- Luật: xe, mã, tượng, sĩ, tướng, pháo, tốt; kiểm tra chiếu, chiếu bí, bế tắc.

## 2. Cấu trúc thư mục

```text
xiangqi_backtracking_project/
├── app.py
├── engine.py
├── requirements.txt
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── app.js
    └── style.css
```

## 3. Chạy bằng VS Code

Mở thư mục dự án trong VS Code.

### Windows

Mở Terminal trong VS Code:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Nếu máy dùng `py`:

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

Sau đó mở trình duyệt:

```text
http://127.0.0.1:5000
```

## 4. Cách chơi

- Người chơi là quân Đỏ.
- Click quân Đỏ.
- Các chấm vàng là các nước đi hợp lệ.
- Click chấm đích.
- Sau khi người chơi đi, AI Đen tự động tìm nước và đi.
- Có thể nhấn `AI đi` để yêu cầu AI suy nghĩ.
- Chọn độ sâu 1–4:
  - 1: rất nhanh, yếu.
  - 2: cân bằng, phù hợp demo.
  - 3: mạnh hơn nhưng chậm hơn.
  - 4: nhiều nút hơn, có thể mất thời gian.

## 5. Ý tưởng Backtracking

AI sử dụng cây tìm kiếm:

```text
Nút hiện tại
 ├── Nước 1
 │    ├── Đối thủ trả lời 1
 │    └── Đối thủ trả lời 2
 ├── Nước 2
 │    ├── Đối thủ trả lời 1
 │    └── Đối thủ trả lời 2
 └── ...
```

Mỗi lần thử một nước:

1. Lưu quân bị ăn.
2. Thực hiện nước đi.
3. Gọi đệ quy `_search(...)`.
4. Đánh giá trạng thái.
5. Hoàn tác nước đi (`undo_move`).
6. Chọn Min/Max.

Đây chính là cơ chế Backtracking: **đi thử → đi sâu → đánh giá → quay lui → thử nhánh khác**.

Alpha-Beta pruning giúp bỏ các nhánh chắc chắn không thể cải thiện kết quả.


## 6. Kiến trúc chương trình

```text
Browser
   │
   ├── SVG Board
   ├── Click quân cờ
   └── API fetch()
          │
          ▼
       Flask
          │
          ▼
      engine.py
          │
          ├── Sinh nước đi
          ├── Kiểm tra luật
          ├── Chiếu / chiếu bí
          └── Backtracking AI
```