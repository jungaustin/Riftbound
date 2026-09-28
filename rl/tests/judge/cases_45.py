"""RiftJudge batch 45 -- unused questions from 8433-8489."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8489, "two stunned units at Vilemaw's Lair simply stay there")
def _():
    need("Vilemaw's Lair", "Rune Prison")
    s = fresh(runes=20)
    give(s, 0, "Rune Prison", "Rune Prison")
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    cast(s, 0, "Rune Prison", att)
    drain(s)
    cast(s, 0, "Rune Prison", d)
    fight(s)
    assert alive(s, att) and alive(s, d), "no Might was contributed"
    assert int(s.perms[att, P_LOC]) == base_loc(0), \
        "466.1.a.2 recalls the attacker, and a Recall is not a move"
    assert int(s.bf_ctrl[0]) == 1, "so the defender keeps the ground"


@case(8488, "Defy reads the printed cost, not the Repeat")
def _():
    need("Bellows Breath", "Defy")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=16)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    choose(s, u)
    choose(s, -1)
    choose(s, -1)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "1 energy and 1 Power is still in range"
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[u, P_DMG]) == 0


@case(8482, "an [Action] cannot answer a spell on the chain")
def _():
    need("Falling Star", "Punch First")
    s = fresh(hand=[T.id_of("Falling Star")], runes=16)
    give(s, 1, "Punch First")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Falling Star", u, u)
    pass_priority_to(s, 1)
    assert "Punch First" not in hand_plays(s, 1), "334.1.a.1"
    run(s)
    assert not alive(s, u)


@case(8481, "Piercing Light's second target must be another unit")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=16)
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, base_loc(1), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Piercing Light"), 0)
    choose(s, a)
    left = targets_offered(s, 0)
    assert a not in left and b in left, "'one OTHER unit'"


@case(8480, "a hidden [Action] answers a spell, because hiding makes it fast")
def _():
    need("Falling Star", "Hidden Blade")
    s = fresh(hand=[T.id_of("Falling Star")], runes=16)
    s.bf_ctrl[1] = 1
    mine = body(s, 1, bf_loc(0), 3)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    cast(s, 0, "Falling Star", mine, mine)
    pass_priority_to(s, 1)
    assert [a for a in A.legal_actions(s, T, V1, 1)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], \
        "a hidden card is played at Reaction speed"


@case(8476, "an activated ability goes on the chain and can be answered")
def _():
    need("Vanguard Armory", "Not So Fast", "Smoke Screen")
    s = fresh(runes=16)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 16
    va = s.add_permanent(T.id_of("Vanguard Armory"), 0, base_loc(0), ready=True)
    body(s, 0, base_loc(0), 3)
    act(s, A.A_ACTIVATE, va, 0)
    assert int(s.n_chain) >= 1, "151.2: it is a chain item"
    pass_priority_to(s, 1)
    assert "Smoke Screen" in hand_plays(s, 1), "and they hold priority over it"


@case(8474, "Not So Fast counters Hostile Takeover, which chooses your unit")
def _():
    need("Hostile Takeover", "Not So Fast")
    s = fresh(hand=[T.id_of("Hostile Takeover")], runes=20)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Hostile Takeover", foe)
    cast(s, 1, "Not So Fast")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 1, "it stayed theirs"


@case(8472, "Vilemaw's Lair only forbids the trip to base")
def _():
    need("Relentless Pursuit", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Relentless Pursuit")], runes=16)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    cast(s, 0, "Relentless Pursuit", u, bf_loc(1))
    run(s, picking(-1))
    assert int(s.perms[u, P_LOC]) == bf_loc(1), "battlefield to battlefield is fine"


@case(8467, "a repeated Marching Orders may pick a different pair")
def _():
    need("Marching Orders")
    s = fresh(hand=[T.id_of("Marching Orders")], runes=20)
    s.bf_ctrl[1] = 1
    m1 = body(s, 0, base_loc(0), 3)
    m2 = body(s, 0, base_loc(0), 4)
    e1 = body(s, 1, bf_loc(0), 3)
    e2 = body(s, 1, bf_loc(0), 4)
    cast(s, 0, "Marching Orders", m1, e1, repeat=True)
    run(s, picks(m2, e2))
    assert not alive(s, m1) and not alive(s, e1)
    assert not alive(s, e2) and not alive(s, m2), "4 for 4 both ways"


@case(8464, "Ravenbloom Conservatory recycles what is not a spell")
def _():
    need("Ravenbloom Conservatory")
    s = fresh(runes=16)
    s.bf_card[0] = T.id_of("Ravenbloom Conservatory")
    s.bf_ctrl[0] = 0
    d = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    att = body(s, 1, base_loc(1), 3, ready=True)
    before = int(s.n_hand[0])
    n = int(s.deck_ptr[0])
    s.deck[0, n] = VANILLA                      # a unit, never a spell
    attack(s, 1, 0, att)
    drain(s)
    assert int(s.n_hand[0]) == before, "a non-spell is recycled, not drawn"
    assert d >= 0


@case(8460, "Salvage may be played with nothing to kill")
def _():
    need("Salvage")
    s = fresh(hand=[T.id_of("Salvage")], runes=12)
    before = int(s.n_hand[0])
    assert "Salvage" in hand_plays(s, 0), "352.13: 'up to one'"
    cast(s, 0, "Salvage", -1)
    run(s)
    assert int(s.n_hand[0]) == before - 1 + 1


@case(8454, "a repeated Bellows Breath kills a 1 Might unit at the end")
def _():
    need("Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=20)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 1)
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    run(s, picking(u, -1))
    assert not alive(s, u), "one lethal check, after both instances"


@case(8453, "Yordle Explorer reads the printed Power, whatever you paid")
def _():
    need("Yordle Explorer", "Punch First", "Vex - Cheerless")
    s = fresh(hand=[T.id_of("Punch First")], runes=20)
    ye = s.add_permanent(T.id_of("Yordle Explorer"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Punch First", u)
    run(s)
    assert combat.might(s, T, u) == 8
    assert int(s.n_hand[0]) == before - 1 + 1, "2 printed Power is enough"
    assert ye >= 0


@case(8452, "Tianna blocks the point but the battlefield still counts as scored")
def _():
    need("Tianna Crownguard")
    s = fresh(runes=20)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1), ready=True)
    s.bf_ctrl[1] = 1
    _next_own_turn(s)
    run(s, limit=40)
    assert int(s.points[0]) == 0, "opponents can't gain points"
    assert int(s.bf_scored[0, 0]) == 1, "the Hold still marked it scored"


@case(8450, "Riposte's Might is not given when its spell is already gone")
def _():
    need("Riposte", "Stupefy", "Defy")
    s = fresh(runes=20)
    give(s, 0, "Stupefy", "Defy")
    give(s, 1, "Riposte")
    s.runes_ready[1, :] = 20
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Stupefy", theirs)
    cast(s, 1, "Riposte", theirs)
    choose(s, sorted(targets_offered(s, 1))[0])
    cast(s, 0, "Defy")
    choose(s, sorted(targets_offered(s, 0))[0])
    run(s)
    assert combat.might(s, T, theirs) == 5, "no +Might arrived from a gone spell"
    assert mine >= 0


@case(8449, "Not So Fast misses Thousand-Tailed Watcher")
def _():
    need("Thousand-Tailed Watcher", "Not So Fast")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=20)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    pass_priority_to(s, 1)
    assert "Not So Fast" not in hand_plays(s, 1)


@case(8448, "Volibear draws when an enemy moves to another battlefield")
def _():
    need("Volibear - Imposing", "Charm", "Stalwart Poro")
    s = fresh(hand=[T.id_of("Charm")], runes=20)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    vb = s.add_permanent(T.id_of("Volibear - Imposing"), 0, bf_loc(0), ready=True)
    poro = s.add_permanent(T.id_of("Stalwart Poro"), 1, base_loc(1), ready=True)
    before = int(s.n_hand[0])
    cast(s, 0, "Charm", poro, bf_loc(1))
    run(s)
    assert int(s.perms[poro, P_LOC]) == bf_loc(1)
    assert int(s.n_hand[0]) == before - 1 + 1, "a battlefield other than mine"
    assert vb >= 0


@case(8447, "Tianna stops the point, not the conquer trigger")
def _():
    need("Kai'Sa, Survivor", "Tianna Crownguard")
    s = fresh(runes=20)
    s.bf_ctrl[0] = 1
    ks = s.add_permanent(T.id_of("Kai'Sa, Survivor"), 0, base_loc(0), ready=True)
    s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1), ready=True)
    s.bf_ctrl[1] = 1
    before = int(s.n_hand[0])
    attack(s, 0, 0, ks)
    fight(s)
    assert int(s.bf_ctrl[0]) == 0, "the conquer happened"
    assert int(s.points[0]) == 0, "but no point"
    assert int(s.n_hand[0]) == before + 1, "and the trigger drew"


@case(8446, "Not So Fast misses Brynhir's global trigger")
def _():
    need("Brynhir Thundersong", "Not So Fast")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")], runes=20)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Brynhir Thundersong"), 0)
    choose(s, base_loc(0))
    pass_priority_to(s, 1)
    assert "Not So Fast" not in hand_plays(s, 1)


@case(8441, "Sacred Shears killed on its own rings no Deathknell")
def _():
    need("Sacred Shears", "Salvage")
    s = fresh(hand=[T.id_of("Salvage")], runes=16)
    u = body(s, 1, base_loc(1), 3)
    g = s.add_permanent(T.id_of("Sacred Shears"), 1, base_loc(1))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, g, 1)
    choose(s, u)
    run(s)
    s.active = s.priority = 0
    before = int(s.n_hand[1])
    cast(s, 0, "Salvage", g)
    run(s)
    assert not alive(s, g) and alive(s, u)
    assert int(s.n_hand[1]) == before, "the Effect Text belongs to the unit"


@case(8435, "you keep priority after playing Discipline")
def _():
    need("Discipline", "Hidden Blade")
    s = fresh(runes=16)
    give(s, 0, "Discipline")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    body(s, 1, bf_loc(1), 3)
    s.bf_ctrl[1] = 1
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    cast(s, 0, "Discipline", mine)
    assert int(s.priority) == 0, "337.1.a: finalizing does not pass priority"
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot]


@case(8433, "Guardian Angel keeps the unit's damage and buff intact")
def _():
    need("Guardian Angel", "Hidden Blade", "Bellows Breath")
    s = fresh(hand=[T.id_of("Hidden Blade"), T.id_of("Bellows Breath")], runes=20)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    s.set_flag(u, F_BUFFED)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, ga, 1)
    choose(s, u)
    run(s)
    s.active = s.priority = 0
    cast(s, 0, "Bellows Breath", u, -1, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 1
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and not alive(s, ga)
    assert s.has_flag(u, F_BUFFED), "it never died, so the buff stayed"
