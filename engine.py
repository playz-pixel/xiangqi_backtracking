
from dataclasses import dataclass
from typing import List, Tuple, Optional
from collections import deque
import math
import random
import time

ROWS, COLS = 10, 9
RED, BLACK = "red", "black"

# Điểm ngưỡng để nhận biết một giá trị trả về là "chiếu bí bắt buộc" (forced mate),
# phân biệt với điểm đánh giá vật chất/vị trí bình thường (luôn nhỏ hơn nhiều).
MATE_THRESHOLD = 900000
MAX_SEARCH_DEPTH = 5  # 5 = chế độ "Siêu khó" (Iterative Deepening)
SUPER_HARD_TIME_BUDGET_SEC = 10.0  # ngân sách thời gian cho chế độ Siêu khó
AUTO_DEEPEN_TIME_BUDGET_SEC = 4.0  # ngân sách ngắn hơn khi TỰ ĐỘNG phát hiện tàn cuộc áp đảo
SUPER_HARD_MAX_PLY = 8  # trần an toàn: ở tàn cuộc (ít quân) cây cờ nhỏ nên có thể đào rất sâu rất nhanh

# --- Ước lượng bộ nhớ theo công thức ĐỘ PHỨC TẠP KHÔNG GIAN kinh điển ---
# Đo bộ nhớ thực tế bằng tracemalloc làm chương trình chậm đi 4-5 lần (ảnh hưởng tới
# trải nghiệm chơi), nên thay vào đó dùng đúng công thức lý thuyết vẫn dạy trong môn AI:
#   - DFS/Backtracking (có quay lui, lưu 1 đường đi tại 1 thời điểm): O(b × m)
#     (b = hệ số nhánh, m = độ sâu tối đa đã đạt được)
#   - BFS (lưu TOÀN BỘ cây đã duyệt trong hàng đợi/bộ nhớ): O(b^d) — chính là tổng số
#     nút cây đã tạo ra, và con số này ta ĐO ĐƯỢC THẬT (self.nodes), không phải ước lượng.
# BYTES_PER_NODE_ESTIMATE quy đổi "1 đơn vị nút" sang byte để 2 thuật toán so sánh được
# trên cùng một đơn vị đo (KB) — giá trị này là ước lượng cho một bản ghi nước đi nhỏ
# trong Python (tuple nước đi + overhead object).
BYTES_PER_NODE_ESTIMATE = 200

Piece = str
Pos = Tuple[int, int]
Move = Tuple[int, int, int, int]

VALUES = {
    "p": 100, "c": 450, "h": 320, "e": 250, "a": 250, "r": 500, "k": 10000
}

CHAR = {
    "K": "帥", "A": "仕", "E": "相", "H": "傌", "R": "俥", "C": "炮", "P": "兵",
    "k": "將", "a": "士", "e": "象", "h": "馬", "r": "車", "c": "砲", "p": "卒",
}

# --- Zobrist hashing: dùng để phát hiện lặp lại vị trí (chống Backtracking đi lặp nước) ---
_ZOBRIST_RNG = random.Random(20240521)  # seed cố định để kết quả tái lập được (phục vụ báo cáo)
_ALL_PIECE_SYMBOLS = list(CHAR.keys())
ZOBRIST_TABLE = {
    sym: [[_ZOBRIST_RNG.getrandbits(64) for _ in range(COLS)] for _ in range(ROWS)]
    for sym in _ALL_PIECE_SYMBOLS
}

def compute_hash(board) -> int:
    """Băm trạng thái bàn cờ (Zobrist hashing) để so sánh/đếm số lần một vị trí xuất hiện."""
    h = 0
    for r in range(ROWS):
        row = board[r]
        for c in range(COLS):
            p = row[c]
            if p:
                h ^= ZOBRIST_TABLE[p][r][c]
    return h


def side_of(piece: Optional[Piece]) -> Optional[str]:
    if not piece:
        return None
    return RED if piece.isupper() else BLACK

def opponent(side: str) -> str:
    return BLACK if side == RED else RED

def initial_board() -> List[List[Optional[Piece]]]:
    return [
        list("rheakaehr"),
        [None, None, None, None, None, None, None, None, None],
        [None, "c", None, None, None, None, None, "c", None],
        ["p", None, "p", None, "p", None, "p", None, "p"],
        [None, None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None],
        ["P", None, "P", None, "P", None, "P", None, "P"],
        [None, "C", None, None, None, None, None, "C", None],
        [None, None, None, None, None, None, None, None, None],
        list("RHEAKAEHR"),
    ]

