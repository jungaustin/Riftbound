"""RiftJudge batch 50 -- unused questions from 8138-8189."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8189, "Leona - Zealot's floor applies after every buff")
def _():
    need("Leona - Zealot", "Rune Prison", "Primal Strength")
    s = fresh(runes=32)
    give(s, 0, "Rune Prison", "Primal Strength")
    s.bf_ctrl[0] = 0
    le = s.add_permanent(T.id_of("Leona - Zealot"), 0, bf_loc(0), ready=True)
    foe = body(s, 1, bf_loc(0), 4)
    cast(s, 0, "Primal Strength", foe)
    drain(s)                                 # a Cleanup here would start combat
    assert combat.might(s, T, foe) == 11
    cast(s, 0, "Rune Prison", foe)
    drain(s)
    assert combat.might(s, T, foe) == 3, "11 - 8, continuously"
    assert le >= 0


@case(8188, "a non-combat showdown heals nothing")
def _():
    need("Hextech Ray")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=24)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Hextech Ray", u)
    run(s)
    assert int(s.perms[u, P_DMG]) == 3
    mover = body(s, 0, base_loc(0), 3, ready=True)
    s.bf_ctrl[1] = -1
    attack(s, 0, 1, mover)
    fight(s)
    assert int(s.perms[u, P_DMG]) == 3, "no combat, no heal"


@case(8186, "Possession is your first card, and the stolen Darius counts it")
def _():
    need("Possession", "Darius - Trifarian", "Discipline")
    s = fresh(hand=[T.id_of("Possession"), T.id_of("Discipline")], runes=32)
    s.bf_ctrl[0] = 1
    dar = s.add_permanent(T.id_of("Darius - Trifarian"), 1, bf_loc(0), ready=True)
    cast(s, 0, "Possession", dar)
    run(s)
    assert int(s.perms[dar, P_CTRL]) == 0
    cast(s, 0, "Discipline", dar)
    run(s)
    assert combat.might(s, T, dar) == 5 + 2 + 2, "his +2 and Discipline's +2"


@case(8181, "Last Rites needs two cards in the trash to equip")
def _():
    need("Last Rites")
    s = fresh(runes=24)
    body(s, 0, base_loc(0), 3, ready=True)
    lr = s.add_permanent(T.id_of("Last Rites"), 0, base_loc(0))
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == lr], "an empty trash"
    s.trash[0, :2] = VANILLA
    s.n_trash[0] = 2
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE and a.arg == lr]


@case(8179, "Bullet Time's Power is paid while it resolves")
def _():
    need("Bullet Time")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=24)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 5)
    before = runes(s, 0)
    cast(s, 0, "Bullet Time", bf_loc(0))
    assert runes(s, 0) == before, "nothing recycled on the way in"
    run(s, picking(5))
    assert not alive(s, u)
    assert before - runes(s, 0) == 5, "and the 5 came out during resolution"


@case(8176, "an increase and a decrease are layered, not netted as they land")
def _():
    need("Primal Strength", "Smoke Screen")
    s = fresh(runes=24)
    give(s, 0, "Primal Strength", "Smoke Screen")
    u = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Primal Strength", u)
    run(s)
    assert combat.might(s, T, u) == 9
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert combat.might(s, T, u) == 5, "9 - 4, floored at 1 and never reached"


@case(8175, "Vanguard Helm chooses before the Hook's unit arrives")
def _():
    need("Vanguard Helm", "Baited Hook", "Riptide Rex")
    s = fresh(runes=32)
    vh = s.add_permanent(T.id_of("Vanguard Helm"), 0, base_loc(0))
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 5)
    s.set_flag(victim, F_BUFFED)
    other = body(s, 0, base_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Riptide Rex")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), other, accept=True), limit=60)
    assert not alive(s, victim)
    assert s.has_flag(other, F_BUFFED), "the only unit it could choose"
    assert vh >= 0


@case(8174, "Volibear, Furious locks his split as the trigger is placed")
def _():
    need("Volibear - Furious")
    s = fresh(runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    vb = s.add_permanent(T.id_of("Volibear - Furious"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, vb)
    run(s, picking(d), limit=10,
        stop=lambda st: int(st.perms[d, P_DMG]) > 0)
    assert int(s.perms[d, P_DMG]) == 5, "all 5 on the one unit that was there"


@case(8173, "Zhonya's Hourglass is not optional")
def _():
    need("Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=24)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Hidden Blade", u)
    run(s, picking(accept=False))
    assert alive(s, u) and not alive(s, z), "it replaced the death regardless"


@case(8172, "Darius - Hand of Noxus adds Energy once you have played a card")
def _():
    need("Darius - Hand of Noxus", "Determined Sentry", "Ravenbloom Student")
    s = fresh(hand=[T.id_of("Determined Sentry"), T.id_of("Ravenbloom Student")],
              runes=0)
    s.legend[0], s.legend_ready[0] = T.id_of("Darius - Hand of Noxus"), 1
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 2
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, base_loc(0))
    run(s)
    assert "Ravenbloom Student" not in hand_plays(s, 0), "one rune is not two"
    act(s, A.A_ACTIVATE, None, 0)
    run(s)
    assert "Ravenbloom Student" in hand_plays(s, 0), "[Legion] was on, so +1 Energy"


@case(8170, "Mask of Foresight triggers again at the next battlefield")
def _():
    need("Mask of Foresight", "Ride The Wind", "Traveling Merchant")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    mask = s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 9)
    attack(s, 0, 1, tm)
    drain(s)
    assert combat.might(s, T, tm) == 3, "2 printed plus the Mask's +1"
    assert mask >= 0


@case(8166, "Unyielding Spirit stops an ability that deals the damage itself")
def _():
    need("Unyielding Spirit", "Caitlyn - Patrolling")
    s = fresh(runes=32)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    ca = s.add_permanent(T.id_of("Caitlyn - Patrolling"), 0, bf_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    d = body(s, 1, bf_loc(1), 9)
    act(s, A.A_ACTIVATE, ca, 0)
    choose(s, d)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert int(s.perms[d, P_DMG]) == 0, "'Deal damage' with no subject is the ability"


@case(8163, "Grand Stratagem reaches only what is already there")
def _():
    need("Grand Strategem", "Determined Sentry")
    s = fresh(hand=[T.id_of("Grand Strategem"), T.id_of("Determined Sentry")],
              runes=32)
    first = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Grand Strategem")
    run(s)
    assert combat.might(s, T, first) == 8
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, base_loc(0))
    run(s)
    late = perm_of(s, "Determined Sentry", 0)[0]
    assert combat.might(s, T, late) == 1, "it arrived after the spell resolved"


@case(8162, "the attacker holds priority on the initial chain")
def _():
    need("Reaver's Row")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_card[0] = T.id_of("Reaver's Row")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    assert int(s.priority) == 0, "the contester keeps it"


@case(8160, "Sett's conquer buff can refill what the Monastery spent")
def _():
    need("Monastery of Hirana", "Sett, Brawler")
    s = fresh(runes=24)
    s.bf_card[0] = T.id_of("Monastery of Hirana")
    s.bf_ctrl[0] = 1
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    before = int(s.n_hand[0])
    attack(s, 0, 0, sett)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1 and s.has_flag(sett, F_BUFFED)


@case(8157, "Svellsongur attaches after finalization, so Irelia gains +1 once")
def _():
    need("Svellsongur", "Irelia, Fervent")
    s = fresh(runes=24)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=True)
    g = s.add_permanent(T.id_of("Svellsongur"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, ir)
    run(s)
    assert int(s.perms[g, P_ATTACHED_TO]) == ir
    assert combat.might(s, T, ir) == 5, "one choice, one +1"


@case(8155, "Yasuo, Unforgiven moves one unit, not a group")
def _():
    need("Yasuo - Unforgiven")
    s = fresh(runes=24)
    s.legend[0], s.legend_ready[0] = T.id_of("Yasuo - Unforgiven"), 1
    s.bf_ctrl[0] = 0
    a = body(s, 0, base_loc(0), 3, ready=False)
    b = body(s, 0, base_loc(0), 3, ready=False)
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(a, bf_loc(0)))
    assert int(s.perms[a, P_LOC]) == bf_loc(0)
    assert int(s.perms[b, P_LOC]) == base_loc(0), "only the one chosen"


@case(8154, "a unit forced onto Ahri's ground is still an attacker")
def _():
    need("Ahri, Inquisitive", "Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    ah = s.add_permanent(T.id_of("Ahri, Inquisitive"), 0, bf_loc(0), ready=True)
    foe = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Charm", foe, bf_loc(0))
    run(s, picking(foe), limit=20)
    assert int(s.perms[foe, P_LOC]) == bf_loc(0)
    assert combat.might(s, T, foe) == 3, "her defend trigger found the attacker"
    assert ah >= 0


@case(8153, "Void Gate raises every instance Icathian Rain deals")
def _():
    need("Icathian Rain", "Void Gate")
    s = fresh(hand=[T.id_of("Icathian Rain")], runes=32)
    s.bf_card[0] = T.id_of("Void Gate")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 12)
    cast(s, 0, "Icathian Rain", u, u, u, u, u, u)
    run(s)
    assert not alive(s, u), "six instances of 3, not of 2"


@case(8143, "a Might change is not damage, so the Decree ignores it")
def _():
    need("Imperial Decree", "Stupefy")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=32)
    give(s, 0, "Stupefy")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Imperial Decree")
    run(s)
    cast(s, 0, "Stupefy", u)
    run(s)
    assert alive(s, u), "-1 Might is not damage taken"


@case(8139, "Discipline needs a unit to choose")
def _():
    need("Discipline")
    s = fresh(runes=24)
    give(s, 0, "Discipline")
    assert "Discipline" not in hand_plays(s, 0), "355.8 with nothing on the board"
    body(s, 0, base_loc(0), 3)
    assert "Discipline" in hand_plays(s, 0)


@case(8138, "Black Market Broker counts a card played from hiding")
def _():
    need("Black Market Broker", "Hidden Blade")
    s = fresh(runes=24)
    bm = s.add_permanent(T.id_of("Black Market Broker"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s, picking(foe))
    assert len(tokens(s, 0)) == 1, "the Facedown Zone is where it came from"
    assert bm >= 0
