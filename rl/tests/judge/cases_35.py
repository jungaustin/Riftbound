"""RiftJudge batch 35 -- unused questions from 8972-9032."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(9028, "Karthus doubles a Deathknell even when he dies alongside it")
def _():
    need("Karthus - Eternal", "Carrion Dredger", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=9)
    ka = s.add_permanent(T.id_of("Karthus - Eternal"), 1, base_loc(1), ready=True)
    cd = s.add_permanent(T.id_of("Carrion Dredger"), 1, base_loc(1), ready=True)
    cast(s, 0, "Falling Star", ka, cd)
    run(s)
    assert not alive(s, ka) and not alive(s, cd)
    assert len(tokens(s, 1)) == 2, "the passive applied as they died together"


@case(9027, "Unyielding Spirit does not stop Imperial Decree's kill")
def _():
    need("Imperial Decree", "Unyielding Spirit")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=14)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = 1
    mine = body(s, 0, base_loc(0), 1, ready=True)
    theirs = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, mine)
    cast(s, 0, "Imperial Decree")
    cast(s, 1, "Unyielding Spirit")
    fight(s)
    assert not alive(s, theirs), "the Decree kills, it does not deal damage"


@case(9024, "the Phoenix that Hidden Blade killed may play itself back")
def _():
    need("Immortal Phoenix", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=12)
    s.bf_ctrl[0] = 0
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, bf_loc(0), ready=True)
    cast(s, 0, "Hidden Blade", ph)
    run(s, picking(base_loc(0)))
    assert len(perm_of(s, "Immortal Phoenix", 0)) == 1, "back from the trash"


@case(9023, "Sunken Temple checks [Mighty] as the conquer trigger condition")
def _():
    need("Sunken Temple", "Sett, Brawler")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Sunken Temple")
    s.bf_ctrl[0] = 1
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    before = int(s.n_hand[0])
    attack(s, 0, 0, sett)
    fight(s)
    assert combat.might(s, T, sett) == 5, "the conquer buff landed"
    assert int(s.n_hand[0]) == before, "but he was 4 Might when the Temple checked"


@case(9022, "Arcane Shift needs an enemy unit at a battlefield to be played")
def _():
    need("Arcane Shift")
    s = fresh(hand=[T.id_of("Arcane Shift")], runes=9)
    body(s, 0, base_loc(0), 3)
    assert "Arcane Shift" not in hand_plays(s, 0), "355.8: no legal second target"
    body(s, 1, bf_loc(0), 3)
    assert "Arcane Shift" in hand_plays(s, 0)


@case(9021, "Vi, Destructive's ability can be paid for again and again")
def _():
    need("Vi, Destructive")
    s = fresh(runes=9)
    vi = s.add_permanent(T.id_of("Vi, Destructive"), 0, base_loc(0), ready=True)
    for j in range(3):
        s.trash[0, j] = VANILLA
    s.n_trash[0] = 3
    for _ in range(3):
        act(s, A.A_ACTIVATE, vi, 0)
        run(s, picking(pack_trash(0, VANILLA)))
    assert combat.might(s, T, vi) == 6, "no once-each-turn is printed"


@case(9019, "a shrink after the damage still kills")
def _():
    need("Bellows Breath", "Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Bellows Breath"), T.id_of("Thousand-Tailed Watcher")],
              runes=14)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 4)
    cast(s, 0, "Bellows Breath", u, -1)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 1
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert not alive(s, u), "1 Might with 1 damage marked is lethal (143.2.a)"


@case(9017, "Mindsplitter's play trigger can be answered, the unit cannot")
def _():
    need("Mindsplitter", "Not So Fast")
    s = fresh(hand=[T.id_of("Mindsplitter")], runes=14)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    act(s, A.A_PLAY, hand_index(s, 0, "Mindsplitter"), 0)
    choose(s, base_loc(0))
    assert len(perm_of(s, "Mindsplitter", 0)) == 1, "the unit never waits on the chain"
    assert int(s.n_chain) + int(s.n_trig) >= 1, "its trigger does"


@case(9011, "a second buff from Pit Rookie can be spent the same turn")
def _():
    need("Sett, Brawler", "Pit Rookie")
    s = fresh(hand=[T.id_of("Pit Rookie")], runes=9)
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    act(s, A.A_ACTIVATE, None, 0)
    run(s)
    assert combat.might(s, T, sett) == 8 and not s.has_flag(sett, F_BUFFED)
    act(s, A.A_PLAY, hand_index(s, 0, "Pit Rookie"), 0)
    choose(s, base_loc(0))
    run(s, picking(sett))
    assert s.has_flag(sett, F_BUFFED), "Pit Rookie buffed him again"
    act(s, A.A_ACTIVATE, None, 0)
    run(s)
    assert combat.might(s, T, sett) == 12


@case(9009, "a Draven saved by Zhonya's Hourglass hands over no point")
def _():
    need("Draven - Audacious", "Zhonya's Hourglass")

    def enemy_points(guarded):
        s = fresh(runes=9)
        s.bf_ctrl[1] = 1
        dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0),
                             ready=True)
        body(s, 1, bf_loc(0), 9)
        if guarded:
            s.death_guard[0] = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0,
                                               base_loc(0))
        attack(s, 0, 0, dr)
        fight(s)
        assert alive(s, dr) == guarded
        return int(s.points[1])

    # Both runs hand the defender a hold point; only the unguarded one adds
    # Draven's own "when I die in combat" gift on top of it.
    assert enemy_points(False) - enemy_points(True) == 1, "366: he never died"


@case(9008, "Facebreaker stuns at Vilemaw's Lair: no move is involved")
def _():
    need("Facebreaker", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Facebreaker")], runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Facebreaker", mine, theirs)
    run(s)
    assert s.has_flag(mine, F_STUNNED) and s.has_flag(theirs, F_STUNNED)


@case(9004, "Defiant Dance still pumps when its other target dies first")
def _():
    need("Defiant Dance", "Deathgrip")
    s = fresh(hand=[T.id_of("Defiant Dance")], runes=9)
    give(s, 1, "Deathgrip")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(0), 3)
    spare = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Defiant Dance", mine, theirs)
    cast(s, 1, "Deathgrip", theirs, spare)
    run(s)
    assert not alive(s, theirs)
    assert combat.might(s, T, mine) == 5, "359.3.e.1: only the lost part is skipped"


@case(9003, "Deathgrip's kill replaced by Soraka gives no Might")
def _():
    need("Deathgrip", "Soraka - Wanderer")
    s = fresh(hand=[T.id_of("Deathgrip")], runes=9)
    s.bf_ctrl[0] = 0
    sor = s.add_permanent(T.id_of("Soraka - Wanderer"), 0, bf_loc(0), ready=True)
    small = body(s, 0, bf_loc(0), 2)
    other = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Deathgrip", small, other)
    run(s)
    assert alive(s, small) and int(s.perms[small, P_LOC]) == base_loc(0)
    assert combat.might(s, T, other) == 3, "it never died, so nothing was given"
    assert sor >= 0


@case(8995, "Piercing Light's second target is optional")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Piercing Light", u, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 2


@case(8990, "Not So Fast answers Adaptatron's conquer ability")
def _():
    need("Adaptatron", "Not So Fast", "Warmog's Armor")
    s = fresh(runes=9)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    ad = s.add_permanent(T.id_of("Adaptatron"), 0, base_loc(0), ready=True)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 1, base_loc(1))
    attack(s, 0, 0, ad)

    def pref(st, who, legal):
        if who == 1:
            play = [a for a in legal if a.kind == A.A_PLAY
                    and a.arg < int(st.n_hand[1])
                    and T.names[int(st.hand[1, a.arg])] == "Not So Fast"]
            if play:
                return play[0]
        return None
    run(s, pref, limit=40)
    assert alive(s, g) and not s.has_flag(ad, F_BUFFED), "the ability was countered"


@case(8989, "Relentless Pursuit can add a second Equipment to one unit")
def _():
    need("Relentless Pursuit", "Warmog's Armor", "B.F. Sword")
    s = fresh(hand=[T.id_of("Relentless Pursuit")], runes=12)
    s.bf_ctrl[0] = 0
    u = body(s, 0, base_loc(0), 3, ready=True)
    a = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    b = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.perms[a, P_ATTACHED_TO] = u
    cast(s, 0, "Relentless Pursuit", u, bf_loc(0))
    run(s, picking(b))
    assert int(s.perms[b, P_ATTACHED_TO]) == u, "744.3.b allows both"
    assert int(s.perms[a, P_ATTACHED_TO]) == u


@case(8987, "King's Edict does not choose, so no [Deflect] is paid")
def _():
    need("King's Edict", "Draven - Audacious")

    def spend(deflect):
        s = fresh(hand=[T.id_of("King's Edict")], runes=12)
        if deflect:
            u = s.add_permanent(T.id_of("Draven - Audacious"), 1, base_loc(1),
                                ready=True)
        else:
            u = body(s, 1, base_loc(1), 6)
        before = runes(s, 0)
        cast(s, 0, "King's Edict")
        run(s, picking(u))
        assert not alive(s, u), "the Edict killed it"
        return before - runes(s, 0)

    assert spend(True) == spend(False), "the Edict never chooses, so no tax"


@case(8984, "Rumble's [Assault] leaves with him, mid-showdown")
def _():
    need("Rumble - Hotheaded", "Hidden Blade", "Bubble Bot")
    s = fresh(runes=12)
    give(s, 1, "Hidden Blade")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[1] = 1
    ru = s.add_permanent(T.id_of("Rumble - Hotheaded"), 0, base_loc(0), ready=True)
    bot = s.add_permanent(T.id_of("Bubble Bot"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 5)
    attack(s, 0, 0, ru, bot)
    assert combat.might(s, T, bot) == 4, "3 Might plus [Assault]"
    cast(s, 1, "Hidden Blade", ru)
    drain(s)
    assert not alive(s, ru)
    assert combat.might(s, T, bot) == 3, "a continuous effect ends with its source"


@case(8983, "Riposte counters a repeated Thwonk! whole")
def _():
    need("Riposte", "Thwonk!")
    s = fresh(runes=12)
    give(s, 0, "Riposte")
    give(s, 1, "Thwonk!")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 5, ready=True)
    b = body(s, 0, base_loc(0), 5, ready=True)
    body(s, 1, bf_loc(0), 5)
    attack(s, 0, 0, a, b)
    cast(s, 1, "Thwonk!", a, b, repeat=True)
    cast(s, 0, "Riposte", a, top_uid(s))
    drain(s)
    assert not s.has_flag(a, F_STUNNED) and not s.has_flag(b, F_STUNNED)


@case(8979, "Ezreal's legend counts a choice made by a countered spell")
def _():
    need("Ezreal - Prodigal Explorer", "Wages of Pain", "Defy")
    s = fresh(hand=[T.id_of("Wages of Pain"), T.id_of("Wages of Pain")], runes=12)
    s.legend[0], s.legend_ready[0] = T.id_of("Ezreal - Prodigal Explorer"), 1
    give(s, 1, "Defy", "Defy")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 9)
    for _ in range(2):
        cast(s, 0, "Wages of Pain", u)
        cast(s, 1, "Defy")
        choose(s, sorted(targets_offered(s, 1))[0])
        run(s)
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE], \
        "two enemy units were chosen, counter or not"


@case(8977, "Ganking with Boots of Swiftness does not choose Irelia")
def _():
    need("Irelia, Fervent", "Boots of Swiftness")
    s = fresh(runes=9)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0), ready=True)
    g = s.add_permanent(T.id_of("Boots of Swiftness"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, ir)
    run(s)
    before = combat.might(s, T, ir)
    attack(s, 0, 1, ir)
    fight(s)
    assert int(s.perms[ir, P_LOC]) == bf_loc(1), "[Ganking] crossed over"
    assert combat.might(s, T, ir) == before, "352.10.c: a move chooses nobody"


@case(8976, "a repeated Piercing Light can hit two battlefields for 4 each")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=14)
    s.bf_ctrl[1] = 1
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Piercing Light", a, b, repeat=True)
    run(s, picks(a, b))
    assert int(s.perms[a, P_DMG]) == 4 and int(s.perms[b, P_DMG]) == 4


@case(8975, "a Deathknell still resolves after the unit leaves the trash")
def _():
    need("Unsung Hero", "Spectral Matron", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade"), T.id_of("Spectral Matron")], runes=14)
    s.bf_ctrl[0] = 0
    uh = s.add_permanent(T.id_of("Unsung Hero"), 0, bf_loc(0), ready=True)
    s.base_might_ply[uh], s.base_might_val[uh] = int(s.ply), 5
    before = int(s.n_hand[0])
    cast(s, 0, "Hidden Blade", uh)
    run(s)
    assert int(s.n_hand[0]) - before == 2 + 2 - 1, "Deathknell 2 plus the draw 2"


@case(8973, "a stolen Equipment goes home when Akshan leaves the board")
def _():
    need("Akshan - Mischievous", "B.F. Sword", "Cull the Weak")
    s = fresh(hand=[T.id_of("Akshan - Mischievous"), T.id_of("Cull the Weak")],
              runes=12)
    body(s, 1, base_loc(1), 3)
    s.bf_ctrl[0] = 0
    sword = s.add_permanent(T.id_of("B.F. Sword"), 1, base_loc(1))
    act(s, A.A_PLAY, hand_index(s, 0, "Akshan - Mischievous"), 0)
    act(s, A.A_PLAY_AT_FAST, bf_loc(0), 0)
    run(s, picking(sword))
    ak = perm_of(s, "Akshan - Mischievous", 0)[0]
    assert int(s.perms[sword, P_CTRL]) == 0, "his ability took control"
    cast(s, 0, "Cull the Weak")
    run(s, picking(ak))
    assert not alive(s, ak)
    assert int(s.perms[sword, P_CTRL]) == 1, "control reverts with the source"


@case(8972, "Vilemaw's Lair stops a Tideturner swap out of it")
def _():
    need("Tideturner", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Tideturner")], runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    stuck = body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Tideturner"), 0)
    choose(s, base_loc(0))
    run(s, picking(stuck))
    assert int(s.perms[stuck, P_LOC]) == bf_loc(0), "a 'can't' beats a 'may'"
