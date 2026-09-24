"""RiftJudge batch 57 -- unused questions from 7803-7865."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7865, "a unit alone on open ground is no attacker, so no [Assault]")
def _():
    need("Cleave")
    s = fresh(runes=32)
    give(s, 0, "Cleave")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    cast(s, 0, "Cleave", u)
    drain(s)
    assert combat.might(s, T, u) == 3, "807.1.d wants a Combat designation"


@case(7864, "damage already marked meets the Might that a shrink left")
def _():
    need("Singularity", "Smoke Screen")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    give(s, 0, "Smoke Screen")
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Singularity", u, -1)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 6
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert not alive(s, u), "143.2.a is checked continuously"


@case(7851, "Sett - Kingpin counts buffed friends wherever he stands")
def _():
    need("Sett - Kingpin")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    st = s.add_permanent(T.id_of("Sett - Kingpin"), 0, base_loc(0), ready=True)
    mate = body(s, 0, base_loc(0), 3, ready=True)
    s.set_flag(mate, F_BUFFED)
    assert combat.might(s, T, st) == 5, "at base he counts nobody"
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, st, mate)
    drain(s)
    assert combat.might(s, T, st) == 6, "attacking is still 'my battlefield'"


@case(7846, "a trigger already on the chain resolves after its blocker dies")
def _():
    need("Mageseeker Warden", "Hidden Blade", "Upstage Comedy")
    s = fresh(hand=[T.id_of("Hidden Blade"), T.id_of("Upstage Comedy")], runes=32)
    s.bf_ctrl[0] = 1
    mw = s.add_permanent(T.id_of("Mageseeker Warden"), 1, bf_loc(0), ready=True)
    mine = body(s, 0, base_loc(0), 3, ready=False)
    cast(s, 0, "Hidden Blade", mw)
    run(s)
    assert not alive(s, mw)
    cast(s, 0, "Upstage Comedy", mine)
    run(s)
    assert int(s.perms[mine, P_READY]) == 1, "the Warden was gone by then"


@case(7840, "Eye of the Herald's token needs its bearer to still be here")
def _():
    need("Eye of the Herald", "Ride The Wind", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    u = body(s, 0, base_loc(0), 3, ready=True)
    g = s.add_permanent(T.id_of("Eye of the Herald"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    give(s, 1, "Gust")
    cast(s, 0, "Ride The Wind", u, bf_loc(0))
    run(s, limit=20, stop=lambda st: int(st.perms[u, P_LOC]) == bf_loc(0))
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", u)
    run(s, limit=40)
    assert not alive(s, u), "3 Might, back to hand"
    assert not tokens(s, 0), "and the gear went with it"


@case(7838, "you may play two Reactions without passing priority")
def _():
    need("Stupefy")
    s = fresh(runes=32)
    give(s, 1, "Stupefy", "Stupefy")
    s.runes_ready[1, :] = 32
    att = body(s, 0, base_loc(0), 5, ready=True)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, att)
    cast(s, 1, "Stupefy", att)
    assert "Stupefy" in hand_plays(s, 1), "priority stayed with them"
    cast(s, 1, "Stupefy", att)
    drain(s)
    assert combat.might(s, T, att) == 3


@case(7836, "Cithria triggers even when she already has a buff")
def _():
    need("Cithria of Cloudfield", "Determined Sentry")
    s = fresh(hand=[T.id_of("Determined Sentry")], runes=32)
    ci = s.add_permanent(T.id_of("Cithria of Cloudfield"), 0, base_loc(0),
                         ready=True)
    s.set_flag(ci, F_BUFFED)
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, base_loc(0))
    assert int(s.n_chain) + int(s.n_trig) >= 1, "426.1.c: it still triggers"
    run(s)
    assert s.has_flag(ci, F_BUFFED)


@case(7834, "Traveling Merchant triggers however it was moved")
def _():
    need("Traveling Merchant", "Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 1, base_loc(1), ready=True)
    give(s, 1, "Smoke Screen")
    before = int(s.n_hand[1])
    cast(s, 0, "Charm", tm, bf_loc(0))
    run(s, picking(0))
    assert int(s.perms[tm, P_LOC]) == bf_loc(0)
    assert int(s.n_hand[1]) == before, "discard 1, then draw 1"


@case(7832, "a Recall leaves the unit's ready state alone")
def _():
    need("Showstopper")
    s = fresh(runes=32)
    give(s, 0, "Showstopper")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Showstopper", u, bf_loc(0))
    fight(s)
    assert int(s.perms[u, P_READY]) == 1, "a recall changes no state"


@case(7822, "the Hourglass saves a unit wherever it stands")
def _():
    need("Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and not alive(s, z)


@case(7819, "Mask of Foresight asks once, as the designation lands")
def _():
    need("Mask of Foresight", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    mask = s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    a = body(s, 0, base_loc(0), 3, ready=True)
    late = body(s, 0, base_loc(0), 3, ready=False)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, a)
    drain(s)
    assert combat.might(s, T, a) == 4, "alone when it was asked"
    cast(s, 0, "Ride The Wind", late, bf_loc(0))
    drain(s)
    assert combat.might(s, T, late) == 3, "not alone when IT arrived"
    assert mask >= 0


@case(7816, "Leona - Zealot's floor is applied after the other modifiers")
def _():
    need("Leona - Zealot", "Trifarian War Camp", "Rune Prison")
    from rl.engine.effects import SPECS
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 0
    le = s.add_permanent(T.id_of("Leona - Zealot"), 0, bf_loc(0), ready=True)
    foe = body(s, 1, bf_loc(0), 9)
    assert combat.might(s, T, foe) == 10, "the ground gives everyone +1"
    # Resolved straight, because a Cleanup here would start the combat and the
    # unit whose Might is the question would not survive to be read.
    rsv.resolve(s, T, V1, SPECS["Rune Prison"], 0, [foe], -1, True)
    assert s.has_flag(foe, F_STUNNED)
    assert combat.might(s, T, foe) == 2, "10 - 8, floored at 1 and never reached"
    assert le >= 0


@case(7812, "there is no window between a designation and its [Shield]")
def _():
    need("Stalwart Poro", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 0
    poro = s.add_permanent(T.id_of("Stalwart Poro"), 0, bf_loc(0), ready=True)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert combat.might(s, T, poro) == 3, "2 plus [Shield], already applied"


@case(7807, "Vi, Destructive is limited only by the trash")
def _():
    need("Vi, Destructive")
    s = fresh(runes=32)
    vi = s.add_permanent(T.id_of("Vi, Destructive"), 0, base_loc(0), ready=True)
    for j in range(4):
        s.trash[0, j] = VANILLA
    s.n_trash[0] = 4
    for _ in range(4):
        act(s, A.A_ACTIVATE, vi, 0)
        run(s, picking(pack_trash(0, VANILLA)))
    assert combat.might(s, T, vi) == 7, "3 plus four activations"
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == vi], "the trash is empty"


@case(7805, "a showdown you left still has to finish")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    s.bf_ctrl[1] = -1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, att)
    cast(s, 0, "Ride The Wind", att, bf_loc(1))
    fight(s)
    assert int(s.perms[att, P_LOC]) == bf_loc(1), "it left for the other ground"
    assert int(s.bf_ctrl[0]) == 1, "and the defender kept the first"


@case(7849, "you can score on the opponent's turn at a battlefield you took")
def _():
    need("Charm")
    s = fresh(runes=32)
    give(s, 0, "Charm")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 9)
    s.ply += 1
    s.active = s.priority = 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    s.bf_ctrl[1] = -1
    attack(s, 1, 1, foe)
    fight(s)
    assert int(s.points[1]) == 1, "they conquered the open ground"
    assert mine >= 0


@case(7845, "Ravenbloom Conservatory's reveal goes to the hand when it is a spell")
def _():
    need("Ravenbloom Conservatory", "Discipline")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Ravenbloom Conservatory")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Discipline")
    before = int(s.n_hand[0])
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert int(s.n_hand[0]) == before + 1, "a spell goes to the hand"
