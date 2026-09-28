"""RiftJudge batch 39 -- unused questions from 8732-8784."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8784, "a unit taken with Hostile Takeover is friendly for Deathgrip")
def _():
    need("Hostile Takeover", "Deathgrip")
    s = fresh(hand=[T.id_of("Hostile Takeover")], runes=16)
    give(s, 0, "Deathgrip")
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 5)
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Hostile Takeover", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0
    cast(s, 0, "Deathgrip", foe, mine)
    run(s)
    assert not alive(s, foe)
    assert combat.might(s, T, mine) == 3 + 5, "its Might came across"


@case(8781, "The Dreaming Tree's draw sits above the spell, so it beats a Defy")
def _():
    need("The Dreaming Tree", "En Garde", "Defy")
    s = fresh(runes=9)
    give(s, 0, "En Garde")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "En Garde", u)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert combat.might(s, T, u) == 3, "the pump was countered"
    assert int(s.n_hand[0]) == before - 1 + 1, "but the Tree had already drawn"


@case(8779, "Rengar, Pouncing may be played to a battlefield you attack")
def _():
    need("Rengar - Pouncing")
    s = fresh(runes=12)
    give(s, 0, "Rengar - Pouncing")
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, att)
    assert "Rengar - Pouncing" in hand_plays(s, 0), "his own exception to 739.3.a"
    act(s, A.A_PLAY, hand_index(s, 0, "Rengar - Pouncing"), 0)
    where = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert bf_loc(0) in where


@case(8774, "Detonate needs a gear to kill")
def _():
    need("Detonate")
    s = fresh(hand=[T.id_of("Detonate")], runes=9)
    body(s, 1, base_loc(1), 3)
    assert "Detonate" not in hand_plays(s, 0), "355.10: no legal target, no play"
    s.add_permanent(T.id_of("B.F. Sword"), 1, base_loc(1))
    assert "Detonate" in hand_plays(s, 0)


@case(8772, "Vex, Apathetic stuns a Ruin Runner: her trigger chooses nobody")
def _():
    need("Vex - Apathetic", "Ruin Runner")
    s = fresh(hand=[T.id_of("Ruin Runner")], runes=14)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0), ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Ruin Runner"), 0)
    choose(s, base_loc(0))
    run(s)
    rr = perm_of(s, "Ruin Runner", 0)[0]
    assert s.has_flag(rr, F_STUNNED), "'when an opponent plays a unit' is no choice"


@case(8771, "Amateur Recital cannot move Baron Nashor")
def _():
    need("Amateur Recital", "Baron Nashor")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Amateur Recital")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    s.bf_ctrl[1] = 1
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(1), ready=True)
    body(s, 1, bf_loc(1), 3)
    _next_own_turn(s)
    offered = targets_offered(s, 0, limit=6)
    assert bn not in offered, "he can't be chosen by enemy abilities"
    assert mine in offered, "but your own unit is fair game"


@case(8768, "two [Action] spells cannot answer each other")
def _():
    need("Bellows Breath", "Ride The Wind")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=12)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 1)
    cast(s, 0, "Bellows Breath", u, -1, -1)
    assert "Ride The Wind" not in hand_plays(s, 1), "an Action needs an open state"
    run(s)
    assert not alive(s, u)


@case(8767, "a repeated Marching Orders never pauses to clear the dead")
def _():
    need("Marching Orders")
    s = fresh(hand=[T.id_of("Marching Orders")], runes=14)
    s.bf_ctrl[1] = 1
    mine = body(s, 0, base_loc(0), 3)
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Marching Orders", mine, a, repeat=True)
    run(s, picks(mine, b))
    assert not alive(s, a) and not alive(s, b), "both trades happened"
    assert not alive(s, mine), "and the same unit took 3 twice"


@case(8762, "Elder Dragon makes one damage enough")
def _():
    need("Elder Dragon")
    s = fresh(runes=16)
    s.bf_ctrl[1] = 1
    ed = s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0), ready=True)
    foes = [body(s, 1, bf_loc(0), 4) for _ in range(5)]
    attack(s, 0, 0, ed)
    fight(s)
    assert all(not alive(s, f) for f in foes), "10 Might, one damage apiece"


@case(8760, "Fresh Beans sees a unit played during a non-combat showdown")
def _():
    need("Fresh Beans", "Rengar - Pouncing")
    s = fresh(runes=12)
    give(s, 0, "Rengar - Pouncing")
    fb = s.add_permanent(T.id_of("Fresh Beans"), 0, base_loc(0), ready=True)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    assert int(s.showdown_bf) == 0 and not s.showdown_combat
    before = int(s.n_hand[0])
    act(s, A.A_PLAY, hand_index(s, 0, "Rengar - Pouncing"), 0)
    choose(s, base_loc(0))
    run(s, picking(accept=True), limit=20)
    assert int(s.perms[fb, P_READY]) == 0, "the Beans were exhausted to draw"
    assert int(s.n_hand[0]) == before - 1 + 1


@case(8758, "Vex, Apathetic stuns a token that was PLAYED")
def _():
    need("Vex - Apathetic", "Sprite Call")
    s = fresh(hand=[T.id_of("Sprite Call")], runes=12)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1), ready=True)
    s.bf_ctrl[1] = 1
    cast(s, 0, "Sprite Call", bf_loc(0))
    run(s)
    tok = tokens(s, 0)[0]
    assert s.has_flag(tok, F_STUNNED), "the token was played, so she saw it"


@case(8757, "Guardian Angel saves Irelia from an Imperial Decree kill")
def _():
    need("Imperial Decree", "Guardian Angel", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=16)
    s.bf_ctrl[1] = 1
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 1, bf_loc(0), ready=True)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, ga, 1)
    choose(s, ir)
    run(s)
    s.active = s.priority = 0
    att = body(s, 0, base_loc(0), 6, ready=True)
    cast(s, 0, "Imperial Decree")
    run(s)
    attack(s, 0, 0, att)
    fight(s)
    assert alive(s, ir) and not alive(s, ga)
    assert int(s.perms[ir, P_LOC]) == base_loc(1), "healed, exhausted and recalled"


@case(8756, "Dunebreaker counts the hand it leaves behind")
def _():
    need("Dunebreaker")

    def ready_on_arrival(extra):
        s = fresh(hand=[T.id_of("Dunebreaker")], runes=16)
        for _ in range(extra):
            give(s, 0, "Smoke Screen")
        act(s, A.A_PLAY, hand_index(s, 0, "Dunebreaker"), 0)
        choose(s, base_loc(0))
        run(s)
        return int(s.perms[perm_of(s, "Dunebreaker", 0)[0], P_READY])

    assert ready_on_arrival(2) == 1, "three in hand, two after playing me"
    assert ready_on_arrival(3) == 0


@case(8755, "Repulse cannot counter Atakhan's attack: it chooses nothing")
def _():
    need("Atakhan", "Repulse")
    s = fresh(runes=16)
    give(s, 1, "Repulse")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[0] = 1
    at = s.add_permanent(T.id_of("Atakhan"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, at)
    assert "Repulse" not in hand_plays(s, 1)


@case(8754, "Hall of Legends readies your legend for 1 Energy")
def _():
    need("Hall of Legends", "Ezreal - Prodigal Explorer")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Hall of Legends")
    s.bf_ctrl[0] = 1
    s.legend[0], s.legend_ready[0] = T.id_of("Ezreal - Prodigal Explorer"), 0
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    run(s, picking(accept=True), limit=40)
    assert int(s.legend_ready[0]) == 1


@case(8750, "Void Gate does not amplify Challenge's damage")
def _():
    need("Void Gate", "Challenge")

    def dealt(gate):
        s = fresh(hand=[T.id_of("Challenge")], runes=9)
        if gate:
            s.bf_card[0] = T.id_of("Void Gate")
        s.bf_ctrl[0] = 0
        mine = body(s, 0, bf_loc(0), 2)
        theirs = body(s, 1, bf_loc(0), 9)
        cast(s, 0, "Challenge", mine, theirs)
        run(s)
        return int(s.perms[theirs, P_DMG])

    assert dealt(True) == dealt(False) == 2, "the units deal it, not the spell"


@case(8746, "Vex's stun wears off in the Ending Step, not before")
def _():
    need("Vex - Apathetic", "Ruin Runner")
    s = fresh(hand=[T.id_of("Ruin Runner")], runes=14)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0), ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Ruin Runner"), 0)
    choose(s, base_loc(0))
    run(s)
    rr = perm_of(s, "Ruin Runner", 0)[0]
    assert s.has_flag(rr, F_STUNNED)
    act(s, A.A_END_TURN, None, 0)
    run(s)
    assert not s.has_flag(rr, F_STUNNED), "423.1.a.2"


@case(8745, "a stunned Yasuo, Remorseful still deals his ability damage")
def _():
    need("Yasuo - Remorseful", "Rune Prison")
    s = fresh(runes=16)
    give(s, 0, "Rune Prison")
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Rune Prison", ya)
    run(s)
    assert s.has_flag(ya, F_STUNNED)
    attack(s, 0, 0, ya)
    choose(s, foe)
    drain(s)
    assert int(s.perms[foe, P_DMG]) == 6, "stun stops combat damage only"


@case(8742, "Diana grows by 2 for every spell you play")
def _():
    need("Diana, No Longer Human", "Discipline")
    s = fresh(runes=12)
    give(s, 0, "Discipline", "Discipline")
    di = s.add_permanent(T.id_of("Diana, No Longer Human"), 0, base_loc(0),
                         ready=True)
    for _ in range(2):
        cast(s, 0, "Discipline", di)
        run(s)
    assert combat.might(s, T, di) == 3 + 2 + 2 + 2 + 2, "+2 each, plus the pumps"


@case(8741, "a unit killed by a spell mid-showdown died in combat")
def _():
    need("Draven - Audacious", "Hidden Blade")
    s = fresh(runes=16)
    give(s, 1, "Hidden Blade")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 3)
    s.ply += 1
    s.ply -= 1
    attack(s, 0, 0, dr)
    cast(s, 1, "Hidden Blade", dr)
    fight(s)
    assert not alive(s, dr)
    assert int(s.points[1]) >= 1, "he was still a designated attacker"


@case(8740, "Rumble may recycle a Mech token, which simply ceases to be")
def _():
    need("Rumble - Hotheaded", "Carrion Dredger")
    s = fresh(runes=16)
    s.bf_ctrl[0] = 1
    ru = s.add_permanent(T.id_of("Rumble - Hotheaded"), 0, base_loc(0), ready=True)
    s.trash[0, 0] = T.id_of("Carrion Dredger")
    s.n_trash[0] = 1
    tok = _sprite_at(s, 0, 1)
    attack(s, 0, 0, ru)
    run(s, picking(tok, pack_trash(0, T.id_of("Carrion Dredger")), base_loc(0)),
        limit=60)
    assert not alive(s, tok), "186: a token in any other zone is gone"


@case(8738, "Sett's conquer buff arrives too late to pay the Monastery")
def _():
    need("Monastery of Hirana", "Sett, Brawler")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Monastery of Hirana")
    s.bf_ctrl[0] = 1
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    before = int(s.n_hand[0])
    attack(s, 0, 0, sett)
    run(s, picking(accept=True), limit=40)
    assert s.has_flag(sett, F_BUFFED), "the conquer buff landed"
    assert int(s.n_hand[0]) == before, "but the Monastery had nothing to spend"


@case(8736, "a card played from Hidden pays neither Energy nor Power")
def _():
    need("Switcheroo")
    s = fresh(runes=0)
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 2)
    b = body(s, 0, bf_loc(0), 6)
    slot = hidden_at(s, 0, 0, "Switcheroo")
    assert [x for x in A.legal_actions(s, T, V1, 0)
            if x.kind == A.A_PLAY_HIDDEN and x.arg == slot], "421.3: it costs 0"
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s, picks(a, b))
    assert combat.might(s, T, a) == 6 and combat.might(s, T, b) == 2


@case(8733, "Not So Fast stops both halves of a Falling Star")
def _():
    need("Falling Star", "Not So Fast")
    s = fresh(hand=[T.id_of("Falling Star")], runes=12)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 12
    a = body(s, 1, base_loc(1), 9)
    b = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", a, b)
    cast(s, 1, "Not So Fast")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[a, P_DMG]) == 0 and int(s.perms[b, P_DMG]) == 0


@case(8732, "Sett's buff is standard speed, so no showdown either")
def _():
    need("Sett, Brawler")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 9
    attack(s, 0, 0, sett)
    assert int(s.showdown_bf) == 0
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE], "no [Action], so not in a showdown"
