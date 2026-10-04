
from flask import Flask, jsonify, render_template, request
from engine import (
    initial_board, legal_moves, apply_move, undo_move, side_of,
    board_to_json, move_to_dict, BacktrackingAI, BFSAI, compute_hash,
    in_check, is_checkmate, is_stalemate, insufficient_material_draw,
    opponent, CHAR, RED, BLACK, MAX_SEARCH_DEPTH,
)

app = Flask(__name__)

MODE_HUMAN_VS_BT = "human_vs_bt"     # Người (Đỏ) đấu với Backtracking (Đen) — chế độ gốc
MODE_BT_VS_OTHER = "bt_vs_other"     # Backtracking (Đen) đấu với BFS (Đỏ) — tự chạy
MAX_GAME_PLIES = 200  # trần an toàn: nếu ván vượt quá số nước này mà chưa phân thắng bại
                       # (thường do 2 AI yếu ở tàn cuộc không còn nước tiến triển, chỉ đảo
                       # Tướng qua lại) thì tự động xử hòa thay vì chạy vô tận.

NO_PROGRESS_PLY_LIMIT = 120  # 60 nước mỗi bên không ăn quân -> hòa (tránh ván đấu vô tận)

def clamp_depth(depth):
    try:
        return max(1, min(int(depth), MAX_SEARCH_DEPTH))
    except (TypeError, ValueError):
        return 2

