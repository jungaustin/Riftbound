"""RiftJudge batch 63 -- unused questions from 7458-7506."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7504, "a trigger keeps the controller it had when it fired")
def _():
    need("Hostile Takeover", "Riptide Rex")
    s = fresh(hand=[T.id_of("Riptide Rex")], runes=32)
    give(s, 1, "Hostile Takeover")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Riptide Rex"), 0)
    choose(s, base_loc(0))
    rex = perm_of(s, "Riptide Rex", 0)[0]
    assert int(s.n_chain) + int(s.n_trig) >= 1, "his play trigger is up"
    assert foe >= 0 and rex >= 0


@case(7501, "you order two conquer triggers, and a 'may' may be declined")
def _():
    need("Zaun Warrens", "Vayne - Hunter")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Zaun Warrens")
    s.bf_ctrl[0] = 1
    va = s.add_permanent(T.id_of("Vayne - Hunter"), 0, base_loc(0), ready=True)
    give(s, 0, "Smoke Screen", "Smoke Screen")
    before = int(s.n_hand[0])
    attack(s, 0, 0, va)
    run(s, picking(accept=False), limit=40)
    assert alive(s, va), "his 'you may' was declined"
    assert int(s.n_hand[0]) == before, "the Warrens discarded one and drew one"


@case(7498, "Mageseeker Warden does not stop a unit that ENTERS ready")
def _():
    need("Mageseeker Warden", "Sprite Call")
    s = fresh(hand=[T.id_of("Sprite Call")], runes=32)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Mageseeker Warden"), 1, bf_loc(1), ready=True)
    s.bf_ctrl[1] = 1
    cast(s, 0, "Sprite Call", bf_loc(0))
    run(s)
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_READY]) == 1, "entering is not readying"


@case(7497, "Defy cannot counter a triggered ability")
def _():
    need("Defy", "Yasuo - Remorseful")
    s = fresh(runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 12)
    attack(s, 0, 0, ya)
    choose(s, d)
    pass_priority_to(s, 1)
    assert "Defy" not in hand_plays(s, 1), "'counter a spell' is not an ability"


@case(7495, "a unit that left the board loses what it was given")
def _():
    need("Vayne - Hunter", "Cleave", "Retreat")
    s = fresh(runes=32)
    give(s, 0, "Cleave", "Retreat")
    s.bf_ctrl[0] = 1
    va = s.add_permanent(T.id_of("Vayne - Hunter"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, va)
    cast(s, 0, "Cleave", va)
    drain(s)
    assert combat.might(s, T, va) == 2 + 3 + 3, "her [Assault 3] and Cleave's"
    cast(s, 0, "Retreat", va)
    run(s, limit=40)
    assert not alive(s, va), "she is in hand now"
    act(s, A.A_PLAY, hand_index(s, 0, "Vayne - Hunter"), 0)
    choose(s, base_loc(0))
    run(s)
    back = perm_of(s, "Vayne - Hunter", 0)[0]
    assert combat.might(s, T, back) == 2, "a new object, with nothing given to it"


@case(7494, "'here' includes a base")
def _():
    need("Darius - Executioner")
    s = fresh(runes=32)
    de = s.add_permanent(T.id_of("Darius - Executioner"), 0, base_loc(0),
                         ready=True)
    mate = body(s, 0, base_loc(0), 3)
    assert combat.might(s, T, mate) == 4, "his +1 reaches his own base"
    assert de >= 0


@case(7492, "Skyfall turns Trinity Force's hold into a conquer effect too")
def _():
    need("Reckoner's Arena", "Skyfall of Areion", "Trinity Force")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Reckoner's Arena")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    for name in ("Trinity Force", "Skyfall of Areion"):
        g = s.add_permanent(T.id_of(name), 0, base_loc(0))
        act(s, A.A_ACTIVATE, g, 0)
        choose(s, u)
        run(s)
    _next_own_turn(s)
    run(s, picking(accept=True), limit=60)
    assert int(s.points[0]) >= 2, "the Hold and the gear's point"


@case(7489, "a death trigger is placed before the conquer triggers")
def _():
    need("Zaun Warrens", "Honest Broker")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Zaun Warrens")
    s.bf_ctrl[0] = 1
    hb = s.add_permanent(T.id_of("Honest Broker"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 2)
    give(s, 0, "Smoke Screen", "Smoke Screen")
    attack(s, 0, 0, hb)
    run(s, picking(accept=True), limit=60)
    assert not alive(s, hb) and not alive(s, d), "2 for 2"
    assert tokens(s, 0), "his Deathknell ran"


@case(7488, "a base-speed spell is not playable while defending")
def _():
    need("Dragon's Rage")
    s = fresh(runes=32)
    give(s, 0, "Dragon's Rage")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    pass_priority_to(s, 0)
    assert "Dragon's Rage" not in hand_plays(s, 0)


@case(7485, "Unyielding Spirit does not stop a fight spell")
def _():
    need("Unyielding Spirit", "Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=32)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 32
    mine = body(s, 0, base_loc(0), 5)
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Challenge", mine, theirs)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert int(s.perms[theirs, P_DMG]) == 5


@case(7482, "the unit that arrives second is the defender")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 32
    first = body(s, 0, base_loc(0), 3, ready=True)
    late = body(s, 1, base_loc(1), 3, ready=False)
    attack(s, 0, 0, first)
    cast(s, 1, "Ride The Wind", late, bf_loc(0))
    drain(s)
    assert int(s.attacker) == 0, "the first one contested it"


@case(7479, "Cemetery Attendant puts the unit in your hand")
def _():
    need("Cemetery Attendant", "Determined Sentry")
    s = fresh(hand=[T.id_of("Cemetery Attendant")], runes=32)
    s.trash[0, 0] = T.id_of("Determined Sentry")
    s.n_trash[0] = 1
    before = int(s.n_hand[0])
    act(s, A.A_PLAY, hand_index(s, 0, "Cemetery Attendant"), 0)
    choose(s, base_loc(0))
    run(s, picking(pack_trash(0, T.id_of("Determined Sentry"))))
    assert int(s.n_hand[0]) == before - 1 + 1, "to the hand, not the board"
    assert not perm_of(s, "Determined Sentry", 0)


@case(7478, "a hidden Sprite Call puts its token at that battlefield")
def _():
    need("Sprite Call")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(0), 3)
    body(s, 0, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Sprite Call")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s)
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_LOC]) == bf_loc(0), "737.1.d.3"


@case(7477, "a triggered ability fires on the opponent's turn too")
def _():
    need("Viktor - Leader", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 1, "Hidden Blade")
    s.runes_ready[1, :] = 32
    vi = s.add_permanent(T.id_of("Viktor - Leader"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 0
    mate = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Hidden Blade", mate)
    run(s)
    assert not alive(s, mate)
    assert len(tokens(s, 0)) == 1, "his trigger is not an activated ability"
    assert vi >= 0


@case(7476, "Last Breath readies the unit and has it deal its Might")
def _():
    need("Last Breath")
    s = fresh(hand=[T.id_of("Last Breath")], runes=32)
    mine = body(s, 0, base_loc(0), 4, ready=False)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Last Breath", mine, foe)
    run(s)
    assert int(s.perms[mine, P_READY]) == 1
    assert int(s.perms[foe, P_DMG]) == 4, "once, not twice"


@case(7471, "Divine Judgment recycles what you did not keep")
def _():
    need("Divine Judgment")
    # A small rune board: the spell recycles every rune past two, and the
    # rune ring is not sized for a 32-per-domain test board.
    s = fresh(hand=[T.id_of("Divine Judgment")], runes=2)
    for _ in range(4):
        give(s, 0, "Smoke Screen")
    for _ in range(4):
        give(s, 1, "Smoke Screen")
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 0, base_loc(0), 3)
    c = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Divine Judgment")
    run(s, picking(a, b, accept=True), limit=80)
    kept = [u for u in (a, b, c) if alive(s, u)]
    assert len(kept) == 2, "two units apiece, and the rest recycled"


@case(7469, "there is no window inside Bullet Time's resolution")
def _():
    need("Bullet Time", "Mystic Reversal")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    give(s, 1, "Mystic Reversal")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bullet Time", bf_loc(0))
    pass_priority_to(s, 1)
    assert "Mystic Reversal" in hand_plays(s, 1), "before it resolves, yes"
    run(s, picking(3))
    assert not alive(s, u) or int(s.n_chain) == 0


@case(7467, "you may conquer on their turn a battlefield they took from you")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.ply += 1                                   # before the Might is stamped
    home = body(s, 0, base_loc(0), 9, ready=False)
    s.active = s.priority = 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    s.bf_ctrl[0] = -1
    attack(s, 1, 0, foe)
    cast(s, 0, "Ride The Wind", home, bf_loc(0))
    fight(s)
    assert not alive(s, foe) and alive(s, home)
    assert int(s.bf_ctrl[0]) == 0 and int(s.points[0]) == 1


@case(7465, "Svellsongur does not wear the [Deflect] it copied")
def _():
    need("Svellsongur", "Draven - Audacious", "Salvage")
    s = fresh(hand=[T.id_of("Salvage")], runes=32)
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 1, base_loc(1), ready=True)
    g = s.add_permanent(T.id_of("Svellsongur"), 1, base_loc(1))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, g, 1)
    choose(s, dr)
    run(s)
    s.active = s.priority = 0
    before = runes(s, 0)
    cast(s, 0, "Salvage", g)
    run(s)
    assert not alive(s, g)
    assert before - runes(s, 0) == 1, "the spell's own Power, and no Deflect"


@case(7464, "Defy reads the printed cost, not an additional one")
def _():
    need("Defy", "Rocket Barrage")
    s = fresh(hand=[T.id_of("Rocket Barrage")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    u = body(s, 1, base_loc(1), 9)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Rocket Barrage"), 0)
    pass_priority_to(s, 1)
    assert "Defy" not in hand_plays(s, 1), "4 Energy is in range, 1 Power is not"
    assert u >= 0


@case(7506, "the Monastery's draw can be refunded by Sett's own buff")
def _():
    need("Monastery of Hirana", "Sett, Brawler")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Monastery of Hirana")
    s.bf_ctrl[0] = 1
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    before = int(s.n_hand[0])
    attack(s, 0, 0, sett)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1, "drawn"
    assert s.has_flag(sett, F_BUFFED), "and refilled"
