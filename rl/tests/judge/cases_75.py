"""RiftJudge batch 75 -- unused questions from 6770-6840."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_MIGHT_MOD, P_OWNER
from rl.engine.effects import pack_trash


@case(6840, "Annie - Stubborn can take the Reinforce that played her")
def _():
    need("Reinforce", "Annie - Stubborn")
    s = fresh(hand=[T.id_of("Reinforce")], runes=32)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Annie - Stubborn")
    cast(s, 0, "Reinforce")
    run(s, limit=20, stop=lambda st: int(st.pend_look) >= 0)
    choose(s, 0)
    run(s, picking(base_loc(0),
                   pack_trash(0, T.id_of("Reinforce")), accept=True), limit=60)
    assert perm_of(s, "Annie - Stubborn", 0), "she was played from the look"
    assert T.id_of("Reinforce") in list(s.hand[0, :int(s.n_hand[0])]), \
        "and her trigger finalized after it had finished resolving"


@case(6839, "Unyielding Spirit stops damage, not a kill")
def _():
    need("Unyielding Spirit", "Hextech Ray", "Fox-Fire")
    s = fresh(runes=32)
    give(s, 0, "Unyielding Spirit")
    give(s, 1, "Hextech Ray", "Fox-Fire")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    shot = body(s, 0, bf_loc(0), 3)
    cut = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Hextech Ray", shot)
    cast(s, 0, "Unyielding Spirit")               # a Reaction, on their turn
    run(s, limit=30)
    assert alive(s, shot) and int(s.perms[shot, P_DMG]) == 0, "the 3 was prevented"
    cast(s, 1, "Fox-Fire", cut)
    run(s, limit=30)
    assert not alive(s, cut), "but a kill is not damage"


@case(6837, "a spell starts no Showdown, and nobody defends")
def _():
    need("Disintegrate", "Fortified Position")
    s = fresh(hand=[T.id_of("Disintegrate")], runes=32)
    s.bf_card[0] = T.id_of("Fortified Position")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Disintegrate", u)
    run(s, limit=40)
    assert int(s.perms[u, P_DMG]) == 3, "the damage landed"
    assert int(s.showdown_bf) < 0, "323: only a unit moving in starts one"
    assert combat.perm_kw(s, T, u, "Shield") == 0, "and nothing defended"


@case(6833, "a card hidden this turn cannot be played this turn")
def _():
    need("Consult the Past")
    s = fresh(hand=[T.id_of("Consult the Past")], runes=32)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hides = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE]
    assert hides, "it may be hidden now"
    A.apply(s, T, V1, hides[0])
    act(s, A.A_HIDE_AT, None, 0)
    run(s, limit=20)
    assert A.A_PLAY_HIDDEN not in kinds(s, 0), "811.1.b: beginning on the NEXT turn"
    _next_own_turn(s)
    assert A.A_PLAY_HIDDEN in kinds(s, 0), "and then it may be played"


@case(6830, "a unit that leaves the board leaves its buff behind")
def _():
    need("Rebuke")
    s = fresh(hand=[T.id_of("Rebuke")], runes=32)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    s.extra_buffs[u] = 2
    assert combat.might(s, T, u) == 6, "three buffs"
    cast(s, 0, "Rebuke", u)
    run(s, limit=30)
    assert not alive(s, u), "it is in hand"
    back = s.add_permanent(VANILLA, 0, base_loc(0))
    assert not s.has_flag(back, F_BUFFED) and int(s.extra_buffs[back]) == 0, \
        "705: counters do not follow a card off the board"


@case(6827, "Ravenbloom Student counts every spell")
def _():
    need("Ravenbloom Student", "Cleave")
    s = fresh(runes=32)
    give(s, 0, "Cleave", "Cleave", "Cleave")
    s.bf_ctrl[0] = 0
    rb = s.add_permanent(T.id_of("Ravenbloom Student"), 0, bf_loc(0))
    for k in range(3):
        cast(s, 0, "Cleave", rb)
        run(s, limit=30)
        assert combat.might(s, T, rb) == 2 + k + 1, f"spell {k + 1}"


@case(6826, "Baited Hook may take a unit smaller than the one it killed")
def _():
    need("Baited Hook", "Pouty Poro")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0))
    bait = body(s, 0, base_loc(0), 4)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Pouty Poro")           # 2 Might, far under the 5
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, bait)
    run(s, limit=20, stop=lambda st: int(st.pend_look) >= 0)
    assert int(s.look_max_might) == 5, "'up to 1 more' is a ceiling, not a match"
    choose(s, 0)
    run(s, picking(base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Pouty Poro", 0)


@case(6824, "a card drawn mid-Chain can be played before the Chain resolves")
def _():
    need("Hextech Ray", "Stupefy", "Retreat", "Lecturing Yordle")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Stupefy")
    give(s, 1, "Hextech Ray")
    s.runes_ready[1, :] = 12
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Retreat")
    s.bf_ctrl[0] = 0
    y = s.add_permanent(T.id_of("Lecturing Yordle"), 0, bf_loc(0))
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Hextech Ray", y)
    cast(s, 0, "Stupefy", y)
    run(s, limit=8, stop=lambda st: T.id_of("Retreat")
        in list(st.hand[0, :int(st.n_hand[0])]))
    assert int(s.n_chain) == 1, "the Ray is still waiting"
    pass_priority_to(s, 0)
    assert "Retreat" in hand_plays(s, 0), "and the card drawn from Stupefy is live"
    cast(s, 0, "Retreat", y)
    run(s, limit=40)
    assert not alive(s, y), "and it saved the Yordle"


@case(6823, "Retreat on a token dissolves it")
def _():
    need("Retreat", "Sprite Call")
    s = fresh(hand=[T.id_of("Retreat")], runes=32)
    rune_deck(s)
    spr = _sprite_at(s, 0, 0)
    before = int(s.n_hand[0])
    cast(s, 0, "Retreat", spr)
    run(s, limit=30)
    assert not alive(s, spr), "it left the board"
    assert int(s.n_hand[0]) == before - 1, "-1 for Retreat, and no token in hand"


@case(6818, "Pack of Wonders only reaches your own side")
def _():
    need("Pack of Wonders")
    s = fresh(runes=32)
    pack = s.add_permanent(T.id_of("Pack of Wonders"), 0, base_loc(0))
    mine = body(s, 0, base_loc(0), 3)
    s.bf_ctrl[0] = 1
    theirs = body(s, 1, bf_loc(0), 3)
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, 0)                                  # the mode: a gear or a unit
    offered = targets_offered(s, 0)
    assert mine in offered and theirs not in offered, "'another FRIENDLY'"
    assert pack not in offered, "and 'another' is not itself"


@case(6813, "Mask of Foresight can make Fiora [Mighty]")
def _():
    need("Mask of Foresight", "Fiora - Victorious")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    fi = s.add_permanent(T.id_of("Fiora - Victorious"), 0, bf_loc(0))
    assert not combat.perm_kw(s, T, fi, "Deflect"), "4 Might, and nothing yet"
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert combat.might(s, T, fi) >= 5, "+1 for defending alone"
    assert combat.perm_kw(s, T, fi, "Deflect"), "740.2: and Mighty is a threshold"


@case(6810, "Snapvine's trigger is a Chain item, not a Showdown")
def _():
    need("Carnivorous Snapvine", "Discipline", "Challenge")
    s = fresh(runes=32)
    give(s, 0, "Carnivorous Snapvine")
    give(s, 1, "Discipline", "Challenge")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Carnivorous Snapvine", base_loc(0))
    choose(s, u)
    assert int(s.showdown_bf) < 0, "no unit moved to a battlefield"
    pass_priority_to(s, 1)
    plays = hand_plays(s, 1)
    assert "Discipline" in plays and "Challenge" not in plays, \
        "a Chain is open, so Reactions only"


@case(6808, "Tideturner is the hidden spell that may choose elsewhere")
def _():
    need("Tideturner")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(1), 3)                      # hold the ground it hides at
    far = body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 1, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(far, accept=True), limit=40)
    tt = perm_of(s, "Tideturner", 0)[0]
    assert int(s.perms[far, P_LOC]) == bf_loc(1), "they swapped across the board"
    assert int(s.perms[tt, P_LOC]) == bf_loc(0), "which is its printed exception"


@case(6806, "Hidden Blade from Hidden is bound to its battlefield; from hand it is not")
def _():
    need("Hidden Blade")

    def blade(from_hidden):
        s = fresh(runes=32)
        s.bf_ctrl[0] = 0
        body(s, 0, bf_loc(0), 3)
        s.bf_ctrl[1] = 1
        u = body(s, 1, bf_loc(0), 3)
        if from_hidden:
            hidden_at(s, 0, 0, "Hidden Blade")
            act(s, A.A_PLAY_HIDDEN, None, 0)
            choose(s, u)
        else:
            give(s, 0, "Hidden Blade")
            cast(s, 0, "Hidden Blade", u)
        s.set_location(u, bf_loc(1))              # answered: it is elsewhere now
        run(s, limit=40)
        return alive(s, u)

    assert blade(True), "811.1.d.2 bound the choice to that battlefield"
    assert not blade(False), "from hand, 'a unit at a battlefield' is any of them"


@case(6802, "Possession takes the unit in the state it is in")
def _():
    need("Possession")
    s = fresh(hand=[T.id_of("Possession")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3, ready=True)
    cast(s, 0, "Possession", u)
    run(s, limit=40)
    assert int(s.perms[u, P_CTRL]) == 0 and int(s.perms[u, P_LOC]) == base_loc(0)
    assert int(s.perms[u, P_READY]) == 1, "455: a Recall is not a move"


@case(6800, "Brynhir stops cards, and a token is not a card")
def _():
    need("Brynhir Thundersong", "Machine Evangel")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")], runes=32)
    ev = s.add_permanent(T.id_of("Machine Evangel"), 1, base_loc(1))
    cast(s, 0, "Brynhir Thundersong", base_loc(0))
    run(s, limit=40)
    combat.destroy(s, T, ev)
    run(s, limit=40)
    assert len(tokens(s, 1, base_loc(1))) == 3, "the Deathknell played no CARDS"


@case(6790, "Unlicensed Armory cannot be activated with an empty hand")
def _():
    need("Unlicensed Armory")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Unlicensed Armory"), 0, base_loc(0))
    body(s, 0, base_loc(0), 3)
    assert A.A_ACTIVATE not in kinds(s, 0), "404.1: the discard is a cost"
    give(s, 0, "Cleave")
    assert A.A_ACTIVATE in kinds(s, 0), "with a card to pitch, it is live"


@case(6785, "Stupefy needs a unit to point at")
def _():
    need("Stupefy")
    s = fresh(hand=[T.id_of("Stupefy")], runes=32)
    assert "Stupefy" not in hand_plays(s, 0), \
        "355.8: 'do as much as you can' is a resolution rule"
    body(s, 0, base_loc(0), 3)
    assert "Stupefy" in hand_plays(s, 0)


@case(6781, "Tibbers is on the board before anyone may answer him")
def _():
    need("Tibbers")
    s = fresh(hand=[T.id_of("Tibbers")], runes=32)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Tibbers"), 0)
    choose(s, base_loc(0))
    assert perm_of(s, "Tibbers", 0), "337.2: a unit play opens no window"
    pass_priority_to(s, 1)
    assert int(s.n_chain) + int(s.n_trig) >= 1, "his trigger is what can be answered"


@case(6774, "Kraken Hunter cannot spend an enemy's buff")
def _():
    need("Kraken Hunter")
    s = fresh(hand=[T.id_of("Kraken Hunter")], runes=32)
    mine = body(s, 0, base_loc(0), 3)
    s.set_flag(mine, F_BUFFED)
    s.bf_ctrl[0] = 1
    theirs = body(s, 1, bf_loc(0), 3)
    s.set_flag(theirs, F_BUFFED)
    act(s, A.A_PLAY, 0, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0)
               if a.kind in _CHOICE_KINDS}
    assert theirs not in offered, "704: a player spends only their own counters"
