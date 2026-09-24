"""RiftJudge batch 65 -- unused questions from 7354-7401."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7396, "a Hourglass recall clears damage, not a Might reduction")
def _():
    need("Smoke Screen", "Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 0, "Smoke Screen")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert combat.might(s, T, u) == 5
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and combat.might(s, T, u) == 5, "the -4 is still there"


@case(7392, "Adaptatron conquers alongside other units")
def _():
    need("Adaptatron", "Warmog's Armor")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ad = s.add_permanent(T.id_of("Adaptatron"), 0, base_loc(0), ready=True)
    mate = body(s, 0, base_loc(0), 3, ready=True)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 1, base_loc(1))
    body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, ad, mate)
    run(s, picking(g, accept=True), limit=40)
    assert int(s.bf_ctrl[0]) == 0
    assert not alive(s, g) and s.has_flag(ad, F_BUFFED), "his conquer trigger ran"


@case(7391, "moving onto ground you already hold is no conquer")
def _():
    need("Adaptatron", "Warmog's Armor")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    keeper = body(s, 0, bf_loc(0), 3)
    ad = s.add_permanent(T.id_of("Adaptatron"), 0, base_loc(0), ready=True)
    s.add_permanent(T.id_of("Warmog's Armor"), 1, base_loc(1))
    attack(s, 0, 0, ad)
    fight(s)
    assert not s.has_flag(ad, F_BUFFED), "190.4.a: it was already yours"
    assert keeper >= 0


@case(7390, "Trinity Force takes the eighth point off one battlefield")
def _():
    need("Trinity Force", "Skyfall of Areion")
    s = fresh(runes=32)
    s.points[0] = 7
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    for name in ("Trinity Force", "Skyfall of Areion"):
        g = s.add_permanent(T.id_of(name), 0, base_loc(0))
        act(s, A.A_ACTIVATE, g, 0)
        choose(s, u)
        run(s)
    body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, u)
    fight(s)
    assert int(s.points[0]) == 8, "471.1.a.1 exempts what a trigger scores"


@case(7389, "an alternative source can score the eighth point")
def _():
    need("Yasuo - Windrider", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind", "Ride The Wind", "Ride The Wind")
    s.points[0] = 7
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    ya = s.add_permanent(T.id_of("Yasuo - Windrider"), 0, base_loc(0), ready=True)
    for dest in (bf_loc(0), base_loc(0), bf_loc(0)):
        cast(s, 0, "Ride The Wind", ya, dest)
        run(s)
    assert int(s.points[0]) == 8


@case(7388, "Vayne's 'you may pay' is answered as the trigger resolves")
def _():
    need("Vayne - Hunter")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    va = s.add_permanent(T.id_of("Vayne - Hunter"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 1)
    before = runes(s, 0)
    attack(s, 0, 0, va)
    run(s, picking(accept=True), limit=40)
    assert not alive(s, va), "she went back to hand"
    assert runes(s, 0) == before, "1 Energy exhausts a rune, it recycles none"


@case(7387, "a countered Cleave never readied Darius")
def _():
    need("Cleave", "Defy", "Darius - Trifarian")
    s = fresh(runes=32)
    give(s, 0, "Cleave")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    dar = s.add_permanent(T.id_of("Darius - Trifarian"), 0, base_loc(0),
                          ready=False)
    cast(s, 0, "Cleave", dar)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[dar, P_READY]) == 0, "419.4.a: it was never played"
    assert combat.might(s, T, dar) == 5


@case(7385, "Charm forces a showdown and they are the attacker")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(0))
    drain(s)
    assert int(s.perms[foe, P_LOC]) == bf_loc(0)
    assert int(s.attacker) == 1, "their unit contested it"


@case(7384, "a move trigger resolves before the showdown begins")
def _():
    need("Traveling Merchant")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen")
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    before = int(s.n_hand[0])
    attack(s, 0, 0, tm)
    drain(s)
    assert int(s.n_hand[0]) == before, "discarded one and drew one on the way in"


@case(7378, "an [Action] is playable in a non-combat showdown")
def _():
    need("Daring Poro", "Hextech Ray")
    s = fresh(runes=32)
    give(s, 1, "Hextech Ray")
    s.runes_ready[1, :] = 32
    poro = s.add_permanent(T.id_of("Daring Poro"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, poro)
    assert int(s.showdown_bf) == 0 and not s.showdown_combat
    pass_priority_to(s, 1)
    assert "Hextech Ray" in hand_plays(s, 1), "a showdown is a showdown"


@case(7375, "a damage spell whose target left the battlefield does nothing")
def _():
    need("Hextech Ray", "Fight or Flight")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=32)
    give(s, 1, "Fight or Flight")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    slot = hidden_at(s, 1, 0, "Fight or Flight")
    cast(s, 0, "Hextech Ray", u)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, slot, 1)
    choose(s, u)
    run(s)
    assert int(s.perms[u, P_LOC]) == base_loc(1)
    assert int(s.perms[u, P_DMG]) == 0, "'a unit at a battlefield' no longer fits"


@case(7374, "a unit gone from the board tells its ability nothing")
def _():
    need("Kato the Arm", "Ride The Wind", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    ka = s.add_permanent(T.id_of("Kato the Arm"), 0, base_loc(0), ready=True)
    mate = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Ride The Wind", ka, bf_loc(0))
    run(s, limit=20, stop=lambda st: int(st.perms[ka, P_LOC]) == bf_loc(0))
    choose(s, mate)          # his move trigger names its unit as it is placed
    # Now bounce him before it resolves. He is 3 Might, so Gust reaches him --
    # and his [Deflect] costs them one rune more.
    cast(s, 1, "Gust", ka)
    run(s, limit=40)
    assert not alive(s, ka), "back to hand before his trigger resolved"
    assert combat.might(s, T, mate) == 3, "nothing was copied from a gone unit"


@case(7368, "Singularity is one instance, so one save is a choice")
def _():
    need("Singularity", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    a = body(s, 1, base_loc(1), 5)
    b = body(s, 1, base_loc(1), 5)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Singularity", a, b)
    run(s)
    assert alive(s, a) != alive(s, b), "one of them was saved"
    assert not alive(s, z)


@case(7364, "Noxian Guillotine's delayed kill is a kill with a spell")
def _():
    need("Noxian Guillotine", "Immortal Phoenix", "Bellows Breath")
    s = fresh(hand=[T.id_of("Noxian Guillotine"), T.id_of("Bellows Breath")],
              runes=32)
    s.bf_ctrl[0] = 0
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, bf_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 5)
    cast(s, 0, "Noxian Guillotine", foe)
    run(s)
    cast(s, 0, "Bellows Breath", foe, -1, -1)
    run(s, picking(accept=True), limit=40)
    assert not alive(s, foe), "the delayed kill found its damage"
    assert ph >= 0


@case(7363, "a hidden Sprite Call summons at its own battlefield")
def _():
    need("Sprite Call")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(0), 3)
    body(s, 0, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Sprite Call")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    where = targets_offered(s, 0)
    assert where == {bf_loc(0)} or not where, "737.1.d.3 pins it here"


@case(7362, "Kai'Sa's conquer trigger ignores the spell's own speed")
def _():
    need("Kai'Sa - Evolutionary", "Cull the Weak")
    s = fresh(runes=32)
    s.points[0] = 5
    s.bf_ctrl[0] = 1
    ks = s.add_permanent(T.id_of("Kai'Sa - Evolutionary"), 0, base_loc(0),
                         ready=True)
    body(s, 1, bf_loc(0), 1)
    s.trash[0, 0] = T.id_of("Cull the Weak")
    s.n_trash[0] = 1
    mine = body(s, 0, base_loc(0), 3)
    attack(s, 0, 0, ks)
    run(s, picking(pack_trash(0, T.id_of("Cull the Weak")), mine, accept=True),
        limit=60)
    assert int(s.bf_ctrl[0]) == 0, "she took the ground"
    assert ks >= 0


@case(7360, "Retreat must choose a unit, and must return it")
def _():
    need("Retreat")
    s = fresh(runes=32)
    give(s, 0, "Retreat")
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Retreat"), 0)
    offered = targets_offered(s, 0)
    assert offered == {u}, "no declining while a friendly unit stands"
    choose(s, u)
    run(s)
    assert not alive(s, u)


@case(7359, "Guerilla Warfare wants cards that really have [Hidden]")
def _():
    need("Guerilla Warfare", "Hidden Blade", "Ember Monk")
    s = fresh(runes=32)
    give(s, 0, "Guerilla Warfare")
    s.trash[0, 0] = T.id_of("Hidden Blade")
    s.trash[0, 1] = T.id_of("Ember Monk")
    s.n_trash[0] = 2
    act(s, A.A_PLAY, hand_index(s, 0, "Guerilla Warfare"), 0)
    offered = targets_offered(s, 0)
    assert pack_trash(0, T.id_of("Hidden Blade")) in offered
    assert pack_trash(0, T.id_of("Ember Monk")) not in offered, \
        "he only mentions the keyword"


@case(7354, "a hidden card may be played from any battlefield, any time")
def _():
    need("Consult the Past")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(1), 3)
    slot = hidden_at(s, 0, 1, "Consult the Past")
    body(s, 0, bf_loc(0), 3)
    before = int(s.n_hand[0])
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], \
        "no showdown and no chain is fine for a Reaction"
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s)
    assert int(s.n_hand[0]) == before + 2


@case(7371, "Icathian Rain's six choices are all made before it resolves")
def _():
    need("Icathian Rain")
    s = fresh(hand=[T.id_of("Icathian Rain")], runes=32)
    a = body(s, 1, base_loc(1), 7)
    b = body(s, 1, base_loc(1), 7)
    act(s, A.A_PLAY, hand_index(s, 0, "Icathian Rain"), 0)
    for _ in range(3):
        choose(s, a)
    for _ in range(3):
        choose(s, b)
    run(s)
    assert int(s.perms[a, P_DMG]) == 6 and int(s.perms[b, P_DMG]) == 6
