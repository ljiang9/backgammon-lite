#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backgammon-lite: 简化版双陆棋（Backgammon）.

规则（简化版）：
- 24 个点，白方从 24→1 走、黑方从 1→24 走，每方 15 子
- 每回合掷两个骰子，按点数走棋；掷出双骰走 4 次
- 落到对方单子（blot）上则打中，对方子送上 bar
- bar 上有子时必须先入场
- 15 子全部进入本营后才能 bear off（收子）；允许大点数从最高占子点收子
- 先收完 15 子者胜；无加倍骰、无 Crawford 等进阶规则

纯标准库，Python 3.10+。
"""

import argparse
import copy
import random
import sys

WHITE, BLACK = 0, 1
NAMES = ("白方", "黑方")
N = 24
BAR = "bar"   # 从 bar 入场
OFF = "off"   # bear off（收子）


def other(p):
    """对方。"""
    return 1 - p


class IllegalMove(Exception):
    """非法走法。"""


class Backgammon:
    """对局状态。points[1..24] 每个点是 [白子数, 黑子数]。"""

    def __init__(self):
        self.points = [[0, 0] for _ in range(N + 1)]
        self.bar = [0, 0]
        self.off = [0, 0]
        for pt, n in ((24, 2), (13, 5), (8, 3), (6, 5)):
            self.points[pt][WHITE] = n
        for pt, n in ((1, 2), (12, 5), (17, 3), (19, 5)):
            self.points[pt][BLACK] = n

    def total(self, p):
        """某方场上子数（点上 + bar 上 + 已收），恒为 15。"""
        return (sum(self.points[i][p] for i in range(1, N + 1))
                + self.bar[p] + self.off[p])


def all_in_home(g, p):
    """是否全部子已进入本营（bar 为空且外侧无子）。"""
    if g.bar[p] > 0:
        return False
    if p == WHITE:
        return all(g.points[i][p] == 0 for i in range(7, N + 1))
    return all(g.points[i][p] == 0 for i in range(1, 19))


def entry_point(p, d):
    """从 bar 入场的目标点。"""
    return 25 - d if p == WHITE else d


def moves_for_die(g, p, d):
    """某方用点数 d 的全部合法走法：(起点, 落点)，起点可为 'bar'，落点可为 'off'。"""
    o = other(p)
    moves = []
    if g.bar[p] > 0:
        e = entry_point(p, d)
        if g.points[e][o] <= 1:
            moves.append((BAR, e))
        return moves
    home = all_in_home(g, p)
    for src in range(1, N + 1):
        if g.points[src][p] == 0:
            continue
        dst = src - d if p == WHITE else src + d
        if 1 <= dst <= N:
            if g.points[dst][o] <= 1:
                moves.append((src, dst))
        elif home:
            if p == WHITE:
                if dst == 0:
                    moves.append((src, OFF))
                elif dst < 0 and not any(g.points[i][p] for i in range(src + 1, 7)):
                    # 大点数只能从最高占子点收子
                    moves.append((src, OFF))
            else:
                if dst == N + 1:
                    moves.append((src, OFF))
                elif dst > N + 1 and not any(g.points[i][p] for i in range(19, src)):
                    moves.append((src, OFF))
    return moves


def apply_move(g, p, move):
    """执行一步走法（含打子）。非法走法抛 IllegalMove。"""
    o = other(p)
    src, dst = move
    if src == BAR:
        if g.bar[p] <= 0:
            raise IllegalMove("bar 上没有子")
        g.bar[p] -= 1
    else:
        if not (1 <= src <= N) or g.points[src][p] <= 0:
            raise IllegalMove(f"起点 {src} 没有己方子")
        g.points[src][p] -= 1
    if dst == OFF:
        g.off[p] += 1
    else:
        if g.points[dst][o] >= 2:
            raise IllegalMove(f"落点 {dst} 被对方占据")
        if g.points[dst][o] == 1:
            g.points[dst][o] = 0
            g.bar[o] += 1
        g.points[dst][p] += 1


def pip_count(g, p):
    """pip 值（剩余路程），越小越接近胜利。"""
    total = g.bar[p] * 25
    for i in range(1, N + 1):
        c = g.points[i][p]
        total += c * (i if p == WHITE else N + 1 - i)
    return total


def move_score(g, p, move):
    """单步走法的贪心评分。"""
    o = other(p)
    src, dst = move
    s = 0.0
    if src == BAR:
        s += 40
    elif g.points[src][p] == 2:
        s -= 12  # 走后起点留单子（blot）
    if dst == OFF:
        s += 60
    else:
        if g.points[dst][o] == 1:
            s += 100  # 打子
        if g.points[dst][p] >= 1:
            s += 8  # 落子成锚（叠子）
    return s


def play_turn(g, p, dice, rng):
    """执行一回合：两种骰序都贪心试走，选"用骰多、局面好"的。返回实际走法序列。"""
    orders = [dice]
    if len(dice) == 2 and dice[0] != dice[1]:
        orders.append([dice[1], dice[0]])
    best = None
    for order in orders:
        gg = copy.deepcopy(g)
        seq = []
        used = 0
        for d in order:
            ms = moves_for_die(gg, p, d)
            if not ms:
                continue
            m = max(ms, key=lambda m: move_score(gg, p, m) + rng.random())
            apply_move(gg, p, m)
            seq.append((d, m))
            used += 1
        o = other(p)
        key = (used, gg.off[p] - gg.off[o],
               -(pip_count(gg, p) - pip_count(gg, o)))
        if best is None or key > best[0]:
            best = (key, gg, seq)
    _, gg, seq = best
    g.points, g.bar, g.off = gg.points, gg.bar, gg.off
    return seq


def play_game(rng, starter=WHITE, max_rounds=400):
    """完整对局。返回 (胜者或 None, 回合数)。"""
    g = Backgammon()
    turn = starter
    for rnd in range(1, max_rounds + 1):
        d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
        dice = [d1] * 4 if d1 == d2 else [d1, d2]
        play_turn(g, turn, dice, rng)
        if g.off[turn] == 15:
            return turn, rnd
        turn = other(turn)
    return None, max_rounds


# ---- 文本渲染与交互 ----

def cell(g, i):
    w, b = g.points[i]
    if w and b:
        return f"W{w}B{b}"
    if w:
        return f"W{w}"
    if b:
        return f"B{b}"
    return "·"


def render(g):
    top = " ".join(f"{cell(g, i):>4}" for i in range(13, 25))
    bot = " ".join(f"{cell(g, i):>4}" for i in range(12, 0, -1))
    nums_t = " ".join(f"{i:>4}" for i in range(13, 25))
    nums_b = " ".join(f"{i:>4}" for i in range(12, 0, -1))
    return (
        f"点: {nums_t}\n"
        f"    {top}\n"
        f"    {bot}\n"
        f"点: {nums_b}\n"
        f"bar: 白 {g.bar[WHITE]} / 黑 {g.bar[BLACK]}"
        f"   已收: 白 {g.off[WHITE]} / 黑 {g.off[BLACK]}"
    )


def parse_move(text):
    """解析 '13-10' / 'bar-22' / '6-off'。"""
    text = text.strip().lower()
    if "-" not in text:
        raise IllegalMove("格式应为 起点-落点，如 13-10、bar-22、6-off")
    s, d = text.split("-", 1)
    src = BAR if s == "bar" else int(s)
    dst = OFF if d == "off" else int(d)
    if src != BAR and not 1 <= src <= N:
        raise IllegalMove(f"起点 {s} 越界")
    if dst != OFF and not 1 <= dst <= N:
        raise IllegalMove(f"落点 {d} 越界")
    return src, dst


def play_interactive():
    if not sys.stdin.isatty():
        print("交互模式需要终端；无头演示请用 --auto", file=sys.stderr)
        return 2
    rng = random.Random()
    g = Backgammon()
    turn = WHITE
    rnd = 0
    print("简化版双陆棋：白方 24→1，黑方 1→24。输入如 13-10、bar-22、6-off；q 退出。")
    while True:
        rnd += 1
        print(f"\n===== 第 {rnd} 回合：{NAMES[turn]} =====")
        print(render(g))
        d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
        dice = [d1] * 4 if d1 == d2 else [d1, d2]
        print(f"骰子：{' '.join(map(str, dice))}")
        for d in dice:
            ms = moves_for_die(g, turn, d)
            if not ms:
                print(f"骰子 {d}：无合法走法，跳过")
                continue
            while True:
                try:
                    text = input(f"骰子 {d}，走棋（起点-落点）：").strip()
                except EOFError:
                    print("\n退出。")
                    return 0
                if text.lower() == "q":
                    print("退出。")
                    return 0
                try:
                    mv = parse_move(text)
                except (IllegalMove, ValueError) as e:
                    print(f"输入有误：{e}")
                    continue
                if mv not in ms:
                    print("该走法不合法（被挡/骰数不符/须先入场等），请重走")
                    continue
                apply_move(g, turn, mv)
                src, dst = mv
                print(f"已走：{src}-{dst}")
                break
        if g.off[turn] == 15:
            print(f"\n{NAMES[turn]} 收完 15 子，获胜！")
            return 0
        turn = other(turn)


def auto(games, seed, verbose):
    rng = random.Random(seed)
    wins = [0, 0]
    draws = 0
    rounds_total = 0
    for i in range(1, games + 1):
        starter = WHITE if i % 2 == 1 else BLACK
        winner, rnd = play_game(rng, starter=starter)
        rounds_total += rnd
        if winner is None:
            draws += 1
            if verbose:
                print(f"第 {i}/{games} 局：和棋（{rnd} 回合）")
        else:
            wins[winner] += 1
            if verbose:
                print(f"第 {i}/{games} 局：{NAMES[winner]}胜（{rnd} 回合）")
    print(f"自动演示结束：共 {games} 局，白方胜 {wins[WHITE]}，黑方胜 {wins[BLACK]}，"
          f"和棋 {draws}，平均 {rounds_total / games:.1f} 回合/局")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="backgammon-lite：简化版双陆棋")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数（默认 10）")
    ap.add_argument("--seed", type=int, default=42, help="随机种子")
    ap.add_argument("--verbose", action="store_true", help="自动演示打印每局结果")
    args = ap.parse_args(argv)
    if args.auto:
        return auto(args.games, args.seed, args.verbose)
    return play_interactive()


if __name__ == "__main__":
    sys.exit(main())