def inside(r: int, c: int) -> bool:
    return 0 <= r < ROWS and 0 <= c < COLS

def in_palace(side: str, r: int, c: int) -> bool:
    if not (3 <= c <= 5):
        return False
    return 7 <= r <= 9 if side == RED else 0 <= r <= 2

def crossed_river(side: str, r: int) -> bool:
    return r <= 4 if side == RED else r >= 5

def clone_board(board):
    return [row[:] for row in board]

def apply_move(board, move: Move):
    r1, c1, r2, c2 = move
    captured = board[r2][c2]
    board[r2][c2] = board[r1][c1]
    board[r1][c1] = None
    return captured

def undo_move(board, move: Move, captured):
    r1, c1, r2, c2 = move
    board[r1][c1] = board[r2][c2]
    board[r2][c2] = captured

def pseudo_moves_for(board, r, c):
    piece = board[r][c]
    if not piece:
        return []
    side = side_of(piece)
    kind = piece.lower()
    out = []

    def add(rr, cc):
        if inside(rr, cc) and side_of(board[rr][cc]) != side:
            out.append((r, c, rr, cc))

    if kind == "r":
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            rr, cc = r + dr, c + dc
            while inside(rr, cc):
                if board[rr][cc] is None:
                    out.append((r,c,rr,cc))
                else:
                    if side_of(board[rr][cc]) != side:
                        out.append((r,c,rr,cc))
                    break
                rr += dr; cc += dc

    elif kind == "c":
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            rr, cc = r + dr, c + dc
            jumped = False
            while inside(rr, cc):
                if not jumped:
                    if board[rr][cc] is None:
                        out.append((r,c,rr,cc))
                    else:
                        jumped = True
                else:
                    if board[rr][cc] is not None:
                        if side_of(board[rr][cc]) != side:
                            out.append((r,c,rr,cc))
                        break
                rr += dr; cc += dc

    elif kind == "h":
        for dr, dc, lr, lc in (
            (2,1,1,0),(2,-1,1,0),(-2,1,-1,0),(-2,-1,-1,0),
            (1,2,0,1),(1,-2,0,-1),(-1,2,0,1),(-1,-2,0,-1)
        ):
            if inside(r+lr, c+lc) and board[r+lr][c+lc] is None:
                add(r+dr, c+dc)

    elif kind == "e":
        for dr, dc in ((2,2),(2,-2),(-2,2),(-2,-2)):
            er, ec = r + dr//2, c + dc//2
            rr, cc = r + dr, c + dc
            if inside(rr,cc) and board[er][ec] is None and not crossed_river(side, rr):
                add(rr,cc)

    elif kind == "a":
        for dr, dc in ((1,1),(1,-1),(-1,1),(-1,-1)):
            rr, cc = r+dr, c+dc
            if in_palace(side, rr, cc):
                add(rr,cc)

    elif kind == "k":
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            rr, cc = r+dr, c+dc
            if in_palace(side, rr, cc):
                add(rr,cc)
        # Flying general capture
        rr = r - 1
        while rr >= 0:
            if board[rr][c] is not None:
                if board[rr][c].lower() == "k" and side_of(board[rr][c]) != side:
                    out.append((r,c,rr,c))
                break
            rr -= 1
        rr = r + 1
        while rr < ROWS:
            if board[rr][c] is not None:
                if board[rr][c].lower() == "k" and side_of(board[rr][c]) != side:
                    out.append((r,c,rr,c))
                break
            rr += 1

    elif kind == "p":
        dr = -1 if side == RED else 1
        add(r+dr, c)
        if crossed_river(side, r):
            add(r, c-1)
            add(r, c+1)

    return out

def find_king(board, side) -> Optional[Pos]:
    target = "K" if side == RED else "k"
    for r in range(ROWS):
        for c in range(COLS):
            if board[r][c] == target:
                return (r,c)
    return None

def square_attacked(board, r, c, by_side) -> bool:
    # Generate pseudo moves for the opponent. Since pseudo king moves include
    # flying-general captures, this also handles the facing-generals rule.
    for rr in range(ROWS):
        for cc in range(COLS):
            if side_of(board[rr][cc]) == by_side:
                for m in pseudo_moves_for(board, rr, cc):
                    if m[2] == r and m[3] == c:
                        return True
    return False

