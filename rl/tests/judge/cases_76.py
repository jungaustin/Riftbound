"""RiftJudge batch 76 -- unused questions from 6690-6767."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_MIGHT_MOD, P_ATTACHED_TO


@case(6766, "a stunned unit still deals its Might through Challenge")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=32)
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    s.set_flag(mine, F_STUNNED)
    s.bf_ctrl[1] = 1
    theirs = body(s, 1, bf_loc(1), 6)
    cast(s, 0, "Challenge", mine, theirs)
    run(s, limit=40)
    assert int(s.perms[theirs, P_DMG]) == 3, "423: Stun stops COMBAT damage"


@case(6761, "Svellsongur copies the unit's text, not another gear's bonus")
def _():
    need("Svellsongur", "Warmog's Armor", "Ravenbloom Student", "Cleave")
    s = fresh(runes=32)
    give(s, 0, "Cleave")
    rb = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    wa = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    sv = s.add_permanent(T.id_of("Svellsongur"), 0, base_loc(0))
    s.attach(wa, rb)
    s.attach(sv, rb)
    assert combat.might(s, T, rb) == 3, "2 printed, +1 from the Armor, +0 from Svell"
    cast(s, 0, "Cleave", rb)
    run(s, limit=30)
    assert combat.might(s, T, rb) == 5, "the copied trigger fired too: +1 and +1"


@case(6758, "one spell choosing two enemies is two choices for Ezreal")
def _():
    need("Ezreal - Prodigal Explorer", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    s.legend[0], s.legend_ready[0] = T.id_of("Ezreal - Prodigal Explorer"), 1
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(0), 9)

    def legend_open():
        return [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and A.is_legend_activate(a.arg)]

    assert not legend_open(), "nothing has been chosen yet"
    cast(s, 0, "Singularity", a, b)
    run(s, limit=40)
    assert legend_open(), "twice this turn, and one spell did it"


@case(6757, "a floored reduction is the floor, and later gains climb from it")
def _():
    need("Thousand-Tailed Watcher", "Ravenbloom Student", "Downstage Dramatics")
    s = fresh(runes=32)
    give(s, 0, "Downstage Dramatics", "Downstage Dramatics", "Downstage Dramatics")
    give(s, 1, "Thousand-Tailed Watcher")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    rb = s.add_permanent(T.id_of("Ravenbloom Student"), 0, bf_loc(0))
    s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(1), 9)                      # somewhere else to be attacked
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Thousand-Tailed Watcher", base_loc(1))
    run(s, limit=40)
    assert combat.might(s, T, rb) == 1, "2 Might, less 3, floored at 1"
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 1, foe)                          # a Showdown, for the windows
    for _ in range(3):
        cast(s, 0, "Downstage Dramatics")
        drain(s)
    assert combat.might(s, T, rb) == 4, "and its own +1s are added to the floor"


@case(6756, "Temptation's repeat has nowhere left to send the unit")
def _():
    need("Temptation")
    s = fresh(hand=[T.id_of("Temptation")], runes=32)
    s.bf_ctrl[0] = 1
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Temptation"), 0)
    run(s, picks(a, bf_loc(1), b, bf_loc(1)), limit=40)
    assert int(s.perms[a, P_LOC]) == bf_loc(1), "the first move happened"
    assert int(s.perms[b, P_LOC]) == bf_loc(1), "and the repeat found no other home"


@case(6752, "Eclipse Herald counts no stun that happened before it arrived")
def _():
    need("Eclipse Herald", "Zenith Blade")
    s = fresh(runes=32)
    give(s, 0, "Zenith Blade", "Zenith Blade")
    s.bf_ctrl[0] = 1
    one = body(s, 1, bf_loc(0), 9)
    two = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Zenith Blade", one)
    run(s, picking(accept=False), limit=40)
    assert s.has_flag(one, F_STUNNED), "stunned before the Herald was played"
    her = s.add_permanent(T.id_of("Eclipse Herald"), 0, base_loc(0), ready=False)
    assert combat.might(s, T, her) == 7 and int(s.perms[her, P_READY]) == 0
    cast(s, 0, "Zenith Blade", two)
    run(s, picking(accept=False), limit=40)
    assert combat.might(s, T, her) == 8 and int(s.perms[her, P_READY]) == 1, \
        "this one he saw"


@case(6751, "Void Seeker still draws when its target was killed in response")
def _():
    need("Void Seeker", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 1, "Void Seeker")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Hidden Blade")
    s.ply += 1
    s.active = s.priority = 1
    before = int(s.n_hand[1])
    cast(s, 1, "Void Seeker", mine)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    choose(s, mine)
    run(s, limit=40)
    assert not alive(s, mine), "I killed my own unit first"
    assert int(s.n_hand[1]) == before - 1 + 1, "Void Seeker's own draw happened"
    assert int(s.n_hand[0]) == 2, "and the Blade drew for the unit's controller"


@case(6749, "Charming an enemy onto empty ground scores it for them")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    s.bf_ctrl[1] = -1
    before = int(s.points[1])
    cast(s, 0, "Charm", u, bf_loc(1))
    run(s, limit=40)
    assert int(s.bf_ctrl[1]) == 1, "190.4: it conquered on arrival"
    assert int(s.points[1]) == before + 1, "and the point is theirs, not mine"


@case(6740, "Call to Glory can be paid entirely with a buff")
def _():
    need("Call to Glory")
    s = fresh(hand=[T.id_of("Call to Glory")], runes=0)
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    assert not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY], \
        "3 Energy is out of reach"
    opts = [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind in (A.A_PLAY_REPEAT, A.A_PLAY_BOTH)]
    assert opts, "820.1: the additional cost is a way to pay it"
    A.apply(s, T, V1, opts[0])
    run(s, picking(u, accept=True), limit=40)
    assert not s.has_flag(u, F_BUFFED), "the buff was spent"
    assert combat.might(s, T, u) == 6, "3 printed, +3, and no buff any more"


@case(6738, "Catalyst of Aeons draws when the Rune Deck is empty")
def _():
    need("Catalyst of Aeons")
    s = fresh(hand=[T.id_of("Catalyst of Aeons")], runes=32)
    assert int(s.rune_left[0]) == 0, "nothing left to channel"
    cast(s, 0, "Catalyst of Aeons")
    run(s, limit=30)
    assert int(s.n_hand[0]) == 1, "-1 for the spell, +1 for the consolation"


@case(6731, "attack triggers go on the Chain before defend triggers")
def _():
    need("Yasuo - Remorseful", "Ahri, Inquisitive")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ahri = s.add_permanent(T.id_of("Ahri, Inquisitive"), 1, bf_loc(0))
    yas = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, yas)
    names = chain_names(s)
    assert names == ["Yasuo - Remorseful", "Ahri, Inquisitive"], names
    fight(s, limit=60)
    assert int(s.perms[yas, P_DMG]) or not alive(s, ahri), "both resolved"


@case(6726, "Piercing Light's second 2 lands even when the first target left")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=32)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Piercing Light", a, b)
    s.set_location(a, base_loc(1))                # answered: it went home
    run(s, limit=40)
    assert int(s.perms[a, P_DMG]) == 0, "'a unit at a battlefield' was not there"
    assert int(s.perms[b, P_DMG]) == 2, "'then' is not a dependency"


@case(6724, "a Might reduction that meets marked damage kills at once")
def _():
    need("Stupefy")
    s = fresh(hand=[T.id_of("Stupefy")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    combat.mark_damage(s, T, u, 2)
    assert alive(s, u), "2 on a 3 Might unit is not lethal"
    cast(s, 0, "Stupefy", u)
    run(s, limit=30)
    assert not alive(s, u), "143.2.a is checked continuously"


@case(6723, "Rhasa at 0 Energy still owes her Power")
def _():
    need("Rhasa the Sunderer")
    s = fresh(hand=[T.id_of("Rhasa the Sunderer")], runes=0)
    for j in range(10):
        s.trash[0, j] = VANILLA
    s.n_trash[0] = 10
    assert "Rhasa the Sunderer" not in hand_plays(s, 0), "10 off her Energy, not her Power"
    dom = int(T.domain_mask[T.id_of("Rhasa the Sunderer")]).bit_length() - 1
    s.runes_ready[0, dom] = 1
    assert "Rhasa the Sunderer" in hand_plays(s, 0), "one rune of her domain is all it takes"


@case(6718, "Not So Fast counters a spell that chose two of your units")
def _():
    need("Not So Fast", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Singularity", a, b)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s, limit=40)
    assert int(s.perms[a, P_DMG]) == 0 and int(s.perms[b, P_DMG]) == 0, "countered"


@case(6717, "Yasuo's attack trigger is answered by Reactions, and Actions wait")
def _():
    need("Yasuo - Remorseful", "Discipline", "Challenge")
    s = fresh(runes=32)
    give(s, 0, "Discipline", "Challenge")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    yas = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, yas)
    assert int(s.n_chain) == 1, "his trigger is on the Chain"
    choose(s, units(s, 1, bf_loc(0))[0])          # 402.2, before any window
    plays = hand_plays(s, 0)
    assert "Discipline" in plays and "Challenge" not in plays, "a Chain is open"
    drain(s)
    assert int(s.showdown_bf) == 0, "the Showdown outlived the trigger"
    pass_priority_to(s, 0)
    assert "Challenge" in hand_plays(s, 0), "and now the Action is playable"


@case(6710, "Ava Achiever mentions [Hidden] without having it")
def _():
    need("Ava Achiever", "Teemo - Strategist", "Hidden Blade")
    assert not T.has(T.id_of("Ava Achiever"), "Hidden"), "it only talks about them"

    def damage_from(top):
        s = fresh(runes=32)
        s.bf_ctrl[0] = 0
        n = int(s.deck_ptr[0])
        for k in range(5):
            s.deck[0, n + k] = T.id_of(top)
        tee = s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0))
        s.ply += 1
        foe = body(s, 1, base_loc(1), 9, ready=True)
        attack(s, 1, 0, foe)
        drain(s)                                  # the heal is at combat's end
        return int(s.perms[foe, P_DMG])

    assert damage_from("Ava Achiever") == 0, "no card with the keyword was revealed"
    assert damage_from("Hidden Blade") == 5, "five that have it, five damage"


@case(6697, "a blinked unit is a new object: it triggers, heals, and drops its buff")
def _():
    need("Portal Rescue", "First Mate")
    s = fresh(hand=[T.id_of("Portal Rescue")], runes=32)
    fm = s.add_permanent(T.id_of("First Mate"), 0, base_loc(0))
    s.set_flag(fm, F_BUFFED)
    combat.mark_damage(s, T, fm, 2)
    mate = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Portal Rescue", fm)
    run(s, picking(mate, accept=True), limit=60)
    back = perm_of(s, "First Mate", 0)[0]
    assert int(s.perms[back, P_DMG]) == 0, "it came back whole"
    assert not s.has_flag(back, F_BUFFED), "705: the buff stayed behind"
    assert int(s.perms[mate, P_READY]) == 1, "and 'when you play me' ran again"


@case(6693, "Caitlyn's ability resolves after she has left the battlefield")
def _():
    need("Caitlyn - Patrolling", "Flash")
    s = fresh(runes=32)
    give(s, 0, "Flash")
    s.bf_ctrl[0] = 0
    cait = s.add_permanent(T.id_of("Caitlyn - Patrolling"), 0, bf_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 9)
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    cast(s, 0, "Flash", cait, -1)
    run(s, limit=40)
    assert int(s.perms[cait, P_LOC]) == base_loc(0), "she is home"
    assert int(s.perms[u, P_DMG]) == 3, "the ability was already on the Chain"


@case(6690, "Ember Monk cannot be hidden")
def _():
    need("Ember Monk", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 0, "Ember Monk", "Hidden Blade")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hides = {T.names[int(s.hand[0, a.arg])]
             for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE}
    assert hides == {"Hidden Blade"}, f"811.1: only cards WITH [Hidden]: {hides}"
