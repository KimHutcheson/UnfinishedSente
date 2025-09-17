import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from tkinter import font as tkfont
from itertools import combinations
from secrets import SystemRandom

# randomness
rng = SystemRandom()

# simulator constants you locked
COST_LOTTO_ONLY = 0.70
COST_LOTTO_PB   = 1.50
COST_STRIKE     = 1.00

# Lotto payouts by division without and with Powerball (Div 1..7)
LOTTO_NO_PB   = [1_000_000, 23_500, 674, 48, 26, 21, 2.80]
LOTTO_WITH_PB = [30_000_000, 32_560, 850, 98, 51, 41, 17.80]

# Strike payouts S1..S4
STRIKE_PAYOUT = [1, 77, 545, 1_000_000]

DEFAULT_SPEED = 10000  # draws per second for autorun pacing

# app state
state = {}
V = []  # base numbers for SYSTEM wheels

def z2(n: int) -> str:
    return f"{n:02d}"

def draw_lotto():
    """Perform one NZ Lotto draw. Returns main6 in draw order, bonus, powerball."""
    balls = list(range(1, 41))
    rng.shuffle(balls)
    main6 = balls[:6]     # drawn order
    bonus = balls[6]
    pb = rng.randrange(1, 11)  # 1..10
    return main6, bonus, pb

def parse_ticket_lines():
    """
    Parse the multiline ticket into a list of dicts:
    {'nums': [six ints in typed order], 'pb': int or None}
    Accept lines like:
      03 11 14 22 33 36
      03 11 14 22 33 36 | PB 05
      03 11 14 22 33 36 PB=05
    The Strike numbers printed at the right are ignored by this parser.
    """
    lines = ticket_text.get("1.0", "end").strip().splitlines()
    parsed = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        # everything before a tab is the left part that we parse
        left = s.split("\t", 1)[0]
        tokens = left.replace("|", " ").replace(",", " ").split()
        nums, pb = [], None
        i = 0
        while i < len(tokens):
            tok = tokens[i].upper()
            if tok.startswith("PB"):
                if tok == "PB" and i + 1 < len(tokens):
                    try:
                        pb = int(tokens[i+1]); i += 2; continue
                    except Exception:
                        i += 2; continue
                if "=" in tok:
                    try:
                        pb = int(tok.split("=", 1)[1])
                    except Exception:
                        pass
                    i += 1; continue
            try:
                val = int(tok)
                nums.append(val)
            except Exception:
                pass
            i += 1
        nums = [n for n in nums if 1 <= n <= 40][:6]
        if len(nums) < 6:
            continue
        if pb is not None and not (1 <= pb <= 10):
            pb = None
        parsed.append({"nums": nums, "pb": pb})
    return parsed

def add_ticket_line(nums, pb=None):
    left = " ".join(z2(n) for n in nums)
    if pb is not None:
        left += f" | PB {z2(pb)}"
    if strike_var.get():
        right = " ".join(z2(n) for n in nums[:4])
        ticket_text.insert("end", left + "\t" + right + "\n")
    else:
        ticket_text.insert("end", left + "\n")

def clear_ticket():
    ticket_text.delete("1.0", "end")

def set_status(msg: str):
    status_var.set(msg)

# payouts and stats
def init_vars():
    for k in ["D1","D2","D3","D4","D5","D6","D7","S1","S2","S3","S4"]:
        stats[k] = tk.IntVar(value=0)      # hit counts per division or strike tier
        paid[k]  = tk.DoubleVar(value=0.0) # dollars paid per division or strike tier

def refresh_paid_labels():
    # update money labels per code
    for code, lbl in paid_labels.items():
        lbl.config(text=f"{code} paid ${paid[code].get():,.2f}")
    # update the small incrementor counters per code
    for code, lbl in count_labels.items():
        lbl.config(text=str(stats[code].get()))
    # update aggregate returns
    total = sum(v.get() for v in paid.values())
    returns.set(total)
    total_label.config(text=f"Total returns ${total:,.2f}")

def award_lotto(division, powerball_matched):
    """division 1..7"""
    code = f"D{division}"
    amount = (LOTTO_WITH_PB if powerball_matched else LOTTO_NO_PB)[division-1]
    stats[code].set(stats[code].get() + 1)
    paid[code].set(paid[code].get() + amount)

def award_strike(hits):
    """hits 1..4 for Strike"""
    code = f"S{hits}"
    stats[code].set(stats[code].get() + 1)
    paid[code].set(paid[code].get() + STRIKE_PAYOUT[hits-1])