class Game:
    def __init__(self):
        self.reset(mode=MODE_HUMAN_VS_BT)

    def reset(self, mode=None):
        self.board = initial_board()
        self.turn = RED
        self.history = []
        self.last_move = None
        self.game_over = False
        self.mode = mode or getattr(self, "mode", MODE_HUMAN_VS_BT)
        self.message = (
            "Lượt của ĐỎ (bạn). Hãy chọn một quân."
            if self.mode == MODE_HUMAN_VS_BT
            else "Chế độ so sánh thuật toán: Backtracking (Đen) đấu với BFS (Đỏ)."
        )
        # Quân Đen LUÔN là AI Backtracking (giữ đúng bản chất bài toán trong mọi chế độ).
        self.ai = BacktrackingAI(2)
        # Quân Đỏ trong chế độ so sánh dùng thuật toán BFS (Tìm kiếm theo chiều rộng,
        # duyệt bằng hàng đợi, không cắt tỉa Alpha-Beta).
        self.other_ai = BFSAI(2)
        # Đếm số lần mỗi vị trí (Zobrist hash) đã xuất hiện trong ván -> chống Backtracking
        # đi lặp nước, và áp dụng luật hòa cờ khi lặp lại đúng một vị trí 3 lần.
        self.position_counts = {}
        self._record_position()
        # Đếm số nửa-nước (ply) liên tiếp KHÔNG ăn quân — nếu quá lâu không có tiến triển
        # (vd 2 AI cứ chạy Tướng qua lại dù một bên áp đảo nhưng chưa tìm ra kỹ thuật ăn hết
        # quân phòng thủ), tự động xử hòa thay vì để ván đấu kéo dài vô tận.
        self.plies_since_capture = 0
        # Nhật ký so sánh 2 thuật toán, dùng để vẽ biểu đồ so sánh (chế độ bt_vs_other).
        self.comparison_log = []

    def _record_position(self):
        h = compute_hash(self.board)
        self.position_counts[h] = self.position_counts.get(h, 0) + 1
        return self.position_counts[h]

    def state(self):
        legal = legal_moves(self.board, self.turn) if not self.game_over else []
        return {
            "board": board_to_json(self.board),
            "turn": self.turn,
            "lastMove": move_to_dict(self.last_move) if self.last_move else None,
            "gameOver": self.game_over,
            "message": self.message,
            "check": in_check(self.board, self.turn),
            "legalMovesCount": len(legal),
            "historyLength": len(self.history),
            "mode": self.mode,
            "redAlgorithm": "human" if self.mode == MODE_HUMAN_VS_BT else "bfs",
            "blackAlgorithm": "backtracking",
            "aiDepth": self.ai.depth,
            "aiSuperHard": self.ai.super_hard,
        }

    def finish_if_needed(self):
        side = self.turn
        if is_checkmate(self.board, side):
            winner = opponent(side)
            self.game_over = True
            self.message = f"Chiếu bí! {('ĐỎ' if winner == RED else 'ĐEN')} thắng."
            return True
        if is_stalemate(self.board, side):
            self.game_over = True
            self.message = "Hòa cờ (bế tắc)."
            return True
        if in_check(self.board, side):
            self.message = f"{'ĐỎ' if side == RED else 'ĐEN'} đang bị chiếu!"
        else:
            self.message = f"Lượt của {'ĐỎ (bạn)' if side == RED else 'ĐEN (AI)'}."
        return False

    def _after_move_common(self, captured=None):
        """Ghi lại vị trí mới + áp dụng luật hòa cờ khi lặp lại 1 vị trí 3 lần, hoặc khi
        quá lâu không có tiến triển (không ăn quân). Được gọi sau MỌI nước đi (người hoặc
        AI, ở mọi chế độ)."""
        if captured:
            self.plies_since_capture = 0
        else:
            self.plies_since_capture += 1
        repeat_count = self._record_position()
        ended = self.finish_if_needed()
        if not ended and repeat_count >= 3:
            self.game_over = True
            self.message = "Hòa cờ do lặp lại đúng một vị trí 3 lần (chống Backtracking đi lặp nước)."
        elif not ended and self.plies_since_capture >= NO_PROGRESS_PLY_LIMIT:
            self.game_over = True
            self.message = (
                f"Hòa cờ do {NO_PROGRESS_PLY_LIMIT // 2} nước liên tiếp không ăn quân "
                "(không có tiến triển)."
            )
        return repeat_count

    def play(self, move):
        if self.game_over:
            return False, "Ván đã kết thúc."
        if self.mode != MODE_HUMAN_VS_BT:
            return False, "Đang ở chế độ Backtracking đấu thuật toán khác — không nhận nước đi của người."
        legal = legal_moves(self.board, self.turn)
        if move not in legal:
            return False, "Nước đi không hợp lệ."
        captured = apply_move(self.board, move)
        self.history.append((move, captured))
        self.last_move = move
        self.turn = opponent(self.turn)
        self._after_move_common(captured)
        return True, self.message

    def ai_move(self, depth=2):
        if self.game_over:
            return False, "Ván đã kết thúc."
        if self.turn != BLACK:
            return False, "Chưa đến lượt AI."
        self.ai.set_depth(depth)
        move, score, nodes = self.ai.choose_move(self.board, BLACK, position_counts=self.position_counts)
        if move is None:
            self.finish_if_needed()
            return False, self.message
        captured = apply_move(self.board, move)
        self.history.append((move, captured))
        self.last_move = move
        self.turn = RED
        self._after_move_common(captured)
        return True, self.message, captured

    def ai_vs_ai_step(self, depth=2):
        """Thực hiện đúng 1 nước trong chế độ so sánh thuật toán: Đen luôn dùng
        Backtracking, Đỏ luôn dùng BFS (Tìm kiếm theo chiều rộng). Trả về thông tin chi tiết của
        nước vừa đi để ghi vào comparison_log / vẽ biểu đồ."""
        if self.mode != MODE_BT_VS_OTHER:
            return False, "Chỉ dùng được trong chế độ Backtracking vs Thuật toán khác.", None
        if self.game_over:
            return False, "Ván đã kết thúc.", None

        side = self.turn
        if side == BLACK:
            self.ai.set_depth(depth)
            move, score, nodes = self.ai.choose_move(self.board, BLACK, position_counts=self.position_counts)
            algo, stats = "backtracking", dict(self.ai.last_stats)
        else:
            self.other_ai.set_depth(depth)  # BFS tự kẹp về tối đa MAX_BFS_DEPTH (2) để tránh bùng nổ tổ hợp
            move, score, nodes = self.other_ai.choose_move(self.board, RED, position_counts=self.position_counts)
            algo, stats = "bfs", dict(self.other_ai.last_stats)

        if move is None:
            self.finish_if_needed()
            return False, self.message, None

        captured = apply_move(self.board, move)
        self.history.append((move, captured))
        self.last_move = move
        self.turn = opponent(side)
        self._after_move_common(captured)

        entry = {
            "moveNumber": len(self.history),
            "side": side,
            "algorithm": algo,
            "move": move_to_dict(move),
            "capturedPiece": CHAR.get(captured, captured) if captured else None,
            "score": score,
            "nodes": nodes,
            "timeMs": stats.get("time_ms"),
            "depth": stats.get("depth"),
            "mateIn": stats.get("mate_in"),
            "peakMemoryKb": stats.get("peak_memory_kb"),
        }
        self.comparison_log.append(entry)
        return True, self.message, entry

game = Game()

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/state")
def state():
    return jsonify(game.state())

@app.post("/api/reset")
def reset():
    game.reset()
    return jsonify(game.state())

@app.post("/api/mode")
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", MODE_HUMAN_VS_BT)
    if mode not in (MODE_HUMAN_VS_BT, MODE_BT_VS_OTHER):
        return jsonify({"ok": False, "message": "Chế độ không hợp lệ."}), 400
    game.reset(mode=mode)
    return jsonify({"ok": True, "state": game.state()})

