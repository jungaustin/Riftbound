"""RiftJudge batch 31 -- unused questions from 9351-9436."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO, P_OWNER, C_UID
from rl.engine.effects import ABILITIES, pack_trash


@case(9436, "Gust answers Fiora - Peerless's trigger before she doubles")
def _():
    need("Fiora - Peerless", "Gust", "Pouty Poro")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Pouty Poro"), 0, bf_loc(0))
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, fi)
    assert "Fiora - Peerless" in chain_names(s)
    pass_priority_to(s, 0)
    cast(s, 0, "Gust", fi)
    run(s)
    assert not alive(s, fi) and T.id_of("Fiora - Peerless") in list(s.hand[1, :int(s.n_hand[1])])


@case(9429, "Undertitan's play trigger gives your other units +2")
def _():
    need("Undertitan")
    s = fresh(hand=[T.id_of("Undertitan")], runes=9)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Undertitan", base_loc(0))
    run(s)
    ut = perm_of(s, "Undertitan")[0]
    assert combat.might(s, T, u) == 5 and combat.might(s, T, ut) == 5


@case(9425, "Sacrifice's only Mighty unit under Tactical Retreat: paid, and it lives")
def _():
    need("Sacrifice", "Tactical Retreat")
    s = fresh(hand=[T.id_of("Tactical Retreat")], runes=9)
    give(s, 0, "Sacrifice")
    rune_deck(s)
    u = body(s, 0, base_loc(0), 6)
    cast(s, 0, "Tactical Retreat", u)
    run(s)
    assert "Sacrifice" in hand_plays(s, 0)
    cast(s, 0, "Sacrifice", u)
    run(s)
    assert alive(s, u) and int(s.n_hand[0]) == 2


@case(9420, "Darius - Trifarian played as the third card is not readied")
def _():
    need("Darius - Trifarian", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=12)
    give(s, 0, "Discipline", "Darius - Trifarian")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    run(s)
    cast(s, 0, "Discipline", u)
    run(s)
    cast(s, 0, "Darius - Trifarian", base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian")[0]
    assert int(s.perms[dar, P_READY]) == 0 and combat.might(s, T, dar) == 5


@case(9417, "a countered spell still discounts Battering Ram")
def _():
    need("Battering Ram", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 0, "Battering Ram")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 4
    assert "Battering Ram" in hand_plays(s, 0), "5 - 1"


@case(9415, "Rek'Sai - Swarm Queen into an empty battlefield: no attack trigger")
def _():
    need("Rek'Sai - Swarm Queen")
    s = fresh()
    rq = s.add_permanent(T.id_of("Rek'Sai - Swarm Queen"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, rq)
    assert "Rek'Sai - Swarm Queen" not in chain_names(s)


@case(9412, "Unyielding Spirit does not stop Cull the Weak")
def _():
    need("Unyielding Spirit", "Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 9
    body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    cast(s, 1, "Unyielding Spirit")
    run(s, picking())
    assert not alive(s, foe), "a kill is not damage"


@case(9407, "Moonfall pulling an enemy into your showdown keeps you the attacker")
def _():
    need("Moonfall")
    s = fresh(hand=[T.id_of("Moonfall")], runes=9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    a = body(s, 0, base_loc(0), 3, ready=True)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 1)
    attack(s, 0, 0, a)
    cast(s, 0, "Moonfall", bf_loc(0), foe)
    run(s, stop=lambda s: bool(s.showdown_combat))
    assert int(s.perms[foe, P_LOC]) == bf_loc(0) and int(s.attacker) == 0


@case(9406, "Keeper of Masks' copies arriving mid-trigger survive the turn")
def _():
    need("Keeper of Masks", "Sprite Call")
    s = fresh()
    s.bf_ctrl[0] = 0
    sprite = _sprite_at(s, 0, 0)
    hidden_at(s, 0, 0, "Keeper of Masks")
    _next_own_turn(s)
    assert chain_names(s), "the Temporary trigger waits on the Chain"
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking())
    km = perm_of(s, "Keeper of Masks")
    assert not alive(s, sprite)
    assert km and len(tokens(s, 0)) == 2, "they were not there when Temporary triggered"


@case(9402, "Death from Below whose target died first: no recast")
def _():
    need("Death from Below")
    s = fresh(hand=[T.id_of("Death from Below")], runes=9)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Death from Below", foe)
    combat.destroy(s, T, foe)                  # the opponent's own answer
    run(s)
    assert A.A_PLAY_FLOW not in kinds(s, 0), "it had no Might to check"


@case(9400, "Death from Below mistargeted: its trash replay is not offered")
def _():
    need("Death from Below", "Gust")
    s = fresh(hand=[T.id_of("Death from Below")], runes=9)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Death from Below", foe)
    cast(s, 1, "Gust", foe)
    run(s)
    assert A.A_PLAY_FLOW not in kinds(s, 0)


@case(9396, "Elder Dragon does not kill through Unyielding Spirit")
def _():
    need("Elder Dragon", "Unyielding Spirit", "Hextech Ray")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=9)
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Hextech Ray", foe)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert alive(s, foe) and int(s.perms[foe, P_DMG]) == 0


@case(9389, "Arcane Shift is an [Action]: no answering a spell with it")
def _():
    need("Arcane Shift", "Hextech Ray")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Arcane Shift")
    give(s, 1, "Hextech Ray")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    body(s, 1, bf_loc(1), 3)
    s.bf_ctrl[1] = 1
    cast(s, 1, "Hextech Ray", mine)
    pass_priority_to(s, 0)
    assert "Arcane Shift" not in hand_plays(s, 0)


@case(9388, "two Falling Stars may stack on one unit in base")
def _():
    need("Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=12)
    give(s, 0, "Falling Star")
    foe = body(s, 1, base_loc(1), 12)
    cast(s, 0, "Falling Star", foe, foe)
    run(s)
    cast(s, 0, "Falling Star", foe, foe)
    run(s)
    assert int(s.perms[foe, P_DMG]) == 12 or not alive(s, foe)


@case(9386, "Not So Fast cannot counter Thousand-Tailed Watcher's play trigger")
def _():
    need("Not So Fast", "Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=12)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    body(s, 1, base_loc(1), 5)
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    A._settle(s, T, V1)
    assert "Thousand-Tailed Watcher" in chain_names(s)
    pass_priority_to(s, 1)
    assert "Not So Fast" not in hand_plays(s, 1)


@case(9385, "Cull the Weak can take Baron Nashor")
def _():
    need("Cull the Weak", "Baron Nashor")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    body(s, 0, base_loc(0), 3)
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, base_loc(1))
    cast(s, 0, "Cull the Weak")
    run(s, picking(bn))
    assert not alive(s, bn)


@case(9381, "Arcane Shift needs an enemy it can choose")
def _():
    need("Arcane Shift", "Ruin Runner")
    s = fresh(hand=[T.id_of("Arcane Shift")], runes=9)
    body(s, 0, base_loc(0), 3)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Ruin Runner"), 1, bf_loc(0))
    assert "Arcane Shift" not in hand_plays(s, 0)


@case(9379, "Deathgrip's kill beside Soraka - Wanderer recalls instead")
def _():
    need("Deathgrip", "Soraka - Wanderer")
    s = fresh(hand=[T.id_of("Deathgrip")], runes=9)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Soraka - Wanderer"), 0, bf_loc(0))
    k = body(s, 0, bf_loc(0), 2, ready=True)
    other = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Deathgrip", k, other)
    run(s)
    assert alive(s, k) and int(s.perms[k, P_LOC]) == base_loc(0)
    assert int(s.perms[k, P_READY]) == 0
    assert combat.might(s, T, other) == 3, "the kill never happened"


@case(9377, "Not So Fast can counter Elder Dragon's play trigger")
def _():
    need("Not So Fast", "Elder Dragon")
    s = fresh(hand=[T.id_of("Elder Dragon")], runes=12)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    foe = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picks(foe), stop=lambda s: "Elder Dragon" in chain_names(s)
        and s.pend_slot < 0 and not chain_mod.decision_open(s))
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert alive(s, foe) and int(s.perms[foe, P_DMG]) == 0


@case(9374, "Immortal Phoenix killed by your own spell may come back")
def _():
    need("Immortal Phoenix", "Hextech Ray")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=12)
    s.bf_ctrl[0] = 0
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, bf_loc(0))
    cast(s, 0, "Hextech Ray", ph)
    run(s, picking(base_loc(0)))
    assert perm_of(s, "Immortal Phoenix"), "it was in the trash when the kill finished"


@case(9373, "Diana - Lunari triggers moving to an open battlefield")
def _():
    need("Diana - Lunari")
    s = fresh(runes=9)
    di = s.add_permanent(T.id_of("Diana - Lunari"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, di)
    assert "Diana - Lunari" in chain_names(s) or A.A_ACCEPT in kinds(s, 0)


@case(9371, "Retreat on a unit you took returns it to its owner, no recall")
def _():
    need("Hostile Takeover", "Retreat")
    s = fresh(hand=[T.id_of("Hostile Takeover")], runes=9)
    give(s, 0, "Retreat")
    rune_deck(s)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Hostile Takeover", foe)
    run(s, picking())
    cast(s, 0, "Retreat", foe)
    run(s)
    assert not alive(s, foe)
    assert VANILLA in list(s.hand[1, :int(s.n_hand[1])]), "its OWNER's hand"


@case(9363, "Singularity may choose no units at all")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=12)
    assert "Singularity" in hand_plays(s, 0)


@case(9351, "a Defy drawn off Discipline can answer the Hidden Blade below it")
def _():
    need("Discipline", "Defy", "Hidden Blade")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 1, "Hidden Blade")
    give(s, 0, "Discipline")
    s.deck[0, 0] = T.id_of("Defy")
    s.bf_ctrl[1] = 1
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    cast(s, 1, "Hidden Blade", mine)
    blade = top_uid(s)
    cast(s, 0, "Discipline", mine)
    run(s, stop=lambda s: "Discipline" not in chain_names(s))
    assert T.id_of("Defy") in list(s.hand[0, :int(s.n_hand[0])])
    cast(s, 0, "Defy", blade)
    run(s)
    assert alive(s, mine)
