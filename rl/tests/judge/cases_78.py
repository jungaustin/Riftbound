"""RiftJudge batch 78 -- unused questions from 6480-6600."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_READY
from rl.engine.effects import unpack_trash


@case(6596, "a Showdown with no Combat is still a Showdown to answer in")
def _():
    need("Shakedown", "Watchful Sentry", "Trifarian War Camp")
    s = fresh(runes=32)
    give(s, 1, "Shakedown")
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = -1                              # nobody's: no defender, no Combat
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, ws)
    assert int(s.showdown_bf) == 0 and not int(s.showdown_combat), \
        "323.14: contesting open ground still stages a Showdown"
    pass_priority_to(s, 1)                         # 346: Focus reaches them
    assert A.A_PLAY in kinds(s, 1), "and 347.1 lets them answer in it"
    cast(s, 1, "Shakedown", ws)
    assert int(s.n_chain) == 1, "the Reaction is on the Chain"


@case(6592, "a move trigger whose unit is gone has no 'here' to recruit at")
def _():
    need("Noxian Drummer", "Shakedown")
    s = fresh(runes=32)
    give(s, 1, "Shakedown")
    s.bf_ctrl[0] = 0
    nd = s.add_permanent(T.id_of("Noxian Drummer"), 0, base_loc(0), ready=True)
    before = len(tokens(s, 0))
    act(s, A.A_DECLARE, bf_loc(0), 0)
    act(s, A.A_ADD, nd, 0)
    act(s, A.A_COMMIT, None, 0)
    assert int(s.n_chain) >= 1 or int(s.n_trig) >= 1, "the move trigger is queued"
    pass_priority_to(s, 1)
    cast(s, 1, "Shakedown", nd)
    # Its controller may hand over two cards instead; they take the 6 damage.
    run(s, picking(accept=False), limit=60)
    assert not perm_of(s, "Noxian Drummer", 0), "6 damage on a 3 Might unit"
    assert len(tokens(s, 0)) == before, \
        "359.3.e: the Recruit had no 'here' left, so it never arrived"


@case(6591, "a Might floor is where the next bonus counts up from")
def _():
    need("Smoke Screen", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen")
    give(s, 1, "Discipline")
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 3)
    mine = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 1, mine)                          # a Showdown, so both get Focus
    cast(s, 0, "Smoke Screen", u)
    drain(s)
    assert combat.might(s, T, u) == 1, "-4 from 3, floored at 1"
    cast(s, 1, "Discipline", u)
    drain(s)
    assert combat.might(s, T, u) == 3, "+2 on top of the floor, not on top of -1"


@case(6590, "Pack of Wonders returns only your own")
def _():
    need("Pack of Wonders")
    s = fresh(runes=32)
    pw = s.add_permanent(T.id_of("Pack of Wonders"), 0, base_loc(0))
    mine = body(s, 0, base_loc(0), 3)
    s.bf_ctrl[1] = 1
    theirs = body(s, 1, bf_loc(1), 3)
    act(s, A.A_ACTIVATE, None, 0)
    act(s, A.A_TARGET, 0, 0)                       # mode 0: a gear or unit
    offered = targets_offered(s, 0)
    assert mine in offered, "a friendly unit is fair game"
    assert theirs not in offered, "'another FRIENDLY gear, unit, or facedown card'"
    assert pw not in offered, "and 'another' excludes itself"


@case(6586, "a unit played from hidden resolves with no window under it")
def _():
    need("Pakaa Cub", "Void Seeker")
    s = fresh(runes=32)
    give(s, 0, "Void Seeker")
    s.bf_ctrl[0] = 0
    keep = body(s, 0, bf_loc(0), 3)                # holds the ground for the hide
    hidden_at(s, 0, 0, "Pakaa Cub")
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 5)
    _next_own_turn(s)
    cast(s, 0, "Void Seeker", foe)                 # their own Chain item to answer
    assert A.A_PLAY_HIDDEN in kinds(s, 0), "811.1.b: it reacts from the next turn"
    before = int(s.n_chain)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    assert perm_of(s, "Pakaa Cub", 0), "337.2: a unit resolves the moment it finalizes"
    assert int(s.n_chain) == before, "so it never waits on the Chain"


@case(6577, "a death that is replaced is not a death, so no [Deathknell]")
def _():
    need("Zhonya's Hourglass", "Watchful Sentry", "Hextech Ray")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Hextech Ray")
    s.bf_ctrl[0] = 0
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 0, bf_loc(0), ready=True)
    zh = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = zh                          # armed by its own play trigger
    before = int(s.n_hand[0])
    cast(s, 0, "Hextech Ray", ws)                  # 3 into a 1 Might unit
    run(s, picking(accept=True), limit=60)
    assert alive(s, ws) and int(s.perms[ws, P_LOC]) == base_loc(0), \
        "the Hourglass recalled it instead"
    assert not alive(s, zh), "and died for it"
    assert int(s.n_hand[0]) == before - 1, \
        "so [Deathknell] never happened -- the Ray left, nothing was drawn"


@case(6571, "the Sprite's own expiry is a window, and the Hold survives it")
def _():
    need("Sprite Call", "Blastcone Fae")
    s = fresh()
    rune_deck(s)
    spr = _sprite_at(s, 0, 0)
    hidden_at(s, 0, 0, "Blastcone Fae")
    pts = int(s.points[0])
    _next_own_turn(s)
    assert int(s.n_chain) >= 1, "[Temporary] is on the Chain"
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(spr, accept=True), limit=60)
    assert not alive(s, spr), "816.1.c takes the token"
    assert perm_of(s, "Blastcone Fae", 0), "but the Fae arrived first"
    assert int(s.points[0]) > pts, "so the battlefield was still held (315.2.b)"


@case(6570, "two instances of [Shield] add up")
def _():
    need("Shen - Kinkou", "Fortified Position")
    s = fresh(runes=32)
    s.bf_card[1] = T.id_of("Fortified Position")
    s.bf_ctrl[1] = 0
    sh = s.add_permanent(T.id_of("Shen - Kinkou"), 0, bf_loc(1))
    printed = int(T.might[T.id_of("Shen - Kinkou")])
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    give(s, 0, "Discipline")                       # a live answer holds the window
    attack(s, 1, 1, foe)
    drain(s)
    assert combat.might(s, T, sh) == printed + 2 + 2, \
        "[Shield 2] printed and [Shield 2] from the ground, both while defending"


@case(6567, "'the first time each turn' is counted per player")
def _():
    need("The Dreaming Tree", "Discipline", "Primal Strength")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    theirs = body(s, 1, bf_loc(0), 3)
    give(s, 0, "Discipline")
    give(s, 1, "Primal Strength")
    h0, h1 = int(s.n_hand[0]), int(s.n_hand[1])
    s.active = s.priority = 1
    cast(s, 1, "Primal Strength", theirs)
    drain(s)
    cast(s, 0, "Discipline", mine)
    drain(s)
    # Each spell draws its own caster 1 for itself, so the Tree's draw is the
    # one card over that: Primal Strength draws nothing, Discipline draws 1.
    assert int(s.n_hand[1]) == h1 - 1 + 1, "their spell, their first time: they draw"
    assert int(s.n_hand[0]) == h0 - 1 + 1 + 1, "and so do I, on my own first time"


@case(6566, "a hidden card is not on the board for a mass Might effect")
def _():
    need("Thousand-Tailed Watcher", "Pakaa Cub")
    s = fresh(runes=32)
    give(s, 0, "Thousand-Tailed Watcher")
    s.bf_ctrl[1] = 1
    fd = hidden_at(s, 1, 1, "Pakaa Cub")
    enemy = body(s, 1, bf_loc(1), 4)
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s, limit=40)
    assert combat.might(s, T, enemy) == 1, "-3 from 4, floored at 1"
    assert int(s.fd_card[fd]) == T.id_of("Pakaa Cub"), \
        "and the facedown card is untouched -- it is not a unit yet"


@case(6562, "Spectral Matron reads the printed cost, not the one you pay")
def _():
    need("Spectral Matron", "Cruel Patron", "Watchful Sentry")
    s = fresh(runes=32)
    give(s, 0, "Spectral Matron")
    s.trash[0, 0] = T.id_of("Cruel Patron")
    s.trash[0, 1] = T.id_of("Watchful Sentry")
    s.n_trash[0] = 2
    body(s, 0, base_loc(0), 3)                     # a friendly unit for the kill cost
    cast(s, 0, "Spectral Matron", base_loc(0))
    offered = targets_offered(s, 0)
    names = {T.names[unpack_trash(i)[1]] for i in offered}
    assert "Watchful Sentry" in names, "{2 energy} is under the limit"
    assert "Cruel Patron" not in names, \
        "820.1: the {4 energy} printed on it is still what the limit reads"


@case(6556, "Tianna stops scoring, and burning out is not scoring")
def _():
    need("Tianna Crownguard")
    s = fresh()
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1))
    pts = int(s.points[1])
    s.n_deck[0] = 0                                # nothing left to draw
    s.deck_ptr[0] = 0
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=60)
    assert int(s.points[1]) == pts + 1, \
        "156.2: burning out GAINS the opponent a point, it does not score one"


@case(6555, "discarded by the move, retrieved by the conquer")
def _():
    need("Traveling Merchant", "Super Mega Death Rocket!")
    s = fresh(runes=32)
    give(s, 0, "Super Mega Death Rocket!", "Discipline")
    s.bf_ctrl[0] = -1
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, tm)
    run(s, picking(hand_index(s, 0, "Super Mega Death Rocket!"), accept=True),
        limit=80)
    assert int(s.bf_ctrl[0]) == 0, "the ground is taken"
    assert T.id_of("Super Mega Death Rocket!") in [
        int(s.hand[0, i]) for i in range(int(s.n_hand[0]))], \
        "and its own conquer trigger bought it back out of the trash"


@case(6552, "a continuous reduction is still there after a bonus is added")
def _():
    need("Leona - Zealot", "Rune Prison", "Primal Strength")
    s = fresh(runes=32)
    give(s, 0, "Rune Prison", "Primal Strength")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Leona - Zealot"), 0, bf_loc(0), ready=True)
    foe = body(s, 1, bf_loc(0), 2)
    cast(s, 0, "Rune Prison", foe)
    drain(s)
    assert combat.might(s, T, foe) == 1, "stunned: -8 from 2, floored at 1"
    cast(s, 0, "Primal Strength", foe)
    drain(s)
    assert combat.might(s, T, foe) == 1, \
        "477.3.e: the +7 goes on first and her passive -8 still comes last"


@case(6546, "a lost target takes its own instruction with it")
def _():
    need("Hidden Blade", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Hidden Blade", "Gust")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 3)
    h1 = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", victim)
    cast(s, 0, "Gust", victim)                     # answering their own spell
    run(s, limit=60)
    assert not alive(s, victim), "it left the board for their hand"
    assert int(s.n_hand[1]) == h1 + 1, \
        "359.3.e.2: no target, so no controller, so nobody draws 2"


@case(6538, "an instruction that is not about the target still happens")
def _():
    need("Void Seeker", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Void Seeker", "Gust")
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 3)
    h0 = int(s.n_hand[0])
    cast(s, 0, "Void Seeker", victim)
    cast(s, 0, "Gust", victim)                     # the target is gone first
    run(s, limit=60)
    assert not alive(s, victim), "returned to hand in response"
    assert int(s.n_hand[0]) == h0 - 2 + 1, \
        "359.3.e.1: the spell resolves and 'Draw 1' is not about the target"


@case(6532, "damage stays marked until a Combat ends or the turn does")
def _():
    need("Flurry of Blades", "Watchful Sentry")
    s = fresh(runes=32)
    give(s, 0, "Flurry of Blades", "Discipline")
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(1), 1)
    b = body(s, 1, bf_loc(1), 2)
    mine = body(s, 0, base_loc(0), 9, ready=True)
    cast(s, 0, "Flurry of Blades")
    drain(s)
    assert not alive(s, a), "1 damage kills the 1 Might unit"
    assert alive(s, b) and int(s.perms[b, P_DMG]) == 1, "and marks the other"
    attack(s, 0, 1, mine)
    fight(s, limit=80)
    assert not alive(s, b), \
        "317.2.b: nothing healed in between, so the combat only had to add 1"


@case(6524, "less Might is less damage needed")
def _():
    need("Stupefy", "Void Seeker")
    s = fresh(runes=32)
    give(s, 0, "Void Seeker", "Stupefy")
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 5)
    cast(s, 0, "Void Seeker", u)
    drain(s)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 4, "4 into 5 Might is not lethal"
    cast(s, 0, "Stupefy", u)
    drain(s)
    assert not alive(s, u), \
        "143.2.a is continuous: 4 damage on 4 Might is lethal the moment it is"


@case(6519, "'when you play a card from [Hidden]' does not say 'here'")
def _():
    need("Ember Monk", "Sprite Call")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    em = s.add_permanent(T.id_of("Ember Monk"), 0, bf_loc(0))
    body(s, 0, bf_loc(1), 3)                       # 190.4.c: hold the other ground
    hidden_at(s, 0, 1, "Sprite Call")              # the OTHER battlefield
    printed = int(T.might[T.id_of("Ember Monk")])
    _next_own_turn(s)
    assert A.A_PLAY_HIDDEN in kinds(s, 0), "hidden cards react from the next turn"
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, limit=60)
    assert combat.might(s, T, em) == printed + 2, \
        "no 'here' clause, so any battlefield's hidden play feeds him"


@case(6505, "an [Action] can never be an answer")
def _():
    need("Void Seeker", "Primal Strength")
    s = fresh(runes=32)
    give(s, 0, "Void Seeker")
    give(s, 1, "Primal Strength", "Discipline")
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 5)
    cast(s, 0, "Void Seeker", u)
    pass_priority_to(s, 1)
    plays = hand_plays(s, 1)
    assert "Discipline" in plays, "309.1: a [Reaction] answers a Chain item"
    assert "Primal Strength" not in plays, \
        "309.1.a: an [Action] needs an Open State, and this is not one"


@case(6513, "a Cleanup follows the resolution, with no window in between")
def _():
    need("Stupefy", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Stupefy")
    give(s, 1, "Gust")
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 4)
    s.perms[u, P_DMG] = 3
    cast(s, 0, "Stupefy", u)
    drain(s)
    assert not alive(s, u), "3 damage on 3 Might: 143.2.a kills it in the Cleanup"
    assert T.id_of("Gust") in [int(s.hand[1, i]) for i in range(int(s.n_hand[1]))], \
        "323.4-323.5: the owner never got a window to Gust it out"
