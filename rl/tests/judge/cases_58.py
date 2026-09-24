"""RiftJudge batch 58 -- unused questions from 7746-7803."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7803, "Ekko's Deathknell resolves after the combat has healed")
def _():
    need("Ekko - Recurrent")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ek = s.add_permanent(T.id_of("Ekko - Recurrent"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    s.runes_spent[0, :] = s.runes_ready[0, :]        # a board of spent runes
    s.runes_ready[0, :] = 0
    attack(s, 0, 0, ek)
    fight(s)
    assert not alive(s, ek), "9 against 5"
    assert int(s.perms[d, P_DMG]) == 0, "the heal came first"
    assert int(s.runes_ready[0].sum()) > 0, "and then his runes came back"


@case(7798, "Fox-Fire pays [Deflect] for each chosen unit that has it")
def _():
    need("Fox-Fire", "Draven - Audacious")

    def spend(n_deflect):
        s = fresh(hand=[T.id_of("Fox-Fire")], runes=32)
        s.bf_ctrl[0] = 1
        small = body(s, 1, bf_loc(0), 2)
        picks = [small]
        for _ in range(n_deflect):
            picks.append(s.add_permanent(T.id_of("Draven - Audacious"), 1,
                                         bf_loc(0), ready=True))
        before = runes(s, 0)
        act(s, A.A_PLAY, hand_index(s, 0, "Fox-Fire"), 0)
        for p in picks[:1]:
            choose(s, p)
        for _ in range(3):
            choose(s, -1)
        run(s)
        return before - runes(s, 0)

    assert spend(0) == spend(1), "only the units actually chosen are taxed"


@case(7794, "Reaver's Row can pull the unit away before the damage lands")
def _():
    need("Reaver's Row", "Yasuo - Remorseful")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Reaver's Row")
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ya)
    choose(s, d)
    run(s, picking(d, accept=True), limit=20,
        stop=lambda st: int(st.perms[d, P_LOC]) == base_loc(1))
    assert int(s.perms[d, P_LOC]) == base_loc(1), "the Row sent it home"
    drain(s)
    assert int(s.perms[d, P_DMG]) == 0, "and the damage found nobody"


@case(7790, "Discipline draws even when Gust took its target first")
def _():
    need("Discipline", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Gust", u)
    run(s)
    assert not alive(s, u)
    assert int(s.n_hand[0]) == before - 1 + 1 + 1


@case(7788, "Emperor's Divide chooses the units, so Irelia sees it")
def _():
    need("Emperor's Divide", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Emperor's Divide")], runes=32)
    s.bf_ctrl[0] = 0
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0), ready=True)
    cast(s, 0, "Emperor's Divide")
    run(s, picking(ir))
    assert int(s.perms[ir, P_LOC]) == base_loc(0)
    assert combat.might(s, T, ir) == 5, "being chosen is being chosen"


@case(7783, "a buff rides along when control changes")
def _():
    need("Possession")
    s = fresh(hand=[T.id_of("Possession")], runes=32)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    s.set_flag(foe, F_BUFFED)
    cast(s, 0, "Possession", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0 and s.has_flag(foe, F_BUFFED)


@case(7781, "damage from Challenge waits for a combat or the turn's end")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=32)
    mine = body(s, 0, base_loc(0), 9)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Challenge", mine, theirs)
    run(s)
    assert int(s.perms[mine, P_DMG]) == 3
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=40)
    assert int(s.perms[mine, P_DMG]) == 0, "the turn ended and it healed"


@case(7780, "a floored -1 took nothing, and a later +1 still adds")
def _():
    need("Ahri - Nine-Tailed Fox", "Siphon Power")
    s = fresh(runes=32)
    give(s, 1, "Siphon Power")
    s.runes_ready[1, :] = 32
    s.legend[0], s.legend_ready[0] = T.id_of("Ahri - Nine-Tailed Fox"), 1
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.ply += 1
    att = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, att)
    drain(s)
    assert combat.might(s, T, att) == 1, "floored at 1"
    cast(s, 1, "Siphon Power", bf_loc(0))
    drain(s)
    assert combat.might(s, T, att) == 2, "and +1 from there"


@case(7778, "The Dreaming Tree's draw beats the answer to the spell")
def _():
    need("The Dreaming Tree", "En Garde", "Gust")
    s = fresh(runes=32)
    give(s, 0, "En Garde")
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "En Garde", u)
    cast(s, 1, "Gust", u)
    run(s)
    assert not alive(s, u)
    assert int(s.n_hand[0]) == before - 1 + 1 + 1, "the Tree drew, then it bounced"


@case(7777, "an effect move does not care whether the unit is ready")
def _():
    need("Maddened Marauder")
    s = fresh(hand=[T.id_of("Maddened Marauder")], runes=32)
    s.bf_ctrl[0] = 1
    tired = body(s, 1, bf_loc(0), 3, ready=False)
    act(s, A.A_PLAY, hand_index(s, 0, "Maddened Marauder"), 0)
    choose(s, base_loc(0))
    run(s, picking(tired))
    assert int(s.perms[tired, P_LOC]) == base_loc(1), "452: no exhaust cost"


@case(7774, "the second Retreat resolves first and the first finds nobody")
def _():
    need("Retreat")
    s = fresh(runes=32)
    give(s, 0, "Retreat", "Retreat")
    rune_deck(s)
    u = body(s, 0, base_loc(0), 3)
    before = runes(s, 0)
    cast(s, 0, "Retreat", u)
    cast(s, 0, "Retreat", u)
    run(s)
    assert not alive(s, u)
    assert runes(s, 0) - before <= 1, "one rune channelled, not two"


@case(7773, "Dune Drake reads its condition as the trigger resolves")
def _():
    need("Dune Drake")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    dd = s.add_permanent(T.id_of("Dune Drake"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9, ready=True)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, dd)
    drain(s)
    assert combat.might(s, T, dd) == 7, "a ready enemy was there"


@case(7772, "there is no window inside the combat damage step")
def _():
    need("Discipline")
    s = fresh(runes=32)
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 5, ready=True)
    d = body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, att)
    fight(s)
    assert not alive(s, d), "nobody got to grow it mid-step"


@case(7770, "Ancient Henge can be used during Bullet Time's resolution")
def _():
    need("Ancient Henge", "Bullet Time")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    ah = s.add_permanent(T.id_of("Ancient Henge"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bullet Time", bf_loc(0))
    run(s, picking(3))
    assert not alive(s, u), "3 Power was chosen as it resolved"
    assert ah >= 0


@case(7768, "Stacked Deck looks, it does not draw")
def _():
    need("Stacked Deck")
    s = fresh(runes=32)
    give(s, 0, "Stacked Deck")
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 3] = VANILLA
    before = int(s.n_hand[0])
    cast(s, 0, "Stacked Deck")
    run(s, picking(0))
    assert int(s.n_hand[0]) == before - 1 + 1, "one card, and it came from a look"


@case(7766, "two play triggers you order can feed each other")
def _():
    need("Albus Ferros", "Cithria of Cloudfield")
    s = fresh(hand=[T.id_of("Albus Ferros")], runes=32)
    rune_deck(s)
    ci = s.add_permanent(T.id_of("Cithria of Cloudfield"), 0, base_loc(0),
                         ready=True)
    before = runes(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Albus Ferros"), 0)
    choose(s, base_loc(0))
    run(s, picking(ci, accept=True), limit=40)
    assert runes(s, 0) >= before, "her buff paid for a channel, or none did"


@case(7763, "Baited Hook is base speed")
def _():
    need("Baited Hook")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    body(s, 0, base_loc(0), 3)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, att)
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == bh], "not in a showdown"


@case(7755, "a 0 Might Mech token does not die of it")
def _():
    need("Rumble - Scrapper", "Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=32)
    ru = s.add_permanent(T.id_of("Rumble - Scrapper"), 1, base_loc(1), ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert alive(s, ru), "4 + 1 - 3 is still alive, and so would 0 be"
    assert combat.might(s, T, ru) == 2


@case(7746, "Last Breath chooses both of its units at cast")
def _():
    need("Last Breath")
    s = fresh(hand=[T.id_of("Last Breath")], runes=32)
    mine = body(s, 0, base_loc(0), 4, ready=False)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Last Breath"), 0)
    assert mine in targets_offered(s, 0), "the friendly unit is a target"
    choose(s, mine)
    assert foe in targets_offered(s, 0), "and so is the enemy"
