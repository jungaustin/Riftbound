"""RiftJudge batch 38 -- unused questions from 8786-8846."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8846, "Sigil of the Storm takes a rune, and takes it without asking")
def _():
    need("Sigil of the Storm")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Sigil of the Storm")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    before = runes(s, 0)
    attack(s, 0, 0, u)
    fight(s)
    assert int(s.bf_ctrl[0]) == 0
    assert runes(s, 0) == before - 1, "one of YOUR runes, recycled"


@case(8845, "Vanguard Armory's tokens need a base or a battlefield you control")
def _():
    need("Vanguard Armory")
    s = fresh(runes=9)
    va = s.add_permanent(T.id_of("Vanguard Armory"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = -1
    act(s, A.A_ACTIVATE, va, 0)
    run(s)
    where = {int(s.perms[i, P_LOC]) for i in tokens(s, 0)}
    assert len(tokens(s, 0)) == 3
    assert bf_loc(1) not in where, "806.3: an open battlefield is not yours"


@case(8844, "Lux's [Add] energy pays for spells only")
def _():
    need("Lux, Crownguard", "Ravenbloom Student", "Meditation")
    s = fresh(hand=[T.id_of("Ravenbloom Student"), T.id_of("Meditation")], runes=0)
    lux = s.add_permanent(T.id_of("Lux, Crownguard"), 0, base_loc(0), ready=True)
    assert hand_plays(s, 0) == set(), "no runes at all to start with"
    act(s, A.A_ACTIVATE, lux, 0)
    run(s)
    plays = hand_plays(s, 0)
    assert "Meditation" in plays, "the 2 added Energy covers a 2-cost spell"
    assert "Ravenbloom Student" not in plays, "but a unit cannot spend it"


@case(8843, "an Equipment does not inherit its bearer's [Deflect]")
def _():
    need("Ornn - Forge God", "Svellsongur", "Salvage")
    s = fresh(hand=[T.id_of("Salvage")], runes=9)
    orn = s.add_permanent(T.id_of("Ornn - Forge God"), 1, base_loc(1), ready=True)
    g = s.add_permanent(T.id_of("Svellsongur"), 1, base_loc(1))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, g, 1)
    choose(s, orn)
    run(s)
    s.active = s.priority = 0
    assert int(s.perms[g, P_ATTACHED_TO]) == orn
    before = runes(s, 0)
    cast(s, 0, "Salvage", g)
    run(s)
    assert not alive(s, g) and alive(s, orn)
    assert before - runes(s, 0) == 1, "the spell's own Power, no Deflect 2"


@case(8788, "a second Hard Bargain can answer the same spell")
def _():
    need("Hard Bargain", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=16)
    give(s, 1, "Hard Bargain", "Hard Bargain")
    s.runes_ready[1, :] = 16
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Singularity", u, -1)
    cast(s, 1, "Hard Bargain")
    choose(s, sorted(targets_offered(s, 1))[0])
    assert "Hard Bargain" in hand_plays(s, 1), "the chain takes another answer"
    cast(s, 1, "Hard Bargain")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert alive(s, u), "one of the two taxes went unpaid"


@case(8835, "Challenge is no combat, so Draven scores nothing for winning it")
def _():
    need("Challenge", "Draven - Audacious")
    s = fresh(hand=[T.id_of("Challenge")], runes=9)
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Challenge", dr, theirs)
    run(s)
    assert not alive(s, theirs) and alive(s, dr)
    assert int(s.points[0]) == 0, "no combat was ever initiated"


@case(8834, "Power Nexus can pay for the eighth point")
def _():
    need("Power Nexus")
    s = fresh(runes=12)
    s.bf_card[0] = T.id_of("Power Nexus")
    s.bf_ctrl[0] = 0
    s.points[0] = 7
    body(s, 0, bf_loc(0), 3)
    _next_own_turn(s)
    run(s, picking(accept=True), limit=40)
    assert int(s.points[0]) == 8, "448.1.a.1 beholds only Conquer and Hold"


@case(8833, "Defy cannot answer a unit: units never reach the Chain")
def _():
    need("First Mate", "Defy")
    s = fresh(hand=[T.id_of("First Mate")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "First Mate"), 0)
    choose(s, base_loc(0))
    assert len(perm_of(s, "First Mate", 0)) == 1
    assert "Defy" not in hand_plays(s, 1), "only its trigger is on the chain"


@case(8832, "a card hidden this turn cannot be played this turn")
def _():
    need("Edge of Night")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd] = 0, T.id_of("Edge of Night")
    s.fd_ply[fd] = int(s.ply)
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_PLAY_HIDDEN], "737.1.b makes you wait a turn"
    s.fd_ply[fd] = int(s.ply) - 2
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_HIDDEN]


@case(8827, "Rek'Sai moving into an empty battlefield is not attacking")
def _():
    need("Rek'Sai - Swarm Queen")
    s = fresh(runes=9)
    rs = s.add_permanent(T.id_of("Rek'Sai - Swarm Queen"), 0, base_loc(0),
                         ready=True)
    attack(s, 0, 0, rs)
    assert not s.showdown_combat, "an empty battlefield is no combat"
    assert int(s.n_chain) == 0 and int(s.n_trig) == 0, "no 'when I attack'"
    assert int(s.bf_ctrl[0]) == 0, "it just conquered"


@case(8825, "Sunken Temple is happy with a unit that was already Mighty")
def _():
    need("Sunken Temple")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Sunken Temple")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 5, ready=True)
    before = int(s.n_hand[0])
    attack(s, 0, 0, u)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1, "708: 5+ Might is Mighty already"


@case(8819, "Trinity Force's point can be the eighth")
def _():
    need("Trinity Force", "Skyfall of Areion")
    s = fresh(runes=12)
    s.points[0] = 7
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    for name in ("Trinity Force", "Skyfall of Areion"):
        g = s.add_permanent(T.id_of(name), 0, base_loc(0))
        act(s, A.A_ACTIVATE, g, 0)
        choose(s, u)
        run(s)
    attack(s, 0, 0, u)
    fight(s)
    assert int(s.points[0]) == 8, "a hold effect made a conquer effect"


@case(8817, "two Eager Apprentices reduce a spell by 2 Energy")
def _():
    need("Eager Apprentice", "Singularity")
    from rl.engine import cost as cost_mod
    cid = T.id_of("Singularity")

    def energy(n):
        s = fresh(runes=12)
        s.bf_ctrl[0] = 0
        for _ in range(n):
            s.add_permanent(T.id_of("Eager Apprentice"), 0, bf_loc(0), ready=True)
        return cost_mod.apply_discounts(
            int(T.energy[cid]), cost_mod.energy_discounts(s, T, 0, cid))

    assert energy(0) == 6 and energy(1) == 5 and energy(2) == 4


@case(8815, "Minotaur Reckoner leaves Reaver's Row's trigger with nothing to do")
def _():
    need("Minotaur Reckoner", "Reaver's Row")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Reaver's Row")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Minotaur Reckoner"), 1, base_loc(1), ready=False)
    home = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    run(s, picking(home), limit=40)
    assert int(s.perms[home, P_LOC]) == bf_loc(0), "'can't' beats 'you may move'"


@case(8814, "Carnivorous Snapvine must choose when there is a unit to choose")
def _():
    need("Carnivorous Snapvine")
    s = fresh(hand=[T.id_of("Carnivorous Snapvine")], runes=14)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Carnivorous Snapvine"), 0)
    choose(s, base_loc(0))
    offered = targets_offered(s, 0)
    assert offered == {foe}, "no decline is offered"
    choose(s, foe)
    run(s)
    assert not alive(s, foe)


@case(8812, "Yordle Explorer reads the printed Power cost, not the Repeat")
def _():
    need("Yordle Explorer", "Called Shot")
    s = fresh(hand=[T.id_of("Called Shot")], runes=12)
    ye = s.add_permanent(T.id_of("Yordle Explorer"), 0, base_loc(0), ready=True)
    before = int(s.n_hand[0])
    cast(s, 0, "Called Shot", repeat=True)
    run(s, picking(0))
    assert ye >= 0
    assert int(s.n_hand[0]) == before - 1 + 2, "two draws from the spell, none else"


@case(8809, "Unchecked Power's damage lands at once, so one save still works")
def _():
    need("Unchecked Power", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Unchecked Power")], runes=16)
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Unchecked Power")
    run(s)
    assert alive(s, a) != alive(s, b), "exactly one of them was saved"
    assert not alive(s, z)


@case(8808, "Hidden Blade on a unit you stole draws YOU the two cards")
def _():
    need("Hostile Takeover", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hostile Takeover"), T.id_of("Hidden Blade")], runes=16)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hostile Takeover", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0
    before = int(s.n_hand[0])
    cast(s, 0, "Hidden Blade", foe)
    run(s)
    assert not alive(s, foe)
    assert int(s.n_hand[0]) == before - 1 + 2, "its controller is you"


@case(8807, "Yordle Explorer draws even when the card played chooses him")
def _():
    need("Yordle Explorer", "Beast Below")
    s = fresh(hand=[T.id_of("Beast Below")], runes=16)
    ye = s.add_permanent(T.id_of("Yordle Explorer"), 0, base_loc(0), ready=True)
    foe = body(s, 1, base_loc(1), 3)
    before = int(s.n_hand[0])
    act(s, A.A_PLAY, hand_index(s, 0, "Beast Below"), 0)
    choose(s, base_loc(0))
    run(s, picks(ye, foe))
    assert not alive(s, ye), "he went back to hand"
    assert int(s.n_hand[0]) == before - 1 + 1 + 1, "drawn, and returned"


@case(8804, "a countered Get Excited! discards nothing")
def _():
    need("Get Excited!", "Defy")
    s = fresh(hand=[T.id_of("Get Excited!"), T.id_of("Singularity")], runes=12)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    before = int(s.n_hand[0])
    cast(s, 0, "Get Excited!", u)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.n_hand[0]) == before - 1, "only Get Excited! itself left the hand"
    assert int(s.perms[u, P_DMG]) == 0


@case(8798, "the showdown continues after Overzealous Fan sends a unit home")
def _():
    need("Overzealous Fan", "Rune Prison")
    s = fresh(runes=12)
    give(s, 0, "Rune Prison")
    s.bf_ctrl[0] = 1
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0), ready=True)
    a = body(s, 0, base_loc(0), 3, ready=True)
    b = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a, b)
    run(s, picking(a, accept=True), limit=12,
        stop=lambda st: int(st.perms[a, P_LOC]) == base_loc(0))
    assert int(s.perms[a, P_LOC]) == base_loc(0) and not alive(s, fan)
    assert int(s.showdown_bf) == 0, "the showdown is still open"


@case(8797, "Fight or Flight cannot pull a unit out of Vilemaw's Lair")
def _():
    need("Fight or Flight", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Fight or Flight")], runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Fight or Flight", u)
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "the move simply fails"


@case(8790, "Defiant Dance's targets are locked in at cast")
def _():
    need("Defiant Dance", "Deathgrip")
    s = fresh(runes=9)
    give(s, 0, "Defiant Dance")
    give(s, 1, "Deathgrip")
    s.runes_ready[1, :] = 9
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    spare = body(s, 1, base_loc(1), 4)
    cast(s, 0, "Defiant Dance", mine, theirs)
    cast(s, 1, "Deathgrip", theirs, spare)
    run(s)
    assert not alive(s, theirs)
    assert combat.might(s, T, spare) == 4 + 3, "no -2 moved onto the survivor"


@case(8787, "a 0 Might unit deals no damage but still dies to Imperial Decree")
def _():
    need("Imperial Decree", "Defiant Dance")
    s = fresh(hand=[T.id_of("Imperial Decree"), T.id_of("Defiant Dance")], runes=16)
    s.bf_ctrl[0] = 1
    mine = body(s, 0, base_loc(0), 3, ready=True)
    spare = body(s, 0, base_loc(0), 3, ready=True)
    theirs = body(s, 1, bf_loc(0), 2)
    cast(s, 0, "Defiant Dance", spare, theirs)
    run(s)
    assert combat.might(s, T, theirs) == 0
    cast(s, 0, "Imperial Decree")
    run(s)
    attack(s, 0, 0, mine)
    fight(s)
    assert alive(s, mine), "0 Might assigns no combat damage"
    assert not alive(s, theirs), "but it took some, and the Decree kills on damage"


@case(8786, "Draven's legend draws for a combat you joined with Ride the Wind")
def _():
    need("Draven - Glorious Executioner", "Ride The Wind")
    s = fresh(runes=12)
    give(s, 1, "Ride The Wind")
    s.legend[1], s.legend_ready[1] = T.id_of("Draven - Glorious Executioner"), 1
    s.runes_ready[1, :] = 12
    att = body(s, 0, base_loc(0), 3, ready=True)
    home = body(s, 1, base_loc(1), 9)
    attack(s, 0, 0, att)
    before = int(s.n_hand[1])
    cast(s, 1, "Ride The Wind", home, bf_loc(0))
    fight(s)
    assert not alive(s, att) and alive(s, home)
    assert int(s.n_hand[1]) == before - 1 + 1, "the spell left, the draw arrived"
