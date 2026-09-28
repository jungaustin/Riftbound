"""RiftJudge batch 11 -- unused questions from 12423-12604."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, P_ATTACHED_TO, P_MIGHT_MOD, P_EMPOWER
from rl.engine.effects import ABILITIES, BF_ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(12430, "Azir - Sovereign's attack moves exhausted token units from base too")
def _():
    need("Azir - Sovereign", "Sprite Call")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    tok = tokens(s, 0)[0]
    s.perms[tok, P_READY] = 0
    az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, az)
    run(s, picks(tok, -1, -1, -1), stop=lambda s: int(s.perms[tok, P_LOC]) == bf_loc(0))
    assert int(s.perms[tok, P_LOC]) == bf_loc(0)


@case(12434, "Retreating Astral Heron with your first card: no discount")
def _():
    need("Astral Heron", "Retreat")
    s = fresh(hand=[T.id_of("Retreat")])
    rune_deck(s)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Retreat", her)
    run(s)
    assert int(s.next_discount[0].sum()) == 0


@case(12437, "Svellsongur on Jayce, Brilliant Inventor: the first gear readies two things")
def _():
    need("Svellsongur", "Jayce, Brilliant Inventor")
    s = fresh(hand=[T.id_of("Frigid Jewel")])
    j = s.add_permanent(T.id_of("Jayce, Brilliant Inventor"), 0, base_loc(0))
    sv = s.add_permanent(T.id_of("Svellsongur"), 0, base_loc(0))
    s.attach(sv, j)
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Frigid Jewel", base_loc(0))
    run(s, picks(a, b))
    assert int(s.perms[a, P_READY]) == 1 and int(s.perms[b, P_READY]) == 1


@case(12438, "Ride the Wind moves Ravenbloom Student into Abandoned Hall: +1 and +1")
def _():
    need("Ride The Wind", "Ravenbloom Student", "Abandoned Hall")
    s = fresh(hand=[T.id_of("Ride The Wind")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    cast(s, 0, "Ride The Wind", st, bf_loc(0))
    run(s, picking(st))
    assert combat.might(s, T, st) == 4, combat.might(s, T, st)


@case(12460, "Morgana, Vindictive's play trigger cannot choose Baron Nashor")
def _():
    need("Morgana, Vindictive", "Baron Nashor")
    s = fresh(hand=[T.id_of("Morgana, Vindictive")], runes=9)
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, base_loc(1))
    s.perms[bn, P_DMG] = 3
    other = body(s, 1, base_loc(1), 9)
    s.perms[other, P_DMG] = 1
    cast(s, 0, "Morgana, Vindictive", base_loc(0))
    offered = targets_offered(s, 0)
    assert other in offered and bn not in offered, offered


@case(12465, "Abandon on a spell played with Flow: it is banished, not returned")
def _():
    need("Abandon", "Public Execution")
    s = fresh(runes=12)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Public Execution"), 1
    give(s, 1, "Abandon")
    mine = body(s, 0, base_loc(0), 5)
    foe = body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY_FLOW, None, 0)
    choose(s, mine)
    choose(s, foe)
    cast(s, 1, "Abandon", top_uid(s))
    run(s, picking(accept=False))
    assert alive(s, foe) and int(s.n_banished[0]) == 1 and int(s.n_hand[0]) == 0


@case(12466, "Zenith Blade cannot choose Akali, Silent sitting alone at a battlefield")
def _():
    need("Zenith Blade", "Akali, Silent")
    s = fresh(hand=[T.id_of("Zenith Blade")])
    ak = s.add_permanent(T.id_of("Akali, Silent"), 1, bf_loc(0))
    s.bf_ctrl[0] = 1
    other = body(s, 1, bf_loc(1), 3)
    s.bf_ctrl[1] = 1
    act(s, A.A_PLAY, 0, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert other in offered and ak not in offered, offered


@case(12471, "Tideturner from hidden may choose a unit at your base")
def _():
    need("Tideturner")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    home = body(s, 0, base_loc(0), 3)
    hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    assert home in targets_offered(s, 0)


@case(12472, "Jayce, Brilliant Inventor's play does not use up the first-gear trigger")
def _():
    need("Jayce, Brilliant Inventor", "Frigid Jewel")
    s = fresh(hand=[T.id_of("Jayce, Brilliant Inventor"), T.id_of("Frigid Jewel")], runes=12)
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Jayce, Brilliant Inventor", base_loc(0))
    run(s, picks(a))
    cast(s, 0, "Frigid Jewel", base_loc(0))
    run(s, picks(b))
    assert int(s.perms[a, P_READY]) == 1 and int(s.perms[b, P_READY]) == 1


@case(12475, "Wild Claw playing Kayle, Justified empowers her once")
def _():
    need("Wild Claw", "Kayle, Justified")
    s = fresh(hand=[T.id_of("Wild Claw")], runes=12)
    s.deck[0, :5] = [T.id_of("Kayle, Justified")] + [VANILLA] * 4
    cast(s, 0, "Wild Claw")
    run(s, picking(0))
    k = perm_of(s, "Kayle, Justified")
    assert k and s.empower_count(k[0]) == 1 and combat.might(s, T, k[0]) == 5


@case(12479, "Vex - Apathetic stuns Akali, Silent: the stun does not choose her")
def _():
    need("Vex - Apathetic", "Akali, Silent")
    s = fresh(hand=[T.id_of("Akali, Silent")], runes=9)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    cast(s, 0, "Akali, Silent", base_loc(0))
    run(s)
    ak = perm_of(s, "Akali, Silent")[0]
    assert s.has_flag(ak, F_STUNNED)


@case(12482, "Trusty Ramhound takes 2 while its ally takes lethal: Ramhound lives")
def _():
    need("Trusty Ramhound")
    s = fresh()
    s.bf_ctrl[0] = 1
    ally = body(s, 1, bf_loc(0), 3)                    # the attacker kills this one...
    rh = s.add_permanent(T.id_of("Trusty Ramhound"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 5, ready=True)         # ...and 2 spill onto Ramhound
    attack(s, 0, 0, a)
    fight(s)
    run(s)
    assert not alive(s, ally) and alive(s, rh), "3 Might at the lethal check, then healed"


@case(12486, "Blue Sentinel doubles the battlefield's own hold effect too")
def _():
    need("Blue Sentinel", "Altar to Unity")
    s = fresh()
    s.bf_card[0] = T.id_of("Altar to Unity")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(), stop=lambda s: int(s.active) == 1 and s.n_chain == 0 and s.n_trig == 0)
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert len(tokens(s, 0)) == 2, len(tokens(s, 0))


@case(12498, "a token unit is not a card: Astral Heron does not trigger")
def _():
    need("Astral Heron", "Viktor - Herald of the Arcane")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    s.legend[0], s.legend_ready[0] = T.id_of("Viktor - Herald of the Arcane"), 1
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(base_loc(0)))
    assert tokens(s, 0) and int(s.next_discount[0].sum()) == 0


@case(12518, "The Harrowing as the first card: Darius - Trifarian enters as the second")
def _():
    need("The Harrowing", "Darius - Trifarian")
    s = fresh(hand=[T.id_of("The Harrowing")], runes=12)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Darius - Trifarian"), 1
    cast(s, 0, "The Harrowing", pack_trash(0, T.id_of("Darius - Trifarian")), base_loc(0))
    run(s)
    d = perm_of(s, "Darius - Trifarian")
    assert d and int(s.perms[d[0], P_READY]) == 1 and combat.might(s, T, d[0]) == 7


@case(12520, "Switcheroo with an empowered Mel: the unit losing Might loses 1 more")
def _():
    need("Switcheroo", "Mel, Newly Awakened")
    s = fresh()
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    small = body(s, 0, bf_loc(0), 2)
    big = body(s, 1, bf_loc(0), 6)
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 0, [small, big], -1, True)
    assert combat.might(s, T, small) == 6 and combat.might(s, T, big) == 1, (
        combat.might(s, T, small), combat.might(s, T, big))


@case(12525, "Heron's discount is not live while the first card is still on the Chain")
def _():
    need("Astral Heron", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline"), T.id_of("Defy")])
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Discipline", u)
    assert int(s.next_discount[0].sum()) == 0


@case(12526, "Bullet Time damages Baron Nashor: it chooses a battlefield, not him")
def _():
    need("Bullet Time", "Baron Nashor")
    s = fresh(hand=[T.id_of("Bullet Time")])
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(0))
    s.bf_ctrl[0] = 1
    cast(s, 0, "Bullet Time", bf_loc(0))
    run(s, picking(3, accept=True))
    assert int(s.perms[bn, P_DMG]) > 0


@case(12530, "Switcheroo at Forbidding Waste: the swap uses the -2 already applied")
def _():
    need("Switcheroo", "Forbidding Waste")
    s = fresh()
    give(s, 0, "Smoke Screen")
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 0
    d = body(s, 0, bf_loc(0), 3)
    a = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, a)
    assert s.showdown_bf == 0 and combat.might(s, T, d) == 1
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 0, [a, d], -1, True)
    assert combat.might(s, T, a) == 1 and combat.might(s, T, d) == 5


@case(12535, "Temporal Breach on an equipped token: gone, and the gear stays unattached")
def _():
    need("Temporal Breach", "Soul Sword")
    s = fresh()
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    tok = tokens(s, 0)[0]
    sw = s.add_permanent(T.id_of("Soul Sword"), 0, base_loc(0))
    s.attach(sw, tok)
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 1, [tok], -1, True)
    run(s)
    assert not tokens(s, 0) and alive(s, sw) and int(s.perms[sw, P_ATTACHED_TO]) < 0


@case(12545, "Star-Crossed with one target Temporal Breached: the other still returns")
def _():
    need("Star-Crossed", "Temporal Breach")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Star-Crossed", mine, foe)
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 1, [foe], -1, True)
    run(s)
    assert not alive(s, mine) and len(units(s, 1)) == 1


@case(12561, "Akali, Deadly Weapon moving in on a lone Akali, Silent: no legal target")
def _():
    need("Akali, Deadly Weapon", "Akali, Silent")
    s = fresh()
    s.bf_ctrl[0] = 1
    sil = s.add_permanent(T.id_of("Akali, Silent"), 1, bf_loc(0))
    dw = s.add_permanent(T.id_of("Akali, Deadly Weapon"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, dw)
    assert sil not in targets_offered(s, 0)


@case(12598, "Temporal Breach replaying a unit spends Astral Heron's discount")
def _():
    need("Temporal Breach", "Astral Heron")
    s = fresh(hand=[T.id_of("Discipline")])
    s.next_discount[0, :] = 2
    u = body(s, 0, base_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [u], -1, True)
    run(s)
    assert int(s.next_discount[0].sum()) == 0


@case(12600, "Rift Herald killed in answer to its move trigger: still look at 3")
def _():
    need("Rift Herald", "Hidden Blade")
    s = fresh()
    h = s.add_permanent(T.id_of("Rift Herald"), 0, base_loc(0))
    s.deck[0, :5] = [VANILLA, VANILLA, T.id_of("Watchful Sentry"), VANILLA, VANILLA]
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [h, bf_loc(0)], -1, True)
    A._settle(s, T, V1)
    assert "Rift Herald" in chain_names(s)
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 1, [h], -1, True)
    run(s, picks(0, 0))                                # Deathknell's unit, then the look
    assert T.id_of("Watchful Sentry") in list(s.hand[0, :int(s.n_hand[0])])
