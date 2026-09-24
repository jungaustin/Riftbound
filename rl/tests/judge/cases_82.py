"""RiftJudge batch 82 -- unused questions from 5950-6323."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_READY


@case(6321, "a snapshotted reduction stays put while the Might around it moves")
def _():
    need("Sett, Brawler", "Smoke Screen")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen")
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    printed = int(T.might[T.id_of("Sett, Brawler")])
    assert combat.might(s, T, sett) == printed + 1, "4 printed and a Buff"
    cast(s, 0, "Smoke Screen", sett)
    drain(s)
    assert combat.might(s, T, sett) == 1, \
        "477.3.b: -4 against his 5 is snapshotted, floored at 1"
    act(s, A.A_ACTIVATE, None, 0)                  # spend the buff for +4
    run(s, picking(accept=True), limit=40)
    assert not s.has_flag(sett, F_BUFFED), "the Buff was the cost"
    assert combat.might(s, T, sett) == printed, \
        "4 + 4 - 4 (the snapshot did not grow when the Buff left)"


@case(6316, "[Temporary] does the killing, so no spell did")
def _():
    need("Fading Memories", "Immortal Phoenix")
    s = fresh(runes=32)
    give(s, 0, "Fading Memories")
    s.trash[0, 0] = T.id_of("Immortal Phoenix")
    s.n_trash[0] = 1
    s.bf_ctrl[0] = 0
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, bf_loc(0))
    cast(s, 0, "Fading Memories", ph)
    run(s, limit=40)
    assert alive(s, ph) and combat.perm_kw(s, T, ph, "Temporary"), \
        "the spell gave it [Temporary] and nothing else"
    _next_own_turn(s)
    run(s, picking(accept=True), limit=60)
    assert not perm_of(s, "Immortal Phoenix", 0), \
        "816.1.c expired it, and 428.1.a.1: that is no spell's kill, so no replay"


@case(6309, "you cannot conquer what you have already scored this turn")
def _():
    need("Retreat", "Ride The Wind")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Retreat", "Ride The Wind", "Discipline")
    s.bf_ctrl[0] = 0
    s.bf_scored[0, 0] = 1                          # held and scored this turn
    holder = body(s, 0, bf_loc(0), 3)
    pts = int(s.points[0])
    cast(s, 0, "Retreat", holder)
    run(s, limit=60)
    assert int(s.bf_ctrl[0]) < 0, \
        "190.4.c: no unit there, so the ground stops being theirs"
    again = body(s, 0, base_loc(0), 3, ready=True)
    cast(s, 0, "Ride The Wind", again, bf_loc(0))
    run(s, limit=60)
    fight(s, limit=80)
    assert int(s.bf_ctrl[0]) == 0, "they walk back in and take it again"
    assert int(s.points[0]) == pts, \
        "470: one Score per battlefield per turn, and they already had it"


@case(6308, "a trigger does not need [Reaction] to fire on their turn")
def _():
    need("Fiora - Grand Duelist", "Primal Strength")
    s = fresh(runes=32)
    s.legend[0], s.legend_ready[0] = T.id_of("Fiora - Grand Duelist"), 1
    give(s, 1, "Primal Strength")                  # THEIR spell, on THEIR turn
    s.runes_ready[1, :] = 24
    rune_deck(s)
    mine = body(s, 0, base_loc(0), 3)
    s.active = s.priority = 1
    left = int(s.rune_left[0])
    cast(s, 1, "Primal Strength", mine)            # +7: now [Mighty]
    run(s, picking(accept=True), limit=60,
        stop=lambda st: int(st.rune_left[0]) < left)
    assert combat.might(s, T, mine) >= 5, "it became Mighty"
    assert not int(s.legend_ready[0]), (
        "383: a triggered ability fires whenever its condition is met, whether "
        "or not it is its controller's turn")
    assert int(s.rune_left[0]) == left - 1, "and she channelled for it"


@case(6306, "a replaced death is no kill, so a kill trigger stays silent")
def _():
    need("Solari Shrine", "Zhonya's Hourglass", "Hextech Ray", "Rune Prison")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Rune Prison", "Hextech Ray")
    shrine = s.add_permanent(T.id_of("Solari Shrine"), 0, base_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 3)
    zh = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = zh                          # theirs, armed
    cast(s, 0, "Rune Prison", victim)              # stun it first
    drain(s)
    hand = int(s.n_hand[0])
    cast(s, 0, "Hextech Ray", victim)              # 3 into 3 Might: lethal
    run(s, picking(accept=True), limit=60)
    assert alive(s, victim) and int(s.perms[victim, P_LOC]) == base_loc(1), \
        "the Hourglass recalled it instead of letting it die"
    assert int(s.n_hand[0]) == hand - 1 and int(s.perms[shrine, P_READY]) == 1, \
        "'when you KILL a stunned enemy unit' never happened, so no draw"


@case(6305, "Defy answers any spell on the Chain, not only the newest")
def _():
    need("Defy", "Stupefy", "Hextech Ray")
    s = fresh(runes=32)
    give(s, 0, "Hextech Ray", "Stupefy")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Hextech Ray", foe)
    ray = top_uid(s)
    cast(s, 0, "Stupefy", foe)                     # a cheap one on top of it
    pass_priority_to(s, 1)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_TARGET}
    act(s, A.A_PLAY, hand_index(s, 1, "Defy"), 1)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_TARGET}
    assert ray in offered and len(offered) >= 2, \
        "359: both items are on the Chain, and either may be countered"


@case(6300, "one death spends one Hourglass")
def _():
    need("Zhonya's Hourglass", "Hextech Ray")
    s = fresh(runes=32)
    give(s, 0, "Hextech Ray")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 1)
    z1 = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    z2 = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z1
    cast(s, 0, "Hextech Ray", u)
    run(s, picking(accept=True), limit=60)
    assert alive(s, u), "saved"
    assert not alive(s, z1) and alive(s, z2), \
        "136.2.d: one replacement replaces the one death; the second is untouched"


@case(6297, "a spell may be played for the half of it that does something")
def _():
    need("Stupefy")
    s = fresh(runes=32)
    give(s, 0, "Stupefy")
    s.bf_ctrl[1] = 1
    tiny = body(s, 1, bf_loc(1), 1)
    hand = int(s.n_hand[0])
    assert "Stupefy" in hand_plays(s, 0), "1 Might is still a legal choice"
    cast(s, 0, "Stupefy", tiny)
    run(s, limit=40)
    assert combat.might(s, T, tiny) == 1, "the -1 has nowhere to go"
    assert int(s.n_hand[0]) == hand - 1 + 1, "but 'Draw 1' happens all the same"


@case(6287, "the spell that brought it back is itself a card played")
def _():
    need("Portal Rescue", "Vanguard Captain")
    s = fresh(runes=32)
    give(s, 0, "Portal Rescue")
    vc = s.add_permanent(T.id_of("Vanguard Captain"), 0, base_loc(0), ready=True)
    before = len(tokens(s, 0))
    cast(s, 0, "Portal Rescue", vc)
    run(s, picking(accept=True), limit=80)
    assert perm_of(s, "Vanguard Captain", 0), "she came straight back"
    assert len(tokens(s, 0)) == before + 2, \
        "812.1.b: Portal Rescue was finalized first, so her [Legion] is on"


@case(6281, "a cost paid with itself is a cost it cannot pay")
def _():
    need("Forge of the Future")
    s = fresh(runes=32)
    fof = s.add_permanent(T.id_of("Forge of the Future"), 0, base_loc(0), ready=True)
    s.trash[0, 0] = T.id_of("Cleave")
    s.n_trash[0] = 1
    act(s, A.A_ACTIVATE, None, 0)
    offered = targets_offered(s, 0)
    from rl.engine.effects import unpack_trash
    names = {T.names[unpack_trash(i)[1]] for i in offered}
    assert "Forge of the Future" not in names, \
        "403: 'Kill this' is the cost, so it is not in a trash to recycle from"
    assert "Cleave" in names and fof >= 0


@case(6280, "'its controller' survives a recall; 'the killed unit' does not")
def _():
    need("Hidden Blade", "Zhonya's Hourglass")
    s = fresh(runes=32)
    give(s, 0, "Hidden Blade")
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 3)
    zh = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = zh
    h1 = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", victim)
    run(s, picking(accept=True), limit=60)
    assert alive(s, victim) and int(s.perms[victim, P_LOC]) == base_loc(1), \
        "the Hourglass recalled it"
    assert int(s.n_hand[1]) == h1 + 2, \
        "359.3.e: the target was legal as it resolved, so its controller draws 2"


@case(6278, "'my original location' is unreadable once I am gone")
def _():
    need("Tideturner", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Tideturner")
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    monk = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Tideturner", bf_loc(0))
    tt = perm_of(s, "Tideturner", 0)[0]
    act(s, A.A_ACCEPT, None, 0)                    # "you MAY choose a unit..."
    choose(s, monk)                                # ...and that choice is now
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", tt)                         # 2 Might: within Gust's reach
    run(s, picking(accept=True), limit=80)
    assert not alive(s, tt), "she went back to hand"
    assert int(s.perms[monk, P_LOC]) == base_loc(0), \
        "359.3.f: no 'my location' to swap into, so the monk stays where it is"


@case(6274, "a snapshotted reduction and a later increase simply add up")
def _():
    need("Thousand-Tailed Watcher", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Thousand-Tailed Watcher")
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 4)
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s, limit=40)
    assert combat.might(s, T, u) == 1, "-3 from 4, floored at 1"
    s.active = s.priority = 1
    cast(s, 1, "Discipline", u)
    drain(s)
    assert combat.might(s, T, u) == 3, \
        "477.3.e: the increase goes on top of the floored value, so 1 + 2"


@case(6273, "exhausting a rune gear is not recycling a rune")
def _():
    need("Sigil of the Storm")
    s = fresh(runes=0)
    rune_deck(s, 4)
    s.runes_ready[0, 3] = 2                        # two runes of one domain
    s.bf_card[0] = T.id_of("Sigil of the Storm")
    s.bf_ctrl[0] = -1
    taker = body(s, 0, base_loc(0), 3, ready=True)
    before, left = runes(s, 0), int(s.rune_left[0])
    attack(s, 0, 0, taker)
    run(s, picking(accept=True), limit=80)
    assert int(s.bf_ctrl[0]) == 0, "conquered"
    assert runes(s, 0) == before - 1 and int(s.rune_left[0]) == left + 1, (
        "416.1.b: a rune left the board for the bottom of the rune deck -- a "
        "recycle, not an exhaust")


@case(6271, "no legal choice, no play")
def _():
    need("Stupefy")
    s = fresh(runes=32)
    give(s, 0, "Stupefy")
    assert not [i for i in range(s.n_perms) if alive(s, i)], "an empty board"
    assert "Stupefy" not in hand_plays(s, 0), \
        "355.8: a spell whose slot cannot be filled cannot be played at all"


@case(6270, "one ability dealing N is one source, so one Deflect")
def _():
    need("Teemo - Strategist", "Hexdrinker")
    s = fresh(runes=32)
    rune_deck(s)
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0))
    hx = s.add_permanent(T.id_of("Hexdrinker"), 1, base_loc(1))
    foe = body(s, 1, base_loc(1), 5, ready=True)
    s.attach(hx, foe) if hasattr(s, "attach") else None
    s.ply += 1
    before = runes(s, 0)
    attack(s, 1, 0, foe)                           # Teemo defends: his trigger
    run(s, picking(foe, accept=True), limit=80)
    spent = before - runes(s, 0)
    assert spent <= 1, \
        f"809.2: one ability, one surcharge, however much damage it deals ({spent})"


@case(6256, "a choose-trigger has already happened when the spell is countered")
def _():
    need("Irelia - Blade Dancer", "Discipline", "Wind Wall")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Discipline")
    give(s, 1, "Wind Wall")
    s.runes_ready[1, :] = 24
    s.legend[0], s.legend_ready[0] = T.id_of("Irelia - Blade Dancer"), 1
    mine = body(s, 0, base_loc(0), 3)
    s.perms[mine, P_READY] = 0                     # exhausted, so a ready shows
    act(s, A.A_PLAY, hand_index(s, 0, "Discipline"), 0)
    spell = top_uid(s)                             # before her trigger joins it
    choose(s, mine)
    # Her "you may exhaust me and pay {any rune}" is decided at finalization
    # (383.3.a), which is now -- before anybody answers the spell.
    run(s, picking(accept=True), limit=20,
        stop=lambda st: not int(st.legend_ready[0]))
    assert not int(s.legend_ready[0]), "she paid for it as the choice was made"
    pass_priority_to(s, 1)
    cast(s, 1, "Wind Wall", spell)                 # ...and the spell is countered
    run(s, picking(accept=True), limit=80)
    assert int(s.n_hand[0]) == 0, "the Discipline never resolved, so no draw"
    assert int(s.perms[mine, P_READY]) == 1, \
        "383.2: her trigger fired when the choice was made, and it still resolves"


@case(6254, "'when you play a [Mighty] unit' reads the unit as it is played")
def _():
    need("Sett, Brawler")
    s = fresh(runes=32)
    give(s, 0, "Sett, Brawler")
    rune_deck(s)
    s.legend[0], s.legend_ready[0] = T.id_of("Volibear - Relentless Storm"), 1
    cast(s, 0, "Sett, Brawler", base_loc(0))
    run(s, picking(accept=True), limit=60,
        stop=lambda st: bool(perm_of(st, "Sett, Brawler", 0))
        and st.has_flag(perm_of(st, "Sett, Brawler", 0)[0], F_BUFFED))
    sett = perm_of(s, "Sett, Brawler", 0)[0]
    assert s.has_flag(sett, F_BUFFED), "his own trigger buffed him"
    assert combat.might(s, T, sett) >= 5, "which makes him Mighty NOW"
    # His Power cost recycles a rune, so the rune deck is no measure here --
    # Volibear pays by EXHAUSTING, and he never did.
    assert int(s.legend_ready[0]) == 1, \
        "419.4.a/383.2: his condition was read as Sett completed his play, at 4"


@case(6246, "Combat lasts through the conquer, designations and all")
def _():
    need("Targon's Peak")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    s.bf_card[1] = T.id_of("Targon's Peak")
    s.bf_ctrl[1] = 1                               # theirs, and defended, so
    body(s, 1, bf_loc(1), 1)                       # this is a real Combat
    u = body(s, 0, base_loc(0), 9, ready=True)
    attack(s, 0, 1, u)
    run(s, limit=20,
        stop=lambda st: int(st.bf_ctrl[1]) == 0 and (int(st.n_chain)
                                                    or int(st.n_trig)))
    assert int(s.bf_ctrl[1]) == 0, "the ground is taken"
    assert int(s.desig[u]) and int(s.perms[u, P_LOC]) == bf_loc(1), (
        "323.2: it is still at the battlefield and still designated while the "
        "conquer trigger is on the Chain")


@case(6243, "a repeated ability runs twice, it does not run bigger")
def _():
    need("Called Shot")
    s = fresh(runes=32)
    give(s, 0, "Called Shot")
    hand = int(s.n_hand[0])
    deck = int(s.n_deck[0]) - int(s.deck_ptr[0])
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Called Shot"), 0)
    run(s, picking(0, accept=True), limit=80)
    assert int(s.n_hand[0]) == hand - 1 + 2, \
        "820.2: two separate looks, so two separate draws"
    assert int(s.n_deck[0]) - int(s.deck_ptr[0]) == deck - 2, \
        "and the other two went to the bottom rather than being drawn"
