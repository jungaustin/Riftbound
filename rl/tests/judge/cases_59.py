"""RiftJudge batch 59 -- unused questions from 7694-7745."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7745, "each spell resolves before Ravenbloom Student grows for it")
def _():
    need("Ravenbloom Student", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Discipline", "Discipline")
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    cast(s, 0, "Discipline", rs)
    run(s)
    assert combat.might(s, T, rs) == 2 + 2 + 1
    cast(s, 0, "Discipline", rs)
    run(s)
    assert combat.might(s, T, rs) == 2 + 4 + 2


@case(7742, "Ravenborn Tome adds to each instance the spell deals")
def _():
    need("Ravenborn Tome", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    rt = s.add_permanent(T.id_of("Ravenborn Tome"), 0, base_loc(0), ready=True)
    a = body(s, 1, base_loc(1), 9)
    b = body(s, 1, base_loc(1), 9)
    act(s, A.A_ACTIVATE, rt, 0)
    run(s)
    cast(s, 0, "Falling Star", a, b)
    run(s)
    assert int(s.perms[a, P_DMG]) == 4 and int(s.perms[b, P_DMG]) == 4


@case(7740, "Relentless Pursuit may take an Equipment off another unit")
def _():
    need("Relentless Pursuit", "B.F. Sword")
    s = fresh(hand=[T.id_of("Relentless Pursuit")], runes=32)
    s.bf_ctrl[0] = 0
    holder = body(s, 0, base_loc(0), 3, ready=True)
    mover = body(s, 0, base_loc(0), 3, ready=True)
    g = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, holder)
    run(s)
    assert int(s.perms[g, P_ATTACHED_TO]) == holder
    cast(s, 0, "Relentless Pursuit", mover, bf_loc(0))
    run(s, picking(g))
    assert int(s.perms[g, P_ATTACHED_TO]) == mover, "it moved across"


@case(7738, "Fox-Fire's limit is the total Might of what you chose")
def _():
    need("Fox-Fire")
    s = fresh(hand=[T.id_of("Fox-Fire")], runes=32)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 2)
    b = body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Fox-Fire"), 0)
    choose(s, a)
    assert b in targets_offered(s, 0), "2 and 2 is four"
    choose(s, b)
    for _ in range(2):
        choose(s, -1)
    run(s)
    assert not alive(s, a) and not alive(s, b)


@case(7736, "Bellows Breath chooses three different units")
def _():
    need("Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 5)
    body(s, 1, bf_loc(0), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Bellows Breath"), 0)
    choose(s, a)
    assert a not in targets_offered(s, 0), "not the same one twice"


@case(7734, "Switcheroo does not re-apply the [Assault] bonus")
def _():
    need("Switcheroo", "Immortal Phoenix")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, base_loc(0), ready=True)
    mate = body(s, 0, base_loc(0), 8, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ph, mate)
    assert combat.might(s, T, ph) == 5
    cast(s, 0, "Switcheroo", ph, mate)
    drain(s)
    assert combat.might(s, T, ph) == 8 and combat.might(s, T, mate) == 5


@case(7732, "an attacker is still at a battlefield for Eager Apprentice")
def _():
    need("Eager Apprentice", "Singularity")
    from rl.engine import cost as cost_mod
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ea = s.add_permanent(T.id_of("Eager Apprentice"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    cid = T.id_of("Singularity")
    assert cost_mod.apply_discounts(
        int(T.energy[cid]), cost_mod.energy_discounts(s, T, 0, cid)) == 6, \
        "at base he does nothing"
    attack(s, 0, 0, ea)
    assert cost_mod.apply_discounts(
        int(T.energy[cid]), cost_mod.energy_discounts(s, T, 0, cid)) == 5, \
        "attacking, he is at a battlefield"


@case(7731, "Hidden Blade draws even when the unit survived")
def _():
    need("Hidden Blade", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u)
    assert int(s.n_hand[1]) == before + 2, "the draw is not conditional"


@case(7729, "Ride the Wind needs no [Ganking] and opens a showdown")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    s.bf_ctrl[1] = -1
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    drain(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(1)
    assert int(s.showdown_bf) == 1, "moving in is a showdown either way"


@case(7726, "Sprite Call cannot put a token on ground you do not control")
def _():
    need("Sprite Call")
    s = fresh(hand=[T.id_of("Sprite Call")], runes=32)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Sprite Call"), 0)
    where = targets_offered(s, 0)
    assert bf_loc(0) not in where, "806.3"


@case(7725, "First Mate cannot ready a legend")
def _():
    need("First Mate", "Ezreal - Prodigal Explorer")
    s = fresh(hand=[T.id_of("First Mate")], runes=32)
    s.legend[0], s.legend_ready[0] = T.id_of("Ezreal - Prodigal Explorer"), 0
    act(s, A.A_PLAY, hand_index(s, 0, "First Mate"), 0)
    choose(s, base_loc(0))
    run(s)
    assert int(s.legend_ready[0]) == 0, "a legend is not a unit"


@case(7724, "a facedown card is nobody, so a unit beside one is alone")
def _():
    need("Wielder of Water")
    s = fresh(runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    ww = s.add_permanent(T.id_of("Wielder of Water"), 0, base_loc(0), ready=True)
    hidden_at(s, 0, 0, "Hidden Blade")
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ww)
    drain(s)
    assert combat.might(s, T, ww) == 4, "2 plus its own +2 while alone"


@case(7721, "Stand United makes every buff worth an extra +1")
def _():
    need("Stand United", "Lee Sin - Ascetic")
    s = fresh(runes=32)
    give(s, 0, "Stand United")
    lee = s.add_permanent(T.id_of("Lee Sin - Ascetic"), 0, base_loc(0), ready=True)
    act(s, A.A_ACTIVATE, lee, 0)
    run(s)
    assert s.has_flag(lee, F_BUFFED)
    before = combat.might(s, T, lee)
    cast(s, 0, "Stand United", lee)
    run(s)
    assert combat.might(s, T, lee) > before, "another buff, and each is worth more"


@case(7719, "Discipline's draw is the caster's, Hidden Blade's is the target's")
def _():
    need("Discipline", "Hidden Blade", "Gust")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    mine, theirs = int(s.n_hand[0]), int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    cast(s, 1, "Gust", u)
    run(s)
    assert int(s.n_hand[0]) == mine - 1, "no draw for you"


@case(7717, "an attack trigger resolves before an [Action] can be played")
def _():
    need("Volibear - Furious", "Rebuke")
    s = fresh(runes=32)
    give(s, 1, "Rebuke")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    vb = s.add_permanent(T.id_of("Volibear - Furious"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, vb)
    pass_priority_to(s, 1)
    assert "Rebuke" not in hand_plays(s, 1), "only Reactions answer the chain"


@case(7715, "Treasure Hoard asks after the conquer")
def _():
    need("Treasure Hoard")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Treasure Hoard")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    run(s, picking(accept=True), limit=40)
    assert int(s.points[0]) == 1, "the conquer point"
    assert len(tokens(s, 0)) == 1, "and the Gold it offered"


@case(7714, "an increase and a decrease both apply from the base")
def _():
    need("Call to Glory", "Smoke Screen", "Sett, Brawler")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen", "Call to Glory")
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    assert combat.might(s, T, sett) == 5, "4 printed plus the buff"
    cast(s, 0, "Smoke Screen", sett)
    run(s)
    assert combat.might(s, T, sett) == 1
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Call to Glory"), 0)
    run(s, picking(sett))
    assert combat.might(s, T, sett) == 3, "4 + 3 - 4, with the buff spent"


@case(7711, "a card played 'ignoring its cost' pays no Power either")
def _():
    need("Dazzling Aurora", "Riptide Rex")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Riptide Rex")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    before = runes(s, 0)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Riptide Rex", 0), "it came down"
    assert runes(s, 0) == before, "and its 2 Power was ignored"


@case(7709, "Mystic Poro's [Vision] looks without drawing")
def _():
    need("Mystic Poro")
    s = fresh(hand=[T.id_of("Mystic Poro")], runes=32)
    before = int(s.n_hand[0])
    act(s, A.A_PLAY, hand_index(s, 0, "Mystic Poro"), 0)
    choose(s, base_loc(0))
    run(s, picking(-1))
    assert int(s.n_hand[0]) == before - 1, "a look is not a draw"


@case(7694, "Gust's target must still be 3 Might or less as it resolves")
def _():
    need("Gust", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Gust")
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Gust", u)
    cast(s, 1, "Discipline", u)
    run(s)
    assert alive(s, u), "359.3.e.2: 5 Might no longer meets the requirement"
