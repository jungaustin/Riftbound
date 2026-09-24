"""RiftJudge batch 80 -- unused questions from 6250-6445."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_READY


@case(6444, "Spirit's Refuge reads 'buffed' continuously, not as it is played")
def _():
    need("Spirit's Refuge", "Adaptatron")
    s = fresh(runes=32)
    later = body(s, 0, base_loc(0), 3)
    ref = s.add_permanent(T.id_of("Spirit's Refuge"), 0, base_loc(0))
    s.set_flag(later, F_BUFFED)                    # buffed after it was already down
    assert s.has_flag(later, F_BUFFED)
    assert combat.perm_kw(s, T, later, "Deflect"), \
        "'friendly BUFFED units have [Deflect]' is a passive, read live"
    plain = body(s, 0, base_loc(0), 3)
    assert not combat.perm_kw(s, T, plain, "Deflect"), "and only for the buffed ones"
    assert ref >= 0


@case(6442, "Retreat pays its owner even when the card it returns ceases to exist")
def _():
    need("Retreat", "Sprite Call")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Retreat")
    spr = _sprite_at(s, 0, 0)
    before, left = runes(s, 0), int(s.rune_left[0])
    hand = int(s.n_hand[0])
    cast(s, 0, "Retreat", spr)
    run(s, limit=40)
    assert not alive(s, spr), "a token returned to hand simply stops existing (187.4)"
    assert int(s.n_hand[0]) == hand - 1, "so nothing arrived in hand"
    assert runes(s, 0) == before + 1 and int(s.rune_left[0]) == left - 1, \
        "but 'its owner channels 1 rune' is not conditional on that"


@case(6441, "nothing heals between a spell and the Showdown that follows")
def _():
    need("Riptide Rex")
    s = fresh(runes=32)
    give(s, 0, "Riptide Rex", "Discipline")
    s.bf_ctrl[1] = 1
    big = body(s, 1, bf_loc(1), 7)
    cast(s, 0, "Riptide Rex", base_loc(0), big)
    run(s, limit=40)
    assert alive(s, big) and int(s.perms[big, P_DMG]) == 6, "6 into 7 Might survives"
    mover = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 1, mover)
    assert int(s.perms[big, P_DMG]) == 6, \
        "317.2.b heals at the END of a Combat, and this one has not even begun"


@case(6440, "Cull the Weak chooses, but its controller is the one choosing")
def _():
    need("Cull the Weak", "Tianna Crownguard")
    s = fresh(runes=32)
    give(s, 0, "Cull the Weak")
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1))   # [Deflect]
    body(s, 0, base_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    assert int(s.pend_tax) < 0, \
        "809.1: each player kills their OWN, so nothing of theirs was chosen by me"
    run(s, picking(accept=True), limit=60,
        stop=lambda st: A.acting_seat(st) == 1 and any(
            x.kind == A.A_TARGET for x in A.legal_actions(st, T, V1, 1)))
    assert A.acting_seat(s) == 1, "and THEY pick which of theirs dies"
    assert int(s.pend_tax) < 0, "still no Deflect surcharge anywhere in it"


@case(6435, "[Temporary]'s trigger is a window; a bare phase is not")
def _():
    need("Retreat", "Fading Memories")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Fading Memories")
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    doomed = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Fading Memories", doomed)
    run(s, limit=40)
    assert combat.perm_kw(s, T, doomed, "Temporary"), "it is living on borrowed time"
    # Their own turn arrives: the expiry is a trigger, and a trigger is a window.
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=20, stop=lambda st: int(st.n_chain) > 0)
    assert int(s.n_chain) >= 1, "816: [Temporary] expires as a triggered ability"
    assert "Retreat" in hand_plays(s, 1), "which their [Reaction] can answer"


@case(6432, "Bullet Time asks how much only as it resolves")
def _():
    need("Bullet Time")
    s = fresh(runes=32)
    give(s, 0, "Bullet Time")
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Bullet Time", bf_loc(1))
    assert int(s.pend_amount) < 0, \
        "355.1: nothing on the card asks for an amount at finalization"
    run(s, picks(2, accept=True), limit=60,
        stop=lambda st: int(st.pend_amount) >= 0)
    assert int(s.pend_amount) >= 0, "'pay any amount' is a choice made on resolution"
    assert alive(s, a), "and nothing has been paid yet, so nothing is dealt yet"


@case(6431, "the killed unit's Might is what it was worth, buffs and all")
def _():
    need("Baited Hook", "Watchful Sentry", "Darius - Trifarian")
    s = fresh(runes=32)
    bait = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    food = body(s, 0, base_loc(0), 3)
    s.set_flag(food, F_BUFFED)
    assert combat.might(s, T, food) == 4, "3 printed plus its Buff"
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Darius - Trifarian")   # 5 Might: 4 + 1
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picks(food, 0, base_loc(0), accept=True), limit=80)
    assert perm_of(s, "Darius - Trifarian", 0), \
        "'up to 1 more than the killed unit' read 4, not the printed 3"
    assert bait >= 0


@case(6426, "a Might swap is arithmetic on what the units are worth now")
def _():
    need("Switcheroo", "Wielder of Water")
    s = fresh(runes=32)
    give(s, 0, "Switcheroo", "Discipline")
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 9)                       # a defender, so this is a Combat
    w = s.add_permanent(T.id_of("Wielder of Water"), 0, base_loc(0), ready=True)
    attack(s, 0, 1, w)
    assert combat.might(s, T, w) == 4, "2 printed, +2 for attacking alone"
    small = body(s, 1, bf_loc(1), 1)
    cast(s, 0, "Switcheroo", w, small)
    drain(s)
    assert combat.might(s, T, w) == 1, \
        "477.3.b: the swap snapshots -3 against her 4, on top of her own +2"


@case(6425, "a trigger outlives its source, and the source can feed it from hand")
def _():
    need("Traveling Merchant", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    act(s, A.A_DECLARE, bf_loc(0), 0)
    act(s, A.A_ADD, tm, 0)
    act(s, A.A_COMMIT, None, 0)
    assert int(s.n_chain) >= 1 or int(s.n_trig) >= 1, "'when I move' is queued"
    cast(s, 0, "Gust", tm)                         # ...and the Merchant goes home
    run(s, picking(accept=True), limit=80)
    assert not alive(s, tm), "it left the board for their hand"
    assert T.id_of("Traveling Merchant") in [
        int(s.trash[0, i]) for i in range(int(s.n_trash[0]))], \
        "359.3.f: the trigger still resolved, and discarded the Merchant itself"


@case(6424, "'move a unit' names the unit and the destination at once")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Ride The Wind", u, bf_loc(0))
    assert int(s.n_chain) == 1 and int(s.pend_slot) < 0, \
        "355: both choices belong to finalization, so the item is complete"
    run(s, limit=40)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "and that is where it goes"


@case(6419, "a Gusted unit takes its own Might out of the equation")
def _():
    need("Carnivorous Snapvine", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Carnivorous Snapvine")
    give(s, 1, "Gust")
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 6)
    cast(s, 0, "Carnivorous Snapvine", base_loc(0), foe)
    sv = perm_of(s, "Carnivorous Snapvine", 0)[0]
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", sv) if combat.might(s, T, sv) <= 3 else None
    # 6 Might is out of Gust's reach, so the vine is sent home by hand instead:
    # the ruling is about the ability finding no Might to read, not about Gust.
    if alive(s, sv):
        combat.return_to_hand(s, T, sv)
    run(s, limit=60)
    assert alive(s, foe) and int(s.perms[foe, P_DMG]) == 0, \
        "359.3.f: 'our Mights' cannot be read off a unit that is not there"


@case(6418, "a trigger can be answered before it resolves, buff included")
def _():
    need("Carnivorous Snapvine", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Carnivorous Snapvine", "Discipline")
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 7)
    cast(s, 0, "Carnivorous Snapvine", base_loc(0), foe)
    sv = perm_of(s, "Carnivorous Snapvine", 0)[0]
    assert int(s.n_chain) >= 1, "419.4.a: her trigger waits on the Chain"
    cast(s, 0, "Discipline", sv)                   # +2 before the fight resolves
    run(s, limit=60)
    assert not alive(s, foe), "8 into a 7 Might unit is lethal"
    assert alive(s, sv), "and 7 into an 8 Might vine is not"


@case(6416, "an effect move needs no [Ganking]")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind", "Discipline")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = -1                              # open ground, nobody's
    u = body(s, 0, bf_loc(0), 3)
    assert not combat.perm_kw(s, T, u, "Ganking"), "a plain unit"
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    run(s, limit=60)
    fight(s, limit=80)
    assert int(s.perms[u, P_LOC]) == bf_loc(1), \
        "450: the Ganking restriction is on the STANDARD move, not on effects"
    assert int(s.bf_ctrl[1]) == 0, "so it conquers"


@case(6415, "a choice with a legal option is not a choice whether to")
def _():
    need("Carnivorous Snapvine")
    s = fresh(runes=32)
    give(s, 0, "Carnivorous Snapvine")
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Carnivorous Snapvine", base_loc(0))
    offered = {a.kind for a in A.legal_actions(s, T, V1, 0)}
    assert A.A_TARGET in offered, "there is an enemy unit at a battlefield"
    assert A.A_DECLINE not in offered, \
        "402.4.b: nothing says 'you may', so the choice must be made"
    assert foe >= 0


@case(6412, "a repeated spell gets its own full set of slots")
def _():
    need("Piercing Light")
    s = fresh(runes=32)
    give(s, 0, "Piercing Light")
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(1), 9)
    b = body(s, 1, bf_loc(1), 9)
    c = body(s, 1, base_loc(1), 9)                 # 'up to one OTHER unit': anywhere
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Piercing Light"), 0)
    seen = []
    while int(s.pend_slot) >= 0 and len(seen) < 6:
        slot = int(s.pend_slot)
        opts = {x.arg for x in A.legal_actions(s, T, V1, 0) if x.kind == A.A_TARGET}
        seen.append((slot, opts))
        want = (a, c, b, c)[len(seen) - 1] if len(seen) <= 4 else -1
        act(s, A.A_TARGET, want, 0)
    assert len(seen) == 4, f"820.2.a: four slots, its own pair per pass ({seen})"
    assert seen[0][1] == seen[2][1] == {a, b}, \
        "'a unit AT A BATTLEFIELD' for the first of each pair"
    assert c in seen[1][1] and c in seen[3][1], \
        "and 'up to one other unit' reaches the one in base"
    run(s, limit=60)
    assert int(s.perms[a, P_DMG]) == 2 and int(s.perms[b, P_DMG]) == 2 \
        and int(s.perms[c, P_DMG]) == 4, "four hits of 2, two of them on the same unit"


@case(6410, "the Showdown opens the moment the move lands")
def _():
    need("Ride The Wind", "Vi - Hotheaded")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Discipline")                       # holds the window open to be read
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 5)                       # their defender
    vi = s.add_permanent(T.id_of("Vi - Hotheaded"), 0, bf_loc(0), ready=True)
    assert A.A_ACTIVATE in kinds(s, 0), \
        "her speedless '{2 energy}{Fury rune}: double my Might' works in an Open State"
    cast(s, 0, "Ride The Wind", vi, bf_loc(1))
    run(s, limit=40, stop=lambda st: int(st.showdown_bf) >= 0)
    assert int(s.showdown_bf) == 1, "461: contested ground stages the Showdown at once"
    assert A.A_ACTIVATE not in kinds(s, 0), \
        "309.1.a: and a speedless ability cannot be activated inside one"


@case(6408, "a finalized item does not care whether its source survives")
def _():
    need("Dazzling Aurora", "Watchful Sentry")
    s = fresh(hand=[T.id_of("Dazzling Aurora")], runes=32)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Watchful Sentry")
    cast(s, 0, "Dazzling Aurora", base_loc(0))
    run(s, limit=30)
    aur = perm_of(s, "Dazzling Aurora", 0)[0]  # its row is reused later
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=20, stop=lambda st: int(st.n_chain) > 0)
    assert int(s.n_chain) >= 1, "its end-of-turn ability is on the Chain"
    combat.destroy(s, T, aur)                      # the hypothetical answer
    run(s, picking(base_loc(0), accept=True), limit=80)
    assert not perm_of(s, "Dazzling Aurora", 0), "the Gear is gone"
    assert perm_of(s, "Watchful Sentry", 0), \
        "359.1: the item still resolves and still plays the unit"


@case(6403, "Falling Star names both of its units up front")
def _():
    need("Falling Star")
    s = fresh(runes=32)
    give(s, 0, "Falling Star")
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(1), 9)
    b = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Falling Star", a, b)
    assert int(s.pend_slot) < 0, "both choices were made as it went on the Chain"
    run(s, limit=60)
    assert int(s.perms[a, P_DMG]) == 3 and int(s.perms[b, P_DMG]) == 3, \
        "3 apiece, with no window in between to re-aim"


@case(6396, "a unit with nothing to say opens no window")
def _():
    need("Shipyard Skulker")
    s = fresh(runes=32)
    give(s, 0, "Shipyard Skulker")
    give(s, 1, "Discipline")
    act(s, A.A_PLAY, hand_index(s, 0, "Shipyard Skulker"), 0)
    act(s, A.A_PLAY_AT, base_loc(0), 0)
    assert int(s.n_chain) == 0 and int(s.n_trig) == 0, \
        "337.2: a unit resolves immediately and triggers nothing here"
    assert A.acting_seat(s) == 0 and not A.legal_actions(s, T, V1, 1), \
        "335: so priority never leaves the turn player"


@case(6393, "'while I'm alone' notices the moment its company dies")
def _():
    need("Wielder of Water", "Hextech Ray")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 9)
    w1 = s.add_permanent(T.id_of("Wielder of Water"), 0, base_loc(0), ready=True)
    w2 = s.add_permanent(T.id_of("Wielder of Water"), 0, base_loc(0), ready=True)
    attack(s, 0, 1, w1, w2)
    printed = int(T.might[T.id_of("Wielder of Water")])
    assert combat.might(s, T, w1) == printed, "two of them: neither is alone"
    combat.destroy(s, T, w2)
    A._settle(s, T, V1)
    assert combat.might(s, T, w1) == printed + 2, \
        "a static is read live, so the survivor is attacking alone now"