def in_check(board, side) -> bool:
    king = find_king(board, side)
    if king is None:
        return True
    return square_attacked(board, king[0], king[1], opponent(side))

def legal_moves(board, side) -> List[Move]:
    result = []
    for r in range(ROWS):
        for c in range(COLS):
            if side_of(board[r][c]) != side:
                continue
            for move in pseudo_moves_for(board, r, c):
                captured = apply_move(board, move)
                if not in_check(board, side):
                    result.append(move)
                undo_move(board, move, captured)
    return result

def is_checkmate(board, side) -> bool:
    return in_check(board, side) and not legal_moves(board, side)

def is_stalemate(board, side) -> bool:
    return not in_check(board, side) and not legal_moves(board, side)

def has_mating_material(board, side) -> bool:
    """Trả về True nếu bên `side` còn ít nhất 1 quân có khả năng chiếu bí đối phương
    (Xe/Pháo/Mã, hoặc Tốt đã qua sông). Chỉ còn Tướng/Sĩ/Tượng thì KHÔNG thể chiếu bí
    (Sĩ/Tượng bị giới hạn trong cung/không qua sông, Tướng không đủ sức một mình)."""
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if side_of(p) != side:
                continue
            kind = p.lower()
            if kind in ("r", "c", "h"):
                return True
            if kind == "p" and crossed_river(side, r):
                return True
    return False

def insufficient_material_draw(board) -> bool:
    """Hòa cờ 'chết' khi CẢ HAI bên đều không còn quân đủ sức chiếu bí — tránh trường
    hợp 2 AI yếu chạy Tướng qua lại vô tận vì không bên nào còn khả năng phân thắng bại."""
    return not has_mating_material(board, RED) and not has_mating_material(board, BLACK)

def terminal_score(board, side_to_move, ply):
    if find_king(board, RED) is None:
        return -1000000 + ply
    if find_king(board, BLACK) is None:
        return 1000000 - ply
    if is_checkmate(board, side_to_move):
        return -1000000 + ply if side_to_move == RED else 1000000 - ply
    if is_stalemate(board, side_to_move):
        return 0
    if insufficient_material_draw(board):
        # Cả hai bên đều không còn quân đủ sức chiếu bí (vd chỉ còn Tướng/Sĩ/Tượng cả
        # hai bên) -> hòa ngay, tránh 2 AI chạy Tướng qua lại vô nghĩa.
        return 0
    return None

def evaluate(board):
    score = 0
    red_king = black_king = None
    red_attackers = []   # các quân Xe/Pháo/Mã của Đỏ — quân thực sự có thể chiếu bí
    black_attackers = []
    # Material + modest positional bonuses.
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if not p:
                continue
            v = VALUES[p.lower()]
            side = side_of(p)
            # Pawns are more valuable after crossing.
            if p.lower() == "p" and crossed_river(side, r):
                v += 35
            # Centralization helps king/pieces a little.
            if p.lower() in ("h","c","r"):
                v += max(0, 4 - abs(4-c)) * 4
            score += v if side == RED else -v
            if p == "K":
                red_king = (r, c)
            elif p == "k":
                black_king = (r, c)
            elif p in ("R", "H", "C"):
                red_attackers.append((r, c))
            elif p in ("r", "h", "c"):
                black_attackers.append((r, c))

    # "Lực hút tướng" (king tropism): thưởng điểm cho quân tấn công (Xe/Pháo/Mã) càng
    # ở gần Tướng đối phương. Nếu không có phần này, khi một bên đã áp đảo hoàn toàn về
    # quân số nhưng chưa có nước ăn/chiếu ngay, điểm đánh giá gần như bằng phẳng ở mọi
    # nước đi -> AI (đặc biệt ở độ sâu thấp) không biết nên đi đâu và chỉ "chạy vòng
    # vòng" mà không chủ động ép Tướng đối phương vào thế bí. Thêm phần này giúp
    # Backtracking có "định hướng" tiến tới chiếu bí ngay cả khi chưa ăn được quân nào.
    TROPISM_WEIGHT = 3
    if black_king is not None:
        for (r, c) in red_attackers:
            dist = abs(r - black_king[0]) + abs(c - black_king[1])
            score += (16 - dist) * TROPISM_WEIGHT
    if red_king is not None:
        for (r, c) in black_attackers:
            dist = abs(r - red_king[0]) + abs(c - red_king[1])
            score -= (16 - dist) * TROPISM_WEIGHT

    # Check bonuses.
    if in_check(board, RED):
        score -= 40
    if in_check(board, BLACK):
        score += 40
    return score

