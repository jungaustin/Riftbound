"""RiftJudge batch 33 -- unused questions from 9166-9209."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(9209, "Immortal Phoenix moving into an empty battlefield is no attacker")
def _():
    need("Immortal Phoenix")
    s = fresh()
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, base_loc(0), ready=True)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    attack(s, 0, 0, ph)
    assert int(s.showdown_bf) == 0 and not s.showdown_combat
    assert combat.might(s, T, ph) == 3, "no [Assault 2] outside combat"


@case(9208, "Defy counters a repeated spell whole")
def _():
    need("Defy", "Upstage Comedy")
    s = fresh(hand=[T.id_of("Upstage Comedy")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    v = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Upstage Comedy", u, v, repeat=True)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert int(s.perms[u, P_READY]) == 0 and int(s.perms[v, P_READY]) == 0


@case(9206, "Not So Fast can counter Singularity aimed at two of your units")
def _():
    need("Not So Fast", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=12)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    a = body(s, 1, base_loc(1), 5)
    b = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Singularity", a, b)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert alive(s, a) and alive(s, b)


@case(9201, "Switcheroo swaps current Might, buffs included")
def _():
    need("Switcheroo")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=9)
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 2)
    s.set_flag(a, F_BUFFED)
    b = body(s, 0, bf_loc(0), 6)
    cast(s, 0, "Switcheroo", a, b)
    run(s)
    assert combat.might(s, T, a) == 6 and combat.might(s, T, b) == 3


@case(9200, "a repeated spell is one card played")
def _():
    need("Upstage Comedy", "Darius - Trifarian")
    s = fresh(hand=[T.id_of("Upstage Comedy")], runes=9)
    dar = s.add_permanent(T.id_of("Darius - Trifarian"), 0, base_loc(0), ready=False)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Upstage Comedy", u, u, repeat=True)
    run(s)
    assert int(s.cards_played[0]) == 1 and combat.might(s, T, dar) == 5


@case(9197, "Bellows Breath cannot choose one unit three times")
def _():
    need("Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    body(s, 1, bf_loc(0), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Bellows Breath"), 0)
    choose(s, u)
    assert u not in targets_offered(s, 0)


@case(9170, "a lone target takes 1 from Bellows Breath, not 3")
def _():
    need("Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", u, -1, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 1


@case(9196, "Defy stops a repeated Piercing Light")
def _():
    need("Defy", "Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=12)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Piercing Light", foe, -1, foe, -1, repeat=True)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert int(s.perms[foe, P_DMG]) == 0


@case(9178, "Flurry of Blades chooses nothing: no Deflect to pay")
def _():
    need("Flurry of Blades", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Flurry of Blades")], runes=9)
    s.bf_ctrl[1] = 1
    vx = s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0))
    before = runes(s, 0)
    cast(s, 0, "Flurry of Blades")
    run(s)
    assert int(s.perms[vx, P_DMG]) == 1
    assert runes(s, 0) == before - int(T.power[T.id_of("Flurry of Blades")])


@case(9166, "Salvage may kill no gear and still draw")
def _():
    need("Salvage")
    s = fresh(hand=[T.id_of("Salvage")], runes=9)
    cast(s, 0, "Salvage", -1)
    run(s)
    assert int(s.n_hand[0]) == 1
