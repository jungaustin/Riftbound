"""RiftJudge batch 40 -- unused questions from 8687-8730."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8730, "'I can't be readied' does not stop Maduli entering ready")
def _():
    need("Confront", "Maduli the Gatekeeper")
    s = fresh(hand=[T.id_of("Confront"), T.id_of("Maduli the Gatekeeper")],
              runes=16)
    cast(s, 0, "Confront")
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Maduli the Gatekeeper"), 0)
    choose(s, base_loc(0))
    run(s)
    md = perm_of(s, "Maduli the Gatekeeper", 0)[0]
    assert int(s.perms[md, P_READY]) == 1, "entering ready is not being readied"


@case(8729, "Counter Strike's draw waits for the spell to resolve")
def _():
    need("Counter Strike", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=12)
    give(s, 1, "Counter Strike")
    s.runes_ready[1, :] = 12
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", u, u)
    before = int(s.n_hand[1])
    cast(s, 1, "Counter Strike", u)
    assert int(s.n_hand[1]) == before - 1, "on the chain, nothing drawn yet"
    run(s)
    assert int(s.n_hand[1]) == before - 1 + 1


@case(8725, "Brutalizer moved to another unit is +3 there")
def _():
    need("Brutalizer", "Angle Shot")
    s = fresh(runes=12)
    give(s, 0, "Angle Shot")
    a = body(s, 0, base_loc(0), 3, ready=True)
    b = body(s, 0, base_loc(0), 3, ready=True)
    br = s.add_permanent(T.id_of("Brutalizer"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, br, 0)
    choose(s, a)
    run(s)
    assert combat.might(s, T, a) == 6
    cast(s, 0, "Angle Shot", b, br)
    run(s)
    assert int(s.perms[br, P_ATTACHED_TO]) == b
    assert combat.might(s, T, a) == 3 and combat.might(s, T, b) == 6


@case(8724, "Hidden Blade's draw lands even when Guardian Angel saves the unit")
def _():
    need("Hidden Blade", "Guardian Angel")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=12)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, ga, 1)
    choose(s, u)
    run(s)
    s.active = s.priority = 0
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and not alive(s, ga)
    assert int(s.n_hand[1]) == before + 2, "the spell resolved on a legal target"


@case(8723, "Wind Wall counters Time Warp like any other spell")
def _():
    need("Wind Wall", "Time Warp")
    s = fresh(hand=[T.id_of("Time Warp")], runes=20)
    give(s, 1, "Wind Wall")
    s.runes_ready[1, :] = 20
    cast(s, 0, "Time Warp")
    cast(s, 1, "Wind Wall")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.extra_turns[0]) == 0, "no turn was taken after this one"


@case(8722, "a countered Salvage draws nothing")
def _():
    need("Salvage", "Defy")
    s = fresh(hand=[T.id_of("Salvage")], runes=12)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    g = s.add_permanent(T.id_of("B.F. Sword"), 1, base_loc(1))
    before = int(s.n_hand[0])
    cast(s, 0, "Salvage", g)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert alive(s, g)
    assert int(s.n_hand[0]) == before - 1, "countered, so it never resolved"


@case(8709, "Cull the Weak is playable with no units of your own")
def _():
    need("Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=12)
    theirs = body(s, 1, base_loc(1), 3)
    assert not [i for i in range(s.n_perms)
                if alive(s, i) and int(s.perms[i, P_CTRL]) == 0]
    assert "Cull the Weak" in hand_plays(s, 0)
    cast(s, 0, "Cull the Weak")
    run(s, picking(theirs))
    assert not alive(s, theirs), "they still have to kill one"


@case(8720, "a stunned unit still deals Challenge's damage")
def _():
    need("Challenge", "Rune Prison")
    s = fresh(hand=[T.id_of("Challenge")], runes=12)
    give(s, 0, "Rune Prison")
    mine = body(s, 0, base_loc(0), 5)
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Rune Prison", mine)
    run(s)
    assert s.has_flag(mine, F_STUNNED)
    cast(s, 0, "Challenge", mine, theirs)
    run(s)
    assert int(s.perms[theirs, P_DMG]) == 5, "423.1.b is about COMBAT damage"


@case(8719, "Last Rites cannot be equipped without two cards to recycle")
def _():
    need("Last Rites")
    s = fresh(runes=9)
    body(s, 0, base_loc(0), 3, ready=True)
    lr = s.add_permanent(T.id_of("Last Rites"), 0, base_loc(0))
    s.trash[0, 0] = VANILLA
    s.n_trash[0] = 1
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == lr], "403.3"
    s.trash[0, 1] = VANILLA
    s.n_trash[0] = 2
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE and a.arg == lr]


@case(8718, "Not So Fast counters Switcheroo, which chooses two units")
def _():
    need("Switcheroo", "Not So Fast")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=12)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 2)
    b = body(s, 1, bf_loc(0), 6)
    cast(s, 0, "Switcheroo", a, b)
    cast(s, 1, "Not So Fast")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert combat.might(s, T, a) == 2 and combat.might(s, T, b) == 6


@case(8717, "Irelia readying in the Ready Step is +1 Might")
def _():
    need("Irelia, Fervent")
    s = fresh(runes=9)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=False)
    _next_own_turn(s)
    run(s, limit=20)
    assert int(s.perms[ir, P_READY]) == 1
    assert combat.might(s, T, ir) == 5, "readying her is readying her"


@case(8715, "Sun Disc never counted itself for [Legion]")
def _():
    need("Sun Disc")
    from rl.engine.state import P_ARRIVED
    s = fresh(hand=[T.id_of("Sun Disc")], runes=12)
    act(s, A.A_PLAY, hand_index(s, 0, "Sun Disc"), 0)
    choose(s, base_loc(0))
    run(s)
    sd = perm_of(s, "Sun Disc", 0)[0]
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE], "812.1.b.1: it is not another card"
    s.perms[sd, P_ARRIVED] = -1
    s.cards_played[0] = 2
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]


@case(8713, "a buff spent on the Monastery does not come back")
def _():
    need("Monastery of Hirana", "Warmog's Armor")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Monastery of Hirana")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    s.set_flag(u, F_BUFFED)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    before = int(s.n_hand[0])
    attack(s, 0, 0, u)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1, "the Monastery drew"
    assert s.has_flag(u, F_BUFFED), "702.2.b spent one, Warmog's gave one back"


@case(8711, "a repeated Hidden Blade finds no second target, so one draw pair")
def _():
    need("Hidden Blade", "Temporal Portal")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=16)
    tp = s.add_permanent(T.id_of("Temporal Portal"), 0, base_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    act(s, A.A_ACTIVATE, tp, 0)
    run(s)
    mine_before, theirs_before = int(s.n_hand[0]), int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u, repeat=True)
    run(s, picking(u))
    assert not alive(s, u)
    assert int(s.n_hand[1]) == theirs_before + 2, "its controller drew once"
    assert int(s.n_hand[0]) == mine_before - 1, "and you drew nothing"


@case(8707, "Imperial Decree's kill lands during the combat, not after it")
def _():
    need("Imperial Decree", "Rune Prison")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=16)
    s.bf_ctrl[0] = 1
    give(s, 0, "Rune Prison")
    att = body(s, 0, base_loc(0), 3, ready=True)
    d = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Rune Prison", d)
    run(s)
    cast(s, 0, "Imperial Decree")
    run(s)
    attack(s, 0, 0, att)
    fight(s)
    assert not alive(s, d), "3 damage it survived, and the Decree killed it"
    assert int(s.bf_ctrl[0]) == 0, "so the attacker took the ground"


@case(8705, "re-attaching an Equipment to its own bearer does nothing")
def _():
    need("Brutalizer")
    s = fresh(runes=12)
    u = body(s, 0, base_loc(0), 3, ready=True)
    br = s.add_permanent(T.id_of("Brutalizer"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, br, 0)
    choose(s, u)
    run(s)
    assert combat.might(s, T, u) == 6, "+1 printed and +2 for the turn it landed"
    _next_own_turn(s)
    assert combat.might(s, T, u) == 4, "a later turn is just the +1"
    # No action in the pool re-attaches a gear to the unit already wearing it
    # (an [Equip] is not offered for an attached gear, and Angle Shot's toggle
    # detaches it), so 434.1.g is asserted at the one call every attaching
    # effect goes through.
    s.attach(br, u)
    assert combat.might(s, T, u) == 4, "434.1.g: nothing happens, not even a restamp"


@case(8702, "Overzealous Fan is dead whether or not its ability is countered")
def _():
    need("Overzealous Fan", "Not So Fast")
    s = fresh(runes=16)
    give(s, 0, "Not So Fast")
    s.bf_ctrl[0] = 1
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0), ready=True)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    run(s, picking(att, accept=True), limit=6,
        stop=lambda st: not alive(st, fan))
    assert not alive(s, fan), "'kill me' is a cost paid to place the ability"


@case(8699, "Downwell sweeps the Gold tokens away with everything else")
def _():
    need("Downwell", "Honest Broker", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade"), T.id_of("Downwell")], runes=20)
    s.bf_ctrl[0] = 0
    hb = s.add_permanent(T.id_of("Honest Broker"), 0, bf_loc(0), ready=True)
    cast(s, 0, "Hidden Blade", hb)
    run(s)
    gold = tokens(s, 0)
    assert gold, "the Deathknell made a Gold token"
    cast(s, 0, "Downwell")
    run(s)
    assert not any(alive(s, g) for g in gold), "186: a token off the board is gone"


@case(8695, "Pickpocket may be played with no gear to kill")
def _():
    need("Pickpocket")
    s = fresh(hand=[T.id_of("Pickpocket")], runes=12)
    assert "Pickpocket" in hand_plays(s, 0), "playing a unit is not its trigger"
    act(s, A.A_PLAY, hand_index(s, 0, "Pickpocket"), 0)
    choose(s, base_loc(0))
    run(s)
    assert len(perm_of(s, "Pickpocket", 0)) == 1
    assert not tokens(s, 0), "nothing was killed, so no Gold"


@case(8693, "Ahri, Inquisitive pays [Deflect] for the unit she shrinks")
def _():
    need("Ahri, Inquisitive", "Draven - Audacious")

    def spend(deflect):
        s = fresh(runes=12)
        s.bf_ctrl[0] = 1
        ah = s.add_permanent(T.id_of("Ahri, Inquisitive"), 0, base_loc(0),
                             ready=True)
        if deflect:
            s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0),
                            ready=True)
        else:
            body(s, 1, bf_loc(0), 6)
        attack(s, 0, 0, ah)
        before = runes(s, 0)
        run(s, picking(accept=True), limit=10)
        return before - runes(s, 0)

    assert spend(True) == spend(False) + 1


@case(8687, "Cull the Weak kills a Ruin Runner: nobody chose it")
def _():
    need("Cull the Weak", "Ruin Runner")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=12)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Cull the Weak")
    run(s, picks(mine, rr))
    assert not alive(s, rr), "its controller chose it, not you"


@case(8703, "a discount that floors at 1 Energy never reaches 0")
def _():
    need("Eager Apprentice", "Bellows Breath")
    from rl.engine import cost as cost_mod
    cid = T.id_of("Bellows Breath")
    s = fresh(runes=16)
    s.bf_ctrl[0] = 0
    for _ in range(3):
        s.add_permanent(T.id_of("Eager Apprentice"), 0, bf_loc(0), ready=True)
    e = cost_mod.apply_discounts(int(T.energy[cid]),
                                 cost_mod.energy_discounts(s, T, 0, cid))
    assert int(T.energy[cid]) == 1 and e == 1, "356.4.e floors it, never 0"


@case(8692, "Overzealous Fan pays [Deflect] to send a unit home")
def _():
    need("Overzealous Fan", "Draven - Audacious")
    s = fresh(runes=12)
    s.bf_ctrl[0] = 1
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0), ready=True)
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, dr)
    before = runes(s, 1)
    run(s, picking(dr, accept=True), limit=10,
        stop=lambda st: int(st.perms[dr, P_LOC]) == base_loc(0))
    assert int(s.perms[dr, P_LOC]) == base_loc(0)
    assert before - runes(s, 1) == 1, "the Fan's controller paid the tax"
    assert fan >= 0