class BacktrackingAI:
    """Recursive backtracking/minimax with alpha-beta pruning and move ordering."""
    def __init__(self, depth=2):
        self.nodes = 0
        # Chỉ ghi lại các nước Đen thực sự được Backtracking duyệt.
        self.search_log = []
        # Thống kê chi tiết của lần chọn nước gần nhất (phục vụ báo cáo/biểu đồ).
        self.last_stats = {}
        self.mate_in = None  # số nửa-nước (ply) tới chiếu bí, nếu tìm thấy chiếu bí bắt buộc.
        self.depth_reached = 0
        self.set_depth(depth)

    def set_depth(self, depth):
        """Đặt độ sâu tìm kiếm. Độ sâu = MAX_SEARCH_DEPTH (5) sẽ tự bật chế độ Siêu khó
        (Iterative Deepening, tìm chiếu bí nhanh nhất)."""
        self.depth = max(1, min(int(depth), MAX_SEARCH_DEPTH))
        self.super_hard = self.depth >= MAX_SEARCH_DEPTH

    def choose_move(self, board, side=BLACK, position_counts=None):
        """Chọn nước đi. `position_counts`: dict {zobrist_hash: số lần đã xuất hiện trong
        ván đấu}, dùng để tránh Backtracking chọn nước dẫn tới lặp lại vị trí (đi lặp nước)."""
        start_time = time.time()
        self.nodes = 0
        self.search_log = []
        self.mate_in = None
        position_counts = position_counts or {}

        moves = legal_moves(board, side)
        if not moves:
            self.last_stats = {
                "nodes": 0, "time_ms": 0.0, "depth": self.depth,
                "mate_in": None, "super_hard": self.super_hard, "algorithm": "backtracking",
                "peak_memory_kb": 0.0,
            }
            return None, evaluate(board), self.nodes

        branching_factor = len(moves)  # hệ số nhánh b, đo thật tại gốc cây
        self.depth_reached = self.depth
        auto_deepen = (not self.super_hard) and self._is_decisive_sparse_endgame(board, side)
        if self.super_hard or auto_deepen:
            # Chế độ Siêu khó: Iterative Deepening (đào sâu dần) từ ply 1 tăng dần, có
            # NGÂN SÁCH THỜI GIAN thay vì ép cứng một độ sâu cố định. Lý do: cây tìm kiếm
            # cờ tướng có hệ số nhánh rất lớn ở khai cuộc/trung cuộc (đào tới ply 4-5 đã có
            # thể mất hàng chục giây), nhưng ở tàn cuộc (ít quân) cây rất nhỏ nên có thể đào
            # tới ply 6-8 trong tích tắc. Time-budget giúp AI TỰ ĐỘNG đào sâu nhất có thể
            # trong thời gian cho phép, và dừng NGAY khi tìm ra chiếu bí bắt buộc -> vì đào
            # từ ply nhỏ tới lớn nên chiếu bí tìm được đầu tiên luôn là chiếu bí NGẮN NHẤT.
            best_move, best_score = self._iterative_deepening(
                board, side, position_counts, start_time,
                time_budget=SUPER_HARD_TIME_BUDGET_SEC if self.super_hard else AUTO_DEEPEN_TIME_BUDGET_SEC,
            )
        else:
            best_move, best_score = self._root_search(board, side, self.depth, position_counts, record_log=True)

        elapsed_ms = round((time.time() - start_time) * 1000, 1)
        # Độ phức tạp không gian của DFS/Backtracking: O(b × m) — tại mỗi tầng đệ quy
        # (tối đa depth_reached tầng), chỉ cần giữ 1 đường đi + danh sách nước ở tầng đó
        # (tối đa branching_factor nước), KHÔNG lưu toàn bộ cây như BFS.
        peak_memory_kb = round((self.depth_reached * branching_factor * BYTES_PER_NODE_ESTIMATE) / 1024, 1)
        self.last_stats = {
            "nodes": self.nodes,
            "time_ms": elapsed_ms,
            "depth": self.depth_reached,
            "mate_in": self.mate_in,
            "super_hard": self.super_hard,
            "auto_deepen": auto_deepen,
            "peak_memory_kb": peak_memory_kb,
            "algorithm": "backtracking",
        }
        return best_move, best_score, self.nodes

    def _is_decisive_sparse_endgame(self, board, side):
        """Phát hiện tàn cuộc đã áp đảo hoàn toàn về quân số nhưng bàn cờ còn ít quân
        (đúng tình huống Xe+Pháo+Tốt+Tượng của Đen so với chỉ Tướng+Sĩ+Tượng của Đỏ).
        Ở tình huống này, độ sâu cố định thấp (1-4) thường KHÔNG đủ để tìm ra kỹ thuật
        ăn dần quân phòng thủ / ép chiếu bí, khiến AI chỉ "chạy vòng vòng" dù đang thắng
        rõ ràng. Khi phát hiện, tạm thời bật Iterative Deepening (giống Siêu khó nhưng
        ngân sách thời gian ngắn hơn) để thực sự tìm ra tiến triển."""
        total_pieces = 0
        for r in range(ROWS):
            for c in range(COLS):
                if board[r][c]:
                    total_pieces += 1
        if total_pieces > 16:
            return False
        rough = evaluate(board)
        DECISIVE_MARGIN = 700  # xấp xỉ giá trị 1 Xe
        if side == BLACK and rough <= -DECISIVE_MARGIN:
            return True
        if side == RED and rough >= DECISIVE_MARGIN:
            return True
        return False

    def _iterative_deepening(self, board, side, position_counts, start_time, time_budget=SUPER_HARD_TIME_BUDGET_SEC):
        # Không dùng cách "chạy rồi hủy giữa chừng" vì Backtracking dùng apply_move/undo_move
        # theo cặp — hủy nửa chừng bằng exception sẽ làm hỏng (undo không khớp) bàn cờ.
        # Thay vào đó: DỰ ĐOÁN thời gian của ply kế tiếp dựa trên hệ số tăng trưởng quan sát
        # được từ ply trước (mỗi ply cờ tướng thường tăng số nút ~6-8 lần). Nếu dự đoán vượt
        # ngân sách còn lại thì DỪNG LẠI TRƯỚC khi bắt đầu ply đó, dùng kết quả ply gần nhất.
        # -> Ở khai/trung cuộc (cây lớn) sẽ dừng sớm, an toàn, không treo máy.
        # -> Ở tàn cuộc (ít quân, cây nhỏ) mỗi ply rất rẻ nên sẽ tự động đào rất sâu,
        #    đúng mục tiêu "tìm đường chiếu bí ngắn nhất".
        GROWTH_FACTOR_GUESS = 6.0
        best_move, best_score = None, None
        depth_reached = 0
        last_iter_time = 0.0
        for d in range(1, SUPER_HARD_MAX_PLY + 1):
            remaining = time_budget - (time.time() - start_time)
            if remaining <= 0.15:
                break
            if d > 1 and last_iter_time * GROWTH_FACTOR_GUESS > remaining:
                break
            iter_start = time.time()
            self.search_log = []  # log của ply đào sâu cuối cùng hoàn tất sẽ được giữ lại
            move, score = self._root_search(board, side, d, position_counts, record_log=True)
            last_iter_time = time.time() - iter_start
            if move is not None:
                best_move, best_score = move, score
                depth_reached = d
            if best_score is not None and abs(best_score) >= MATE_THRESHOLD:
                self._update_mate_in(best_score)
                break
        self.depth_reached = depth_reached if depth_reached else 1
        return best_move, best_score

    def _update_mate_in(self, score):
        # terminal_score(): thắng cho ĐỎ = 1_000_000 - ply ; thắng cho ĐEN = -1_000_000 + ply
        if score > 0:
            self.mate_in = int(round(1_000_000 - score))
        else:
            self.mate_in = int(round(1_000_000 + score))

    def _repetition_adjustment(self, board, move, side, position_counts):
        """Phạt điểm những nước khiến vị trí bị lặp lại, để Backtracking không đi lặp
        đi lặp lại một nước (vd: đi tới đi lui một quân) khi không có nước nào rõ ràng tốt hơn."""
        if not position_counts:
            return 0
        captured = apply_move(board, move)
        h = compute_hash(board)
        undo_move(board, move, captured)
        count = position_counts.get(h, 0)
        if count >= 2:
            magnitude = 700   # vị trí này sẽ là lần lặp thứ 3 trở lên -> tránh mạnh
        elif count == 1:
            magnitude = 180   # đã từng xảy ra 1 lần -> hơi tránh để đa dạng nước đi
        else:
            return 0
        return magnitude if side == BLACK else -magnitude

    def _root_search(self, board, side, depth, position_counts, record_log=True):
        moves = legal_moves(board, side)
        if not moves:
            return None, evaluate(board)

        maximizing = side == RED
        best_move = moves[0]
        best_score = -math.inf if maximizing else math.inf

        # Capture/checking moves first improves alpha-beta pruning.
        moves.sort(key=lambda m: self._move_priority(board, m), reverse=True)

        alpha, beta = -math.inf, math.inf
        for move in moves:
            log_entry = None
            if side == BLACK and record_log:
                log_entry = {
                    "ply": 1,
                    "depth": depth,
                    "move": move_to_dict(move),
                    "captured": CHAR.get(board[move[2]][move[3]], board[move[2]][move[3]]) if board[move[2]][move[3]] else None,
                }
                self.search_log.append(log_entry)
            captured = apply_move(board, move)
            raw_score = self._search(board, opponent(side), depth - 1, alpha, beta, depth, record_log)
            undo_move(board, move, captured)

            score = raw_score
            if abs(raw_score) < MATE_THRESHOLD:
                score = raw_score + self._repetition_adjustment(board, move, side, position_counts)

            if log_entry is not None:
                log_entry["score"] = raw_score

            if maximizing:
                if score > best_score:
                    best_score, best_move = score, move
                alpha = max(alpha, best_score)
            else:
                if score < best_score:
                    best_score, best_move = score, move
                beta = min(beta, best_score)
            if beta <= alpha:
                break

        return best_move, best_score

    def _move_priority(self, board, move):
        target = board[move[2]][move[3]]
        score = VALUES.get(target.lower(), 0) if target else 0
        # Prefer moves that give check.
        captured = apply_move(board, move)
        mover_side = side_of(board[move[2]][move[3]])
        if in_check(board, opponent(mover_side)):
            score += 900
        undo_move(board, move, captured)
        return score

    def _search(self, board, side, depth, alpha, beta, root_depth=None, record_log=True):
        # root_depth = độ sâu ban đầu của LẦN GỌI HIỆN TẠI (không phải self.depth), để
        # tính đúng "ply" (số nửa-nước đã đi) ngay cả khi đang ở giữa Iterative Deepening.
        if root_depth is None:
            root_depth = self.depth
        self.nodes += 1
        terminal = terminal_score(board, side, root_depth - depth)
        if terminal is not None:
            return terminal
        if depth == 0:
            return evaluate(board)

        moves = legal_moves(board, side)
        if not moves:
            return evaluate(board)

        maximizing = side == RED
        moves.sort(key=lambda m: self._move_priority(board, m), reverse=True)

        if maximizing:
            value = -math.inf
            for move in moves:
                log_entry = None
                if side == BLACK and record_log:
                    target = board[move[2]][move[3]]
                    log_entry = {
                        "ply": root_depth - depth + 1,
                        "depth": depth,
                        "move": move_to_dict(move),
                        "captured": CHAR.get(target, target) if target else None,
                    }
                    self.search_log.append(log_entry)
                captured = apply_move(board, move)
                child_value = self._search(board, BLACK, depth-1, alpha, beta, root_depth, record_log)
                value = max(value, child_value)
                undo_move(board, move, captured)
                if log_entry is not None:
                    log_entry["score"] = child_value
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value
        else:
            value = math.inf
            for move in moves:
                log_entry = None
                if side == BLACK and record_log:
                    target = board[move[2]][move[3]]
                    log_entry = {
                        "ply": root_depth - depth + 1,
                        "depth": depth,
                        "move": move_to_dict(move),
                        "captured": CHAR.get(target, target) if target else None,
                    }
                    self.search_log.append(log_entry)
                captured = apply_move(board, move)
                child_value = self._search(board, RED, depth-1, alpha, beta, root_depth, record_log)
                value = min(value, child_value)
                undo_move(board, move, captured)
                if log_entry is not None:
                    log_entry["score"] = child_value
                beta = min(beta, value)
                if beta <= alpha:
                    break
            return value