@app.get("/api/moves/<int:r>/<int:c>")
def moves(r, c):
    if not (0 <= r < 10 and 0 <= c < 9):
        return jsonify({"moves": []}), 400
    if game.mode != MODE_HUMAN_VS_BT:
        return jsonify({"moves": []})
    piece = game.board[r][c]
    if side_of(piece) != game.turn or game.game_over:
        return jsonify({"moves": []})
    legal = legal_moves(game.board, game.turn)
    selected = [{"to": [m[2], m[3]], "move": move_to_dict(m)} for m in legal if m[0] == r and m[1] == c]
    return jsonify({"moves": selected})

@app.post("/api/move")
def player_move():
    data = request.get_json(force=True) or {}
    f = data.get("from")
    t = data.get("to")
    depth = data.get("depth", 2)
    if not (isinstance(f, list) and isinstance(t, list) and len(f) == 2 and len(t) == 2):
        return jsonify({"ok": False, "message": "Dữ liệu nước đi không hợp lệ."}), 400
    try:
        move = (int(f[0]), int(f[1]), int(t[0]), int(t[1]))
        depth = clamp_depth(depth)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Tọa độ hoặc độ sâu AI không hợp lệ."}), 400

    ok, message = game.play(move)
    if not ok:
        return jsonify({"ok": False, "message": message, "state": game.state()})

    # Quan trọng: AI được gọi NGAY TRÊN SERVER sau nước đi của Đỏ.
    # Vì vậy trạng thái trả về cho trình duyệt đã bao gồm cả nước AI.
    ai_info = None
    if not game.game_over and game.turn == BLACK:
        ai_ok, ai_message, captured = game.ai_move(depth)
        if ai_ok and game.last_move:
            ai_info = {
                "move": move_to_dict(game.last_move),
                "capturedPiece": CHAR.get(captured, captured) if captured else None,
                "depth": game.ai.last_stats.get("depth", game.ai.depth),
                "nodes": game.ai.nodes,
                "timeMs": game.ai.last_stats.get("time_ms"),
                "mateIn": game.ai.last_stats.get("mate_in"),
                "peakMemoryKb": game.ai.last_stats.get("peak_memory_kb"),
                "superHard": game.ai.super_hard,
            }
        elif not ai_ok:
            ai_info = {"error": ai_message, "depth": game.ai.depth, "nodes": game.ai.nodes}

    return jsonify({
        "ok": True,
        "message": game.message,
        "state": game.state(),
        "ai": ai_info,
    })

@app.get("/api/ai/search-log")
def ai_search_log():
    return jsonify({
        "depth": game.ai.depth,
        "nodes": game.ai.nodes,
        "moves": game.ai.search_log,
        "stats": game.ai.last_stats,
    })

@app.post("/api/ai")
def ai_move():
    data = request.get_json(silent=True) or {}
    depth = clamp_depth(data.get("depth", 2))
    result = game.ai_move(depth)
    ok, message, captured = result if len(result) == 3 else (*result, None)
    captured_char = CHAR.get(captured, captured) if captured else None
    return jsonify({
        "ok": ok, "message": message, "state": game.state(),
        "depth": game.ai.last_stats.get("depth", game.ai.depth), "nodes": game.ai.nodes,
        "capturedPiece": captured_char,
        "timeMs": game.ai.last_stats.get("time_ms"),
        "mateIn": game.ai.last_stats.get("mate_in"),
        "peakMemoryKb": game.ai.last_stats.get("peak_memory_kb"),
        "superHard": game.ai.super_hard,
    })

@app.post("/api/ai-vs-ai/step")
def ai_vs_ai_step():
    data = request.get_json(silent=True) or {}
    depth = clamp_depth(data.get("depth", 2))
    ok, message, entry = game.ai_vs_ai_step(depth)
    return jsonify({"ok": ok, "message": message, "state": game.state(), "entry": entry})

@app.post("/api/ai-vs-ai/run")
def ai_vs_ai_run():
    """Tự động chạy nhiều nước liên tiếp trong chế độ so sánh thuật toán, trả về toàn bộ
    nhật ký để vẽ biểu đồ so sánh. Giới hạn số nước để tránh treo server khi độ sâu lớn."""
    data = request.get_json(silent=True) or {}
    depth = clamp_depth(data.get("depth", 2))
    max_moves = max(1, min(int(data.get("maxMoves", 12)), 40))
    entries = []
    for _ in range(max_moves):
        if game.game_over:
            break
        ok, message, entry = game.ai_vs_ai_step(depth)
        if not ok:
            break
        entries.append(entry)
    return jsonify({
        "ok": True, "state": game.state(),
        "entries": entries, "comparisonLog": game.comparison_log,
    })

@app.get("/api/comparison")
def comparison():
    return jsonify({"comparisonLog": game.comparison_log, "mode": game.mode})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
