"""Champion Legend tests -- the third source of abilities.

Run: python3 rl/tests/test_legends.py

A legend is not a permanent and not a card in any zone a card can be played
from: 103.1 puts it in the Legend Zone from turn 1, where it stays for the
whole game. Three consequences shape every test here:

  * It has no `perms` row, so nothing that walks the board can see it. Its
    triggers are reached by `chain.fire_watchers` (which asks the champion
    after the permanents) and by `chain.fire_legend` at the player-events --
    conquer, hold, the Beginning Phase.
  * Its statics reach the board without a source standing on it, so
    `combat.static_reaches` answers them with `src_i = -1` and a seat.
  * It can be Exhausted (315.1.b readies it each Awaken) and Empowered
    (`state.legend_emp`), and both are costs its abilities charge.
"""
import sys
from dataclasses import replace

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from rl.config import Config
from rl.engine import actions as A
from rl.engine import chain, combat, phases
from rl.engine import resolve as rsv
from rl.engine.cardtable import full_table
from rl.engine.effects import SPECS, legend_abilities_for
from rl.engine.state import (MAIN, P_ALIVE, P_CARD, P_CTRL, P_LOC, P_READY,
                             RK_GEAR, RK_SHOWDOWN, RK_SPELL, RK_UNIT,
                             GameState, base_loc, bf_loc, legend_src)

T = full_table()
V1 = replace(Config().at_victory_score(8), units_only=False)

VANILLA = next(c for c in range(T.n) if T.names[c] == "Shipyard Skulker")


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def fresh(legend=None, seat=0, runes=6, hand=()):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = VANILLA
    for j, c in enumerate(hand):
        s.hand[seat, j] = c
    s.n_hand[seat] = len(hand)
    s.runes_ready[:, :] = runes
    s.phase, s.active, s.priority = MAIN, seat, seat
    if legend is not None:
        s.legend[seat] = T.id_of(legend)
        s.legend_ready[seat] = 1
    return s


def body(s, seat, loc, might=3, ready=False):
    i = s.add_permanent(VANILLA, seat, loc, ready=ready)
    if might != int(T.might[VANILLA]):
        s.base_might_ply[i] = int(s.ply)
        s.base_might_val[i] = might
    return i


def drain(s, limit=40):
    """Settle the chain, taking every offer, until nothing is pending."""
    for _ in range(limit):
        A._settle(s, T, V1)
        if s.n_chain == 0 and s.n_trig == 0 and not chain.decision_open(s) \
                and s.pend_slot < 0 and s.pend_may < 0:
            return
        who = A.acting_seat(s)
        if who < 0:
            return
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            return
        pick = next((a for a in legal if a.kind == A.A_ORDER),
                    next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)


def activations(s, seat=0):
    """The legend activations `seat` is offered right now."""
    return [a for a in A.legal_actions(s, T, V1, seat)
            if a.kind == A.A_ACTIVATE and A.is_legend_activate(a.arg)]


# ---------------------------------------------------------------------------
print("[1] restricted resources: an [Add] that says what it may pay for")

# Diana - Scorn of the Moon: "[Add] {1 energy}. Spend this Energy only during
# showdowns."
s = fresh("Diana - Scorn of the Moon")
acts = activations(s)
if not acts:
    die("diana", "her Exhaust ability should be offered on her own turn")
A.apply(s, T, V1, acts[0])
if int(s.pool_rstr_e[0, RK_SHOWDOWN]) != 1:
    die("diana", f"the Energy is restricted, got {list(s.pool_rstr_e[0])}")
if int(s.pool_energy[0]):
    die("diana", "...and it must not land in the general pool")
if int(s.legend_ready[0]):
    die("diana", "she exhausted to pay for it")
ok("Diana banks Energy that only a showdown may spend")

from rl.engine.cost import plan_payment, restricted_pools
SPELL = next(c for c in range(T.n)
             if T.is_type(c, "Spell") and int(T.energy[c]) == 1
             and int(T.power[c]) == 0)
s.runes_ready[0, :] = 0                     # nothing but the banked Energy
if restricted_pools(s, T, 0, SPELL, False) != (0, 0):
    die("diana", "outside a showdown that Energy pays for nothing")
s.showdown_bf, s.showdown_combat = 0, 1
if restricted_pools(s, T, 0, SPELL, False) != (1, 0):
    die("diana", "inside one it is spendable")
