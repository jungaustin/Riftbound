"""RiftJudge batch 79 -- unused questions from 6380-6505."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_READY


@case(6504, "a target chosen at finalization is the only target it ever has")
def _():
    need("Hextech Ray", "Retreat")
    s = fresh(runes=32)
    give(s, 0, "Hextech Ray")
    give(s, 1, "Retreat")
    rune_deck(s)
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 5)
    other = body(s, 1, bf_loc(1), 5)
    cast(s, 0, "Hextech Ray", victim)
    pass_priority_to(s, 1)
    cast(s, 1, "Retreat", victim)
    run(s, limit=60)
    assert not alive(s, victim), "it went back to hand"
    assert int(s.perms[other, P_DMG]) == 0, \
        "355: the choice was made at finalization and cannot be remade"


@case(6498, "'if you do' makes the kill a requirement, not a hope")
def _():
    need("Pickpocket")
    s = fresh(runes=32)
    give(s, 0, "Pickpocket")
    s.bf_ctrl[1] = 1
    gold = s.add_permanent(T.id_of("Gold // Buff"), 1, base_loc(1))
    cast(s, 0, "Pickpocket", base_loc(0))
    act(s, A.A_ACCEPT, None, 0)                    # "you MAY kill a gear"
    choose(s, gold)                                # the trigger names their gear
    combat.destroy(s, T, gold)                     # ...which they then spend
    A._settle(s, T, V1)
    run(s, picking(accept=True), limit=60)
    assert not alive(s, gold), "their gear went of its own accord"
    assert not [i for i in range(s.n_perms) if alive(s, i)
                and int(s.perms[i, P_CTRL]) == 0
                and T.is_token(int(s.perms[i, P_CARD]))], \
        "359.3.e.2: no kill, so no 'if you do', so no Gold token"


@case(6494, "two sources of [Assault] add up on everybody else")
def _():
    need("Captain Farron")
    s = fresh(runes=32)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 9)                       # a defender, so this is a Combat
    f1 = s.add_permanent(T.id_of("Captain Farron"), 0, base_loc(0), ready=True)
    f2 = s.add_permanent(T.id_of("Captain Farron"), 0, base_loc(0), ready=True)
    plain = body(s, 0, base_loc(0), 3, ready=True)
    give(s, 1, "Discipline")                       # keeps the Showdown open
    printed = int(T.might[T.id_of("Captain Farron")])
    attack(s, 0, 1, f1, f2, plain)
    assert combat.might(s, T, plain) == 3 + 2, \
        "'OTHER friendly units here have [Assault]', twice over"
    assert combat.might(s, T, f1) == printed + 1 and \
        combat.might(s, T, f2) == printed + 1, \
        "and each Farron gets it only from the other one"


@case(6492, "Possession chooses on the way onto the Chain")
def _():
    need("Possession", "Retreat")
    s = fresh(runes=32)
    give(s, 0, "Possession")
    give(s, 1, "Retreat")
    rune_deck(s)
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Possession", victim)
    pass_priority_to(s, 1)
    cast(s, 1, "Retreat", victim)
    run(s, limit=60)
    assert not alive(s, victim), "back to its owner's hand first"
    assert not [i for i in range(s.n_perms) if alive(s, i)
                and int(s.perms[i, P_CTRL]) == 0
                and int(s.perms[i, P_CARD]) == VANILLA], \
        "359.3.e.2: nothing left to take control of"


@case(6490, "a [Repeat] is one spell, so one lost target costs only itself")
def _():
    need("Piercing Light", "Flash")
    s = fresh(runes=32)
    give(s, 0, "Piercing Light")
    give(s, 1, "Flash")
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(1), 2)
    b = body(s, 1, bf_loc(1), 3)                   # 3 Might: it takes both hits
    cast(s, 0, "Piercing Light", a, b, a, b, repeat=True)
    pass_priority_to(s, 1)
    cast(s, 1, "Flash", a)                         # one of them goes home
    run(s, limit=60)
    assert alive(s, a) and int(s.perms[a, P_LOC]) == base_loc(1), \
        "the Flashed unit is at base and out of reach"
    assert not alive(s, b), \
        "820.2: the repeat's own slots still land, and 2 twice is lethal"


@case(6488, "a reveal that runs out of deck is not a Burn Out")
def _():
    need("Dazzling Aurora")
    s = fresh(hand=[T.id_of("Dazzling Aurora")], runes=32)
    # A deck of nothing but spells: the reveal never finds a unit.
    n = int(s.deck_ptr[0])
    for k in range(int(s.n_deck[0]) - n):
        s.deck[0, n + k] = T.id_of("Cleave")
    cast(s, 0, "Dazzling Aurora", base_loc(0))
    run(s, limit=40)
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=80)
    assert int(s.winner) < 0, \
        "the cards never left the Main Deck, so nobody burned out"
    assert int(s.n_deck[0]) - int(s.deck_ptr[0]) > 0, "and the deck is still there"


@case(6487, "a champion unit is a unit")
def _():
    need("Cemetery Attendant", "Darius - Trifarian")
    s = fresh(runes=32)
    give(s, 0, "Cemetery Attendant")
    s.trash[0, 0] = T.id_of("Darius - Trifarian")
    s.n_trash[0] = 1
    cast(s, 0, "Cemetery Attendant", base_loc(0))
    offered = targets_offered(s, 0)
    from rl.engine.effects import unpack_trash
    assert {T.names[unpack_trash(i)[1]] for i in offered} == {"Darius - Trifarian"}, \
        "'a unit from your trash' does not exclude a champion"


@case(6486, "+1 Might from the ground is not a Buff")
def _():
    need("Trifarian War Camp")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    assert combat.might(s, T, u) == 4, "'Units here have +1 Might'"
    assert not s.has_flag(u, F_BUFFED), \
        "703: a Buff is a game object, and nothing here says 'buff'"


@case(6482, "a recalled unit goes to its CONTROLLER's base")
def _():
    need("Possession", "Maddened Marauder")
    s = fresh(runes=32)
    give(s, 0, "Possession", "Maddened Marauder")
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Possession", victim)
    run(s, limit=60)
    assert alive(s, victim) and int(s.perms[victim, P_CTRL]) == 0, "taken"
    assert int(s.perms[victim, P_LOC]) == base_loc(0), \
        "455: 'send it to YOUR base' -- control decides which base that is"


@case(6480, "killed by their spell is not killed by yours")
def _():
    need("Cull the Weak", "Immortal Phoenix")
    s = fresh(runes=32)
    give(s, 1, "Cull the Weak")
    s.runes_ready[1, :] = 24
    s.trash[0, 0] = T.id_of("Immortal Phoenix")
    s.n_trash[0] = 1
    body(s, 0, base_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    s.active = s.priority = 1
    cast(s, 1, "Cull the Weak")
    run(s, picking(accept=True), limit=60)
    assert not perm_of(s, "Immortal Phoenix", 0), \
        "428.1.a.1: it was their spell, so the kill was not 'with a spell' of mine"
    assert T.id_of("Immortal Phoenix") in [
        int(s.trash[0, i]) for i in range(int(s.n_trash[0]))], "still in the trash"


@case(6475, "a unit that walks off the battlefield walks out of the spell")
def _():
    need("Falling Comet", "Flash")
    s = fresh(runes=32)
    give(s, 0, "Falling Comet")
    give(s, 1, "Flash")
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Falling Comet", victim)
    pass_priority_to(s, 1)
    cast(s, 1, "Flash", victim)
    run(s, limit=60)
    assert alive(s, victim) and int(s.perms[victim, P_LOC]) == base_loc(1), \
        "359.3.e.2: 'a unit AT A BATTLEFIELD' is re-read as it resolves"
    assert int(s.perms[victim, P_DMG]) == 0, "so the 6 never lands"


@case(6472, "a unit that already has a Buff cannot be buffed again")
def _():
    need("Mistfall", "Adaptatron")
    s = fresh(runes=32)
    mf = s.add_permanent(T.id_of("Mistfall"), 0, base_loc(0))
    ad = s.add_permanent(T.id_of("Adaptatron"), 0, base_loc(0), ready=True)
    s.set_flag(ad, F_BUFFED)                       # already carrying one
    gear = s.add_permanent(T.id_of("Mistfall"), 0, base_loc(0))
    s.bf_ctrl[1] = -1
    was = int(s.perms[mf, P_READY])
    attack(s, 0, 1, ad)
    run(s, picking(gear, accept=True), limit=80)
    assert s.has_flag(ad, F_BUFFED), "it still has exactly the one Buff"
    assert int(s.perms[mf, P_READY]) == was, \
        "705.2: no second Buff was given, so Mistfall never fired"


@case(6471, "a recall is not a move, so 'can't move to base' does not stop it")
def _():
    need("Vilemaw's Lair", "Zhonya's Hourglass", "Hextech Ray")
    s = fresh(runes=32)
    give(s, 0, "Hextech Ray")
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 1)
    zh = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = zh
    cast(s, 0, "Hextech Ray", u)
    run(s, limit=60)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0), \
        "455/456.1: the Hourglass recalls it off ground it may not walk off"


@case(6470, "a moved target loses the damage, not the draw")
def _():
    need("Void Seeker", "Retreat")
    s = fresh(runes=32)
    give(s, 0, "Void Seeker")
    give(s, 1, "Retreat")
    rune_deck(s)
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 5)
    h0 = int(s.n_hand[0])
    cast(s, 0, "Void Seeker", victim)
    pass_priority_to(s, 1)
    cast(s, 1, "Retreat", victim)
    run(s, limit=60)
    assert int(s.n_hand[0]) == h0 - 1 + 1, "359.3.e.1: 'Draw 1' is its own instruction"


@case(6469, "'Kill this:' is a cost you pay, not something that happens to you")
def _():
    need("Forge of the Future", "Adaptatron")
    s = fresh(runes=32)
    fof = s.add_permanent(T.id_of("Forge of the Future"), 0, base_loc(0))
    s.trash[0, 0] = T.id_of("Cleave")
    s.trash[0, 1] = T.id_of("Cleave")
    s.n_trash[0] = 2
    before = int(s.n_trash[0])
    combat.destroy(s, T, fof)
    A._settle(s, T, V1)
    run(s, limit=40)
    assert not alive(s, fof), "somebody else killed it"
    assert int(s.n_trash[0]) >= before, \
        "377.1: an activated ability needs activating, so nothing was recycled"


@case(6464, "a Showdown's Combat status is fixed when it begins")
def _():
    need("Overzealous Fan")
    s = fresh(runes=32)
    s.bf_ctrl[1] = 1
    give(s, 0, "Discipline")
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(1))
    mine = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 1, mine)
    assert int(s.showdown_combat), "a defender was there: this is a Combat"
    run(s, picking(mine, accept=True), limit=40)
    assert not alive(s, fan), "it killed itself to push the attacker home"
    assert int(s.perms[mine, P_LOC]) == base_loc(0), "and the attacker went home"
    assert int(s.showdown_bf) < 0 or int(s.showdown_combat), \
        "460.2: the Showdown does not stop being a Combat Showdown"


@case(6460, "damage is measured against the Might of the moment")
def _():
    need("Cleave")
    s = fresh(runes=32)
    give(s, 0, "Cleave")
    s.bf_ctrl[1] = 1
    small = body(s, 0, base_loc(0), 2, ready=True)
    foe = body(s, 1, bf_loc(1), 2)
    cast(s, 0, "Cleave", small)
    drain(s)
    attack(s, 0, 1, small)
    fight(s, limit=80)
    assert alive(s, small), \
        "2 damage into 5 Might while attacking, and it heals before the +3 lapses"
    assert not alive(s, foe), "while 5 into a 2 Might defender is lethal"


@case(6456, "a battlefield already scored this turn cannot be conquered")
def _():
    need("Sigil of the Storm")
    s = fresh(runes=32)
    rune_deck(s)
    s.bf_card[0] = T.id_of("Sigil of the Storm")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)                       # holding it
    s.bf_scored[0, 0] = 1                          # scored on the Hold already
    taker = body(s, 0, base_loc(0), 3, ready=True)
    s.bf_ctrl[0] = 1                               # then lost...
    before = runes(s, 0)
    attack(s, 0, 0, taker)                         # ...and taken back
    fight(s, limit=80)
    assert int(s.bf_ctrl[0]) == 0, "the ground is theirs again"
    assert runes(s, 0) == before, \
        "471.2: no Conquer, because they had already scored it this turn"


@case(6445, "a Might reduction is a one-off, not a standing rule")
def _():
    need("Thousand-Tailed Watcher")
    s = fresh(runes=32)
    give(s, 0, "Thousand-Tailed Watcher")
    s.bf_ctrl[1] = 1
    early = body(s, 1, bf_loc(1), 4)
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s, limit=40)
    assert combat.might(s, T, early) == 1, "-3 from 4, floored at 1"
    late = body(s, 1, bf_loc(1), 4)
    assert combat.might(s, T, late) == 4, \
        "477.3.b: the effect snapshotted on resolution, so a newcomer is untouched"
