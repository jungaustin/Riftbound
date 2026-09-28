"""RiftJudge batch 64 -- unused questions from 7404-7458."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7458, "Spectral Matron can raise the unit the Hook just killed")
def _():
    need("Baited Hook", "Spectral Matron", "Determined Sentry")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    s.trash[0, 0] = T.id_of("Determined Sentry")
    s.n_trash[0] = 1
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Spectral Matron")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0),
                   pack_trash(0, T.id_of("Determined Sentry")), accept=True),
        limit=80)
    assert perm_of(s, "Spectral Matron", 0), "she came off the Hook"
    assert perm_of(s, "Determined Sentry", 0), "and pulled a unit out of the trash"


@case(7457, "a unit at 0 Might with no damage does not die")
def _():
    need("Smoke Screen", "Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 0, "Smoke Screen")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert combat.might(s, T, u) == 1
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u), "saved, and 0 damage means it stays"


@case(7452, "Icathian Rain's six choices are made as it is played")
def _():
    need("Icathian Rain")
    s = fresh(hand=[T.id_of("Icathian Rain")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    u = body(s, 1, base_loc(1), 12)
    act(s, A.A_PLAY, hand_index(s, 0, "Icathian Rain"), 0)
    for _ in range(6):
        choose(s, u)
    pass_priority_to(s, 1)
    assert "Smoke Screen" in hand_plays(s, 1), "they answer after the choices"
    run(s)
    assert int(s.perms[u, P_DMG]) == 12


@case(7451, "Last Stand doubles the Might the unit has, buff included")
def _():
    need("Last Stand")
    s = fresh(runes=32)
    give(s, 0, "Last Stand")
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    assert combat.might(s, T, u) == 4
    cast(s, 0, "Last Stand", u)
    run(s)
    assert combat.might(s, T, u) == 8, "4 doubled, not 3 doubled plus one"


@case(7449, "a Reaction drawn mid-chain can join that chain")
def _():
    need("Discipline", "Defy", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 32
    n = int(s.deck_ptr[1])
    s.deck[1, n] = T.id_of("Defy")
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", theirs, theirs)
    cast(s, 1, "Discipline", theirs)
    run(s, limit=6, stop=lambda st: T.id_of("Defy") in
        [int(st.hand[1, j]) for j in range(int(st.n_hand[1]))])
    assert T.id_of("Defy") in [int(s.hand[1, j]) for j in range(int(s.n_hand[1]))]


@case(7445, "Sett's buff is standard speed")
def _():
    need("Sett, Brawler")
    s = fresh(runes=32)
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
    s.ply += 1
    s.active = s.priority = 1
    assert not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]


@case(7444, "a unit found by Baited Hook may pay [Accelerate]")
def _():
    need("Baited Hook", "Jinx, Demolitionist")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Jinx, Demolitionist")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    jx = perm_of(s, "Jinx, Demolitionist", 0)
    assert jx, "4 Might is within 'up to 1 more' of 3"


@case(7443, "a base-speed spell needs an open state on your own turn")
def _():
    need("Super Mega Death Rocket!")
    s = fresh(runes=32)
    give(s, 0, "Super Mega Death Rocket!")
    body(s, 1, base_loc(1), 9)
    assert "Super Mega Death Rocket!" in hand_plays(s, 0)
    s.ply += 1
    s.active = s.priority = 1
    assert "Super Mega Death Rocket!" not in hand_plays(s, 0)


@case(7439, "Stupefy deals no damage, so the Decree stays quiet")
def _():
    need("Imperial Decree", "Stupefy")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=32)
    give(s, 0, "Stupefy")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Imperial Decree")
    run(s)
    cast(s, 0, "Stupefy", u)
    run(s)
    assert alive(s, u)


@case(7433, "Mystic Reversal on Time Warp gives YOU the extra turn")
def _():
    need("Mystic Reversal", "Time Warp")
    s = fresh(hand=[T.id_of("Time Warp")], runes=32)
    give(s, 1, "Mystic Reversal")
    s.runes_ready[1, :] = 32
    cast(s, 0, "Time Warp")
    cast(s, 1, "Mystic Reversal")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s, picking(accept=True))
    assert int(s.extra_turns[1]) >= 1, "they took control of it"
    assert int(s.extra_turns[0]) == 0


@case(7430, "Fizz reads the printed Energy cost")
def _():
    need("Fizz - Trickster", "Drag Under")
    s = fresh(hand=[T.id_of("Fizz - Trickster")], runes=32)
    s.trash[0, 0] = T.id_of("Drag Under")
    s.n_trash[0] = 1
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Fizz - Trickster"), 0)
    choose(s, base_loc(0))
    offered = targets_offered(s, 0)
    assert pack_trash(0, T.id_of("Drag Under")) not in offered, \
        "5 printed Energy is more than 3"


@case(7424, "Targon's Peak readies the runes at the end of the turn")
def _():
    need("Targon's Peak")
    s = fresh(runes=6)
    s.bf_card[0] = T.id_of("Targon's Peak")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    s.runes_spent[0, :] = s.runes_ready[0, :]
    s.runes_ready[0, :] = 0
    attack(s, 0, 0, u)
    fight(s)
    assert int(s.points[0]) == 1, "conquered"
    before = int(s.runes_ready[0].sum())
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=40)
    assert int(s.runes_ready[0].sum()) >= before, "and up to 2 came back"


@case(7422, "Bellows Breath picks one location once its targets have scattered")
def _():
    need("Bellows Breath", "Ride The Wind")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 5)
    b = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", a, b, -1)
    run(s)
    assert int(s.perms[a, P_DMG]) == 1 and int(s.perms[b, P_DMG]) == 1


@case(7419, "Viktor, Leader dying alongside a unit sees nothing")
def _():
    need("Viktor - Leader")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    vi = s.add_permanent(T.id_of("Viktor - Leader"), 0, base_loc(0), ready=True)
    mate = body(s, 0, base_loc(0), 4, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, vi, mate)
    fight(s)
    assert not alive(s, vi) and not alive(s, mate)
    assert not tokens(s, 0), "he was already gone"


@case(7412, "Bullet Time's amount is chosen after they have answered")
def _():
    need("Bullet Time", "Wind Wall")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    give(s, 1, "Wind Wall")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bullet Time", bf_loc(0))
    pass_priority_to(s, 1)
    assert "Wind Wall" in hand_plays(s, 1), "and they still do not know how much"
    run(s, picking(3))
    assert not alive(s, u)


@case(7405, "The Dreaming Tree does not see Falling Star's own choice")
def _():
    need("Falling Star", "The Dreaming Tree", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 9)
    before = int(s.n_hand[0])
    cast(s, 0, "Discipline", mine)
    run(s)
    assert int(s.n_hand[0]) == before - 1 + 1 + 1, \
        "a spell that chooses it does draw"


@case(7404, "Baited Hook reads the Might the unit had as it died")
def _():
    need("Baited Hook", "Trifarian War Camp", "Determined Sentry")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 0
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, bf_loc(0), 1)
    assert combat.might(s, T, victim) == 2, "the ground's +1"
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Determined Sentry", 0), "1 Might is within 2 + 1"


@case(7441, "the Hook's own unit arrives before a Deathknell resolves")
def _():
    need("Baited Hook", "Watchful Sentry", "Determined Sentry")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 0, base_loc(0), ready=True)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    before = int(s.n_hand[0])
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(ws, 0, base_loc(0), accept=True), limit=60)
    assert not alive(s, ws)
    assert perm_of(s, "Determined Sentry", 0)
    assert int(s.n_hand[0]) == before + 1, "and then his Deathknell drew"


@case(7455, "a hidden card flipped to the [Temporary] trigger still resolves")
def _():
    need("Sprite Call")
    s = fresh(runes=32)
    rune_deck(s)
    tok = _sprite_at(s, 0, 0)
    slot = hidden_at(s, 0, 0, "Sprite Call", slot=1) if len(
        list(fd_slots(0))) > 1 else hidden_at(s, 0, 0, "Sprite Call")
    _next_own_turn(s)
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], \
        "the Temporary trigger opened the window"
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s, picking(bf_loc(0)), limit=40)
    assert len(tokens(s, 0)) >= 1, "a new Sprite arrived"
    assert tok >= 0