if plan_payment(s, T, 0, SPELL) is None:
    die("diana", "so a 1-Energy spell is affordable with no ready runes")
ok("...and it is unspendable until a showdown is open")

# Ornn - Fire Below the Mountain: "[Add] {any rune}. Use only to play gear or
# use gear abilities." Power, not Energy.
GEAR = next(c for c in range(T.n) if T.is_type(c, "Gear")
            and int(T.power[c]) == 1 and not T.is_token(c))
s = fresh("Ornn - Fire Below the Mountain")
A.apply(s, T, V1, activations(s)[0])
if int(s.pool_rstr_p[0, RK_GEAR]) != 1:
    die("ornn", f"{{any rune}} is Power: {list(s.pool_rstr_p[0])}")
# A payment plan lists the runes that must be RECYCLED for Power. The banked
# [A] covers the gear's single symbol, so the list comes back empty; the same
# cost on a spell still has to recycle a rune, which is the restriction.
SPELL_P = next(c for c in range(T.n) if T.is_type(c, "Spell")
               and int(T.power[c]) == int(T.power[GEAR])
               and int(T.energy[c]) <= int(T.energy[GEAR]))
if plan_payment(s, T, 0, GEAR) != []:
    die("ornn", f"the banked Power should cover the gear's symbol: "
                f"{plan_payment(s, T, 0, GEAR)}")
if plan_payment(s, T, 0, SPELL_P) == []:
    die("ornn", "...but a spell must still pay its own Power")
ok("Ornn's rune pays for gear and for nothing else")

# ---------------------------------------------------------------------------
print("\n[2] a legend's statics reach the board with no source standing on it")

s = fresh("Master Yi - Wuju Bladesman")
mine = body(s, 0, bf_loc(0))
base = int(T.might[VANILLA])
if combat.might(s, T, mine) != base:
    die("yi", "no combat, so nobody is defending alone")
foe = body(s, 1, bf_loc(0))
s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 1
if combat.might(s, T, mine) != base + 2:
    die("yi", f"defending alone is +2, got {combat.might(s, T, mine)}")
if combat.might(s, T, foe) != base:
    die("yi", "the ENEMY attacker gets nothing from my legend")
friend = body(s, 0, bf_loc(0))
if combat.might(s, T, mine) != base:
    die("yi", "a second defender ends 'alone' the instant it arrives")
ok("Master Yi's +2 follows whoever defends alone, live")

# ---------------------------------------------------------------------------
print("\n[3] player events reach the legend: the Beginning Phase and a spell")

# Jinx - Loose Cannon: "at the start of your Beginning Phase, draw 1 if you
# have one or fewer cards in your hand."
def turn_draw(legend, n_hand):
    """Cards gained over one `start_turn`, hand starting at `n_hand`."""
    s = fresh(legend)
    s.hand[0, :n_hand] = VANILLA
    s.n_hand[0] = n_hand
    phases.start_turn(s, T, V1)
    drain(s)
    return int(s.n_hand[0]) - n_hand


plain_empty = turn_draw(None, 0)            # the Draw Phase on its own
if turn_draw("Jinx - Loose Cannon", 0) != plain_empty + 1:
    die("jinx", f"an empty hand refills by 1 more than the Draw Phase "
                f"({plain_empty})")
if turn_draw("Jinx - Loose Cannon", 3) != turn_draw(None, 3):
    die("jinx", "a full hand draws nothing extra")
ok("Jinx refills an empty hand at the start of the turn, and only then")

# Lux - Lady of Luminosity: "when you play a spell that costs {5 energy} or
# more, draw 1."
BIG = next(c for c in range(T.n) if T.is_type(c, "Spell")
           and int(T.energy[c]) >= 5 and int(T.power[c]) == 0
           and T.names[c] in SPECS and not SPECS[T.names[c]].targets)
def play_spell(legend, card):
    s = fresh(legend, hand=[card], runes=9)
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    drain(s)
    return int(s.n_hand[0])


if play_spell("Lux - Lady of Luminosity", BIG) != play_spell(None, BIG) + 1:
    die("lux", "playing a 5+ Energy spell draws 1 more than playing it alone")
SMALL = next(c for c in range(T.n) if T.is_type(c, "Spell")
             and int(T.energy[c]) <= 2 and int(T.power[c]) == 0
             and T.names[c] in SPECS and not SPECS[T.names[c]].targets)