def score_line_against_draw(line, main6, bonus, pb_draw, strike_on):
    """
    Score one ticket line and return the spend incurred for this line this draw.
    Applies payout side effects to stats and paid.
    """
    cost = COST_LOTTO_PB if line["pb"] is not None else COST_LOTTO_ONLY
    if strike_on:
        cost += COST_STRIKE

    nums = line["nums"]
    m = sum(1 for x in nums if x in main6)   # count of main matches
    b = bonus in nums                         # bonus matched

    # division by (m, b)
    division = None
    if m == 6:
        division = 1
    elif m == 5 and b:
        division = 2
    elif m == 5:
        division = 3
    elif m == 4 and b:
        division = 4
    elif m == 4:
        division = 5
    elif m == 3 and b:
        division = 6
    elif m == 3:
        division = 7

    pb_matched = (line["pb"] is not None and line["pb"] == pb_draw)

    if division is not None:
        award_lotto(division, pb_matched)

    if strike_on:
        # Strike uses first 4 numbers in typed order vs first 4 drawn in draw order
        strike_guess = nums[:4]
        strike_draw  = main6[:4]
        hits = sum(1 for i in range(4) if strike_guess[i] == strike_draw[i])
        if hits >= 1:
            award_strike(hits)

    return cost

# GUI callbacks
def set_base_numbers():
    s = simpledialog.askstring(
        "Base numbers",
        "Enter base numbers 1..40 separated by space or comma.",
        parent=root
    )
    if not s:
        return
    try:
        parts = s.replace(",", " ").split()
        vals = sorted({int(p) for p in parts if 1 <= int(p) <= 40})
        if not vals:
            messagebox.showwarning("Base numbers", "No valid numbers found.")
            return
        V[:] = vals
        base_numbers_var.set("Base: " + " ".join(z2(x) for x in V))
        set_status(f"Base numbers set: {V}")
    except Exception:
        messagebox.showerror("Base numbers", "Could not parse numbers.")

def qp10():
    for _ in range(10):
        nums = sorted(rng.sample(range(1, 41), 6))
        pb = rng.randrange(1, 11) if powerball_var.get() else None
        add_ticket_line(nums, pb)
    set_status("Added 10 Quick Picks.")

def system_wheel(m):
    # choose base
    if len(V) == m:
        base = V[:]
    else:
        base = sorted(rng.sample(range(1, 41), m))
    count_before = int(float(ticket_text.index("end")))
    for comb in combinations(base, 6):
        pb = rng.randrange(1, 11) if powerball_var.get() else None
        add_ticket_line(list(comb), pb)
    added = int(float(ticket_text.index("end"))) - count_before
    set_status(f"SYSTEM{m} base {base} produced {added} lines.")

def clear_wheel_and_base():
    V.clear()
    base_numbers_var.set("")
    clear_ticket()
    set_status("Cleared base and ticket.")

def do_draw_once():
    lines = parse_ticket_lines()
    if not lines:
        set_status("No valid ticket lines. Add some first.")
        return

    # increment draw counter
    draw_number.set(draw_number.get() + 1)

    main6, bonus, pb = draw_lotto()

    drawno_label.config(text=f"Draw #{draw_number.get()}")
    main_label.config(text="Main: " + " ".join(z2(x) for x in main6))
    bonus_label.config(text="Bonus: " + z2(bonus))
    first4_label.config(text="First 4: " + " ".join(z2(x) for x in main6[:4]))
    pb_label.config(text="PB draw: " + z2(pb))

    total_cost = 0.0
    strike_on = strike_var.get()
    for line in lines:
        total_cost += score_line_against_draw(line, main6, bonus, pb, strike_on)

    spend.set(spend.get() + total_cost)
    refresh_paid_labels()
    set_status(f"Draw done. Lines={len(lines)} Cost=${total_cost:,.2f} BAL=${returns.get()-spend.get():,.2f}")

def start_autorun():
    if state.get("running"):
        return
    state["running"] = True
    schedule_next()