class BFSAI:
    """Thuật toán Tìm kiếm theo chiều rộng (BFS - Breadth-First Search) — thuật toán tìm
    đường cơ bản. Khác với Backtracking (đệ quy DFS + quay lui + cắt tỉa Alpha-Beta),
    BFS DÙNG HÀNG ĐỢI (queue) để duyệt cây trò chơi THEO TỪNG LỚP (từng nửa-nước/ply):
    duyệt hết toàn bộ lớp hiện tại rồi mới sang lớp kế tiếp, và KHÔNG cắt tỉa bất kỳ
    nhánh nào (phải duyệt toàn bộ cây trong giới hạn độ sâu). Vì không cắt tỉa và phải
    lưu cả cây trong bộ nhớ, BFS thường duyệt NHIỀU NÚT HƠN và TỐN BỘ NHỚ HƠN nhiều so
    với Backtracking ở cùng độ sâu — đây chính là điểm so sánh trực quan giữa 2 thuật
    toán. Sau khi duyệt xong bằng BFS, điểm số được truyền ngược (backup) kiểu Minimax
    từ lá lên gốc để chọn nước đi tốt nhất."""

    MAX_BFS_DEPTH = 2  # không cắt tỉa Alpha-Beta nên số nút tăng theo cấp số nhân rất
    # nhanh (~40 nước hợp lệ mỗi lớp); độ sâu 3 đã lên tới hàng chục nghìn nút, quá chậm
    # để dùng tương tác — giữ ở 2 để phản hồi trong vài giây mà vẫn thấy rõ sự khác biệt
    # về số nút duyệt so với Backtracking (có cắt tỉa) ở cùng độ sâu.

    def __init__(self, depth=2):
        self.nodes = 0
        self.search_log = []
        self.last_stats = {}
        self.mate_in = None
        self.super_hard = False
        self.set_depth(depth)

    def set_depth(self, depth):
        self.depth = max(1, min(int(depth), self.MAX_BFS_DEPTH))

    def choose_move(self, board, side, position_counts=None):
        start_time = time.time()
        self.nodes = 0
        self.search_log = []
        self.mate_in = None
        position_counts = position_counts or {}

        root_moves = legal_moves(board, side)
        if not root_moves:
            self.last_stats = {
                "nodes": 0, "time_ms": 0.0, "depth": self.depth,
                "mate_in": None, "super_hard": False, "algorithm": "bfs",
                "peak_memory_kb": 0.0,
            }
            return None, evaluate(board), self.nodes

        # --- BƯỚC 1: DUYỆT THEO CHIỀU RỘNG BẰNG HÀNG ĐỢI (queue) ---
        # Xây dựng cây trò chơi (mỗi "node" gắn với 1 nước đi) từ gốc, duyệt hết từng
        # lớp (từng ply) trước khi mở rộng lớp kế tiếp — đúng bản chất BFS. Không cắt
        # tỉa: mọi nước hợp lệ ở mỗi lớp đều được thêm vào hàng đợi.
        roots = [_BFSNode(m) for m in root_moves]
        queue = deque()
        for node, mv in zip(roots, root_moves):
            queue.append((node, [mv], 1))

        while queue:
            node, path, ply = queue.popleft()
            captured_stack = []
            cur_side = side
            for mv in path:
                captured_stack.append(apply_move(board, mv))
                cur_side = opponent(cur_side)
            self.nodes += 1

            terminal = terminal_score(board, cur_side, ply)
            if terminal is not None:
                node.score = terminal
            elif ply >= self.depth:
                node.score = evaluate(board)
            else:
                next_moves = legal_moves(board, cur_side)
                if not next_moves:
                    node.score = evaluate(board)
                else:
                    for m in next_moves:
                        child = _BFSNode(m)
                        node.children.append(child)
                        queue.append((child, path + [m], ply + 1))

            for mv, cap in zip(reversed(path), reversed(captured_stack)):
                undo_move(board, mv, cap)

        # --- BƯỚC 2: TRUYỀN NGƯỢC (backup) KIỂU MINIMAX TỪ LÁ LÊN GỐC ---
        def backup(node, side_to_move):
            if not node.children:
                return node.score
            maximizing = side_to_move == RED
            values = [backup(child, opponent(side_to_move)) for child in node.children]
            node.score = max(values) if maximizing else min(values)
            return node.score

        for node in roots:
            backup(node, opponent(side))

        # --- BƯỚC 3: chọn nước gốc tốt nhất, có cộng phạt chống lặp nước giống Backtracking ---
        maximizing_root = side == RED
        best_move, best_score = None, None
        for node in roots:
            score = node.score
            if abs(score) < MATE_THRESHOLD:
                score += self._repetition_adjustment(board, node.move, side, position_counts)
            self.search_log.append({
                "ply": 1, "depth": self.depth, "move": move_to_dict(node.move),
                "captured": None, "score": node.score,
            })
            if best_score is None or (maximizing_root and score > best_score) or (not maximizing_root and score < best_score):
                best_score, best_move = score, node.move

        if best_score is not None and abs(best_score) >= MATE_THRESHOLD:
            if best_score > 0:
                self.mate_in = int(round(1_000_000 - best_score))
            else:
                self.mate_in = int(round(1_000_000 + best_score))

        elapsed_ms = round((time.time() - start_time) * 1000, 1)
        # Độ phức tạp không gian của BFS: O(b^d) — mỗi "node" trong hàng đợi/cây được GIỮ
        # LẠI TRONG BỘ NHỚ (các đối tượng _BFSNode với danh sách con), khác hẳn DFS chỉ
        # giữ 1 đường đi. self.nodes ở đây chính là TỔNG SỐ NÚT THỰC SỰ đã tạo ra và lưu
        # trong cây — không phải ước lượng, mà là số đo thật.
        peak_memory_kb = round((self.nodes * BYTES_PER_NODE_ESTIMATE) / 1024, 1)
        self.last_stats = {
            "nodes": self.nodes, "time_ms": elapsed_ms, "depth": self.depth,
            "mate_in": self.mate_in, "super_hard": False, "algorithm": "bfs",
            "peak_memory_kb": peak_memory_kb,
        }
        return best_move, best_score, self.nodes

    def _repetition_adjustment(self, board, move, side, position_counts):
        if not position_counts:
            return 0
        captured = apply_move(board, move)
        h = compute_hash(board)
        undo_move(board, move, captured)
        count = position_counts.get(h, 0)
        if count >= 2:
            magnitude = 700
        elif count == 1:
            magnitude = 180
        else:
            return 0
        return magnitude if side == BLACK else -magnitude


