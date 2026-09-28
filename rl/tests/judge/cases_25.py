"""RiftJudge batch 25 -- unused questions from 9893-9971."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(9971, "a Zenith Blade that brings combat to Atakhan makes him attack")
def _():
    need("Atakhan", "Zenith Blade")
    s = fresh(runes=12)
    s.runes_ready[1, :] = 9
    give(s, 1, "Zenith Blade")
    at = s.add_permanent(T.id_of("Atakhan"), 0, base_loc(0), ready=True)
    other = body(s, 1, base_loc(1), 3)
    attack(s, 0, 0, at)
    assert "Atakhan" not in chain_names(s), "an empty battlefield: no attack yet"
    cast(s, 1, "Zenith Blade", at)
    run(s, picks(other), stop=lambda s: "Atakhan" in chain_names(s))
    assert int(s.perms[other, P_LOC]) == bf_loc(0)
    assert "Atakhan" in chain_names(s), "the combat designated him an attacker"


@case(9969, "a stunned unit still deals full Alpha Strike damage")
def _():
    need("Alpha Strike")
    s = fresh(hand=[T.id_of("Alpha Strike")], runes=9)
    u = body(s, 0, base_loc(0), 3)
    assert s.stun(u)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Alpha Strike", u)
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) == 3, int(s.perms[foe, P_DMG])


@case(9968, "Flash to base dodges Elder Dragon's per-location targets")
def _():
    need("Elder Dragon", "Flash")
    s = fresh(seat=1, runes=12)
    s.runes_ready[0, :] = 9
    give(s, 1, "Elder Dragon")
    give(s, 0, "Flash")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    u1 = body(s, 0, bf_loc(0), 5)
    u2 = body(s, 0, bf_loc(1), 5)
    cast(s, 1, "Elder Dragon", base_loc(1))
    run(s, picks(u1, u2), stop=lambda s: "Elder Dragon" in chain_names(s)
        and s.pend_slot < 0 and not chain_mod.decision_open(s))
    cast(s, 0, "Flash", u1, u2)
    run(s)
    assert alive(s, u1) and alive(s, u2)
    assert int(s.perms[u1, P_DMG]) == 0 and int(s.perms[u2, P_DMG]) == 0


@case(9967, "Ride The Wind is an [Action]: no answer to a Hidden Blade outside a showdown")
def _():
    need("Ride The Wind", "Hidden Blade")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[1] = 1
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    hidden_at(s, 1, 1, "Hidden Blade")
    body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY_HIDDEN, None, 1)
    pass_priority_to(s, 0)
    assert "Ride The Wind" not in hand_plays(s, 0), hand_plays(s, 0)


@case(9965, "Void Assault needs a friendly unit to move")
def _():
    need("Void Assault")
    s = fresh(hand=[T.id_of("Void Assault")], runes=9)
    body(s, 1, base_loc(1), 3)
    assert "Void Assault" not in hand_plays(s, 0)
    body(s, 0, base_loc(0), 3)
    assert "Void Assault" in hand_plays(s, 0)


@case(9962, "holding Reckoner's Arena with Yone is not conquering an open battlefield")
def _():
    need("Reckoner's Arena", "Yone - Blademaster")
    s = fresh()
    s.bf_card[0] = T.id_of("Reckoner's Arena")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Yone - Blademaster"), 0, bf_loc(0))
    foe = body(s, 1, base_loc(1), 9)
    _next_own_turn(s)
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) == 0


@case(9960, "Cruel Patron may be played where its killed unit stood alone")
def _():
    need("Cruel Patron")
    s = fresh(hand=[T.id_of("Cruel Patron")], runes=9)
    s.bf_ctrl[0] = 0
    lone = body(s, 0, bf_loc(0), 1)
    act(s, A.A_PLAY, hand_index(s, 0, "Cruel Patron"), 0)
    choose(s, lone)
    assert int(s.bf_ctrl[0]) == 0, "187.4.c -- mid-play, control is not lost"
    choose(s, bf_loc(0))
    run(s)
    cp = perm_of(s, "Cruel Patron")
    assert cp and int(s.perms[cp[0], P_LOC]) == bf_loc(0) and not alive(s, lone)


@case(9957, "a hidden Guards! puts its Sand Soldier at that battlefield")
def _():
    need("Guards!")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    hidden_at(s, 0, 1, "Guards!")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    dests = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_TARGET, A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert base_loc(0) not in dests, dests
    run(s, picking(bf_loc(1), accept=False))
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_LOC]) == bf_loc(1)


@case(9954, "Stalking Wolf may go somewhere other than its victim's battlefield")
def _():
    need("Stalking Wolf", "Lonely Poro")
    s = fresh(hand=[T.id_of("Stalking Wolf")], runes=9)
    s.bf_ctrl[0] = 0
    poro = s.add_permanent(T.id_of("Lonely Poro"), 0, bf_loc(0))
    act(s, A.A_PLAY, hand_index(s, 0, "Stalking Wolf"), 0)
    choose(s, poro)
    dests = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert base_loc(0) in dests and bf_loc(0) in dests, dests
    choose(s, base_loc(0))
    run(s)
    sw = perm_of(s, "Stalking Wolf")
    assert sw and int(s.perms[sw[0], P_LOC]) == base_loc(0)


@case(9952, "Lunar Boon may be played with no other card in hand")
def _():
    need("Lunar Boon")
    s = fresh(hand=[T.id_of("Lunar Boon")], runes=9)
    assert "Lunar Boon" in hand_plays(s, 0)
    cast(s, 0, "Lunar Boon")
    run(s)
    assert int(s.n_hand[0]) == 2, "nothing to discard, still draw 2"


@case(9948, "Revna asks what was spent, not the spell's printed cost")
def _():
    need("Revna the Lorekeeper", "Falling Comet", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    rv = s.add_permanent(T.id_of("Revna the Lorekeeper"), 0, base_loc(0), ready=False)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    run(s)
    assert int(s.perms[rv, P_READY]) == 0, "2 spent is not 4"
    give(s, 0, "Falling Comet")
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Falling Comet", foe)
    run(s)
    assert int(s.perms[rv, P_READY]) == 1, "5 spent"


@case(9946, "Ravenbloom Student gets nothing for a countered spell")
def _():
    need("Ravenbloom Student", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, st) == 2


@case(9944, "Yordle Explorer reads the printed Power, not an optional extra")
def _():
    need("Yordle Explorer", "Akshan - Mischievous")
    s = fresh(hand=[T.id_of("Akshan - Mischievous")], runes=9)
    s.add_permanent(T.id_of("Yordle Explorer"), 0, base_loc(0))
    act(s, A.A_PLAY, hand_index(s, 0, "Akshan - Mischievous"), 0)
    fast = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT_FAST]
    if fast:
        A.apply(s, T, V1, fast[0])
    else:
        choose(s, base_loc(0))
    run(s, picking(accept=False))
    assert int(s.n_hand[0]) == 0, "printed Power 1: no draw"


@case(9943, "a Defied card is not Darius - Trifarian's second card")
def _():
    need("Darius - Trifarian", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 0, "Discipline")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    dar = s.add_permanent(T.id_of("Darius - Trifarian"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    run(s)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, dar) == 5, combat.might(s, T, dar)


@case(9942, "Abandon on your own Falling Star after Not So Fast: back to hand")
def _():
    need("Abandon", "Falling Star", "Not So Fast")
    s = fresh(hand=[T.id_of("Falling Star")], runes=9)
    give(s, 0, "Abandon")
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    foe = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Falling Star", foe, foe)
    mine = top_uid(s)
    cast(s, 1, "Not So Fast", mine)
    cast(s, 0, "Abandon", mine)
    run(s, picking(accept=False))
    assert T.id_of("Falling Star") in list(s.hand[0, :int(s.n_hand[0])])
    assert int(s.perms[foe, P_DMG]) == 0


@case(9941, "Frigid Touch twice then Discipline: Mutated Mouser at 1")
def _():
    need("Frigid Touch", "Discipline", "Mutated Mouser")
    s = fresh(hand=[T.id_of("Frigid Touch")], runes=9)
    mm = s.add_permanent(T.id_of("Mutated Mouser"), 1, base_loc(1))
    cast(s, 0, "Frigid Touch", mm, mm, repeat=True)
    run(s)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 1, [mm], -1, True)
    assert combat.might(s, T, mm) == 0, combat.might(s, T, mm)


@case(9940, "Alpha Strike cannot split damage onto Baron Nashor")
def _():
    need("Alpha Strike", "Baron Nashor")
    s = fresh(hand=[T.id_of("Alpha Strike")], runes=9)
    u = body(s, 0, base_loc(0), 5)
    s.bf_ctrl[1] = 1
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(1))
    foe = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Alpha Strike"), 0)
    choose(s, u)
    seen = set()

    def pref(s, who, legal):
        seen.update(a.arg for a in legal if a.kind == A.A_TARGET)
        return None
    run(s, pref)
    assert bn not in seen and foe in seen, seen


@case(9935, "Moonlight Affliction can drive Might below 0, and it stays there")
def _():
    need("Moonlight Affliction")
    s = fresh(hand=[T.id_of("Moonlight Affliction")], runes=9)
    u = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Moonlight Affliction", u)
    run(s)
    assert combat.might(s, T, u) == 0 and alive(s, u), "negative counts as 0; no damage"
    combat.set_might_mod(s, T, u, 12)
    assert combat.might(s, T, u) == 5, "3 - 10 + 12"


@case(9932, "Moonlight Affliction alone does not kill an undamaged Gromp")
def _():
    need("Moonlight Affliction", "Voracious Gromp")
    s = fresh(hand=[T.id_of("Moonlight Affliction")], runes=9)
    g = s.add_permanent(T.id_of("Voracious Gromp"), 1, base_loc(1))
    cast(s, 0, "Moonlight Affliction", g)
    run(s)
    assert alive(s, g), "lethal damage must be non-zero"


@case(9931, "Sacrifice on a Tactical Retreated Ruined Rex: no Deathknell")
def _():
    need("Sacrifice", "Tactical Retreat", "Ruined Rex")
    s = fresh(hand=[T.id_of("Tactical Retreat")], runes=9)
    give(s, 0, "Sacrifice")
    rune_deck(s)
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Tactical Retreat", rex)
    run(s)
    cast(s, 0, "Sacrifice", rex)
    run(s, picking(foe))
    assert alive(s, rex) and int(s.perms[foe, P_DMG]) == 0
    assert int(s.n_hand[0]) == 2


@case(9927, "Meditation may exhaust the Temporary unit whose trigger it answers")
def _():
    need("Meditation", "Sprite Call")
    s = fresh()
    sprite = _sprite_at(s, 0, 0)
    s.perms[sprite, P_READY] = 0
    give(s, 0, "Meditation")
    s.runes_ready[0, :] = 6
    _next_own_turn(s)
    assert int(s.perms[sprite, P_READY]) == 1, "the Awaken Phase readied it first"
    cast(s, 0, "Meditation", repeat=True)
    run(s, picks(sprite))
    assert int(s.n_hand[0]) == 3, int(s.n_hand[0])      # its turn draw + 2


@case(9926, "Imperial Decree does not reach back to damage already dealt")
def _():
    need("Imperial Decree", "Bellows Breath")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=9)
    u = body(s, 1, base_loc(1), 5)
    rsv.resolve(s, T, V1, SPECS["Bellows Breath"], 0, [u, -1, -1], -1, True)
    assert int(s.perms[u, P_DMG]) == 1
    cast(s, 0, "Imperial Decree")
    run(s)
    assert alive(s, u)


@case(9924, "damage already marked counts toward lethal assignment")
def _():
    need("Flurry of Blades")
    s = fresh()
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 2)
    rsv.resolve(s, T, V1, SPECS["Flurry of Blades"], 0, [], -1, True)
    assert int(s.perms[u, P_DMG]) == 1
    assert combat.lethal_cost(s, T, u) == 1


@case(9920, "a countered big spell still lets Jhin, Meticulous Killer cost [C]")
def _():
    need("Jhin - Meticulous Killer", "Singularity", "Hard Bargain")
    s = fresh(hand=[T.id_of("Singularity")], runes=9)
    give(s, 0, "Jhin - Meticulous Killer")
    give(s, 1, "Hard Bargain")
    s.runes_ready[1, :] = 9
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Singularity", foe, -1)
    cast(s, 1, "Hard Bargain", top_uid(s))
    run(s, picking(accept=False))
    assert alive(s, foe), "countered"
    s.runes_ready[0, :] = 0
    dom = int(T.domain_mask[T.id_of("Jhin - Meticulous Killer")]).bit_length() - 1
    s.runes_ready[0, dom] = 1
    assert "Jhin - Meticulous Killer" in hand_plays(s, 0), hand_plays(s, 0)


@case(9918, "Counter Strike prevents Elder Dragon's damage, so nothing dies")
def _():
    need("Counter Strike", "Elder Dragon")
    s = fresh(seat=1, runes=12)
    s.runes_ready[0, :] = 9
    give(s, 1, "Elder Dragon")
    give(s, 0, "Counter Strike")
    u = body(s, 0, base_loc(0), 5)
    cast(s, 1, "Elder Dragon", base_loc(1))
    run(s, picks(u), stop=lambda s: "Elder Dragon" in chain_names(s)
        and s.pend_slot < 0 and not chain_mod.decision_open(s))
    cast(s, 0, "Counter Strike", u)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 0


@case(9913, "Turn to Dust on an attached Equipment: it dies next Beginning Phase")
def _():
    need("Turn to Dust", "Spinning Axe")
    s = fresh(hand=[T.id_of("Turn to Dust")], runes=9)
    u = body(s, 0, base_loc(0), 3)
    ax = s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0))
    s.attach(ax, u)
    cast(s, 0, "Turn to Dust", ax)
    run(s)
    _next_own_turn(s)
    run(s)
    assert not alive(s, ax), "the GRANTED Temporary is active on attached gear"


@case(9909, "Defy cannot counter Mindsplitter's play trigger")
def _():
    need("Defy", "Mindsplitter")
    s = fresh(hand=[T.id_of("Mindsplitter")], runes=12)
    give(s, 1, "Defy", "Discipline")
    s.runes_ready[1, :] = 9
    cast(s, 0, "Mindsplitter", base_loc(0))
    A._settle(s, T, V1)
    assert "Mindsplitter" in chain_names(s)
    pass_priority_to(s, 1)
    assert "Defy" not in hand_plays(s, 1)


@case(9907, "Falling Star twice at one Deflect unit pays Deflect twice")
def _():
    need("Falling Star", "Vex - Apathetic")
    s = fresh()
    vx = s.add_permanent(T.id_of("Vex - Apathetic"), 1, base_loc(1))
    assert rsv.deflect_cost(s, T, 0, [vx, vx], SPECS["Falling Star"]) == 2


@case(9899, "Rengar - Pouncing may be played to a battlefield you are defending")
def _():
    need("Rengar - Pouncing")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Rengar - Pouncing")
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    a = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, a)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Rengar - Pouncing"), 0)
    dests = {x.arg for x in A.legal_actions(s, T, V1, 0)
             if x.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert bf_loc(0) in dests, dests


@case(9898, "Hard Bargain cannot be played with nothing on the Chain")
def _():
    need("Hard Bargain")
    s = fresh(hand=[T.id_of("Hard Bargain")])
    assert "Hard Bargain" not in hand_plays(s, 0)


@case(9893, "Heedless Resurrection cannot return the unit it kills")
def _():
    need("Heedless Resurrection", "Ferrous Forerunner")
    s = fresh(hand=[T.id_of("Heedless Resurrection")], runes=9)
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 0, base_loc(0))
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    act(s, A.A_PLAY, hand_index(s, 0, "Heedless Resurrection"), 0)
    choose(s, ff)
    offered = targets_offered(s, 0)
    assert pack_trash(0, T.id_of("Ferrous Forerunner")) not in offered, offered