if play_spell("Lux - Lady of Luminosity", SMALL) != play_spell(None, SMALL):
    die("lux", f"...and nothing off a {int(T.energy[SMALL])}-Energy spell")
ok(f"Lux draws off a big spell ({T.names[BIG]}) and not a small one")

# ---------------------------------------------------------------------------
print("\n[4] conquer and hold reach the champion, once for the player")

def conquer_with(legend, n_units):
    """Take an uncontrolled battlefield with `n_units` and settle everything."""
    s = fresh(legend)
    s.bf_ctrl[0] = -1
    movers = [body(s, 0, base_loc(0), ready=True) for _ in range(n_units)]
    A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
    for m_ in movers:
        A.apply(s, T, V1, A.Action(A.A_ADD, m_))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    drain(s)
    return s


s = conquer_with("Garen - Might of Demacia", 4)
if int(s.n_hand[0]) != 2:
    die("garen", f"4 units at the conquered ground draws 2, got "
                 f"{int(s.n_hand[0])}")
s = conquer_with("Garen - Might of Demacia", 3)
if int(s.n_hand[0]) != 0:
    die("garen", f"3 units draws nothing, got {int(s.n_hand[0])}")
ok("Garen counts the units at the battlefield he just took")

# Poppy - Keeper of the Hammer: "when you hold, gain 1 XP" and an XP sink.
s = fresh("Poppy - Keeper of the Hammer")
s.bf_ctrl[0] = 0
body(s, 0, bf_loc(0))
phases.score_holds(s, V1, T)
drain(s)
if int(s.xp[0]) != 1:
    die("poppy", f"holding gives the champion 1 XP, got {int(s.xp[0])}")
if activations(s):
    die("poppy", "her draw costs 3 XP and must not be offered at 1")
s.xp[0] = 3
acts = activations(s)
if not acts:
    die("poppy", "at 3 XP the draw is available")
A.apply(s, T, V1, acts[0])
drain(s)
if int(s.xp[0]) != 0 or int(s.n_hand[0]) != 1:
    die("poppy", f"3 XP for a card: xp={int(s.xp[0])} hand={int(s.n_hand[0])}")
ok("Poppy banks XP off a Hold and spends 3 of it for a card")

# Vex - Gloomist: the Exhaust is an OPTIONAL cost inside the trigger.
s = fresh("Vex - Gloomist")
s.bf_ctrl[0] = 0
body(s, 0, bf_loc(0))
phases.score_holds(s, V1, T)
A._settle(s, T, V1)
offers = [a for a in A.legal_actions(s, T, V1, 0)
          if a.kind in (A.A_ACCEPT, A.A_DECLINE)]
if len(offers) != 2:
    die("vex", f"the may-exhaust should be a real choice: {offers}")
A.apply(s, T, V1, next(a for a in offers if a.kind == A.A_DECLINE))
drain(s)
if int(s.n_hand[0]) or not int(s.legend_ready[0]):
    die("vex", "declining draws nothing and leaves her ready")
s = fresh("Vex - Gloomist")
s.bf_ctrl[0] = 0
body(s, 0, bf_loc(0))
phases.score_holds(s, V1, T)
drain(s)                                    # `drain` accepts what it is offered
if int(s.n_hand[0]) != 1 or int(s.legend_ready[0]):
    die("vex", f"accepting draws 1 and exhausts her: hand={int(s.n_hand[0])} "
               f"ready={int(s.legend_ready[0])}")
ok("Vex's 'you may exhaust me' is paid by the champion, or declined")

# ---------------------------------------------------------------------------
print("\n[5] watchers: a play, a stun, a Might threshold")

s = fresh("Rengar - Pridestalker", hand=[VANILLA])
mine = body(s, 0, base_loc(0))
base = combat.might(s, T, mine)
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
A._settle(s, T, V1)
tgt = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if not tgt:
    die("rengar", "playing a unit should ask where the +1 goes")
A.apply(s, T, V1, next(a for a in tgt if a.arg == mine))
drain(s)
if combat.might(s, T, mine) != base + 1:
    die("rengar", f"+1 Might this turn, got {combat.might(s, T, mine)}")
ok("Rengar hands out +1 Might when a unit is played")