class _BFSNode:
    """Một nút trong cây BFS: gắn với 1 nước đi, có danh sách nút con và điểm số
    (được điền sau khi truyền ngược kiểu Minimax)."""
    __slots__ = ("move", "children", "score")

    def __init__(self, move):
        self.move = move
        self.children = []
        self.score = None


class GreedyAI:
    """Thuật toán Tham lam (Greedy Best-First Search): CHỈ nhìn 1 nước, không đệ quy,
    không nhìn trước đối thủ sẽ phản ứng ra sao. Chọn ngay nước có điểm evaluate() tốt
    nhất tại chỗ. Dùng làm 'đối thủ' để so sánh trực quan với Backtracking (Minimax +
    Alpha-Beta): Backtracking nhìn được nhiều nước sau nên tránh được bẫy/thí quân mà
    Greedy không thấy được, trong khi Greedy chạy nhanh hơn rất nhiều và duyệt ít nút hơn."""

    def __init__(self):
        self.nodes = 0
        self.search_log = []
        self.last_stats = {}
        self.mate_in = None
        self.depth = 1
        self.super_hard = False

    def choose_move(self, board, side, position_counts=None):
        start_time = time.time()
        self.nodes = 0
        self.search_log = []
        self.mate_in = None
        moves = legal_moves(board, side)
        if not moves:
            self.last_stats = {
                "nodes": 0, "time_ms": 0.0, "depth": 1,
                "mate_in": None, "super_hard": False, "algorithm": "greedy",
            }
            return None, evaluate(board), self.nodes

        maximizing = side == RED
        best_move, best_score = None, None
        for move in moves:
            self.nodes += 1
            target = board[move[2]][move[3]]
            captured_char = CHAR.get(target, target) if target else None
            captured = apply_move(board, move)
            score = evaluate(board)
            undo_move(board, move, captured)
            self.search_log.append({
                "ply": 1, "depth": 1, "move": move_to_dict(move),
                "captured": captured_char, "score": score,
            })
            if best_score is None or (maximizing and score > best_score) or (not maximizing and score < best_score):
                best_score, best_move = score, move

        elapsed_ms = round((time.time() - start_time) * 1000, 1)
        self.last_stats = {
            "nodes": self.nodes, "time_ms": elapsed_ms, "depth": 1,
            "mate_in": None, "super_hard": False, "algorithm": "greedy",
        }
        return best_move, best_score, self.nodes


def move_to_dict(move):
    return {"from": [move[0], move[1]], "to": [move[2], move[3]]}

def board_to_json(board):
    return [[p if p else "" for p in row] for row in board]