def schedule_next():
    if not state.get("running"):
        return
    s = max(1, int(speed_var.get()))
    if s <= 1000:
        # one draw per tick
        do_draw_once()
        delay_ms = max(1, int(1000 / s))
        state["after_id"] = root.after(delay_ms, schedule_next)
    else:
        # batch multiple draws per 1 ms tick
        batch = max(1, s // 1000)
        for _ in range(batch):
            do_draw_once()
        state["after_id"] = root.after(1, schedule_next)

def pause_autorun():
    state["running"] = False
    aid = state.pop("after_id", None)
    if aid:
        try:
            root.after_cancel(aid)
        except Exception:
            pass
    set_status("Paused.")

def on_reset():
    # stop autorun and cancel timers
    state["running"] = False
    aid = state.pop("after_id", None)
    if aid:
        try:
            root.after_cancel(aid)
        except Exception:
            pass

    # clear ticket
    try:
        ticket_text.delete("1.0", "end")
    except Exception:
        pass

    # zero counters and money tallies
    for v in stats.values():
        v.set(0)
    for v in paid.values():
        v.set(0.0)

    # zero aggregates
    spend.set(0.0)
    returns.set(0.0)

    # restore controls
    speed_var.set(DEFAULT_SPEED)
    powerball_var.set(False)
    strike_var.set(False)
    base_numbers_var.set("")
    V.clear()

    # clear labels
    main_label.config(text="")
    bonus_label.config(text="")
    first4_label.config(text="")
    pb_label.config(text="")
    draw_number.set(0)
    drawno_label.config(text="")
    status_var.set("Reset complete.")

    # refresh panels then blank the small incrementors as requested
    refresh_paid_labels()
    for lbl in count_labels.values():
        lbl.config(text="")  # show blank instead of 0 after reset
    refresh_money_labels()

def quit_app():
    root.destroy()

# UI
root = tk.Tk()
root.title("NZ Lotto Simulator")

# top controls
top = ttk.Frame(root, padding=6)
top.grid(row=0, column=0, columnspan=2, sticky="ew")
top.columnconfigure(1, weight=1)

ttk.Label(top, text="Speed (draws/sec)").grid(row=0, column=0, sticky="w")
speed_var = tk.IntVar(value=DEFAULT_SPEED)
speed_spin = ttk.Spinbox(top, from_=1, to=10_000, textvariable=speed_var, width=8)
speed_spin.grid(row=0, column=1, sticky="w")

powerball_var = tk.BooleanVar(value=False)
strike_var    = tk.BooleanVar(value=False)
ttk.Checkbutton(top, text="Include Powerball in new lines", variable=powerball_var).grid(row=0, column=2, padx=10)
ttk.Checkbutton(top, text="Play Strike per line", variable=strike_var).grid(row=0, column=3, padx=10)
ttk.Button(top, text="Single DRAW", command=do_draw_once).grid(row=0, column=4, padx=10)

# left pane
left = ttk.Frame(root, padding=6)
left.grid(row=1, column=0, sticky="ns")
for c in range(2):
    left.columnconfigure(c, weight=1)

ttk.Button(left, text="QP10", command=qp10).grid( row=0, column=0, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="START", command=start_autorun).grid( row=1, column=0, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="PAUSE", command=pause_autorun).grid( row=2, column=0, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="RESET", command=on_reset).grid( row=3, column=0, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="QUIT", command=quit_app).grid(  row=4, column=0, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="PLAYING SET", command=set_base_numbers).grid( row=5, column=0, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="CLEAR BASE + TICKET", command=clear_wheel_and_base).grid(row=6, column=0, sticky="ew", padx=2, pady=2)

ttk.Button(left, text="SYSTEM7",  command=lambda: system_wheel(7)).grid( row=0, column=1, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="SYSTEM8",  command=lambda: system_wheel(8)).grid( row=1, column=1, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="SYSTEM9",  command=lambda: system_wheel(9)).grid( row=2, column=1, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="SYSTEM10", command=lambda: system_wheel(10)).grid(row=3, column=1, sticky="ew", padx=2, pady=2)
ttk.Button(left, text="SYSTEM11", command=lambda: system_wheel(11)).grid(row=4, column=1, sticky="ew", padx=2, pady=2)

# last draw labels with resizable big draw number
last = ttk.LabelFrame(left, text="Last draw", padding=6)
last.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8,4))
_draw_font = tkfont.Font(family="Segoe UI", size=12, weight="bold")
drawno_label = ttk.Label(last, text="", font=_draw_font)
drawno_label.grid(row=0, column=0, sticky="w", pady=(0,2))
main_label  = ttk.Label(last, text="")
bonus_label = ttk.Label(last, text="")
first4_label= ttk.Label(last, text="")
pb_label    = ttk.Label(last, text="")
main_label.grid( row=1, column=0, sticky="w")
bonus_label.grid(row=2, column=0, sticky="w")
first4_label.grid(row=3, column=0, sticky="w")
pb_label.grid(   row=4, column=0, sticky="w")