s = fresh("Leona - Radiant Dawn")
mine = body(s, 0, bf_loc(0))
foe = body(s, 1, bf_loc(0))
from rl.engine.state import F_BUFFED
s.stun(foe)
chain.fire_watchers(s, T, 0, __import__("rl.engine.effects",
                                        fromlist=["x"]).TR_STUN, subj=foe)
drain(s)
if not s.has_flag(mine, F_BUFFED):
    die("leona", "stunning an enemy buffs one of my units")
ok("Leona buffs a friendly unit when an enemy is stunned")

# ---------------------------------------------------------------------------
print("\n[6] the Empowered status on a champion (441)")

s = fresh("Ambessa - Matriarch of War")
u = body(s, 0, base_loc(0))
if activations(s):
    die("ambessa", "her ability costs a status she does not have yet")
chain.fire_empowered(s, T, u)               # something else became Empowered
drain(s)
if not s.src_empowered(legend_src(0)):
    die("ambessa", "'when you empower something else, empower me'")
if int(s.legend_emp[1]):
    die("ambessa", "the status is per seat, not shared")
acts = activations(s)
if not acts:
    die("ambessa", "now 'Disempower me, {any rune}, Exhaust: ready a unit' is on")
exhausted = body(s, 0, base_loc(0))
s.perms[exhausted, P_READY] = 0
A.apply(s, T, V1, acts[0])
tg = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
A.apply(s, T, V1, next(a for a in tg if a.arg == exhausted))
drain(s)
if s.src_empowered(legend_src(0)):
    die("ambessa", "the Disempower is a COST and is spent at finalization")
if not int(s.perms[exhausted, P_READY]):
    die("ambessa", "...and the unit is readied")
ok("Ambessa empowers herself off the board and spends the status again")

# Akali - Rogue Assassin: an [Action] ability used INSIDE a showdown.
def akali_retreat(empowered):
    s = fresh("Akali - Rogue Assassin")
    mine = body(s, 0, bf_loc(0))
    s.perms[mine, P_READY] = 0              # it fought; it is exhausted
    body(s, 1, bf_loc(0))
    s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 1
    s.legend_emp[0] = int(empowered)
    acts = [a for a in activations(s)]
    if not acts:
        die("akali", "an [Action] ability belongs in a showdown window (151.2)")
    A.apply(s, T, V1, acts[-1])
    A.apply(s, T, V1, A.Action(A.A_TARGET, mine))
    drain(s)
    return s, mine


s, mine = akali_retreat(False)
if int(s.perms[mine, P_LOC]) != base_loc(0):
    die("akali", "the unit is pulled out of the fight to its base")
if int(s.perms[mine, P_READY]):
    die("akali", "un-Empowered, it comes home exhausted")
s, mine = akali_retreat(True)
if not int(s.perms[mine, P_READY]):
    die("akali", "[Empowered] readies it as well")
ok("Akali retreats a unit mid-showdown, readying it only while Empowered")

# Jayce - Defender of Tomorrow: [Empower] is an activated ability of its own,
# and 827.1.c.1 stops it being used twice.
GEAR2 = next(c for c in range(T.n) if T.is_type(c, "Gear")
             and not T.is_token(c) and not T.is_type(c, "Unit"))
s = fresh("Jayce - Defender of Tomorrow", runes=9)
g1 = s.add_permanent(GEAR2, 0, base_loc(0))
s.perms[g1, P_READY] = 0
def offered_indices(s):
    return sorted(A.legend_ability_index(a.arg) for a in activations(s))


if offered_indices(s) != [0, 1]:
    die("jayce", f"[Empower] and the plain ready: {offered_indices(s)}")
A.apply(s, T, V1, activations(s)[0])
drain(s)
if not s.src_empowered(legend_src(0)):
    die("jayce", "[Empower] {2}{any}{any} empowers the champion")
if offered_indices(s) != [1, 2]:
    die("jayce", f"827.1.c.1 -- no second [Empower], and the [Empowered] "
                 f"ability is on instead: {offered_indices(s)}")
ok("Jayce's [Empower] is an ability, payable once, and unlocks the other")

# ---------------------------------------------------------------------------
print("\n[7] events the engine had no trigger for: a rune, a banish, a play")

# Sivir - Battle Mistress: "when you recycle a rune, you may exhaust me to
# play a Gold gear token exhausted." Recycling a rune is how Power is paid.
s = fresh("Sivir - Battle Mistress")
s.recycle_rune(0, 0)                        # as paying a Power cost does
drain(s)
gold = [i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1
        and T.names[int(s.perms[i, P_CARD])].startswith("Gold")]
