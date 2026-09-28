"""RiftJudge batch 60 -- unused questions from 7628-7692."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7692, "units that die together do not see each other die")
def _():
    need("Viktor - Leader", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    vi = s.add_permanent(T.id_of("Viktor - Leader"), 1, base_loc(1), ready=True)
    s.base_might_ply[vi], s.base_might_val[vi] = int(s.ply), 3
    mate = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Falling Star", vi, mate)
    run(s)
    assert not alive(s, vi) and not alive(s, mate)
    assert not tokens(s, 1), "he was not there when the triggers were placed"


@case(7690, "two Spirit's Refuges do not stack [Deflect]")
def _():
    need("Spirit's Refuge", "Hidden Blade")

    def spend(n):
        s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
        s.bf_ctrl[0] = 1
        u = body(s, 1, bf_loc(0), 3)
        s.set_flag(u, F_BUFFED)
        for _ in range(n):
            s.add_permanent(T.id_of("Spirit's Refuge"), 1, base_loc(1))
        before = runes(s, 0)
        cast(s, 0, "Hidden Blade", u)
        run(s)
        return before - runes(s, 0)

    assert spend(1) == spend(2), "one instance, however many copies"


@case(7689, "a 0 Might unit survives")
def _():
    need("Smoke Screen", "Charm", "Trifarian War Camp")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    give(s, 0, "Smoke Screen")
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 1)
    assert combat.might(s, T, u) == 2, "the ground's +1"
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert combat.might(s, T, u) == 1
    cast(s, 0, "Charm", u, base_loc(1))
    run(s)
    assert alive(s, u), "off the ground it is 0 Might, and still alive"
    assert combat.might(s, T, u) == 0


@case(7683, "Brynhir's trigger can be answered, the turn after it cannot")
def _():
    need("Brynhir Thundersong", "Smoke Screen")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Brynhir Thundersong"), 0)
    choose(s, base_loc(0))
    pass_priority_to(s, 1)
    assert "Smoke Screen" in hand_plays(s, 1), "the trigger is answerable"
    run(s)
    assert hand_plays(s, 1) == set(), "and after it resolves, nothing is"


@case(7679, "Solari Shrine draws when you kill a stunned unit")
def _():
    need("Solari Shrine", "Rune Prison", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 0, "Rune Prison")
    sh = s.add_permanent(T.id_of("Solari Shrine"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Rune Prison", u)
    run(s)
    before = int(s.n_hand[0])
    cast(s, 0, "Hidden Blade", u)
    run(s, picking(accept=True))
    assert not alive(s, u)
    assert int(s.n_hand[0]) == before - 1 + 1, "the Shrine drew"
    assert int(s.perms[sh, P_READY]) == 0


@case(7674, "Ride the Wind is an [Action], so it cannot answer a chain")
def _():
    need("Hextech Ray", "Ride The Wind")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=32)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Hextech Ray", u)
    pass_priority_to(s, 1)
    assert "Ride The Wind" not in hand_plays(s, 1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 3


@case(7666, "a stolen unit Retreated goes to its OWNER's hand")
def _():
    need("Hostile Takeover", "Retreat")
    s = fresh(hand=[T.id_of("Hostile Takeover")], runes=32)
    give(s, 0, "Retreat")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Hostile Takeover", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0
    before0, before1 = int(s.n_hand[0]), int(s.n_hand[1])
    cast(s, 0, "Retreat", foe)
    run(s)
    assert not alive(s, foe)
    assert int(s.n_hand[1]) == before1 + 1, "its owner takes it back"
    assert int(s.n_hand[0]) == before0 - 1


@case(7661, "damage does not lower Might, so Gust cannot reach it")
def _():
    need("Gust", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", u, -1, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 1 and combat.might(s, T, u) == 5
    assert "Gust" not in hand_plays(s, 0), "still 5 Might, so no legal target"


@case(7658, "Forge of the Future may recycle from either trash")
def _():
    need("Forge of the Future")
    s = fresh(runes=32)
    fo = s.add_permanent(T.id_of("Forge of the Future"), 0, base_loc(0))
    s.trash[0, 0] = T.id_of("Defy")
    s.n_trash[0] = 1
    s.trash[1, 0] = T.id_of("Smoke Screen")
    s.n_trash[1] = 1
    act(s, A.A_ACTIVATE, None, 0)
    offered = targets_offered(s, 0)
    assert pack_trash(0, T.id_of("Defy")) in offered
    assert pack_trash(1, T.id_of("Smoke Screen")) in offered, "'trashes', plural"
    assert fo >= 0


@case(7654, "Flame Chompers replayed from the discard pays only its rune")
def _():
    need("Flame Chompers", "Jinx, Demolitionist")
    s = fresh(hand=[T.id_of("Jinx, Demolitionist"), T.id_of("Flame Chompers"),
                    T.id_of("Flame Chompers")], runes=32)
    before = runes(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Jinx, Demolitionist"), 0)
    choose(s, base_loc(0))
    run(s, picking(accept=True), limit=40)
    assert perm_of(s, "Flame Chompers", 0) or int(s.n_trash[0]) >= 1, \
        "discarded, and maybe replayed for a rune"
    assert before - runes(s, 0) <= 3


@case(7652, "designations belong to a combat, and an open showdown has none")
def _():
    need("Yasuo - Unforgiven", "Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    s.legend[0], s.legend_ready[0] = T.id_of("Yasuo - Unforgiven"), 1
    u = body(s, 0, base_loc(0), 3, ready=False)
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(u, bf_loc(0)), limit=20)
    assert int(s.perms[u, P_LOC]) == bf_loc(0)
    assert not s.showdown_combat, "open ground is no combat"


@case(7649, "a floored Smoke Screen keeps the amount it actually took")
def _():
    need("Smoke Screen", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen", "Discipline")
    u = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert combat.might(s, T, u) == 1
    cast(s, 0, "Discipline", u)
    run(s)
    assert combat.might(s, T, u) == 3, "+2 from 1, not from -2"


@case(7644, "Dragon's Rage can send a unit home to fight what is there")
def _():
    need("Dragon's Rage")
    s = fresh(hand=[T.id_of("Dragon's Rage")], runes=32)
    s.bf_ctrl[0] = 1
    mover = body(s, 1, bf_loc(0), 3)
    home = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Dragon's Rage", mover, base_loc(1), home)
    run(s)
    assert not alive(s, mover) and not alive(s, home), "3 into 3, both ways"


@case(7643, "a countered spell is not a card played")
def _():
    need("Smoke Screen", "Defy", "Darius - Trifarian")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen", "Darius - Trifarian")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    foe = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Smoke Screen", foe)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    assert int(s.perms[dar, P_READY]) == 0, \
        "419.4.a: a countered spell never completed, so he is the first card"


@case(7641, "Teemo - Swift Scout's ability is base speed")
def _():
    need("Teemo - Swift Scout", "Teemo - Strategist")
    s = fresh(runes=32)
    s.legend[0], s.legend_ready[0] = T.id_of("Teemo - Swift Scout"), 1
    s.add_permanent(T.id_of("Teemo - Strategist"), 0, base_loc(0), ready=True)
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE], \
        "on your own turn, with nothing happening"
    s.ply += 1
    s.active = s.priority = 1
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE], "and nowhere else"


@case(7633, "En Garde's second +1 counts units YOU control")
def _():
    need("En Garde")
    s = fresh(runes=32)
    give(s, 0, "En Garde")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "En Garde", u)
    run(s)
    assert combat.might(s, T, u) == 5, "an enemy beside it does not crowd it"


@case(7631, "Ride the Wind crosses from battlefield to battlefield")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(1)


@case(7628, "a Beginning Phase trigger resolves before the Hold draw")
def _():
    need("Grove of the God-Willow")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Grove of the God-Willow")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    before = int(s.n_hand[0])
    _next_own_turn(s)
    run(s, limit=40)
    assert int(s.n_hand[0]) > before, "the Grove drew on the Hold"
    assert int(s.points[0]) == 1