def _resize_draw_font(event):
    try:
        w = max(1, event.width)
        size = max(10, min(36, w // 20))
        _draw_font.configure(size=size)
    except Exception:
        pass
last.bind("<Configure>", _resize_draw_font)

# money vars created before panels
spend   = tk.DoubleVar(value=0.0)
returns = tk.DoubleVar(value=0.0)
draw_number = tk.IntVar(value=0)

# expenditure panel above awards
money = ttk.LabelFrame(left, text="Expenditure", padding=6)
money.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4,4))
ttk.Label(money, text="Spent").grid(row=0, column=0, sticky="w")
ttk.Label(money, text="Prizes won").grid(row=1, column=0, sticky="w")
ttk.Label(money, text="BAL = Won − Spent").grid(row=2, column=0, sticky="w")
spent_val = ttk.Label(money, text="$0.00")
won_val   = ttk.Label(money, text="$0.00")
bal_val   = ttk.Label(money, text="$0.00", font=("Segoe UI", 10, "bold"))
spent_val.grid(row=0, column=1, sticky="e")
won_val.grid(  row=1, column=1, sticky="e")
bal_val.grid(  row=2, column=1, sticky="e")

def refresh_money_labels(*_):
    s = spend.get()
    w = returns.get()
    b = w - s  # BAL = Won - Spent
    spent_val.config(text=f"${s:,.2f}")
    won_val.config(  text=f"${w:,.2f}")
    bal_val.config(  text=f"${b:,.2f}")

spend.trace_add("write", refresh_money_labels)
returns.trace_add("write", refresh_money_labels)
refresh_money_labels()

# payout tallies with widened boxes and small incrementors
tally = ttk.LabelFrame(left, text="Payout tallies", padding=6)
tally.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(4,8))
tally.columnconfigure(0, weight=1)
tally.columnconfigure(1, weight=0)

paid_labels = {}
count_labels = {}  # per-division hit counters displayed as tiny labels

row_i = 0
for code in ["D1","D2","D3","D4","D5","D6","D7","S1","S2","S3","S4"]:
    lbl_money = ttk.Label(tally, text=f"{code} paid $0.00", width=26, anchor="w", padding=(6,2), relief="groove")
    lbl_money.grid(row=row_i, column=0, sticky="ew")
    paid_labels[code] = lbl_money
    lbl_hits = ttk.Label(tally, width=8, anchor="e", padding=(6,2), relief="groove")
    lbl_hits.grid(row=row_i, column=1, sticky="e", padx=(6,0))
    count_labels[code] = lbl_hits

    row_i += 1

total_label = ttk.Label(tally, text="Total returns $0.00", font=("Segoe UI", 10, "bold"))
total_label.grid(row=row_i, column=0, sticky="w", pady=(8,0))

# base numbers display
base_numbers_var = tk.StringVar(value="")
ttk.Label(left, textvariable=base_numbers_var, foreground="#444").grid(row=10, column=0, columnspan=2, sticky="w", padx=2, pady=(0,6))

# right ticket panel with small monosized font and yellow background
right = ttk.Frame(root, padding=6)
right.grid(row=1, column=1, sticky="nsew")
root.columnconfigure(1, weight=1)
root.rowconfigure(1, weight=1)
right.rowconfigure(0, weight=1)
right.columnconfigure(0, weight=1)

# small monospaced font and yellow background for the ticket
_fixed = tkfont.nametofont("TkFixedFont")
_fixed.configure(size=10)
ticket_text = tk.Text(right, width=44, height=28, font=_fixed, background="#fff9c4", wrap="none")
scroll = ttk.Scrollbar(right, orient="vertical", command=ticket_text.yview)
ticket_text.configure(yscrollcommand=scroll.set)
ticket_text.grid(row=0, column=0, sticky="nsew")
scroll.grid(row=0, column=1, sticky="ns")

# align Strike numbers to the east using a dynamic right-aligned tab stop
def _ticket_resize(event=None):
    try:
        w = ticket_text.winfo_width()
        ticket_text.configure(tabs=(f"{max(40, w-16)}p", "right"))
    except Exception:
        pass
_ticket_resize()
ticket_text.bind("<Configure>", _ticket_resize)

# status bar
status_var = tk.StringVar(value="Ready.")
status_bar = ttk.Label(root, textvariable=status_var, anchor="w", padding=4, relief="sunken")
status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")

# init variables and paint tallies
stats, paid = {}, {}
init_vars()
refresh_paid_labels()

root.mainloop()