if not gold:
    die("sivir", "416.1.b -- recycling a rune is her trigger")
if int(s.legend_ready[0]):
    die("sivir", "she exhausted for it")
if int(s.perms[gold[0], P_READY]):
    die("sivir", "the Gold token arrives exhausted")
ok("Sivir turns a recycled rune into a Gold token")

# Zed - Master of Shadows: "when you banish a card you own, empower me."
s = fresh("Zed - Master of Shadows")
s.banish_card(0, VANILLA)
drain(s)
if not s.src_empowered(legend_src(0)):
    die("zed", "banishing a card you own empowers him")
if not activations(s):
    die("zed", "...which turns on his [Action] Disempower ability")
ok("Zed empowers off a banish and unlocks his Action")

# Yordle, Kennen - Heart of the Tempest: "when you play a card from anywhere
# other than your hand, empower me."
s = fresh("Yordle, Kennen - Heart of the Tempest")
s.trash[0, 0], s.n_trash[0] = VANILLA, 1
combat.record_effect_play(s, T, 0, VANILLA, base_loc(0), 0)
drain(s)
if not s.src_empowered(legend_src(0)):
    die("kennen", "a play from the trash is a play from outside your hand")
s2 = fresh("Yordle, Kennen - Heart of the Tempest", hand=[VANILLA])
A.apply(s2, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s2, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
drain(s2)
if s2.src_empowered(legend_src(0)):
    die("kennen", "...and a play FROM the hand is not")
ok("Kennen empowers on a non-hand play only")

# ---------------------------------------------------------------------------
print("\n[8] the two that change a zone: a battlefield, and Banishment")

# Ivern - Green Father: "replace that battlefield with a Brush token."
s = fresh("Ivern - Green Father")
s.bf_card[0] = T.id_of("Seat of Power")
s.bf_ctrl[0] = 0
held = body(s, 0, bf_loc(0))
phases.score_holds(s, V1, T)
drain(s)
if T.names[int(s.bf_card[0])] != "Brush":
    die("ivern", f"the ground becomes Brush, got {T.names[int(s.bf_card[0])]}")
if int(s.bf_replaced[0]) != T.id_of("Seat of Power"):
    die("ivern", "...and remembers what it replaced")
if int(s.bf_ctrl[0]) != 0 or int(s.perms[held, P_LOC]) != bf_loc(0):
    die("ivern", "control and the units standing there are untouched")
if combat.might(s, T, held) != int(T.might[VANILLA]):
    die("ivern", "a Skulker is none of Brush's five tags, so no +1")
ok("Ivern swaps a battlefield for Brush, keeping the ground itself")

# Jhin - Virtuoso: four big spells banished, then all four come back.
# 419.4.a -- the trigger waits for each spell to RESOLVE, so the fixture spell's
# own effect happens too; one that touches runes or the trash would muddy the
# counts below.
BIG4 = next(c for c in range(T.n) if T.is_type(c, "Spell")
            and int(T.energy[c]) >= 4 and int(T.power[c]) == 0
            and T.names[c] in SPECS and not SPECS[T.names[c]].targets
            and not any(w in T.raw_text[c].lower()
                        for w in ("rune", "trash", "discard", "recycle")))
s = fresh("Jhin - Virtuoso", runes=9)
s.hand[0, :4] = BIG4
s.n_hand[0] = 4
s.rune_deck[0, :6] = 0
s.rune_left[0] = 6
runes0 = int(s.runes_ready[0].sum() + s.runes_spent[0].sum())
for rep in range(4):
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    drain(s)
    if rep < 3 and int(s.legend_pile_n[0]) != rep + 1:
        die("jhin", f"spell {rep} should be on the pile")
if int(s.legend_pile_n[0]) or int(s.n_banished[0]):
    die("jhin", "at four the pile empties and Banishment gives them up")
if int(s.n_trash[0]) != 4:
    die("jhin", f"all four go to the trash, got {int(s.n_trash[0])}")
if int(s.runes_ready[0].sum() + s.runes_spent[0].sum()) != runes0 + 4:
    die("jhin", "...and four runes are channelled")
ok("Jhin banishes four spells with him, then cashes them in")

print("\n\033[32mall legend tests passed\033[0m")
