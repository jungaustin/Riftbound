"""The effect DSL -- card text as data, not as code.

**What is and is not in here.** Keywords are *not* DSL. `[Action]`, `[Hidden]`,
`[Tank]`, `[Temporary]` are permissions and behaviours the engine keys off bits
in `CardTable.kw_mask`; that is PLAN.md §3's rule and it is what keeps this file
small. What needs a language is the part keyword flags cannot express: the
*effect body* and *which things it applies to*.

    Back Off:  [Hidden] [Action] Stun a unit.
               If you played this from your hand, draw 1.
               ^^^^^^^^^^^^^^^^^^^ flags     ^^^^^^^^^^^ this is the DSL's job

So a card is: a speed, a list of target slots, and a list of ops. Adding a card
is adding a data entry. Adding a *kind* of card is adding an op.

**Targets are slots, filled one at a time.** Rule 355 makes targeting a
finalization-time commitment, and 355.10 lists six things that look like targets
and are not. Getting this wrong is not a rules quibble -- "Kill a unit if it has
3 might or less" and "Kill a unit with 3 might or less" differ in whether an
opponent can respond by growing the unit (355.9.b). So a `TargetSpec` carries the
*restriction* separately from any *condition*: a restriction narrows what may be
chosen, a condition is checked at resolution and can fail.

**Locality is per slot, not per card** (811.1.d.2.a). A `[Hidden]` card played
from a Facedown Zone may only target things at *that* battlefield -- but a slot
marked free, and any effect that does not target, is unrestricted. That is why
locality lives on the slot rather than on the card: `Smoke and Mirrors` is
playable from hiding at battlefield A in response to an attack on battlefield B,
because its effect chooses units it does not target.
"""

from __future__ import annotations

from typing import NamedTuple

# The only import in this file, and it is one-way: `state` imports nothing from
# the engine, so naming its zone constants here cannot cycle. A card that says
# "recycle that spell after you play it" has to name a zone, and inventing a
# parallel enum for the DSL would mean two lists to keep in step.
from rl.engine.state import (COST_FREE, COST_NO_ENERGY,  # noqa: F401
                             COST_PRINTED, D_ANY, DEST_BANISH, DEST_HAND,
                             DEST_RECYCLE, DEST_TOP, DEST_TRASH, MAX_DECK,
                             MAX_LOOK,
                             MAX_TARGETS, N_SEATS, P_CARD,
                             RK_GEAR, RK_SHOWDOWN, RK_SPELL, RK_UNIT)

# --- speeds. When may this card be played? Wire format: append only. -------
SPEED_MAIN, SPEED_ACTION, SPEED_REACTION = range(3)
SPEED_NAMES = ("main", "action", "reaction")

# --- target slots ---------------------------------------------------------
TK_UNIT, TK_BATTLEFIELD, TK_SPELL, TK_LOCATION, TK_TRASH_CARD, TK_MODE = range(6)

# Per-player sequential choices opened by OP_EACH_KILLS_OWN:
#   CULL_KILL_OWN    "each player kills one of their units" (Cull the Weak)
#   CULL_RETURN_ANY  "each player MAY return a unit to its owner's hand"
#                    (Whirlwind) -- any unit, and declining is allowed
#   CULL_KEEP_OWN    "each player chooses a unit they control. Kill the rest."
#                    (Cataclysmic Duel)
CULL_KILL_OWN, CULL_RETURN_ANY, CULL_KEEP_OWN, CULL_MOVE_OWN_TO = range(4)
KD_NONE, KD_KILLED_COST, KD_POWER_EACH = range(3)
#   CULL_MOVE_OWN_TO "they move a unit they control to the same battlefield"
#                    (Call to Battle) -- the destination is `target_b`.
# TK_MODE -- "Choose one --" (Flurry of Feathers, Minah Swiftfoot). The choice
# of mode is made as slot 0, before any other target, and its value is the mode
# index. Everything after it comes from the chosen mode: `compose_mode` builds
# that spec with the mode's own slots renumbered from 1, so the announce ->
# targets -> finalize -> resolve machinery runs on it unchanged.

# The stored value of a target slot means whatever its KIND says it means:
# TK_UNIT a permanent row, TK_SPELL a Chain Item uid (C_UID), TK_LOCATION a
# location int, TK_TRASH_CARD an (owner, card) pair packed by `pack_trash`.
# Nothing has to disambiguate them at runtime because the slot's kind is always
# known from the spec.
#
# **TK_TRASH_CARD stores the card, not the trash index, and that is the rules
# answer rather than a convenience.** 108.2.c: "Cards in each player's Trash are
# unordered. Their sequence does not matter." Two copies of one card in an
# unordered zone are indistinguishable, so there is nothing for a per-copy
# identity to mean -- and an index would be actively wrong, because the window
# between finalization and resolution (359.3.e) is exactly when another card
# dies into the trash and shifts everything after it.
#
# **It stores WHICH TRASH alongside the card, because a card id alone is not a
# choice.** Most trash cards say "your trash" and narrow to one pile, but the
# pool also prints "cards from trashes" (Forge of the Future, Shadows of the
# Past) and "cards from opponents' trashes" (Disposal Order). When both piles
# are in scope and each holds a Sprite Call, "Sprite Call" names two different
# decisions -- and they are not interchangeable the way two copies in ONE pile
# are, because 416.1.c recycles each card to its OWNER's deck. Packing the
# owner in is what lets the destination be owner-relative without a second
# lookup that could disagree.

W_ANY, W_FRIENDLY, W_ENEMY = range(3)      # relative to the caster
LOOK_REVEAL_NONE, LOOK_REVEAL_ALL, LOOK_REVEAL_PICK = range(3)
WHO_NAMES = ("any", "friendly", "enemy")


def pack_trash(owner: int, card: int) -> int:
    """Pack a trash choice into the single int a target slot stores.

    Card-major so that sorting packed values groups the copies of one card
    together, which keeps the option list stable and readable.
    """
    return card * N_SEATS + owner


def unpack_trash(value: int) -> tuple[int, int]:
    """Inverse of `pack_trash`. Returns `(owner, card)`."""
    card, owner = divmod(value, N_SEATS)
    return owner, card


# Locality of a slot when the card is played from a Facedown Zone (811.1.d.2.a).
LOC_FREE, LOC_BOUND = range(2)

# Relations between slots. `Facebreaker` needs "at the same battlefield";
# `Smoke and Mirrors` needs "at a different location".
REL_NONE, REL_SAME_BF, REL_DIFFERENT_LOC = range(3)

# --- ops ------------------------------------------------------------------
(OP_STUN, OP_DRAW, OP_SWAP_LOC, OP_MODIFY_MIGHT, OP_COUNTER,
 OP_NO_SPELLS, OP_CREATE_TOKEN, OP_MOVE_TO, OP_RETURN_TO_HAND,
 OP_DAMAGE, OP_KILL, OP_DRAW_CONTROLLER, OP_READY,
 OP_MODIFY_MIGHT_ALL, OP_DAMAGE_ALL,
 OP_DISCARD, OP_KILL_ALL, OP_EXHAUST_ALL, OP_HEAL_AT,
 OP_ADD_ENERGY, OP_ADD_POWER, OP_BUFF, OP_BUFF_ALL_AT,
 OP_BLINK, OP_TRASH_TO_HAND, OP_PLAY_FROM_TRASH,
 OP_PLAY_UNIT_FROM_TRASH, OP_RECYCLE_FROM_TRASH,
 OP_GAIN_XP, OP_GRANT_KEYWORD, OP_LOOK_TOP, OP_EMPOWER,
 OP_CHANNEL, OP_DEATH_GUARD, OP_REVEAL_HAND,
 OP_SCORE, OP_EACH_KILLS_OWN, OP_NO_MOVE,
 OP_ANY_DAMAGE_KILLS, OP_SWAP_MIGHT,
 OP_READY_RUNES, OP_DISCARD_CHOOSE,
 OP_RECYCLE_SELF, OP_SEE_HAND, OP_SEE_FACEDOWN,
 OP_READY_LEGEND, OP_COUNTER_UNLESS_PAYS,
 OP_ARM_DELAYED, OP_BURN, OP_DISCOUNT_NEXT,
 OP_NO_CARDS, OP_ATTACH, OP_DIG_TRASH,
 OP_DISEMPOWER, OP_BANISH, OP_FIGHT,
 OP_MIGHT_UP_TO, OP_READY_ALL, OP_RETURN_ALL,
 OP_UNITS_ENTER_READY, OP_UNCHOOSABLE_TURN, OP_GRANT_KEYWORD_ALL,
 OP_PREVENT_EFFECT_DAMAGE, OP_SPEND_BUFF, OP_DISCOUNT_NEXT_SPELL,
 OP_MOVE_ALL_TO_BASE, OP_WEAPONMASTER, OP_DEATH_SHIELD, OP_GUILLOTINE,
 OP_MARK, OP_BUFF_BONUS_TURN, OP_BASE_MIGHT, OP_TAKE_CONTROL,
 OP_REVEAL_TOP, OP_ASK, OP_TO_DECK, OP_ADD_ANY_NEXT_MAIN,
 OP_DAMAGE_SHIELD, OP_DOUBLE_DAMAGE, OP_BANISH_ON_DEATH, OP_NEXT_UNIT_READY,
 OP_BANISH_FROM_TRASH, OP_EXTRA_TURN, OP_GRANT_MY_KEYWORDS,
 OP_TOGGLE_ATTACH, OP_DETACH_THIS, OP_NEXT_SPELL_BONUS,
 OP_NEXT_SPELL_REPEAT, OP_PLAY_FROM_HAND, OP_RETURN_FACEDOWN,
 OP_MIGHT_THIS_COMBAT, OP_EXHAUST_LEGEND, OP_WIN, OP_REVEAL_RUNE,
 OP_REVEAL_PLAY, OP_QUEUE_FOLLOWUP, OP_REVEAL_COUNT_DAMAGE,
 OP_PAY_POWER, OP_RECYCLE_TRASH_ALL, OP_SPLIT_DAMAGE, OP_DETACH_ONE,
 OP_ADD_SPELL_ENERGY, OP_PAY_ANY_AMOUNT, OP_FREE_GEAR, OP_ARMORY,
 OP_GRANT_FLOW, OP_SARC_BANISH, OP_SARC_PLAY, OP_STEAL_SPELL,
 OP_GAIN_TAG, OP_NAME, OP_COPY_PREP, OP_BECOME_COPY,
 OP_GRANT_ABILITY, OP_REPLAY_CARD, OP_LINK_CONTROL, OP_ZERO_BANISH,
 OP_ZERO_PLAY, OP_PROMISING_FUTURE, OP_DIVINE_JUDGMENT,
 OP_ENDLESS_RICHES, OP_REPLACE_BF, OP_RESTORE_BF,
 OP_BANISH_SPELL_PILE, OP_RECYCLE_RUNE, OP_ACTIVATE_CONQUERS,
 OP_UNIT_TAX, OP_FREE_HIDE) = range(128)
# OP_ACTIVATE_CONQUERS -- "activate the conquer effects of units here"
# (Reckoner's Arena): queue the TR_CONQUER abilities of the units standing at
# the captured location, as if they had just taken the ground.
# OP_UNIT_TAX -- "your non-token units cost {1 energy} more to play this turn"
# (Vaults of Helia): a per-seat turn stamp `cost.effective_energy` reads.
# OP_FREE_HIDE -- "you can hide cards ignoring costs this turn" (Guerilla
# Warfare): the same idiom for the Hide action's {any rune}, a per-seat turn
# stamp that `chain.hideable` and `actions._hide_at` read instead of 811.1.b's
# cost.
# OP_RECYCLE_RUNE -- "you must recycle one of your runes" (Sigil of the
# Storm). 416.1.b sends it to the bottom of the Rune Deck; the card says "this
# doesn't choose anything", so the domain is picked for the player -- the one
# they hold most of, which is the choice a player makes anyway.
# OP_BANISH_SPELL_PILE -- Jhin - Virtuoso: banish the spell that triggered
# this (it never resolves) and put it on the legend's pile. At four, the four
# go to their owners' trashes, the player channels 4 runes and draws 1.
# OP_REPLACE_BF -- swap the battlefield at the captured location for a token
# battlefield named by `tag` (Ivern - Green Father's Brush). The card it
# replaced is remembered in `state.bf_replaced` so the token's own text can put
# it back; OP_RESTORE_BF is that other half.
# OP_ENDLESS_RICHES -- "banish your hand and trash, then [Burn 7]" and switch
# on the card's three standing rules (`state.riches_on`).
# OP_DIVINE_JUDGMENT -- "Each player chooses 2 units, 2 gear, 2 runes, and 2
# cards in their hands. Recycle the rest." A walk over seats and categories
# (`state.dj_*`); a category with 2 or fewer candidates keeps them all.
# OP_PROMISING_FUTURE -- "Each player looks at the top 5 cards of their Main
# Deck, banishes one of them, then recycles the rest. Starting with the next
# player, each player plays those cards, ignoring Energy costs." A walk:
# caster's look, opponent's look, opponent's play, caster's play
# (`state.pf_*`, through the look and reveal-play decisions).
# OP_ZERO_BANISH -- "[Deathknell] -- Banish me" from The Zero Drive's band:
# the dead unit goes from its owner's trash to Banishment, remembered as
# banished WITH the gear (`state.zero_cards`); OP_ZERO_PLAY -- "play all units
# banished with this, ignoring their costs", then banish the gear.
# OP_LINK_CONTROL -- "you control it until I leave the board": the permanent
# in `target` returns to its owner when the source leaves (Akshan).
# OP_REPLAY_CARD -- the controller of `target` pays [A] and plays the
# resolving card again from its trash, free (Dancing Grenade).
# OP_GRANT_ABILITY -- "this turn, give it '<ability>'" (Dominus): the unit in
# `target` has the resolving card's GRANTED_ABILITIES until end of turn.
# OP_COPY_PREP -- remember the card of `target` (a unit slot or T_SELF) for a
# following "becomes a copy of it"; OP_BECOME_COPY -- the tokens the last
# OP_CREATE_TOKEN made become copies of it, gaining `keyword` if set
# (Mirror Image's [Temporary]). Token creation must be its card's last op,
# so the copy rides that op's `then_key`.
# OP_NAME -- "name a tag" (`n=0`, The List) / "name a spell" (`n=1`, Fallen
# Feline), stored on the source row (`state.named`). The names offered are
# the ones the namer can SEE: tags of enemy units on the board or in their
# trash, spells in the enemy trash -- naming something never seen would be a
# guess the engine cannot enumerate. `state.pend_name`.
NAME_TAG, NAME_SPELL, NAME_FRIENDLY_UNIT = range(3)
# OP_GAIN_TAG -- the unit in `target` gains the tag `tag` (Ivern - Friend to
# All); read everywhere a permanent's tags are through `combat.perm_tags`.
GRANTABLE_TAGS = ("Bird", "Cat", "Dog", "Poro", "Mech")
# OP_STEAL_SPELL -- "gain control of a spell. You may make new choices for
# it" (Mystic Reversal). With `power`: "you may pay {any rune}. If you do,
# gain control ...; otherwise, counter it" (Rebuttal). `state.steal_*`.
# OP_SARC_BANISH -- "banish all units from your trash", remembered as banished
# WITH this (`state.sarc_cards`); OP_SARC_PLAY -- "play a unit banished with
# this (you must pay its costs)" through the reveal-play decision (Cursed
# Sarcophagus).
# OP_GRANT_FLOW -- let the resolving player play a trash card for a cost:
# `target` (a TK_TRASH_CARD slot) or `self_card`; with `n_from_spell_energy`
# style "equal to its cost" as `grant_this_turn` + `ready` (banish after, as
# [Flow] does: Kennen), else a lasting `n` Energy / `power` Power permission
# that returns the card to the trash (Death from Below).
# OP_FREE_GEAR -- "you may play a gear with Energy cost no more than {7
# energy} from hand this turn, ignoring its Energy cost" (Jayce, Man of
# Progress): `state.free_gear_ply`, spent by the next such gear.
# OP_ARMORY -- "the next time it would die this turn, you may pay {Fury rune}
# to heal it, exhaust it, and recall it instead" (Unlicensed Armory):
# `state.armory_ply`, paid automatically when it can be.
# OP_PAY_ANY_AMOUNT -- "pay any amount of X to Y that much": the resolving
# player picks the amount (`state.pend_amount`, A_PICK k). `n` is the kind:
AMT_DAMAGE_ENEMIES_AT, AMT_ENERGY_TO_ANY, AMT_ANY_TO_ENERGY = range(3)
#   AMT_DAMAGE_ENEMIES_AT  pay [A], deal that much to all enemy units at the
#                          battlefield in `target` (Bullet Time)
#   AMT_ENERGY_TO_ANY      pay Energy, [Add] that much [A] (Ancient Henge)
#   AMT_ANY_TO_ENERGY      pay [A], [Add] that much Energy (Hextech Anomaly)
AMOUNT_CAP = 6
OP_NAMES = ("stun", "draw", "swap_loc", "modify_might", "counter",
            "no_spells", "create_token", "move_to", "return_to_hand",
            "damage", "kill", "draw_controller", "ready", "modify_might_all",
            "damage_all", "discard", "kill_all", "exhaust_all", "heal_at",
            "add_energy", "add_power", "buff", "buff_all_at", "blink",
            "trash_to_hand", "play_from_trash",
            "play_unit_from_trash", "recycle_from_trash", "gain_xp",
            "grant_keyword", "look_top", "empower", "channel",
            "death_guard", "reveal_hand", "score", "each_kills_own",
            "no_move", "any_damage_kills", "swap_might",
            "ready_runes", "discard_choose", "recycle_self", "see_hand",
            "see_facedown", "ready_legend", "counter_unless_pays",
            "arm_delayed", "burn", "discount_next", "no_cards",
            "attach", "dig_trash", "disempower", "banish", "fight",
            "might_up_to", "ready_all", "return_all",
            "units_enter_ready", "unchoosable_turn", "grant_keyword_all",
            "prevent_effect_damage", "spend_buff", "discount_next_spell",
            "move_all_to_base", "weaponmaster", "death_shield", "guillotine",
            "mark", "buff_bonus_turn", "base_might", "take_control",
            "reveal_top", "ask", "to_deck", "add_any_next_main",
            "damage_shield", "double_damage", "banish_on_death",
            "next_unit_ready", "banish_from_trash", "extra_turn",
            "grant_my_keywords", "toggle_attach", "detach_this",
            "next_spell_bonus", "next_spell_repeat", "play_from_hand",
            "return_facedown", "might_this_combat", "exhaust_legend", "win",
            "reveal_rune", "reveal_play", "queue_followup",
            "reveal_count_damage", "pay_power", "recycle_trash_all",
            "split_damage", "detach_one", "add_spell_energy", "pay_any_amount",
            "free_gear", "armory", "grant_flow", "sarc_banish", "sarc_play",
            "steal_spell", "gain_tag", "name", "copy_prep", "become_copy",
            "grant_ability", "replay_card", "link_control", "zero_banish",
            "zero_play", "promising_future", "divine_judgment", "endless_riches")
# OP_ADD_SPELL_ENERGY -- "[Add] {N energy/any rune}. Spend it only on ..."
# (Lux, Crownguard; Diana - Scorn of the Moon; Ornn; Kai'Sa; Renekton). `n` is
# the Energy and `power` the wildcard Power; `level` is the state.RK_* kind
# that says what the resource may pay for, and `cost.spendable_restricted`
# turns that back into a yes/no for one payment.
# OP_SPLIT_DAMAGE -- "deal N damage split among any number of enemy units
# here / at battlefields": `n` (or `n_from_might`) points, handed out one at
# a time by the resolving player (`state.pend_split`), dealt together at the
# end. `at=T_HERE` scopes to the source's location, else `at_battlefields`.
# `xp_per_kill` -- "for each unit this kills, gain 1 XP" (Alpha Strike).
# OP_DETACH_ONE -- detach an Equipment from the unit in `target` (Strike Down;
# the first one attached).
# OP_RECYCLE_TRASH_ALL -- recycle every card in your trash (the short-trash
# branch of "recycle 3 from your trash", Dr. Mundo - Expert).
# OP_PAY_POWER -- pay `n` Power of `domain` inside a resolution ("you may pay
# {Order rune} to ready it"). OP_ASK with `power` asks only when it can be
# paid, and otherwise takes its no-branch.
# OP_REVEAL_COUNT_DAMAGE -- reveal the top `n`, deal 1 to `target` for each
# card with `keyword`, recycle them all (Teemo - Strategist).
# OP_REVEAL_PLAY -- "look at / reveal the top N ... you may banish one, then
# play it" (Reinforce, Wild Claw, Void Rush, Rek'Sai - Swarm Queen): a look
# whose pick (`pick_types`, `pick_optional`, `rest_dest`) is banished and then
# played through `state.rp_*`, with `cost` (COST_*) less `play_discount`
# Energy, `play_here` adding the source's location, `play_empower` empowering
# what lands. `until_type` reveals until the first `pick_types` card (Dazzling
# Aurora); `from_opponent` takes the opponent's top card (Blind Fury).
# OP_REVEAL_RUNE -- reveal the top rune of your rune deck, recycle it, and
# queue this source's TR_RUNE_<its domain> abilities.
# OP_MIGHT_THIS_COMBAT -- +Might that lasts while the unit is in the current
# combat (`n_from_might=T_SELF` doubles it: Fiora - Peerless).
# OP_EXHAUST_LEGEND / OP_READY_LEGEND with `who=W_ENEMY` -- the opponent's
# legend rather than your own (Royal Entourage).
# OP_WIN -- "you win the game" (Gutter Palace).
# DB_ENERGY_DAMAGE -- OP_DISCARD_CHOOSE branch: the discarded card's Energy
# cost as damage to the unit in the op's `target` (Get Excited!).
DB_ENERGY_DAMAGE = -3
# OP_RETURN_FACEDOWN -- the facedown card at the battlefield in `target`
# returns to its owner's hand (Pack of Wonders).
# OP_DISCARD_CHOOSE with `branch_key=DB_TO_DECK` -- not a discard: the chosen
# hand card goes on the top or bottom of your Main Deck (Altar of Memories),
# asked as a one-card look (pick = top, none = bottom).
DB_TO_DECK = -2
# OP_PLAY_FROM_HAND -- an effect plays a permanent out of the resolving
# player's hand (`state.pend_hand_play`). `pick_types` / `max_energy` via
# `level` (the Energy cap, -1 none) / `tag` ("Equipment") limit the card;
# `cost` is the COST_* mode with `n` Energy off; `target_b` is the destination
# (T_MY_BASE, T_HERE, or -2 "a battlefield you control"); `pick_optional` is
# "you may"; `attach_to_source` attaches a played Equipment to the source.
# OP_ASK -- another player answers yes/no and FOLLOWUPS[then_key] (yes) or
# FOLLOWUPS[ask_no_key] (no) runs for the caster (`state.pend_ask`). Asked:
# the controller of `target` ("its controller"), its OWNER with `ask_owner`,
# the resolving player with `who=W_FRIENDLY`, otherwise the opponent.
# OP_TO_DECK -- a permanent to its owner's Main Deck, top (`pick_dest`
# DEST_TOP) or bottom (DEST_RECYCLE); a token simply ceases to exist.
# OP_REVEAL_TOP -- "reveal the top card of your Main Deck. If it's a <type>,
# draw it. Otherwise, <rest_dest> it" (Pakaa Protector, Apprentice Smith). No
# choice, so no suspend: `pick_types` is the test and `rest_dest` the miss.
# OP_MOVE_ALL_TO_BASE -- a MOVE (449.1), not a recall: "move all enemy units at
# that battlefield with less Might than the chosen unit to their base" (Stare
# Down). A sweep, scoped by `at`/`who`/`less_might_than_slot`.

# What an op's "for each ..." clause counts, for `Op.n_from_count`. Distinct
# from the CNT_* used by a Static's scaling: these are per-OP, and they are
# defined up here because SPECS below references them.
(CT_MY_BATTLEFIELDS, CT_MY_MIGHTY_UNITS, CT_ENEMIES_AT_TARGET,
 CT_MY_OTHER_BATTLEFIELDS, CT_MY_EQUIPMENT, CT_MY_UNITS,
 CT_ANIMAL_TAGS, CT_SOURCE_EQUIPMENT) = range(8)
# CT_SOURCE_EQUIPMENT -- "for each Equipment attached to me" (Riven, Shattered).
# CT_ANIMAL_TAGS -- "for each of the following tags among your units -- Bird,
# Cat, Dog, and Poro" (Friendship): 0-4, how many of the four are present.
# CT_MY_UNITS -- "for each friendly unit" (Scrutinizing Sergeant), counted
# at resolution, so the unit whose trigger this is counts itself.

# CT_MY_EQUIPMENT counts Equipment you control, ATTACHED OR NOT. 718.5 is
# explicit that an Attached card "still has all properties of being a card on
# the board" and 718.5.a keeps its Types and Tags, so an equipped sword counts
# exactly as a loose one does. 718.5.e/f matter here too: control of an
# Attached card is independent of control of its Top-Most card, so this asks
# the Equipment's own controller and never the unit's.

# CT_MY_OTHER_BATTLEFIELDS is Seat of Power's "for each OTHER battlefield you
# control". Its own is excluded by LOCATION rather than by subtracting one: a
# battlefield ability fires while its own control is being established, and
# "count then subtract" would be off by one in whichever direction the write
# had not happened yet.

# --- pseudo target slots --------------------------------------------------
# A spell's ops address targets by slot index. A unit's ability also has to say
# "me" and "here", which are not choices and so are not slots. These negative
# indices mean exactly those, and `resolve._slot` is the one place that decodes
# them -- so every op that takes a target works with them for free.
T_SELF = -2      # the permanent the ability is printed on
T_HERE = -3      # that permanent's current location
T_CTX = -4       # the location captured when the trigger fired (359.3.f.3)
T_OWNER_BASE = -5  # the base of the unit in the op's FIRST slot ("to its base")
# "at YOUR base" -- the resolving player's own base. Distinct from T_HERE, which
# is wherever the source happens to stand: Gear is base-only under 149.2, but a
# Gear played from a Facedown Zone sits at a battlefield instead, and Forge of
# the Future still makes its token at the base either way.
T_MY_BASE = -6
# The permanent a trigger fired FOR, as opposed to the one it is printed on.
# Mask of Foresight watches from a base while another unit attacks: T_SELF is
# the gear, T_SUBJECT is the attacker, and "give IT +1 Might" means the latter.
T_SUBJECT = -7
# The location a Move ENDED at, captured when the trigger fired. `T_CTX` is the
# other end of the same Move -- where the unit came from -- and printed text
# picks between them by word: Lillia's "play a Sprite THERE" is the origin,
# Irresistible Faefolk's "move an enemy unit to THAT battlefield" is the
# destination. Neither is `T_HERE`, which re-reads the source's own row and so
# means "this battlefield" -- true only while the source is still standing on
# it. See `state.C_CTX2` for why all three exist.
T_CTX2 = -8
# The contested battlefield of the Combat now running (459). Not a choice and
# not anybody's "here": Cannon Barrage is played from a hand, by either player,
# and "all enemy units IN COMBAT" means the ones standing on the ground being
# fought over. Outside a Showdown it decodes to `LOC_NONE`, and a sweep scoped
# to a location that does not exist reaches nothing -- see `_sweep`.
T_COMBAT = -9
# The first token the last OP_CREATE_TOKEN of this game made ("...ready IT",
# Guards!). Read off `state.last_token`.
T_LAST_TOKEN = -10

# --- conditions, checked at resolution ------------------------------------
(COND_NONE, COND_FROM_HAND, COND_ANY_TARGET_TEMPORARY,
 COND_ONLY_UNIT_THERE, COND_CONTROL_N_GEAR, COND_DIED_ALONE,
 COND_LEGION, COND_LEVEL, COND_EMPOWERED,
 COND_PLAYED_TRIO,
 COND_FEW_RUNES,
 COND_NOT_DIED_ALONE, COND_CTX_BATTLEFIELD, COND_SELF_AT_BF,
 COND_N_OTHERS_HERE, COND_OTHERS_MIGHT,
 COND_READY_ENEMY_HERE, COND_CTX2_BATTLEFIELD,
 COND_FIRST_TURN, COND_DEFENDING_ALONE,
 COND_WAS_MIGHTY, COND_FEWER_RUNES_THAN_OPP,
 COND_PAID_ADDITIONAL, COND_TARGET_EMPOWERED,
 COND_OPP_NEAR_VICTORY, COND_IN_COMBAT,
 COND_EMPOWERED_N, COND_ATTACHED_THIS_TURN,
 COND_TARGET_MAX_MIGHT, COND_TARGET_OVER_MIGHT,
 COND_NOT_EMPOWERED, COND_AT_BF_N_OTHERS,
 COND_SLOT_FRIENDLY, COND_SLOT_ENEMY,
 COND_SRC_BUFFED, COND_RUNES_AT_LEAST, COND_ANOTHER_FRIENDLY_HERE,
 COND_FACEDOWN_AT_BF, COND_SRC_AT_BF, COND_TARGET_STUNNED,
 COND_TARGET_NOT_STUNNED, COND_SLOT_DIED, COND_CONTROL_TAG,
 COND_GAINED_XP_THIS_TURN, COND_OPP_CONTROLS_STUNNED,
 COND_OPP_ANOTHER_SPELL, COND_ENEMY_ALONE_WHERE_MOVED,
 COND_NOT_DAMAGED_THIS_TURN, COND_CONTROL_EMPOWERED,
 COND_ENEMY_DIED_THIS_TURN, COND_ATTACKING_WITH_ANOTHER, COND_COMBAT_ALONE,
 COND_NOT_AT_BF_N_OTHERS, COND_STUNNED_ENEMY_HERE,
 COND_DISCARDED_THIS_TURN, COND_CHOSE_ENEMY_THIS_TURN, COND_ALL_ANIMAL_TAGS,
 COND_TARGET_NOT_EMPOWERED, COND_BF_EXACTLY_TWO_UNITS,
 COND_BIG_SPELL_THIS_TURN, COND_BELOW_LEVEL, COND_NO_FACEDOWN,
 COND_TARGET_ATTACKING, COND_TARGET_NOT_ATTACKING, COND_MY_BEGINNING,
 COND_ENEMY_ALONE_HERE, COND_NOT_MY_BEGINNING, COND_NOT_LEGION,
 COND_RUNES_BELOW, COND_FRIENDLY_COUNT_AT_SLOT, COND_REVEAL_MISSED,
 COND_PLAYED_CARD_THIS_TURN, COND_NOT_PAID_ADDITIONAL,
 COND_NOT_CONQUERED_THIS_TURN, COND_SRC_MIGHTY, COND_POWER_SPENT_2,
 COND_EXCESS_AT_LEAST, COND_EXCESS_AFTER_ATTACK,
 COND_ONE_ON_ONE, COND_HAND_UNITS_AT_BF, COND_DISEMPOWERED,
 COND_PICKED_ANIMAL, COND_HELD_HERE, COND_KILLED_N,
 COND_TRASH_BELOW, COND_CONQUERED_UNCONTROLLED, COND_BURNED_UNIT,
 COND_KILLED_MIGHT_AT_MOST, COND_HAND_AT_MOST,
 COND_UNITS_AT_CTX, COND_PLAYED_EQUIPMENT, COND_CTX_BF_MINE,
 COND_CHOSE_ENEMY_TWICE, COND_MIGHTY_AT_CTX) = range(94)
# COND_MIGHTY_AT_CTX -- you have a [Mighty] unit (5+ Might) at the location the
# trigger captured (Sunken Temple's "when you conquer here with one or more
# [Mighty] units").
# COND_CHOSE_ENEMY_TWICE -- you have chosen enemy units and/or gear twice or
# more this turn with spells or unit abilities (Ezreal - Prodigal Explorer).
# COND_CTX_BF_MINE -- the captured location is a battlefield the ability's
# controller controls ("when an enemy unit attacks a battlefield YOU control",
# Ahri - Nine-Tailed Fox).
# COND_PLAYED_EQUIPMENT -- you have played an Equipment this turn (Azir).
# COND_UNITS_AT_CTX -- you have `level` or more units at the location the
# trigger captured (Garen - Might of Demacia's "if you have 4+ units at that
# battlefield"). Reads `ctx`, so it answers for the ground that was conquered
# and not for wherever the source happens to stand -- which for a legend is
# nowhere at all.
# COND_HAND_AT_MOST -- `level` or fewer cards in your hand (Jinx - Loose
# Cannon's refill, which is the whole reason her deck may empty itself).
# COND_KILLED_MIGHT_AT_MOST -- the unit an earlier OP_KILL of this resolution
# killed had `level` Might or less (Death from Below).
# COND_BURNED_UNIT -- the last card Burned (`state.last_burned`) is a unit
# (Forgotten Relic).
# COND_CONQUERED_UNCONTROLLED -- the battlefield at ctx had no controller
# before this conquest (Yone - Blademaster; `state.bf_prev_ctrl`).
# COND_HELD_HERE -- the source stands at a battlefield its controller Held this
# turn (at Main-Phase start nothing can have Conquered yet: Iascylla).
# COND_KILLED_N -- earlier ops of this resolution killed `level` permanents.
# COND_TRASH_BELOW -- fewer than `level` cards in your trash.
# COND_PICKED_ANIMAL -- the card just picked from a look is a Bird, Cat, Dog
# or Poro (`state.look_last_pick`).
# COND_DISEMPOWERED -- an earlier OP_DISEMPOWER of this resolution spent a
# status ("disempower something ... TO empower ...", Profiteer).
# COND_ONE_ON_ONE -- the source is in combat and it and one enemy are the only
# units there ("attack or defend one on one", Fiora - Peerless).
# COND_HAND_UNITS_AT_BF -- exactly `level` cards in hand AND exactly `level`
# units of yours at battlefields (Gutter Palace).
# COND_EXCESS_AT_LEAST -- `level`+ excess damage assigned this turn (Yeti
# Brawler); COND_EXCESS_AFTER_ATTACK -- the same, as the attacker ("When I
# conquer after an attack", Tryndamere, Sivir - Ambitious).
# COND_REVEAL_MISSED -- the "Otherwise" of an OP_REVEAL_TOP earlier in the same
# resolution (Pakaa Protector's +2 Might).
# COND_FRIENDLY_COUNT_AT_SLOT -- exactly `level` units of the resolving player
# at the location in `cond_slot` (Shadow Dash's "exactly two units there").
# COND_BELOW_LEVEL -- the "otherwise" of a [Level N] "instead" (Combat
# Experience): fewer than N XP. COND_NO_FACEDOWN -- the complement of
# COND_FACEDOWN_AT_BF. COND_MY_BEGINNING -- "if it's your Beginning Phase"
# (LeBlanc - Fragmented). COND_ENEMY_ALONE_HERE -- "if an enemy unit is alone
# here" (Kha'Zix - Mutating Horror), at the source's location.
# COND_BIG_SPELL_THIS_TURN -- "if you've spent {4 energy} or more to play a
# spell this turn" (Prepared Neophyte): one spell, 4+ Energy, stamped as it is
# paid for (`state.big_spell_ply`).

# COND_EMPOWERED_N is "while I'm [Empowered] N times", with N in `level` --
# the same field `COND_LEVEL` uses for XP, because both are "at least this
# many". Distinct from COND_EMPOWERED, which asks only whether the status is
# held at all.

# COND_TARGET_EMPOWERED is Guttural Roar's "if IT'S [Empowered]" -- the same
# 441.1.a status COND_EMPOWERED reads, asked of the op's TARGET instead of its
# source. A separate condition rather than a flag on the existing one because
# overloading COND_EMPOWERED to mean "the target, if there is one" would
# silently change every card already using it: Noxian Emissary's Deathknell
# names a destination in `target` and would start asking about a base.

# COND_PAID_ADDITIONAL is "when you play me, IF YOU PAID THE ADDITIONAL COST,
# ...". A snapshot on the permanent (`F_PAID_ADDITIONAL`), not a live question:
# the payment happens as the card is played and the trigger resolves a priority
# window later, by which time nothing else on the board records it. See
# `PLAY_COSTS` for the costs themselves.

# COND_WAS_MIGHTY is Unsung Hero's "[Deathknell] - If I was [Mighty], draw 2".
# Past tense, so it reads the `F_DIED_MIGHTY` snapshot taken as the unit died
# rather than its row now: by the time a Deathknell resolves the turn's Might
# modifiers may already have been swept, and 740.2's 5+ Might is exactly the
# kind of fact a buff supplies.
#
# COND_FEWER_RUNES_THAN_OPP is Forsaken Baccai's "if you control FEWER runes
# than an opponent". A comparison between two boards, which is what separates
# it from COND_FEW_RUNES's fixed threshold -- the card is a catch-up mechanic
# and turns itself off the moment the rune counts level.

# COND_FIRST_TURN is The Arena's Greatest: "at the start of EACH PLAYER'S FIRST
# Beginning Phase". `state.turn` counts ROUNDS rather than plies -- it advances
# after the second seat's turn -- so both players' first Beginning Phase falls
# on turn 1, and the condition is that plain.
#
# COND_DEFENDING_ALONE is Forbidding Waste's "while a unit here is defending
# alone". Two facts at once, and both are live: the unit must be on the
# DEFENDING side of a running combat (459 designation, not who moved), and
# 740.2.a's "alone" -- no other friendly unit at that location. A static rather
# than a trigger, so it switches off the instant a second unit arrives.

# COND_PLAYED_TRIO is Swain's "if you've played a non-token unit, a non-token
# gear, and a spell this turn" -- all three kinds, in one turn. Read off
# `state.played_types`, which is set at the moment each card is PLAYED (349)
# rather than when it resolves, so a countered spell still counts toward it.

# COND_NOT_DIED_ALONE is Loyal Poro's "If I DIDN'T die alone" -- the negation
# of the flag Lonely Poro reads, and a separate value rather than a `negate`
# field because there is exactly one card on each side and a flag that applies
# to every condition is a lot of surface for that.
#
# COND_CTX_BATTLEFIELD is Harpoon Squad's "when I move FROM a battlefield":
# TR_MOVE captures the location left behind (359.3.f.3), so the question is
# about `ctx`, not about where the unit is now.
#
# COND_SELF_AT_BF is Mischievous Marai's "when you play me TO a battlefield" --
# about the source's own location, which for a play trigger is where it landed.
#
# COND_CTX2_BATTLEFIELD is the same question asked of the OTHER end of a Move:
# Irresistible Faefolk's "when I move TO a battlefield" is about where she
# arrived, so a retreat to base must not fire it. `ctx2` rather than her row,
# because the trigger has to survive her being removed in response to it.

# COND_READY_ENEMY_HERE is Dune Drake's "if there is a READY enemy unit
# here" -- an exhausted enemy does not count, which is what makes the card
# reward attacking into a board that can still answer.

# COND_N_OTHERS_HERE is Shen's "if there is EXACTLY ONE other unit you
# control here" -- an exact count, not a threshold, so `level` is the
# number it must equal. A second friendly unit turns it off again.
#
# COND_OTHERS_MIGHT is Kinkou Initiate's "if your OTHER units have total
# Might 5 or more": the sum of every other friendly unit's EFFECTIVE
# Might (statics and buffs included), against `level` as the threshold.

# COND_FEW_RUNES is Eclipse Dragon's "if you control 4 or fewer runes" --
# a count of the rune BOARD (ready plus spent), not the rune deck, since
# that is what "control" means for a rune. The threshold rides on the Op as
# `level`, reusing the field COND_LEVEL already uses for a number.

# COND_EMPOWERED is 828.1.b.1's dependent keyword: "[Empowered] - [Text]" is
# short for "While I have the Empowered status, this card gains '[Text]'". So
# it gates a static or an op on the SOURCE's own flag, and is read live --
# unlike COND_LEGION's snapshot, the status can be gained mid-turn and the
# ability switches on the instant it is.

# COND_LEVEL is "[Level N] - while you have N+ XP, get the effect". The
# threshold rides on the Op or Static as `level`, so one condition covers all
# of [Level 3], [Level 6] and [Level 11]. Unlike [Legion] this is genuinely
# continuous -- XP does not reset, and a static gated on it switches on the
# instant the XP arrives -- so it is read LIVE in both places.

# COND_LEGION is 822's [Legion]: "get the effect if you've played another card
# this turn". On a STATIC it reads the live counter, because a cost is worked
# out as the card is played and the card itself has not been counted yet. On an
# OP it reads the F_LEGION snapshot taken when the source was played, because
# by resolution the source HAS been counted and a priority window has passed.
# Same words, two readings, and only one of them is right in each place.


class TargetSpec(NamedTuple):
    """One target slot. Restrictions here narrow what is *legal to choose*."""
    kind: int = TK_UNIT
    # Whose things this slot may name, relative to the caster. **W_ANY is not a
    # default to fall back on -- it is a printed word, or rather its absence.**
    # "Give an ENEMY unit -2 Might" and "Give a unit -2 Might" are different
    # cards, and the second one may point at your own. The same reading applies
    # to a TK_TRASH_CARD slot, where `who` selects the PILE: W_FRIENDLY is
    # "your trash", W_ENEMY is "an opponent's trash", and W_ANY is the
    # unqualified "trashes", which reaches both.
    who: int = W_ANY
    locality: int = LOC_BOUND
    rel: int = REL_NONE
    rel_to: int = -1          # index of the earlier slot `rel` refers to
    # "up to one OTHER unit" -- must differ from the unit already chosen in
    # slot N, with NO location clause. Distinct from `rel`, whose every
    # value ties the two slots' LOCATIONS together; REL_DIFFERENT_LOC in
    # particular means a different place, not a different unit, and using
    # it for "another" is a mistake this codebase has made before.
    distinct_from: int = -1
    max_might: int = -1       # 355.9.b "with N might or less"; -1 = no limit
    # "ready something else that's EXHAUSTED" (Miss Fortune - Captain). A
    # restriction on the target's state rather than on its identity, and it is
    # load-bearing: readying a ready permanent is a no-op, so without it the
    # "you may" would offer choices that do nothing and 355.8 would let the
    # ability fire on a board where every option was already ready.
    #
    # Re-checked at resolution like every other restriction (359.3.e), so
    # something readied during the response window drops out of range.
    must_be_exhausted: bool = False
    # "...spend a buff" off a chosen unit (Wildclaw Shaman): it must have one.
    must_be_buffed: bool = False
    # For a TK_TRASH_CARD slot: Energy cost LESS THAN the chooser's points
    # (Kai'Sa - Evolutionary).
    energy_below_points: bool = False
    # The slot's unit must be at one EXACT location, named relative to the
    # chooser: 0 your base, 1 the opponent's base, 2 / 3 battlefield 0 / 1.
    # "Choose up to one enemy unit at each location" (Elder Dragon).
    exact_loc: int = -1
    # The same unit may fill this slot even if an earlier slot chose it
    # (Icathian Rain's six separate "Deal 2 to a unit").
    allow_repeat: bool = False
    # "...with total Might N or less" across every unit slot of the card
    # (Decree of Discord 5, Tricksy Tentacles 8).
    max_total_might: int = -1
    # The unit must be a copy of this card NAME ("a Shadow Clone you control",
    # Zed, Without a Sound).
    card_name: str | None = None
    # The slot's permanent has the same controller as the unit in slot N ("a
    # unit and an Equipment with the same controller", Angle Shot).
    same_ctrl_as: int = -1
    # A TK_BATTLEFIELD controlled by an enemy, with enemy units there whose
    # total Might is LESS than the source's (Maduli the Gatekeeper).
    enemy_might_below_source: bool = False
    # "Disempower a unit that's [Empowered]" (Sanction).
    must_be_empowered: bool = False
    # "A unit AT A BATTLEFIELD or a gear" (Fading Memories): with `card_type`
    # naming both, only the UNIT half must be at a battlefield.
    unit_at_battlefield: bool = False
    # [Level N] on the SLOT: below N XP the slot has no options and is skipped;
    # at N+ it is an ordinary required slot (Skyward Strike's stun).
    level_gate: int = 0
    # A destination that must hold another unit controlled by the controller
    # of the unit in slot N (Temptation's "a location where there's a unit
    # with the same controller").
    dest_has_ally_of: int = -1
    # [Weaponmaster] (821.1.c): an Equipment you control whose Equip cost,
    # reduced by [A], you can pay right now. Unpayable ones are not offered.
    weaponmaster: bool = False
    # "a friendly [Mighty] unit" (Sacrifice) -- [Mighty] is not a kw_mask bit
    # (unlike [Tank]/[Deflect]/...): it is a dynamically-computed STATUS, "5+
    # effective Might", the same reading `combat.might(...) >= 5` already uses
    # at its two other call sites. -1 = no limit, mirroring `max_might`.
    min_might: int = -1
    # "an enemy unit with LESS Might than it" (Public Execution) -- the index
    # of an earlier slot to compare against, rather than a printed number.
    # Strictly less, and both sides read effective Might.
    less_might_than: int = -1
    at_battlefield: bool = False   # must be at a Battlefield, not a base
    # The mirror: "Deal 4 to a unit in a base", "Deal 3 to a unit at a base".
    # Unqualified, so it reaches EITHER base -- narrow it with `who` to get
    # "a friendly unit at your base". Both flags false means "anywhere", which
    # is what most cards print.
    at_base: bool = False
    # For TK_SPELL: may this slot also name an ABILITY on the Chain? Eleven of
    # the thirteen counter cards say "Counter a spell" and mean only a spell;
    # Not So Fast and Repulse say "spell or ability". Units never reach the
    # Chain at all (337.2), so they are never a question here.
    chain_abilities: bool = False
    # Not So Fast: "Counter an enemy spell or ability THAT CHOOSES a friendly
    # unit or gear." A restriction on what the countered item picked, not on
    # the item itself -- so it reads that Chain Item's own chosen targets.
    # Only permanent-kind slots count: a location or a Chain-uid target is not
    # "a friendly unit or gear", and reading either as a permanent row would
    # match whichever unit happened to sit in row 0-3.
    chooses_friendly_perm: bool = False
    # For TK_BATTLEFIELD: "a battlefield where you have units" (Moonfall). A
    # restriction on the battlefield itself, so it is re-checked at resolution
    # -- the units that qualified it can be answered in the response window.
    needs_own_units: bool = False
    # Cost restrictions, for TK_SPELL. Defy: "costs no more than {4 energy}
    # and no more than {any rune}" -- energy <= 4 AND power <= 1.
    max_energy: int = -1
    max_power: int = -1
    # "a unit that costs no more Energy and no more Power than the KILLED
    # unit" (Heedless Resurrection) -- unlike `max_energy`/`max_power`, the
    # bound is not a printed number baked in here at import time; it is read
    # from `C_COST_KILL`, the card THIS SAME PLAY killed as its own printed
    # additional cost (820). Threaded down as `cost_kill_card` rather than
    # read from state directly, because the OFFERING check
    # (`chain.playable_hand_indices`) has to ask it once per CANDIDATE kill
    # target before any of them has actually been chosen -- see
    # `_playable_with_cost_kill`.
    capped_by_cost_kill: bool = False
    # "another unit" on a unit's own ability: exclude the ability's source.
    # Distinct from `rel`, which relates a slot to an earlier SLOT.
    not_self: bool = False
    # "ANOTHER unit" where the other one is the trigger's SUBJECT, not its
    # source: Star Spring's "move another unit they control here" can't pick
    # the unit whose play triggered it (RiftJudge #12296).
    not_subject: bool = False
    # "an enemy unit here WITH LESS MIGHT THAN ME". `less_might_than` compares
    # against an earlier SLOT, and the source is not a slot -- it is not a
    # choice anyone made -- so the two cannot share a field. Strictly less, and
    # both sides read effective Might, exactly as the slot version does.
    less_might_than_source: bool = False
    # "a gear with Energy cost no more than MY Might" (Noxian Demolitionist) --
    # `max_energy` with the cap read off the source's EFFECTIVE Might.
    max_energy_source_might: bool = False
    # A TK_LOCATION slot that is the DESTINATION of moving the unit chosen in
    # slot N: the only base offered is that unit's controller's, and its
    # current location is not offered at all. "Move a unit" never sends it to
    # the other player's base, and a move to where it already stands is no
    # move.
    move_dest_of: int = -1
    # "an enemy unit HERE" -- at the SOURCE's location. `rel`/`rel_to` cannot
    # express this: they point at an earlier target slot, and "here" is not a
    # choice anyone made. Meaningless on a spell, which has no location.
    same_loc_as_source: bool = False
    # The mirror: "an enemy unit AT A DIFFERENT LOCATION" (Evelynn -
    # Entrancing), meaning different from the SOURCE's. Not expressible as
    # `rel`/`rel_to`, which relate a slot to an earlier SLOT -- the source is
    # not a slot, exactly as `same_loc_as_source`'s own comment notes.
    #
    # It is also the shape 811.1.d.2's Tideturner example calls out: a
    # restriction that can NEVER be satisfied at the bound battlefield, so
    # such a slot must be marked LOC_FREE or a card played from hiding could
    # never fill it.
    different_loc_from_source: bool = False
    # "an enemy CHAOS unit or gear" -- a restriction on the target's DOMAIN.
    # -1 is no restriction, which is what almost every card prints.
    domain: int = -1
    # "an ATTACKING unit" -- 459 designates every unit the Attacker
    # controls at the contested battlefield. Only meaningful during a
    # Showdown; outside one nothing is attacking and the slot is empty.
    attacking: bool = False
    # "a friendly unit IN A SHOWDOWN" (Akali - Rogue Assassin) -- at the
    # battlefield where the open Showdown is, whichever side it is on. The
    # difference from `attacking` is exactly that: this asks only where the
    # unit stands, that one also asks which seat applied Contested.
    in_showdown: bool = False
    # "your Chosen CHAMPION" (Hallowed Tomb) -- 103.2.b's supertype, which the
    # card table carries as its own column.
    champion_only: bool = False
    # "up to N" -- the slot may be left EMPTY. 355.14 lets a player choose
    # fewer targets than the maximum, so the card is still legal to play with
    # nothing to point at, and each unfilled slot simply does nothing. Without
    # this, "Deal 6 to each of up to two units" would be unplayable whenever
    # only one unit existed.
    optional: bool = False
    # For TK_TRASH_CARD: which cards in the trash the slot may name.
    # `card_type` is the printed type ("Unit", "Spell", "Gear"); a tuple means
    # "a unit OR gear", which Guardian of the Passage asks for. `tags` is a
    # tag whitelist -- Starhound's "a Bird, Cat, Dog, or Poro". Both empty means
    # any card, which is what Guerilla Warfare's keyword restriction needs once
    # it is expressed through `has_keyword` instead.
    card_type: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    # "a NON-Dragon unit" (Ocean Drake) -- a tag the choice must NOT carry, the
    # slot-side mirror of `Ability.subject_lacks_tag`.
    lacks_tag: str | None = None
    has_keyword: str | None = None
    # "a friendly unit WITHOUT [Temporary]" (Shadow's Call). Read through
    # `combat.perm_kw`, so a unit that was GIVEN the keyword is excluded too --
    # otherwise the card would happily double up on a unit already dying.
    lacks_keyword: str | None = None
    # The slot names a card that will be PLAYED, not merely moved, so it must
    # be a card the engine can actually play: it needs a DSL spec, and its
    # controller must be able to pay whatever this play still costs. Same
    # reasoning as [Deflect]'s surcharge -- affordability is part of target
    # LEGALITY, because offering a target that cannot be finalized announces a
    # card that then deadlocks (359.3.e.14.a).
    playable: bool = False
    # Which cost that play pays -- a COST_* from state.py. The pool prints
    # three: the printed cost, "ignoring its Energy cost. (You must still pay
    # its Power cost.)", and the flat "ignoring its cost". The reminder text on
    # the middle one exists because players get it wrong, and so would this.
    playable_cost: int = COST_PRINTED
    # A TK_LOCATION slot that names where a card will be PLAYED, so it must be
    # narrowed to 806.3's "your base or a Battlefield you control" rather than
    # offering every battlefield the way a movement destination does.
    play_destination: bool = False
    # "your TOKEN units" (Azir - Sovereign).
    token_only: bool = False
    # A TK_BATTLEFIELD holding a facedown card the chooser owns ("another
    # friendly ... facedown card", Pack of Wonders).
    own_facedown: bool = False
    # "exhaust a friendly unit" as a cost -- it must be ready to exhaust.
    must_be_ready: bool = False
    # "an EQUIPPED unit" -- at least one Equipment attached (Strike Down).
    equipped: bool = False
    # "a friendly unit that's in combat with an enemy Fury unit or that's being
    # chosen by an enemy Fury spell" (Decree of Focus).
    fury_threatened: bool = False
    # TK_SPELL: an enemy spell or ability that chooses the unit in slot N and
    # no other friendly unit (Repulse).
    chooses_only: int = -1
    # An Equipment attached to the unit chosen in slot N (Azir - Ascendant).
    attached_to_slot: int = -1
    # TK_BATTLEFIELD with no units at all ("an open battlefield").
    open_bf: bool = False
    # "a unit at a battlefield I moved to or from" -- the source's last Move
    # (`state.move_from` / `move_to`; Akali, Deadly Weapon).
    at_source_move_ends: bool = False
    # "a legend, unit, or gear" (Profiteer): the slot may also name a Champion
    # Legend, encoded as `state.legend_src(seat)`. You control your own legend
    # (RiftJudge #11765). Only OP_EMPOWER / OP_DISEMPOWER read such a slot.
    or_legend: bool = False
    # The unit carries the tag its source named (The List).
    named_tag_of_source: bool = False


class Op(NamedTuple):
    op: int
    target: int = -1          # index into the card's target slots, or -1
    target_b: int = -1        # second slot, for two-place ops like swap
    n: int = 0                # numeric parameter (cards drawn, Might delta)
    cond: int = COND_NONE
    # A card-printed Might floor, e.g. Stupefy's "to a minimum of 1 Might".
    # Stricter than the general floor of 0 in 143.2.b, and part of the effect
    # rather than a rule, which is why it lives on the Op.
    floor: int | None = None
    # The N in "[Level N]", when `cond` is COND_LEVEL.
    level: int = 0
    # Read the amount off a TARGET's current Might instead of `n`. Deathgrip
    # gives "+Might equal to its Might", where "its" is the unit being killed
    # -- so the number is whatever that unit is worth at resolution, statics
    # and buffs included, which is why it cannot be baked into `n`.
    n_from_might: int = -1
    # "draw 1 FOR EACH battlefield you control" / "for each of your Mighty
    # units" -- the amount is a board count rather than a printed number.
    # -1 is none; otherwise one of the CT_* kinds, and the amount is
    # `n * count` -- so `n` is the per-unit rate, not a flat number.
    n_from_count: int = -1
    # Destination = the LOCATION of the unit chosen in slot N. Zenith Blade
    # moves a friendly unit to "that enemy unit's battlefield", which is
    # neither `T_HERE` (the source's) nor a location slot the player picked.
    loc_of_target: int = -1
    # For OP_GRANT_KEYWORD: which keyword, and whether the grant expires. The
    # pool grants both ways -- Cleave's "[Assault 3] this turn" against Shadow's
    # Call's [Temporary], which lasts until the unit leaves. `n` carries the
    # value, so a bare keyword is n=1.
    keyword: str | None = None
    grant_this_turn: bool = True
    # For OP_CREATE_TOKEN: the token card's name, and whether the created
    # units enter ready. Units normally enter exhausted; "Play a READY
    # 3 Might Sprite" overrides that, which is most of the card's value.
    token: str | None = None
    ready: bool = False
    # For OP_MOVE_TO / OP_CREATE_TOKEN: also ready the unit afterwards.
    then_ready: bool = False
    # For OP_ADD_POWER: which domain's Power is added to the Rune Pool.
    domain: int = -1
    # "an ATTACKING unit" -- 459 designates every unit the Attacker
    # controls at the contested battlefield. Only meaningful during a
    # Showdown; outside one nothing is attacking and the slot is empty.
    attacking: bool = False
    # For OP_LOOK_TOP: `n` is how many cards to look at; these say where the
    # one the player picks goes and where everything else goes. Stacked Deck is
    # "Put 1 into your hand and recycle the rest" -- DEST_HAND and DEST_RECYCLE.
    # `pick_optional` is Lightning Rush's "you MAY choose a card from among
    # them", where declining is legal and all N take the rest-destination.
    pick_dest: int = DEST_HAND
    rest_dest: int = DEST_RECYCLE
    pick_optional: bool = False
    # 436.1.a -- "When more than one card is Predicted, the Predicting player
    # looks at that many cards and Recycles ANY NUMBER of them." A pick that
    # may repeat: each A_PICK sends one card to `pick_dest` and the look stays
    # open, and A_PICK_NONE ("done") sends the rest. Without it [Predict 2]
    # could recycle at most one of the two, which is a different card.
    pick_multi: bool = False
    # "EACH PLAYER discards their hand, then draws 4" (Invert Timelines). For
    # OP_DISCARD and OP_DRAW: run once per seat, turn player first, instead of
    # for the resolving player alone. Not `who=W_ANY`, which is the field's
    # default and already means "the resolving player" everywhere.
    each_player: bool = False
    # The slot a COND_SLOT_* condition inspects, when that is not the op's own
    # target. Blood Money kills slot 0 and then makes tokens at your base --
    # "if it was an ENEMY unit" is a question about slot 0, asked by an op
    # whose own target is a location.
    cond_slot: int = -1
    # For OP_COUNTER: "return it to its owner's hand INSTEAD OF putting it in
    # their trash" (Abandon). Its own field, not `pick_dest` -- that one
    # DEFAULTS to DEST_HAND, so reading it here would have sent every
    # countered spell in the game back to hand.
    counter_to_hand: bool = False
    # For COND_CONTROL_TAG: "if you control a PORO" (Poro Herder).
    cond_tag: str | None = None
    # Read the amount off the excess damage the resolving player assigned this
    # turn (Sivir - Ambitious: "deal that much").
    n_from_excess: bool = False
    # Read the amount off the ENERGY COST of the spell in a TK_SPELL slot:
    # "+Might equal to that spell's Energy cost" (Riposte).
    n_from_spell_energy: int = -1
    # Read the amount off a slot's [Assault] value: "deal damage equal to my
    # [Assault]" (Lucian - Gunslinger). Printed plus granted.
    n_from_assault: int = -1
    # For OP_LOOK_TOP: the pick must have at least this printed Energy cost --
    # "a spell with Energy cost {4 energy} or more" (Fate Weaver).
    pick_min_energy: int = 0
    # Read the amount off the DAMAGE marked on a slot's unit: "deal damage to a
    # unit equal to the damage marked on it" (Morgana, Vindictive).
    n_from_damage: int = -1
    # Sweep narrowing: only units with LESS effective Might than the unit in
    # this slot (Stare Down).
    less_might_than_slot: int = -1
    # "This deals 1 Bonus Damage for each card with this name in your trash"
    # (Consuming Curse): add that count to the amount.
    plus_same_name_trash: bool = False
    # Sweep narrowing: only units with damage marked (Warwick - Hunter's "kill
    # all DAMAGED enemy units here").
    damaged_only: bool = False
    # For OP_RETURN_ALL: only units with at most this EFFECTIVE Might, and
    # units only (no gear) when set. -1 is Downwell's "all units and gear".
    # Angler Beast: "return all units with 2 Might or less".
    sweep_max_might: int = -1
    # "You may reveal a GEAR from among them" (Ornn), "a unit from among them"
    # (Ivern, Rift Herald). Empty means any card, which is what Stacked Deck
    # prints. A restriction on the pick only -- the rest still go wherever the
    # rest-destination says, whatever their types.
    pick_types: tuple[str, ...] = ()
    # OP_LOOK_TOP: what is REVEALED, which is what "as I'm revealed" (Undertitan)
    # reads. LOOK_REVEAL_NONE for "look at" and [Predict]; LOOK_REVEAL_ALL for
    # "reveal the top card" (Ravenbloom Conservatory); LOOK_REVEAL_PICK for
    # "you may reveal a unit from among them" (Rift Herald) -- only the chosen
    # card. Looking is not revealing (RiftJudge #12051).
    reveal: int = 0
    # For OP_CHANNEL: the runes arrive exhausted unless `ready`, and
    # `draw_if_short` is the "If you can't / if you couldn't channel N this
    # way, draw 1" rider several of these cards print -- a consolation for an
    # empty Rune Deck, checked against how many actually came off it.
    ready_runes: bool = False
    # For OP_READY_RUNES: defer to the end of the turn instead of readying now
    # (Targon's Peak). "At the end of THIS turn" is the current turn whoever's
    # it is, and `ending` runs once per turn, so a promise made on the
    # opponent's turn is kept at the end of THAT turn.
    at_end_of_turn: bool = False
    draw_if_short: int = 0
    # For OP_PLAY_FROM_HAND: attach the played Equipment to the source.
    attach_to_source: bool = False
    # For OP_ASK: the follow-up on DECLINE, and whether the target's OWNER
    # (rather than its controller) is the one asked.
    ask_no_key: int = -1
    ask_owner: bool = False
    # For OP_PLAY_UNIT_FROM_TRASH: the card is the resolving card itself, found
    # in its controller's trash -- "you may pay {Fury rune} to play ME" (Flame
    # Chompers).
    self_card: bool = False
    # For OP_EMPOWER / OP_DISEMPOWER: "...at end of turn" undoes it (Sanction,
    # Tornado Warrior). For OP_TAKE_CONTROL: lose control at end of turn
    # (Hostile Takeover).
    eot_revert: bool = False
    # For OP_EACH_KILLS_OWN: which per-player instruction it is (CULL_*), and
    # whether the walk starts with the NEXT player rather than the resolving
    # one. `who=W_ENEMY` leaves the resolving player out ("each OTHER player").
    cull_mode: int = 0
    start_next: bool = False
    # For OP_KILL_ALL: which printed type the sweep reaches.
    # Empty means Unit, which is what every board wipe meant before
    # "Kill all gear" needed the distinction.
    card_type: str = ""
    # For OP_DISCARD_CHOOSE: which entry of `DISCARD_BRANCHES` to run
    # once the discarded card's type is known.
    branch_key: int = -1
    # Chaining: after THIS op's deferred decision resolves, run the ops in
    # `FOLLOWUPS[then_key]`. Those may suspend again, which is how a card
    # gets two decisions in sequence. -1 for the common case of none.
    then_key: int = -1
    # --- scoping for the board-wide ops -----------------------------------
    # These three turn "all units at battlefields" into "each other enemy unit
    # THERE", which is what most of the mass effects in the pool actually say.
    # 355.10 still applies: none of this makes them targets, because there is
    # no count and no choice -- the SLOT that names the location is the target,
    # and the sweep that follows is not.
    at: int = -1              # slot (or T_*) giving the location to sweep
    who: int = W_ANY          # whose units the sweep reaches
    except_target: int = -1   # slot whose unit is spared -- "each OTHER unit"
    # "Give your MECHS +1 Might" (Danger Zone) -- a tag the swept units must
    # carry. Empty reaches every unit, which is what the mass effects that name
    # no kin print. A restriction and not a target (355.10): there is still no
    # count and no choice, so the opponent cannot answer by making one illegal.
    tag: str = ""
    # "all units AT BATTLEFIELDS" -- printed on the mass-damage cards and NOT
    # on the mass Might reduction, which reaches units at bases too. A property
    # of the card, so it lives here rather than being a default.
    at_battlefields: bool = False
    # For OP_PLAY_FROM_TRASH: where the replayed card goes afterwards. Fizz
    # says "Recycle that spell after you play it"; Kai'Sa says nothing, so hers
    # trashes normally. A DEST_* from state.py.
    dest: int = 0
    # For the play-from-trash ops: which cost the play pays. A COST_* from
    # state.py, and it must agree with the slot's `playable_cost` -- the slot
    # uses it to decide legality, the op uses it to charge.
    cost: int = 0
    # For OP_BLINK: send it back to its owner's base instead of where it stood.
    to_base: bool = False
    # For OP_REVEAL_HAND: XP the CHOICE costs (383.3.b), 0 for a free pick.
    # A field of its own rather than a second meaning for `cost`, which is a
    # COST_* enum saying which cost a replayed card pays -- two different
    # questions that happen to fit in one int, which is exactly how a field
    # ends up answering the wrong one.
    cost_xp: int = 0
    # For OP_CREATE_TOKEN: how many of the tokens just made enter READY, when
    # that is fewer than all of them. Arise! plays one Sand Soldier per
    # Equipment "then readies two of them" -- and WHICH two is not a decision,
    # because the tokens are identical (they are made by the same op, from the
    # same card, at the same location). Offering the choice would put a solved
    # problem in the action space, the same reason discount ordering is not
    # there. `ready` stays the all-or-nothing flag.
    ready_n: int = 0
    # The POWER half of a two-component amount, where `n` is the Energy half.
    # "Costs {2 energy}{any rune}{any rune} less" is a reduction of BOTH
    # components (356.4.d applies discounts per component), so one number
    # cannot express it.
    power: int = 0
    # "Ready up to 4 units, gear, and/or runes" (Acceleration Gate): `n` less
    # the permanent slots that are still filled at resolution.
    n_less_filled: bool = False
    # OP_TAKE_CONTROL: "...exhaust it" (Conscription).
    then_exhaust: bool = False
    # OP_REVEAL_PLAY -- see the op.
    play_discount: int = 0
    play_here: bool = False
    play_empower: bool = False
    until_type: bool = False
    from_opponent: bool = False
    # OP_REVEAL_PLAY's pick has printed Might <= the unit an earlier OP_KILL of
    # this resolution killed, plus this (Baited Hook: 1). -1 is no limit.
    pick_max_might_killed: int = -1
    # OP_REVEAL_HAND: the pick is mandatory, banished, and returns to its
    # owner's hand when they next hold (Ashe - Focused).
    hold_return: bool = False
    # OP_REVEAL_HAND: the revealer PLAYS the picked unit, free, to the location
    # in `target_b` and it is stunned (Bone Skewer).
    reveal_play_there: bool = False
    xp_per_kill: bool = False
    # OP_MODIFY_MIGHT by the printed Might of `state.last_burned`.
    n_from_last_burned: bool = False
    # +1 damage for each time this card has dealt damage this turn (Dancing
    # Grenade; `state.grenade_hits`).
    grenade_bonus: bool = False
    # OP_PLAY_FROM_HAND: the card must carry `keyword`, and may be a spell,
    # cast free onto the Chain (Ava Achiever's "a card with [Hidden]").
    play_spells: bool = False


class CardSpec(NamedTuple):
    speed: int
    targets: tuple[TargetSpec, ...] = ()
    ops: tuple[Op, ...] = ()
    # "Ignore [Deflect] while paying this spell's cost" (Decree of Insight).
    ignore_deflect: bool = False
    # "Banish this." -- the spell goes to Banishment instead of the trash
    # when it resolves (Arcane Shift, Time Warp).
    banish_self: bool = False
    # "Choose one --": the modes, each a CardSpec carrying targets and ops. A
    # modal spec's own `targets` is the single TK_MODE slot and its `ops` are
    # empty; see TK_MODE and `compose_mode`.
    modes: tuple = ()
    # "As an additional cost to play this, kill a [...]" (820) -- a REQUIRED
    # cost that names a target, chosen through the same A_TARGET slot UI
    # `targets` uses but stored separately (`state.chain[item, C_COST_KILL]`),
    # never one of `targets` and never referenced by an Op. With no legal
    # target this card cannot be played at all (`chain.playable_hand_indices`
    # gates it the same way `can_be_cast` gates an unfillable ordinary slot).
    # Paid at finalization, same moment `cost_kill_self` pays for an ability.
    cost_kill: TargetSpec | None = None
    # "This can't be countered." (Decree of Rage) -- read by every counter's
    # target enumerator, so the spell is simply never a legal choice. Not a
    # protection on the targets it chooses; only on the spell itself.
    uncounterable: bool = False
    # "You MAY kill a friendly gear as an additional cost to play me" (Zaun
    # Punk): the unit play offers a decline, and paying sets F_PAID_ADDITIONAL.
    cost_kill_optional: bool = False
    # The cost RETURNS the chosen permanent to its owner's hand instead of
    # killing it (Legion Quartermaster).
    cost_return: bool = False
    # The chosen permanent is EXHAUSTED (Meditation) or its buff SPENT (Call
    # to Glory, Wallop) instead of killed.
    cost_exhaust_unit: bool = False
    cost_spend_buff: bool = False
    # A spell's optional additional costs with no choice in them: discard N
    # (Ruthless Strike), Power of its domain (Rampage). A spell with any
    # optional additional cost is paid through A_PLAY_REPEAT (C_REPEAT = 2),
    # and COND_PAID_ADDITIONAL reads `state.resolving_paid`.
    opt_cost_discard: int = 0
    opt_cost_power: int = 0
    # "If you do, ignore this spell's cost." (Call to Glory, Wallop)
    paid_ignores_cost: bool = False
    # Optional additional cost in XP (Conscription), and the target slots that
    # replace `targets` once it is paid ("...choose any enemy unit at a
    # battlefield instead"). `chain.item_spec` applies them.
    opt_cost_xp: int = 0
    paid_targets: tuple = ()
    # What an optional unit kill cost buys off the unit's own cost:
    # KD_KILLED_COST "I cost {1 energy} less for each Energy it costs and
    # {Order rune} less for each Power it costs" (Atakhan); KD_POWER_EACH
    # "kill any number ... reduce my cost by {Order rune} for each" (Commander
    # Ledros), which keeps the kill decision open until declined.
    cost_kill_discount: int = 0
    # Extra (energy, power) to pay per mode, parallel to `modes` -- the [Repeat]
    # costs a combined mode stands for (Curtain Call).
    mode_costs: tuple = ()
    # Nonzero only on the spec `repeated_spec` builds: the number of target
    # slots ONE execution has. Slots from here on belong to the repeat.
    exec_len: int = 0

    @property
    def n_targets(self) -> int:
        return len(self.targets)


# TargetSpec fields that hold the index of another slot of the same spec.
_SLOT_REF_FIELDS = ("rel_to", "distinct_from", "same_ctrl_as", "dest_has_ally_of",
                    "less_might_than", "move_dest_of", "chooses_only",
                    "attached_to_slot")
_REPEATED: dict = {}


def repeated_spec(spec: "CardSpec") -> "CardSpec":
    """`spec` with a second set of target slots for its [Repeat] execution.

    820.2 -- the repeat's choices are made "at the usual time", as the spell is
    played, and 820.2.a lets them differ from the first execution's: Existential
    Dread paid twice stuns two different attackers (RiftJudge #12143), and
    Bellows Breath may pick the same unit again (#12522). So the item carries
    both sets, slots [0, n) for the first pass and [n, 2n) for the second, with
    every slot-to-slot reference in the copy shifted by n.
    """
    got = _REPEATED.get(id(spec))
    if got is not None and got[0] is spec:
        return got[1]
    n = len(spec.targets)
    second = tuple(t._replace(**{f: getattr(t, f) + n for f in _SLOT_REF_FIELDS
                                 if getattr(t, f) >= 0})
                   for t in spec.targets)
    out = spec._replace(targets=spec.targets + second, exec_len=n)
    _REPEATED[id(spec)] = (spec, out)
    return out


def single_execution(spec: "CardSpec") -> "CardSpec":
    """The one-execution spec a `repeated_spec` was built from."""
    if not getattr(spec, "exec_len", 0):
        return spec
    return spec._replace(targets=spec.targets[:spec.exec_len], exec_len=0)


# --- triggered abilities (382-383) ----------------------------------------
# Trigger conditions. Wire format: append only.
#
# TR_DEATH is [Deathknell] (808.1.c, "When I die, [Effect]"). TR_MOVE fires on
# the source leaving a location, and its captured `ctx` is the location it left
# -- Lillia's "play a Sprite unit token THERE" means where she came from, and
# 359.3.f.3 fixes that at trigger time, not at resolution.
(TR_PLAY_ME, TR_DEATH, TR_MOVE, TR_HOLD, TR_CONQUER,
 TR_PLAY_SPELL, TR_ACTIVATED, TR_ATTACK_OR_DEFEND,
 TR_PLAY_UNIT, TR_OTHER_DIES, TR_GEAR_ABILITY,
 TR_DISCARD, TR_BEGINNING, TR_END_OF_TURN,
 TR_OPPONENT_SCORES, TR_READIED, TR_CHOSEN,
 TR_PLAY_FROM_HIDDEN, TR_HIDE, TR_LEAVES_BOARD,
 TR_COMBAT_ENDS, TR_REVEALED_FROM_DECK, TR_NTH_CARD,
 TR_BECOME_EMPOWERED, TR_WIN_COMBAT, TR_STUN, TR_BUFFED,
 TR_MOVED_ENEMY, TR_SPEND_BUFF, TR_EQUIPPED, TR_MARKED_DIES,
 TR_MARKED_WINS, TR_DISCARD_ME, TR_CONQUER_FROM_TRASH,
 TR_FIRST_BEGINNING_DEATH, TR_UNIT_MOVES,
 TR_RUNE_BODY, TR_RUNE_CALM, TR_RUNE_CHAOS, TR_RUNE_FURY, TR_RUNE_MIND,
 TR_RUNE_ORDER, TR_FOLLOWUP, TR_BECOME_MIGHTY, TR_YOU_KILL,
 TR_KILL_FROM_TRASH, TR_MAIN_START, TR_SECOND_DRAW,
 TR_MARKED_CONQUERS, TR_RECYCLED, TR_TEMPORARY,
 TR_RUNE_RECYCLED, TR_BANISHED, TR_PLAY_NONHAND,
 TR_SHOWDOWN_HERE, TR_ENEMY_HOLDS_HERE) = range(56)
# TR_ENEMY_HOLDS_HERE -- [Deploy]'s "When an opponent holds here, kill this"
# (RAD). Not TR_HOLD with a condition: TR_HOLD is queued for the units of the
# seat that is SCORING, and this fires for a permanent belonging to the seat
# that just LOST the ground, which that loop never looks at.
# TR_SHOWDOWN_HERE -- "When a showdown begins here" (Diana - Lunari). Any
# Showdown, Non-Combat included, which is why it is not TR_ATTACK_OR_DEFEND:
# no one is designated when a unit walks onto open ground (RiftJudge #11567).
# TR_RUNE_RECYCLED -- "when you recycle a RUNE" (Sivir - Battle Mistress).
# 416.1.b makes that a different event from recycling a card to the Main Deck,
# which is TR_RECYCLED; paying a Power cost is the usual way it happens.
# TR_BANISHED -- "when you banish a card you own" (Zed - Master of Shadows).
# TR_PLAY_NONHAND -- "when you play a card from anywhere other than your hand"
# (Yordle, Kennen - Heart of the Tempest): from a trash, a deck, a look buffer
# or the Facedown Zone. A token is not a card (185) and never counts.
# TR_TEMPORARY -- 816: "[Temporary]" is a TRIGGERED ability ("kill me at the
# start of my controller's Beginning Phase"), not a state-based expiry, so it
# goes on the Chain and both players get a window before the unit dies. No
# card carries it in `ABILITIES`: the keyword can be GRANTED (Fading Memories,
# Shadow's Call, Last Stand), so the ability is synthesized per permanent --
# see `TEMPORARY_ABILITY` and `chain.fire`.
# TR_RECYCLED -- "when you recycle one or more cards to your Main Deck"
# (Karma - Channeler): a watcher, once per action in which the seat recycled.
# TR_MARKED_CONQUERS -- a marked unit conquered this turn ("This turn, that
# unit has 'When I conquer, ...'", Relentless Pursuit); see OP_MARK.
# TR_SECOND_DRAW -- "when you draw your second card each turn" (Frigid
# Jewel): a watcher for the drawing seat, fired once per turn at settle.
# TR_MAIN_START -- "at the start of your Main Phase" (Bottled Constellation),
# for the turn player's permanents, queued by `phases.enter_main`.
# TR_YOU_KILL -- a watcher: a unit died and YOU killed it (a spell or ability
# you controlled was resolving, or your side's combat damage did it; see
# `combat.KILLER`). TR_KILL_FROM_TRASH -- the same event, for a card in your
# trash (Immortal Phoenix). `subject_stunned` narrows to a stunned victim.
# TR_BECOME_MIGHTY -- a watcher: a unit its controller controls went from
# under 5 Might to 5+ (740.2), read by `combat.scan_might_transitions`.
# TR_FOLLOWUP -- queued for its source by OP_QUEUE_FOLLOWUP, so a follow-up
# that must CHOOSE a target ("...then buff a friendly unit", Ivern - Nurturer)
# becomes its own Chain Item instead of a target-less FOLLOWUPS entry.
# TR_RUNE_<domain> -- queued by OP_REVEAL_RUNE for its source with the domain
# of the rune it revealed: "do one of the following based on its domain"
# (Twisted Fate - Gambler). A separate Chain Item, so its target is chosen
# knowing the domain. `TR_RUNE_BODY + domain` in `config.DOMAINS` order.
# TR_UNIT_MOVES -- a WATCHER on another unit's Move: "when a friendly unit
# moves from my location" (Stealthy Pursuer, `move_from_my_loc`), "when an
# opponent moves to a battlefield other than mine" (Volibear - Imposing,
# `subject_enemy` + `move_to_other_bf`). Fires once per watcher per Move, so a
# declaration of three units is one event to it. ctx = from, ctx2 = to.
TRIGGER_NAMES = ("play_me", "death", "move", "hold", "conquer", "play_spell",
                 "activated", "attack_or_defend", "play_unit",
                 "other_dies", "gear_ability", "discard",
                 "beginning", "end_of_turn", "opponent_scores",
                 "readied", "chosen", "play_from_hidden", "hide",
                 "leaves_board", "combat_ends", "revealed_from_deck",
                 "nth_card", "become_empowered", "win_combat", "stun",
                 "buffed", "moved_enemy", "spend_buff", "equipped",
                 "marked_dies", "marked_wins", "discard_me",
                 "conquer_from_trash", "first_beginning_death")
# TR_FIRST_BEGINNING_DEATH -- "The first time a friendly unit dies during your
# Beginning Phase each turn" (Shard of Undoing): a watcher, fired once per turn
# at the death that first sets `state.died_in_beginning`.
# TR_CONQUER_FROM_TRASH -- "When you conquer, ..." printed on a card that acts
# from its owner's TRASH (Super Mega Death Rocket!).
# TR_DISCARD_ME -- "When you discard me" -- fires from the TRASH the card just
# reached (`state.trash_src`), queued by `chain.fire_discarded`.
# TR_MARKED_DIES / TR_MARKED_WINS -- the Delayed Abilities of "When IT dies this
# turn" / "When it wins a combat this turn": armed by OP_MARK onto one unit and
# queued from that unit's death / combat win, sourced from the delayed slot.
# TR_EQUIPPED -- "When you attach an Equipment to me" (Jax - Unrelenting):
# queued for the unit as an Equipment attaches to it, by whichever effect.

# TR_MOVED_ENEMY -- "When you move an enemy unit" (Blast Cone): fired by the
# resolving player of an effect that moves a unit they do not control.
# TR_SPEND_BUFF -- "When you spend a buff" (Fae Dragon): fired wherever a Buff
# counter is spent as a cost or by an effect.

# TR_BUFFED -- "When you buff a friendly unit" (Mistfall), "When you buff me"
# (Simian Ancestor). Fired by the resolving player of the op that buffed, only
# when the unit had no Buff a moment ago: 426.1.b.1 caps a unit at one, so a
# buff that adds nothing is no event.

# TR_STUN -- "When you stun an enemy unit" (Eclipse Herald). A watcher fired by
# the RESOLVING player of the op that stunned, with the stunned unit as the
# subject, and only on a real transition: `GameState.stun` returns False for a
# unit already Stunned (423.1.a.1), and a no-op is not an event.

# TR_WIN_COMBAT -- 466.3.a: "A Player has won a combat if they received either
# the attacker or defender designation and are the only Player that has units
# remaining at this battlefield". 466.3.c then hands that result to "units at
# this battlefield", so "When I win a combat" (Nidalee) fires for each of the
# winner's units still standing there, and "When YOU win a combat" (Draven -
# Glorious Executioner, a legend) fires once for the player.
#
# Fired at 466.3, before Control settles (466.5), because 466.4 makes the
# result's triggers resolve first. A "No Result" -- a recall, or both sides
# still present -- wins nothing and fires nothing.

# TR_BECOME_EMPOWERED is 441.1's TRANSITION, not the status. 441.1.b/c make
# re-Empowering something already Empowered a no-op, and a no-op is not an
# event -- so this fires only when the permanent was NOT Empowered a moment
# ago. That is the same reading TR_READIED takes of readying, and for the same
# reason: "when I become X" is about the change, not about holding X.
#
# Kayle, Justified is the one card that can climb past 1 (`EMPOWER_LIMIT`), and
# each of her Empowers IS a transition, so she fires it every time.
#
# `subject_is_self` separates the two shapes in the pool: "When I become
# [Empowered]" (Kharox, Apprentice Mage) watches the permanent itself, while
# "When you empower something ELSE" (Ambessa) watches its controller's board
# and must not fire on its own Empower.

# TR_NTH_CARD -- "when you play your FIRST card each turn" (Astral Heron),
# "your SECOND card in a turn" (Darius - Trifarian). One trigger with an
# ordinal rather than one trigger per number, because the event is identical
# and only the count differs; `Ability.subject_nth` carries the N.
#
# It is deliberately NOT `TR_PLAY_UNIT` with a condition. 349 makes a card
# played at FINALIZATION, so this has to fire for spells the instant they are
# committed to the Chain -- a countered spell was still your first card --
# and `fire_play_unit` runs only for permanents. The count it reads is
# `cards_played`, which every one of the four play sites already maintains for
# [Legion], so the ordinal is exact for free.
#
# "each turn" and "in a turn" mean the same thing here: `cards_played` is
# zeroed at end of turn, so the Nth card of the turn can only happen once.

# TR_PLAY_FROM_HIDDEN and TR_HIDE are the two halves of the Facedown Zone that
# a BYSTANDER can watch (Black Market Broker, Katarina - Reckless). Both are
# watcher triggers in the `fire_watchers` family, and both are about the
# controller's own action rather than the watcher's, so neither carries a
# subject.
#
# They are deliberately separate, because 811.1.c.1 makes them different
# events: **Hide is not a subset of Play**, so "when you hide a card" does not
# fire on playing one back, and "when you play a card from face down" does not
# fire on hiding it. Katarina prints both clauses precisely because neither
# implies the other.
#
# TR_PLAY_FROM_HIDDEN is distinct from `Ability.from_hidden` too, and the pair
# is easy to confuse: the flag narrows a permanent's OWN TR_PLAY_ME ("when you
# play ME from face down" -- Evelynn), while this fires for OTHER permanents
# watching any such play, including of a spell.

# TR_READIED fires on the exhausted -> ready TRANSITION, not on every write of
# P_READY. The Awaken Phase readies the turn player's whole board at once
# (315.1.b) and that DOES count as readying -- so a wide board fires it several
# times a turn, which is the card's intent -- but a unit that was already ready
# has not become ready and fires nothing. A unit ENTERING ready never was
# exhausted, so it is not a readying either.
#
# TR_CHOSEN fires when a target slot is filled with a permanent (355.7), from
# the one site where that happens. "You" is the card's controller throughout
# this family, which is why the cards reward targeting your OWN units --
# [Deflect] exists precisely because an opponent choosing you is a different
# event, and no card in the pool watches for that one.

# TR_OPPONENT_SCORES is a watcher on the OTHER seat's points, so it fires from
# every site that awards one -- Hold in `phases.score_holds`, Conquer in
# `combat._establish_control`, and `OP_SCORE` for the cards that grant a point
# outright. Three sites rather than one because the engine has no single
# "award a point" primitive; if a fourth ever appears it has to fire here too.

# TR_BEGINNING and TR_END_OF_TURN are phase-timed: they fire for the TURN
# PLAYER's permanents at a point in their own turn, not off any game event.
# "at the start of YOUR Beginning Phase" and "at the end of YOUR turn" are
# both about the controller's turn, so neither fires on the opponent's.

# TR_OTHER_DIES and TR_GEAR_ABILITY are WATCHER triggers: they fire for a
# permanent because something happened to a DIFFERENT one. TR_DEATH fires
# for the thing that died; "when ANOTHER friendly unit dies" is a different
# question and needs its own firing site. Both go through
# `chain.fire_watchers`, which is `fire_play_unit` generalised -- one place
# that knows how to ask "who was watching for this".

# TR_ACTIVATED is not a trigger at all -- it is the marker for an ACTIVATED
# ability (151.1: "Costs followed by a ':' and then an effect"). No event ever
# fires it; the player pays and puts it on the Chain themselves via A_ACTIVATE.
# It rides the trigger machinery because 151.2.a.1 says an activated ability
# "behaves, once activated, like a spell without an associated card" -- the
# same finalization, targeting, priority and resolution a triggered ability
# already uses. Giving it its own path would duplicate all of that.

# Which side of a Combat a TR_ATTACK_OR_DEFEND ability cares about (459). The
# Attacker is the seat that declared the Move; every unit it controls at that
# battlefield attacks, and every unit anyone else controls there defends.
ROLE_EITHER, ROLE_ATTACK, ROLE_DEFEND = range(3)

# TR_HOLD and TR_CONQUER are the two ways a battlefield Scores (469/470), and
# they fire for the units standing there rather than for the player. TR_PLAY_SPELL
# fires on its controller playing any spell -- 349 makes "played" mean finalized,
# so it fires when the spell is put on the Chain, not when it resolves.


# [Repeat] (820), not implemented yet -- the constraint is recorded because it
# is the part that is easy to get wrong. 820.1.c.3: **each Repeat cost can be
# paid only a single time.** It is an optional additional cost that buys ONE
# extra execution, not a loop, so nothing can be repeated arbitrarily by paying
# again. A card printing two separate Repeat instances (820.1.c.2, 820.3) may
# pay each once, for three executions total; that is the only way past two.
# 820.2.a: the choices for the extra execution are made at the normal time and
# need not match the first, so a repeated targeted effect needs a second set of
# target slots rather than a re-use of the first. Confirmed with the project
# owner.
REPEAT_PAYMENTS_PER_INSTANCE = 1


class Ability(NamedTuple):
    """One triggered ability. Deliberately shaped like a `CardSpec`.

    383.3 -- "a Triggered Ability behaves like an Activated Ability and is
    placed on the Chain". So it finalizes, targets, and resolves through
    exactly the machinery a spell already uses; `targets`/`ops`/`n_targets`
    match `CardSpec` so `resolve.py` needs no idea which it is holding. What a
    spell has and this does not is a *speed*: an ability is never played, so
    there is no timing permission to check.

    `optional` is 383.3.a's "you may" **as the first part of the effect**,
    which is decided at FINALIZATION, not on resolution -- declining removes
    the ability from the chain and it counts as never having triggered
    (383.3.a.2). A "you may" appearing later in the text is a different thing
    and is decided on resolution (383.3.a.3); that is a condition, not this.
    """
    trigger: int
    targets: tuple[TargetSpec, ...] = ()
    ops: tuple[Op, ...] = ()
    optional: bool = False
    # --- activated abilities only (trigger == TR_ACTIVATED) ---------------
    # 204.1.b: "on activated abilities, the Base Cost is the resource or
    # instruction written before the ':'". 151.2 restricts a Gear's activated
    # ability to its controller's Main Phase in an Open State and NOT during a
    # Showdown, which is exactly what SPEED_MAIN already means.
    speed: int = SPEED_MAIN
    cost_energy: int = 0
    cost_power: int = 0
    cost_exhaust: bool = False        # "Exhaust:" -- the source must be ready
    # "Kill this:" -- the source is killed to pay, which makes the ability a
    # once-per-permanent effect rather than a repeatable one. It is a COST, so
    # it is paid at finalization and the source is already gone by the time the
    # effect resolves; nothing here may reference it (383.2.c.2). Killing is a
    # real death, not a banish (427.2.a), so the card lands in its trash and any
    # [Deathknell] on it fires.
    cost_kill_self: bool = False
    # 820, as a TARGETED cost: "[Empower] -- Kill a friendly unit" (Escaped
    # Grayback). The same field `CardSpec` carries and the same machinery pays
    # it -- `item_spec` hands both kinds to the finalization path and nothing
    # downstream knows which it is holding, so this needed a field rather than
    # a mechanism. Distinct from `cost_kill_self`, which names its victim.
    cost_kill: "TargetSpec | None" = None
    # "Disempower this, Exhaust: ..." -- 441.2, spending the Empowered status
    # as a cost. Four cards in the pool pair it with Exhaust, which makes the
    # whole ability once-per-Empower rather than once-per-turn: the status has
    # to be bought back through [Empower] before it can be paid again.
    #
    # A COST, so it is paid at finalization and the status is gone by the time
    # the effect resolves -- nothing in the ops may ask whether the source is
    # Empowered (383.2.c.2).
    cost_disempower_self: bool = False
    # "Spend my buff: ..." (Sett, Brawler). The Buff counter is the cost, so
    # the ability is withheld from an unbuffed unit and paying removes it --
    # together with the +1 Might it was giving (703), which the effect then
    # more than pays back.
    cost_spend_buff_self: bool = False
    # "[Empower] -- Discard 1" / "Discard a spell" (Punching Poro, Mel -
    # Defiant Soul): a card from hand as the cost, optionally of one type.
    # Withheld while no such card is in hand; the oldest match is discarded.
    cost_discard: int = 0
    cost_discard_type: str = ""
    # "Recycle N from your trash:" (Garbage Grabber, Vi - Destructive, Last
    # Rites). A cost with a CHOICE in it -- 3956 makes the recycled cards "of
    # the instructed player's choice" -- and the choice is real: Last Rites'
    # own payoff replays units from that same trash, so which cards leave it
    # decides what the ability can do next. Paid one pick at a time through
    # `pend_cost_recycle`, before the ability's targets and finalization, the
    # same place `cost_kill` is chosen. Not a target (3956 says so), so nothing
    # that cares about being chosen reacts to it.
    #
    # `cost_recycle_type` narrows WHAT may be recycled: Assembly Rig's
    # "Recycle a UNIT from your trash". Empty means any card.
    # "[Level N][>] <activated ability> (Use this ability only while you have
    # N+ XP.)" (Honeyfruit). A gate on ACTIVATING, not a cost: nothing is
    # spent, and dropping below N later does not undo a use already made.
    # Checked where every other activation restriction is, in the offer loop.
    min_xp: int = 0
    # "Use this ability only while I'm at a battlefield" (Xerath - Freed,
    # Ultrasoft Poro, Caitlyn - Patrolling, Renata Glasc). An activation gate
    # on the SOURCE's location, checked where it is offered; not a cost, and
    # not re-checked at resolution -- moving away in the response window does
    # not undo an activation already made.
    use_at_battlefield: bool = False
    cost_recycle_trash: int = 0
    cost_recycle_type: str = ""
    # "Spend N XP:" -- 204.1.b again, an instruction before the ':'. A player
    # resource rather than a permanent's, so unlike Exhaust it does not care
    # which copy activates, and unlike a rune cost it is not refunded by
    # anything: XP spent is gone.
    cost_xp: int = 0
    # 337.2 -- a resource-adding ability resolves IMMEDIATELY and never waits
    # on the Chain, so it cannot be responded to. The cards say so themselves:
    # "Abilities that add resources can't be reacted to." Without this an [Add]
    # would open a priority window in which the opponent could answer the mana
    # before it existed, which is the opposite of the rule.
    immediate: bool = False
    # For TR_PLAY_UNIT: fire only when the unit played was a TOKEN. Lillia
    # grows on "a token unit"; a watcher for any unit would be a different and
    # much stronger card, and no rules text distinguishes them for free.
    subject_token: bool = False
    # For TR_READIED / TR_CHOSEN: the event's subject must be the watcher
    # itself. "When you choose or ready ME" is a different card from "when you
    # ready a friendly unit" (Pirate's Haven), and `fire_watchers` walks every
    # permanent its controller owns -- so without this, Irelia would grow every
    # time anything of yours was readied.
    subject_is_self: bool = False
    # "When you choose me WITH A SPELL" (Jae Medarda). An ability that chooses
    # is still a choice (355.7), so the narrowing has to be stated.
    subject_by_spell: bool = False
    # For TR_PLAY_UNIT: which card TYPE the played card must be. Every play of
    # a permanent comes through one firing site, gear included, so without this
    # "when you play another unit" fired on a gear -- Reluctant Leader grew off
    # a Cull, and Vex would stun one. A multi-type card satisfies each of its
    # types (a gear unit answers both watchers), so this is a membership test
    # and never an elif over types.
    subject_card_type: str = "Unit"
    # For TR_PLAY_UNIT: watch the OPPONENT's plays instead of your own.
    # Vex - Apathetic stuns what an opponent plays; Lillia grows on what
    # you play. Same trigger, opposite side.
    subject_enemy: bool = False
    # "When you play ANOTHER unit" -- the watcher must not be the unit that
    # was just played. Reluctant Leader grows on the rest of the board and
    # not on its own arrival.
    subject_not_self: bool = False
    # "When another NON-RECRUIT unit you control dies" -- a tag the subject
    # must NOT carry. Viktor makes Recruits, so without this he would feed
    # on his own tokens and never stop.
    subject_lacks_tag: str | None = None
    # "When you play me or another DRAGON" -- a tag the subject must carry, the
    # mirror of `subject_lacks_tag`. Gentle Gemdragon's second ability watches
    # its kin and nothing else; without this it would fire on every unit played
    # and be a strictly better card than the one printed.
    subject_tag: str | None = None
    # "The FIRST TIME ... each turn" -- gated on `state.once_used`, the same
    # per-permanent turn stamp Zilean's once-each-turn uses. Spent when the
    # trigger fires, so a second death in the same turn does nothing.
    once_each_turn: bool = False
    # "while I'm at a battlefield" -- a condition on the WATCHER's own
    # location, not the subject's. Vex in a base watches nothing.
    subject_at_battlefield: bool = False
    # --- TR_ATTACK_OR_DEFEND narrowing ------------------------------------
    # 459 designates every unit at the battlefield as an Attacker or a Defender
    # when the Combat begins, and most cards care which: "When I attack" is
    # half of what "when I attack or defend" means. Both are checked at TRIGGER
    # time (359.3.f.3) -- a unit that does not qualify never triggers at all,
    # and one that does keeps the effect even if the board changes during the
    # response window.
    #
    # These lived in `combat.open_showdown` as an unconditional gate, which was
    # correct for the single card that needed them and silently wrong for every
    # other: Mask of Foresight's "alone" clause was being applied to all
    # attack/defend triggers, so a card without the clause would have inherited
    # it. Anything printed on one card belongs on that card.
    # 383.3.b -- a cost inside the instructions: "you may PAY {1 energy}. If
    # you do, ...". Distinct from `optional`, which is a free yes/no. The
    # ability is only offered when the cost is affordable, and accepting
    # pays it; declining removes the ability (383.3.a.2) and costs nothing.
    opt_cost_energy: int = 0
    opt_cost_power: int = 0
    # 383.3.b again, paid in a body rather than in runes: "you may KILL ME to
    # ...". Always affordable -- the source is on the board or the ability
    # never triggered -- so unlike a rune cost it needs no offer-time check.
    # It is a cost, so it is paid at finalization and the source is a corpse
    # by the time the effect resolves; nothing in the ops may reference it.
    opt_cost_kill_self: bool = False
    # 383.3.b paid in CARDS: "you may [Burn 1] to ...". Always affordable, like
    # `opt_cost_kill_self` -- an empty deck does not refuse the cost, it just
    # makes paying it a Burn Out (431.2), which is a price rather than a
    # prohibition.
    opt_cost_burn: int = 0
    # --- TR_PLAY_ME narrowing (811) ---------------------------------------
    # "When you play me FROM FACE DOWN" (Evelynn - Entrancing, Tornado
    # Warrior). A narrowing of the TRIGGER, not a condition on the effect:
    # 359.3.f decides whether the ability triggers at all, so a play from hand
    # must not put it on the Chain and then fizzle it -- with `optional` set
    # that would ask the player a "you may" whose answer could never matter.
    #
    # Read off `F_FROM_HIDDEN` on the source's row, never from the chain
    # item's `from_hand`. The two are NOT complements: `from_hand` is False
    # for every triggered ability ever pushed, so `not from_hand` would fire
    # this on a unit played normally out of hand.
    # "When you play me TO A BATTLEFIELD" as a narrowing of the TRIGGER rather
    # than a condition on the ops (359.3.f). `COND_SELF_AT_BF` says the same
    # thing at RESOLUTION and is right for Mischievous Marai, whose ability is
    # not optional -- but Blitzcrank's begins "you MAY", and an optional
    # ability that fires and then fizzles asks the player a question with no
    # meaning behind it. Narrowing the trigger means a play to a base never
    # reaches the Chain at all.
    at_battlefield: bool = False
    from_hidden: bool = False
    # For TR_NTH_CARD: WHICH card of the turn this watches. 1 is "your first
    # card each turn", 2 is "your second card in a turn". An exact match, not a
    # threshold -- the Heron's discount is offered once, on the first card, and
    # not again on the third.
    subject_nth: int = 0
    # For TR_DEATH: "When I die IN COMBAT" (Draven - Audacious). A narrowing
    # of the trigger (359.3.f), read off `F_DIED_IN_COMBAT` on the dead row, so
    # a death anywhere else never reaches the Chain.
    died_in_combat: bool = False
    # 828.1.d -- an [Empowered] dependent TRIGGERED ability exists only while
    # its source holds the status, so it does not trigger at all otherwise.
    # A narrowing rather than a condition on the ops: an op condition would put
    # the ability on the Chain, ask for its target ("choose a unit here"), and
    # then fizzle -- a decision with no consequence the policy would still have
    # to make. (The older entries in this file gate the ops instead; they have
    # no targets, so the difference never surfaced.)
    while_empowered: bool = False
    # For watcher triggers: the subject must stand at the WATCHER's location.
    # "When an enemy unit HERE dies" (Nasus, Guardian of Knowledge).
    subject_here: bool = False
    # For watcher triggers: the subject must be BUFFED as the event happens.
    # "When a buffed friendly unit dies" (Vanguard Helm) -- read at the death,
    # while the dying row still carries its Buff.
    subject_buffed: bool = False
    # A condition on the ability ITSELF, checked before it reaches the Chain
    # (359.3.f for a trigger, the activation offer for an activated ability)
    # rather than at resolution: "When I attack WHILE your units have all 4
    # tags" (Daisy!), "Use only if you've chosen an enemy unit this turn"
    # (Hungry Wolf). Gating the trigger rather than its ops keeps a failed
    # condition from asking the player to choose a target for nothing.
    cond: int = COND_NONE
    cond_level: int = 0
    cond_tag: str | None = None
    # 383.3.b paid by BANISHING the source: "you may banish me to banish it"
    # (Ravenbloom Prefect). Always affordable, like `opt_cost_kill_self`.
    opt_cost_banish_self: bool = False
    # For attack/defend watchers: fire once for the watcher per combat, not
    # once per defending unit ("When you defend at a battlefield", Loyal Pup).
    once_per_combat: bool = False
    # For watchers: the SUBJECT must stand at a battlefield ("When you stun an
    # enemy unit AT A BATTLEFIELD", Vex - Mocking).
    subject_on_battlefield: bool = False
    # For TR_PLAY_SPELL: "if you spent {4 energy} or more" (Revna), the Energy
    # actually paid for that spell. Filtered where the trigger is queued.
    subject_min_spent: int = 0
    # For TR_NTH_CARD: "a card with Power cost {any rune}{any rune} or more"
    # (Yordle Explorer), the printed Power cost of the card played.
    subject_min_power: int = 0
    # An activated ability's own Energy discount -- see `cost.ability_energy`.
    energy_less_per_rune: int = 0
    energy_less_if_runes_at_most: tuple[int, int] = (0, 0)
    # 383.3.b paid in CARDS FROM HAND: "you may discard 1 to ..." (Super Mega
    # Death Rocket!). Offered only with a card in hand to discard.
    opt_cost_discard: int = 0
    # 383.3.b paid in XP: "you may spend 3 XP to ..." (Kha'Zix, Evolving
    # Hunter). Offered only while affordable, like a rune cost.
    opt_cost_xp: int = 0
    # "Choose one --" on an ability: modes as CardSpecs, exactly as on a card.
    modes: tuple = ()
    # "Choose one you've NOT CHOSEN THIS TURN" -- a mode is spent for this
    # permanent until the turn ends (`state.mode_used_mask`).
    modes_once_per_turn: bool = False
    # A Delayed Ability that fires ONCE and disarms: "the NEXT time you play a
    # unit this turn" (Nami - Headstrong), as against Rally the Troops' "when a
    # friendly unit is played this turn".
    delayed_once: bool = False
    # 383.3.b paid by tapping the source: "you may EXHAUST ME to ...". Offered
    # only while the source is ready, and paid on acceptance like the other
    # optional costs. Combines with `opt_cost_energy` (Spirit Wheel's "pay
    # {1 energy} and exhaust this").
    opt_cost_exhaust_self: bool = False
    # "...on an OPPONENT'S turn" (Chemtech Cask, Viktor, Innovator) -- the
    # mirror of `own_turn`, a narrowing of the trigger.
    opp_turn: bool = False
    # For TR_PLAY_SPELL: "a spell that costs {5 energy} or more" (Lux -
    # Illuminated), read off the printed Energy cost. Filtered where the
    # trigger is QUEUED, which is the only place the spell's card is known.
    subject_min_energy: int = 0
    # For TR_PLAY_UNIT: "during a showdown" (Fresh Beans).
    in_showdown: bool = False
    # "...ON YOUR TURN" (Evelynn's other half). 811.6 makes a facedown card
    # playable in any window a [Reaction] is -- the opponent's turn included --
    # so this genuinely excludes something rather than restating the timing.
    own_turn: bool = False
    subject_alone: bool = False       # "...attacks or defends ALONE" (740.2.a)
    subject_role: int = ROLE_EITHER   # attacker-only / defender-only / either
    # Whose attack this watches. "When I attack" (the common case) fires only
    # for the permanent the ability is printed on; "When a friendly unit
    # attacks or defends alone" fires for any of them, which is what lets Mask
    # of Foresight sit at a base and watch a battlefield.
    #
    # Defaults to the narrow reading on purpose. A card that wants the wide one
    # and forgets this under-fires, which is visible as a card that does
    # nothing; the other default would make a forgotten flag fire for the whole
    # board, which reads as a plausible effect and hides.
    subject_any_friendly: bool = False
    # TR_UNIT_MOVES filters -- see the trigger.
    move_from_my_loc: bool = False
    move_to_other_bf: bool = False
    subject_stunned: bool = False
    # "a NON-TOKEN gear" (Jayce, Brilliant Inventor).
    subject_nontoken: bool = False
    # "Use only if unattached." (The Zero Drive)
    unattached_only: bool = False
    # A `cost_kill` that EXHAUSTS the chosen unit instead (Forgotten Signpost);
    # its location is kept as the item's ctx2 ("the location of the unit you
    # exhausted").
    cost_exhaust_unit: bool = False

    @property
    def n_targets(self) -> int:
        return len(self.targets)


# ---------------------------------------------------------------------------
# The card data. This is the part that grows; everything above is fixed.
# ---------------------------------------------------------------------------
# Each entry is a transcription of the printed text. Keep the text in the
# comment so a future reader can check the transcription without the card.

# Token identities. The name on the right is the CARD, and every characteristic
# a card's text recites about it -- "2 Might", "with [Deflect]" -- is printed on
# that card already (rule 187), so the recitation is reminder text and nothing
# here has to re-state it. `data/tokens.json` supplies the eight rule-187 tokens
# the export omits; Recruit and Sprite come from `cards.json` and carry a back
# face and a collector number in their names.
SPRITE_TOKEN = "Sprite (274) // Buff"   # 3 Might Fae unit token, [Temporary]
RECRUIT_TOKEN = "Recruit (271) // Buff"  # 1 Might Recruit unit token
SAND_SOLDIER_TOKEN = "Sand Soldier"     # 187.3 -- 2 Might, Shurima tag
MECH_TOKEN = "Mech"                     # 187.4 -- 3 Might, Mech tag
REFLECTION_TOKEN = "Reflection"         # 187.6 -- 0 Might, domainless
BIRD_TOKEN = "Bird"                     # 187.7 -- 1 Might, Bird tag, [Deflect]
TENTACLE_TOKEN = "Tentacle"             # 187.10 -- 1 Might, Bilgewater tag
# 187.5 -- a GEAR token, not a unit. Every card that makes one says "exhausted",
# which is the default (`Op.ready` is False), and every one of them sends it to
# the controller's base: 149.2 keeps gear there, and T_MY_BASE says so
# explicitly rather than leaning on OP_CREATE_TOKEN's fallback.
GOLD_TOKEN = "Gold // Buff"
# Tokens that are NOT units. The token-op-must-be-last assertion below exists
# for Zilean - Time Mage's doubling, which 187 scopes to token UNITS -- so a
# gear token is never deferred and never needs its op last. Kept as names
# because this module is imported before any card table exists; the test suite
# checks each one really is a non-unit against the compiled table.
NON_UNIT_TOKENS: frozenset[str] = frozenset({GOLD_TOKEN})

# --- printed play-destination permissions (806.3 exceptions) ---------------
# 806.3/813.3.a restrict a Unit to its controller's base or a Battlefield they
# already control. Several cards print an exception to that, and until now every
# one of them was a dead letter -- `play_destinations` said so in its docstring.
#
# **"Open" and "occupied" are not defined rules terms.** They appear only in
# card text, so these are readings rather than citations, and both are stated
# here so a wrong one is visible and cheap to change:
#   PERM_OPEN   -- no units there at all, from either player. An empty
#                  battlefield is an uncontrolled one (190.4.c), which is what
#                  makes "play me to an open battlefield" a free claim.
#   PERM_ENEMY  -- at least one ENEMY unit there. Rengar's whole card is
#                  dropping onto a battlefield the opponent is holding.
#   PERM_ATTACK -- the battlefield you are currently attacking: the contested
#                  one (459) where you hold the Attacker designation. Unlike
#                  the other two this is a COMBAT-scoped permission, so it is
#                  empty outside a Showdown and the card is then an ordinary
#                  base play.
PERM_NONE, PERM_OPEN, PERM_ENEMY, PERM_ATTACK, PERM_OCCUPIED_ENEMY, \
    PERM_ENEMY_ALONE = range(6)
# PERM_OCCUPIED_ENEMY -- "an occupied enemy battlefield" (Deadbloom Predator,
#   Dauntless Vanguard). 170.11.a defines OCCUPIED as "has a Unit present",
#   and an ENEMY battlefield is one an opponent controls, the counterpart of
#   806.3's "a battlefield you control". Stricter than PERM_ENEMY, which
#   only asks for an enemy unit there and so also admits a battlefield
#   nobody controls yet.

# Cards that replace a token-unit play with "that token and an additional copy
# of it". Keyed by name for the same reason PLAY_PERMISSIONS is: there is one
# such card, and a general replacement registry for n=1 would be scaffolding
# around a single entry. If a second one prints, this is where it goes.
#
# Zilean's clause carries three separate restrictions, all enforced in
# `resolve`'s OP_CREATE_TOKEN: the token must be a UNIT, Zilean must be AT A
# BATTLEFIELD, and it is ONCE EACH TURN (tracked per row in `state.once_used`).
TOKEN_DOUBLERS: frozenset[str] = frozenset({"Zilean - Time Mage"})

# "Then, do the following based on the discarded card's type." The branch runs
# AFTER the player has chosen what to pitch, so it cannot be ordinary ops on
# the card -- resolution has already returned by then. Keyed by card name and
# looked up when the choice comes back, the same shape as PLAY_PERMISSIONS.
#
# A card with more than one type takes EVERY matching branch: a gear unit is
# both, so it would draw AND ready runes. See `_played_bits` for the same rule
# on Swain, and note the branches are checked independently for that reason.
# Indexed by INT, not by name: `GameState` holds no Python objects (PLAN.md
# §1.8), and `state_hash` reads every non-array field through `int(v)`. A
# string here parsed fine and then broke determinism, cloning and the digest
# all at once -- the rule exists for a reason.
DB_HWEI = 0

# Op lists that run AFTER a deferred decision resolves -- see `Op.then_key`.
# Indexed by int for the same reason DISCARD_BRANCHES is: nothing but ints may
# reach `GameState`, and the key is stored there while the decision is pending.
FU_DIANA_REVEAL = 0
FU_GUARDS_READY = 1
FU_DRAW_1 = 2
FU_THEY_DRAW_1 = 3
FU_DRAW_2 = 4
FU_DRAW_1_XP_1 = 5
FU_DAMAGE_SUBJECT_6 = 6
FU_GOLD_ME = 7
FU_GOLD_BOTH = 8
FU_CARD_SHARP_ASK_OPP = 9
FU_CARD_SHARP_MINE_THEN_OPP = 10
FU_BOTH_DRAW_1 = 11
FU_BOTH_CHANNEL_1 = 12
FU_SUBJECT_TO_TOP = 13
FU_SUBJECT_TO_BOTTOM = 14
FU_IVERN = 15
FU_GUARDS_PAY = 16
FU_BECOME_COPY = 17
FU_BECOME_COPY_TEMP = 18
FU_GRENADE_REPLAY = 19

# Populated below, once the ops they reference are defined.
FOLLOWUPS: list[tuple] = [()] * 20
# [FU_DIANA_REVEAL] "...then reveal the top card of your Main Deck. If it's a
# spell, draw it." A second look at N=1: the spell goes to hand, anything else
# goes back on top. `pick_optional` because a type-restricted pick must always
# leave a way out -- the top card need not be a spell.

DISCARD_BRANCHES: tuple[dict[str, tuple], ...] = (
    # [DB_HWEI] Hwei - Brooding Painter: "Then, do the following based on the
    # discarded card's type: Spell - Draw 1. Gear - Ready up to 2 runes.
    # Unit - Give me +3 Might this turn."
    {
        "Spell": (Op(OP_DRAW, n=1),),
        "Gear": (Op(OP_READY_RUNES, n=2),),
        "Unit": (Op(OP_MODIFY_MIGHT, target=T_SELF, n=3),),
    },
)

# Cards that suppress the [Temporary] expiry. LeBlanc - Everywhere At Once:
# "Your [Temporary] effects at my battlefield don't trigger." 816's reminder --
# "Kill it at the start of its controller's Beginning Phase" -- is the trigger
# being suppressed, so a Temporary permanent standing with a friendly LeBlanc
# at a BATTLEFIELD simply does not expire.
#
# Two restrictions the wording carries and a loose reading drops: "YOUR"
# effects, so it never spares an opponent's Temporary units; and "at MY
# BATTLEFIELD", so a LeBlanc sitting in a base suppresses nothing.
# Heimerdinger - Inventor: "I have all Exhaust abilities of all friendly
# legends, units, and gear." Keyed by name like the other bespoke registries.
# The borrowed ability is HIS: its Exhaust cost taps him, its effects say "me"
# about him, and the donor is untouched.
ABILITY_BORROWERS: frozenset[str] = frozenset({"Heimerdinger - Inventor"})

# "I can't be chosen by enemy spells and abilities unless I'm in combat."
# Absolute untargetability with a condition, unlike [Deflect]'s surcharge --
# there is no price that makes it legal. Keyed by name like the other bespoke
# registries; `resolve._matches` enforces it for every slot at once, so it
# covers spells and abilities without either having to opt in.
SAFE_UNLESS_IN_COMBAT: frozenset[str] = frozenset({"Akali, Silent"})

TEMPORARY_SUPPRESSORS: frozenset[str] = frozenset(
    {"LeBlanc - Everywhere At Once"})

# 359.2.c -- units enter EXHAUSTED. [Accelerate] is the printed exception the
# engine already knows; these are cards that print their own, each with a
# different condition. Keyed by name for the same reason PLAY_PERMISSIONS is:
# the condition is bespoke per card, not a shared mechanism.
ER_TWO_OTHERS_AT_BASE, ER_DIED_IN_BEGINNING, ER_LEVEL_3, ER_ALWAYS, \
    ER_ANOTHER_DRAGON, ER_HAND_AT_MOST_2, ER_ANOTHER_MECH, \
    ER_OPP_STUNNED, ER_OPP_CONTROLS_BF, ER_UNIT_DIED_THIS_TURN, \
    ER_SAME_NAME_IN_TRASH, ER_OPP_NEAR_VICTORY, ER_SELF_NOT_NEAR_VICTORY = range(13)
# ER_SELF_NOT_NEAR_VICTORY -- "If your score is not within 3 points of the
# Victory Score, I enter ready" (Corrupted Dragon).

ENTERS_READY_IF: dict[str, int] = {
    # "I enter ready if you have two or more OTHER units in your base."
    "Xin Zhao - Vigilant": ER_TWO_OTHERS_AT_BASE,
    # "If a friendly unit died during your Beginning Phase this turn, I enter
    # ready." Past tense -- see `state.died_in_beginning`.
    "Shadow Watcher": ER_DIED_IN_BEGINNING,
    # "[Level 3][>] I have +1 Might and enter ready." The Might half is a
    # STATIC gated on COND_LEVEL; only the readiness half belongs here,
    # because 359.2.c is decided once as the unit is played and a static
    # cannot express a one-shot replacement.
    "Scorchclaw": ER_LEVEL_3,
    # "[Level 3][>] I enter ready." -- Scorchclaw's gate without the Might half.
    "Bandle Soldier": ER_LEVEL_3,
    # "I enter ready." Unconditional; 369.3 makes it a replacement of the way
    # the unit enters, which is why it lives here and not in a static.
    "Eager Drakehound": ER_ALWAYS,
    "Vanguard Attendant": ER_ALWAYS,
    "Arena Kingpin": ER_ALWAYS,
    "Master Yi - Honed": ER_ALWAYS,
    # "I enter ready if you control another Dragon." -- checked as he is played,
    # before he is on the board, so any Dragon already there is "another".
    "Direwing": ER_ANOTHER_DRAGON,
    # "If you have two or fewer cards in your hand, I enter ready." Counted as
    # he is played, when he has already left the hand he is counted from.
    "Dunebreaker": ER_HAND_AT_MOST_2,
    # "I enter ready if you control another Mech."
    "Breakneck Mech": ER_ANOTHER_MECH,
    # "If an opponent controls a stunned unit, I cost {2 energy} less and
    # enter ready." The discount half is a static on the same condition.
    "Monch": ER_OPP_STUNNED,
    # "If an opponent controls a battlefield, I enter ready."
    "Vayne - Hunter": ER_OPP_CONTROLS_BF,
    # "If an opponent's score is within 3 points of the Victory Score, I enter
    # ready."
    "Leona - Zealot": ER_OPP_NEAR_VICTORY,
    # "If a unit died this turn, I enter ready." Either player's.
    "Towering Pairofant": ER_UNIT_DIED_THIS_TURN,
    # "I enter ready."
    "Warwick - Hunter": ER_ALWAYS,
    "Daisy!": ER_ALWAYS,
    # "I enter ready if you have a card with my name in your trash."
    "Shadow Assassin": ER_SAME_NAME_IN_TRASH,
    "Corrupted Dragon": ER_SELF_NOT_NEAR_VICTORY,
}

# Printed OPTIONAL ADDITIONAL COSTS, in runes, paid as the card is played.
#
# **The same shape as [Accelerate], and deliberately the same action.** 805.2
# makes [Accelerate] an Optional Additional Cost paid *as* the unit is played,
# and `A_PLAY_AT_FAST` already folds it into the destination choice so that
# where to put the unit and whether to pay extra stay one decision. A card that
# prints its own optional additional cost is that same decision with a
# different payload, so it rides the same action rather than adding a second
# one -- and no card in the pool prints both, which is asserted where they meet.
#
# What differs is what paying BUYS. [Accelerate] buys entering ready (805.6, a
# replacement). These buy a clause in the card's own text: "when you play me,
# IF YOU PAID THE ADDITIONAL COST, ...". So paying sets `F_PAID_ADDITIONAL` on
# the permanent and the trigger reads it through `COND_PAID_ADDITIONAL` -- a
# snapshot on the row, like F_LEGION, because the ability resolves a priority
# window after the payment happened.
#
# **The Power is domain-bound to the card's own domain in every printed case**,
# which is what `plan_payment` already does for [Accelerate] under 805.1.a.1.
# All six read "{X rune}" where X is the card's single domain; if one ever
# prints a rune it does not itself have, this registry is where that shows up.
PLAY_COSTS: dict[str, tuple[int, int]] = {
    # "You may pay {1 energy}{Fury rune} as an additional cost to play me."
    "Blast Corps Cadet": (1, 1),
    # "As you play me, you may pay {Calm rune} as an additional cost."
    "Clockwork Keeper": (0, 1),
    # "You may pay {Mind rune} as an additional cost to play me."
    "Frostcoat Cub": (0, 1),
    # "You may pay {Order rune} as an additional cost to play me."
    "Masa, Crashing Thunder": (0, 1),
    # "You may pay {Fury rune} as an additional cost to play me."
    "Pyke - Dockside Butcher": (0, 1),
    # "You may pay {Body rune}{Body rune} as an additional cost to play me."
    "Akshan - Mischievous": (0, 2),
    # "You may pay {1 energy} as an additional cost to play me." No rune at all,
    # which is why the pair is (energy, power) rather than a domain.
    "Sea Monkey": (1, 0),
    # "If you've played a spell this turn, you may pay {Chaos rune} as an
    # additional cost to play me. If you do, I enter ready."
    "Crescent Guardian": (0, 1),
    # "You may pay {Calm rune} as an additional cost to play me."
    "Nami - Headstrong": (0, 1),
    # "You may pay {1 energy} as an additional cost to play me."
    "Gust Monk": (1, 0),
}

# Optional additional costs paid in XP, as a unit is played: "You may spend 3
# XP as an additional cost to play me." What paying buys is either a discount
# (`PAID_XP_DISCOUNT`, Poppy) or a clause read through COND_PAID_ADDITIONAL
# (Safety Inspector). Rides A_PLAY_AT_FAST like the rune costs above.
PLAY_COSTS_XP: dict[str, int] = {"Poppy - Defender of the Meek": 3,
                                 "Safety Inspector": 3}
PAID_XP_DISCOUNT: dict[str, int] = {"Poppy - Defender of the Meek": 3}
# Optional additional costs paid by DISCARDING 1 (another card from hand):
# name -> the Energy discount it buys (0 when it buys a clause instead).
# "You may exhaust your legend as an additional cost to play me." (Bard -
# Mercurial) -- rides A_PLAY_AT_FAST like the rune costs; needs a ready legend.
PLAY_COSTS_LEGEND: frozenset[str] = frozenset({"Bard - Mercurial"})
PLAY_COSTS_DISCARD: dict[str, int] = {"Brazen Buccaneer": 2,
                                      "Zed, From the Shadows": 0}
# "Optional additional costs you pay cost {1 energy} or {any rune} less."
# (Ezreal, Prodigy) -- each copy takes 1 off the Energy, or off the Power when
# the cost has no Energy.
ADD_COST_REDUCERS: frozenset[str] = frozenset({"Ezreal, Prodigy"})
# "I can't be readied." (Maduli the Gatekeeper)
NEVER_READIED: frozenset[str] = frozenset({"Maduli the Gatekeeper"})
# "Your spells that choose me cost {1 energy} or {any rune} less." (Irelia -
# Graceful) -- read as a spell is finalized, once its targets are known.
CHOSEN_DISCOUNT: frozenset[str] = frozenset({"Irelia - Graceful"})
# "If you play me to a battlefield, I enter ready." (Shadow) -- read where the
# destination is known.
ENTERS_READY_AT_BF: frozenset[str] = frozenset({"Shadow"})
# "While I'm in a showdown, your spells have [Repeat] {2 energy}{Chaos rune}."
# (Syndra - Transcendent) -- the granted Repeat cost, see `cost.repeat_cost`.
SHOWDOWN_REPEAT: dict[str, tuple[int, int]] = {"Syndra - Transcendent": (2, 1)}

# PLAY_COSTS that may only be paid once a spell has been played this turn.
PLAY_COST_NEEDS_SPELL: frozenset[str] = frozenset({"Crescent Guardian"})
# PLAY_COSTS whose whole purchase is entering ready -- [Accelerate]'s payload
# on a printed cost. The card's entire text, so membership is what
# `decks.plays_as_printed` credits.
PAID_COST_ENTERS_READY: frozenset[str] = frozenset({"Crescent Guardian"})
# "Each Equipment attached to me gives double its base Might bonus" (Gearhead),
# read by `combat.attached_might`.
EQUIP_BONUS_DOUBLERS: frozenset[str] = frozenset({"Gearhead"})
# "If another unit you control here would die, if it has less Might than me,
# instead heal it, exhaust it, and recall it." (Soraka - Wanderer) -- a
# replacement read by `combat._destroy`.
SMALLER_ALLY_GUARDS: frozenset[str] = frozenset({"Soraka - Wanderer"})
# "If a combat where you are the attacker ends in a tie, recall ALL units
# instead." (Symbol of the Solari), read by `combat.resolution_step`.
TIE_RECALLS_ALL: frozenset[str] = frozenset({"Symbol of the Solari"})
# "Your conquer effects for conquering here trigger an additional time." (Red
# Brambleback) / "Your hold effects for holding here..." (Blue Sentinel).
EXTRA_CONQUER_HERE: frozenset[str] = frozenset({"Red Brambleback"})
EXTRA_HOLD_HERE: frozenset[str] = frozenset({"Blue Sentinel"})
# "Any amount of your damage is enough to kill enemy units." (Elder Dragon)
YOUR_DAMAGE_KILLS: frozenset[str] = frozenset({"Elder Dragon"})
# "If I have moved twice this turn, I don't take damage." (Kayn - Unleashed)
MOVED_TWICE_NO_DAMAGE: frozenset[str] = frozenset({"Kayn - Unleashed"})
# Rule-changing permanents read where the rule is applied, one per sentence:
#   Ol' Poro          "I can't be played on your first, second, or third turns."
#   Perched Grimwyrm  "Play me only to a battlefield you conquered this turn."
#   Tianna Crownguard "While I'm at a battlefield, opponents can't gain points."
#   Sandstone Chimera "While I'm at a battlefield, players only channel 1 rune
#                      at the start of their Channel Phase."
#   Mageseeker Warden "While I'm at a battlefield, opponents can only play
#                      units to their base. ... spells and abilities can't
#                      ready enemy units and gear."
#   Annie - Fiery     "Your spells and abilities deal 1 Bonus Damage."
#   Esteemed Hierophant "While you control 7 or more runes, prevent all damage
#                      that enemy spells and abilities would deal to me."
#   Dune Surfer       "You ignore [Tank] while assigning combat damage here."
PLAY_AFTER_TURN: dict[str, int] = {"Ol' Poro": 3}
PLAY_ONLY_CONQUERED: frozenset[str] = frozenset({"Perched Grimwyrm"})
BLOCKS_OPP_POINTS: frozenset[str] = frozenset({"Tianna Crownguard"})
ONE_RUNE_CHANNEL: frozenset[str] = frozenset({"Sandstone Chimera"})
WARDEN_LOCKS: frozenset[str] = frozenset({"Mageseeker Warden"})
EFFECT_BONUS_DAMAGE: dict[str, int] = {"Annie - Fiery": 1}
# The same Bonus Damage printed in an Equipment's "Attached:" band -- counted
# only while the Equipment is attached (Rabadon's Deathcrown).
EQUIP_EFFECT_BONUS_DAMAGE: dict[str, int] = {"Rabadon's Deathcrown": 3}
# "Spells with [Flow] you play from your trash cost {2 energy} less, to a
# minimum of {1 energy}." (Stargazer) -- (amount, floor), read by
# `cost.flow_energy`.
FLOW_DISCOUNTERS: dict[str, tuple[int, int]] = {"Stargazer": (2, 1)}
RUNE_WARD: frozenset[str] = frozenset({"Esteemed Hierophant"})
IGNORE_TANK_HERE: frozenset[str] = frozenset({"Dune Surfer"})
# "If a player would score 1 point from conquering or holding during their
# first or second turn, they draw 1 instead." (Otterpus) -- read where points
# are awarded for conquering and holding.
EARLY_SCORE_TO_DRAW: frozenset[str] = frozenset({"Otterpus"})


# "This enters exhausted." -- a GEAR's printed exception to 359.2.d, which
# otherwise has gear enter ready. The mirror of ENTERS_READY_IF for units.
# Only gear print it in this form; a unit already enters exhausted (359.2.c),
# so the sentence would be a no-op on one and is asserted not to appear.
ENTERS_EXHAUSTED: frozenset[str] = frozenset({
    "Scryer's Bloom", "Platewyrm Egg", "Honeyfruit", "Hextech Formula",
    "Iron Ballista",
})


PLAY_PERMISSIONS: dict[str, int] = {
    # [Ambush] I can be played to a battlefield where there are enemy units.
    "Rengar, Trophy Hunter": PERM_ENEMY,
    # You may play me to an open battlefield.
    "Ocean Drake": PERM_OPEN,
    "Sneaky Deckhand": PERM_OPEN,
    "Sai Scout": PERM_OPEN,
    # ...and her SECOND sentence gives the same permission to everything else
    # you play (`ST_PLAY_OPEN` in STATICS). Both are needed and neither is
    # redundant: this one is how she reaches an open battlefield herself, when
    # she is still in hand and her own static is not yet on the board.
    "Miss Fortune - Buccaneer": PERM_OPEN,
    # "You may play me to an occupied enemy battlefield." -- straight into a
    # fight: both players' units present means the Cleanup stages a Combat.
    "Deadbloom Predator": PERM_OCCUPIED_ENEMY,
    "Dauntless Vanguard": PERM_OCCUPIED_ENEMY,
    # [Reaction] [Assault 2] I can be played to a battlefield you're attacking.
    # Its own reminder text spells the timing out -- "play any time, even
    # before spells and abilities resolve" -- so unlike the Trophy Hunter this
    # is a Reaction rather than an Ambush, and it reinforces an attack you have
    # already committed to rather than starting one.
    "Rengar - Pouncing": PERM_ATTACK,
    # "I can be played to an occupied battlefield if an enemy unit is alone
    # there." (Arachnoid Horror; the grant to friendly units is a static.)
    "Arachnoid Horror": PERM_ENEMY_ALONE,
}

# "You may play me to ITS BATTLEFIELD" -- Stalking Wolf, where "it" is the
# `cost_kill` target this same play just killed. Unlike every entry in
# `PLAY_PERMISSIONS`, this destination is not a fixed property of a
# battlefield the enumerator can check per-slot; it is READ from
# `state.pend_kill_play_loc`, which `actions._choose_unit_cost_kill_target`
# sets the instant the cost is paid -- see `actions.play_destinations`.
PLAY_TO_COST_KILL_LOC: frozenset[str] = frozenset({"Stalking Wolf"})

# "Your [Deathknell] effects trigger an additional time." (Karthus - Eternal)
# Read by `combat._destroy` as Death triggers are queued: one extra queue per
# copy the dying card's controller has. The card's whole text, so membership
# is what `decks.plays_as_printed` credits.
DEATHKNELL_DOUBLERS: frozenset[str] = frozenset({"Karthus - Eternal"})

# "As you look at or reveal me from the top of your deck, you may banish me.
# If you do, you may play me for {any rune}." -- Nocturne, Horrifying.
#
# **Read the ERRATA text, not the printed one.** `data/cards.json` still prints
# "when you look at cards ... and see me, you may play me", which is a different
# card: no banish, and no "or reveal". `data/errata.json` supersedes it and
# `cardtable.full_table` applies the overlay -- see `_raw_cards`.
#
# A PERMISSION, not a triggered ability, and it is modelled the way [Hidden]'s
# permission is (811.1.b): the player exercises it during the window the look is
# already suspended in, so there is nothing for the Chain to hold and nothing to
# resolve. Routing it through a trigger would need an ability that fires,
# suspends, waits for a destination and a payment, and then unwinds back into
# the look -- all to express "here is an extra legal action while you are
# looking".
#
# The value is the [A] count: the cost is Power of any Domain (163.2.b), so it
# RECYCLES a rune rather than exhausting one -- see `cost.plan_wild_power`.
#
# Two branches of the errata are deliberately NOT offered, and both are
# dominated rather than unimplemented:
#
#   banish, then decline to play   Costs the card and buys nothing. It only
#                                  differs from declining outright by taking
#                                  him out of the deck, which no card in the
#                                  pool rewards.
#   "or REVEAL"                    There is no reveal-from-deck path distinct
#                                  from a look yet -- `TR_REVEALED_FROM_DECK`
#                                  fires inside `OP_LOOK_TOP` -- so the look
#                                  site is currently exhaustive. When one
#                                  appears (Teemo - Strategist reveals five),
#                                  it must offer this too.
PLAY_FROM_LOOK: dict[str, int] = {"Nocturne - Horrifying": 1}


def play_from_look_cost(table, card: int) -> int:
    """The [A] cost to play `card` out of a look buffer, or -1 if it cannot be.

    -1 rather than 0 because 0 is a real answer: a card could print "play me
    for free", and "free" must not read as "not allowed".
    """
    return PLAY_FROM_LOOK.get(table.names[card], -1)


# 827.1.c.1 caps Empower at once per permanent ("use only if not Empowered"),
# and that is the default every card in the pool but this one takes. Kayle,
# Justified prints "I can be [Empowered] up to three times" and her reminder
# text pointedly omits the restriction, so the cap is a card property rather
# than a rule constant.
EMPOWER_LIMIT: dict[str, int] = {"Kayle, Justified": 3}

# "When my Might becomes 10 or more, empower me." (Renekton, Brute) -- checked
# with the Mighty transitions; empowering is idempotent, so the check is just
# "10+ and not Empowered".
EMPOWER_AT_MIGHT: dict[str, int] = {"Renekton, Brute": 10}

# "My hold effects are also conquer effects, and vice versa." (Skyfall of
# Areion) -- on the unit it is attached to, read at both queue sites.
HOLD_CONQUER_SWAP: frozenset[str] = frozenset({"Skyfall of Areion"})
# Cards whose activated-ability Power is {any rune} rather than their domain.
ANY_RUNE_ABILITY_COSTS: frozenset[str] = frozenset({"Glowstone", "Dominus"})
# "Opponents must pay {any rune} for each unit beyond the first to move
# multiple units to my battlefield at the same time." (Mageseeker
# Investigator) -- charged on a declared Move's commit.
MOVE_TAXERS: frozenset[str] = frozenset({"Mageseeker Investigator"})
# "I can have any number of buffs." (Lee Sin - Ascetic) -- `state.extra_buffs`.
MULTI_BUFF: frozenset[str] = frozenset({"Lee Sin - Ascetic"})
# An Equipment whose "Attached:" band grants its unit a TAG ("I am a Mech",
# Experimental Hexplate): name -> tag.
EQUIP_GRANTS_TAG: dict[str, str] = {"Experimental Hexplate": "Mech"}
# "While I'm at a battlefield, opponents can't play spells with that name."
# (Fallen Feline)
NAMED_SPELL_LOCKS: frozenset[str] = frozenset({"Fallen Feline"})
# Cards whose transcription runs part of their text and knowingly not the rest
# -- kept OUT of the coverage number by `decks.plays_as_printed` however much
# of the card is scripted. Baron Nashor's Baron Pit is a third battlefield.
PARTIAL_TRANSCRIPTIONS: frozenset[str] = frozenset({
    # Legends and battlefields, whose coverage number `decks.plays_as_printed`
    # does not count anyway -- listed here so the caveat has one home:
    #   Lucian - Purifier          "your Equipment EACH give [Assault]" is one
    #                              instance per equipped unit, not per gear.
    #   Nasus - Curator of the...  the "activated ability with Energy cost 7+"
    #                              half: TR_PLAY_UNIT sees permanents only.
    #   Renata Glasc - Chem-...    "your Gold [Add] an additional {1 energy}"
    #                              modifies the TOKEN's ability, which nothing
    #                              can reach.
    #   Sett - The Boss            the death replacement that charges a cost at
    #                              the moment of death; his Conquer half is in.
    #   Teemo - Swift Scout        the hide-cost substitution, and the Champion
    #                              Zone half of his return.
    #   Hallowed Tomb              returns the champion to HAND: the Champion
    #                              Zone (107.5) is not modelled.
    "Lucian - Purifier", "Nasus - Curator of the Sands",
    "Renata Glasc - Chem-Baroness", "Sett - The Boss", "Teemo - Swift Scout",
    "Hallowed Tomb",
})
# Cards that add the Baron Pit as they are played (Baron Nashor) -- read at
# every permanent play site through `combat.baron_pit_entry`.
BARON_PIT_MAKERS: frozenset[str] = frozenset({"Baron Nashor"})
# Battlefields units may move to from anywhere (187.9, the Baron Pit).
BF_MOVE_FROM_ANYWHERE: frozenset[str] = frozenset({"Baron Pit"})
# "If you would reveal cards from a deck, look at the top card first. You may
# recycle it. Then reveal those cards." (Void Hatchling) -- before a reveal op
# on its controller's own deck, resolution pauses for that look and resumes at
# the reveal (`state.resume_*`). Revealing the OPPONENT's deck (Blind Fury)
# does not pause: the look machinery reads the looker's own deck.
REVEAL_PEEKERS: frozenset[str] = frozenset({"Void Hatchling"})
# "Friendly units played from anywhere other than a player's hand have
# [Accelerate]." (Rek'Sai - Breacher) -- offered, at {1 energy} plus a rune of
# the unit's domain, on the reveal-play destination choice (reveals, Undying
# Legion, Cursed Sarcophagus). Plays that choose no destination (a trash
# reanimation to base, a facedown unit) are not offered it.
NONHAND_ACCELERATE: frozenset[str] = frozenset({"Rek'Sai - Breacher"})
# "As this is attached to a unit, copy that unit's text to this Equipment's
# effect text" (Svellsongur) -- the unit's abilities, statics and keywords
# counted a second time while it is attached.
TEXT_COPIERS: frozenset[str] = frozenset({"Svellsongur"})
# "As this is attached to a unit, choose another friendly unit. The equipped
# unit becomes a copy of that unit for as long as this is attached to it."
# (Shady Spectacles)
COPY_ON_ATTACH: frozenset[str] = frozenset({"Shady Spectacles"})


_TAG_VOCAB: list = []


def tag_vocab(table) -> list:
    """Every tag in the card pool, sorted -- the index a named tag is stored as."""
    if not _TAG_VOCAB:
        _TAG_VOCAB.extend(sorted({t for c in range(table.n) for t in table.tags[c]}))
    return _TAG_VOCAB
# "[Legion] You may play me from your trash for {3 energy}{Fury rune}."
# (Undying Legion) -- name -> (energy, power); offered as A_PLAY_FLOW only
# while [Legion] holds, then placed through the reveal-play decision.
TRASH_UNIT_PLAY: dict[str, tuple[int, int]] = {"Undying Legion": (3, 1)}
# "This ability's Energy cost is reduced by the Might of the unit you choose."
# (Hextech Gauntlets' [Equip]) -- applied at finalization, once the unit is
# chosen. Still only OFFERED when the full cost is affordable.
EQUIP_LESS_CHOSEN_MIGHT: frozenset[str] = frozenset({"Hextech Gauntlets"})
# "Your opponents' [Hidden] cards can't be revealed here." (Noxus Saboteur)
# -- an opponent cannot play a facedown card at its battlefield.
HIDDEN_LOCKS: frozenset[str] = frozenset({"Noxus Saboteur"})
# [Empowered] "Your spells and abilities can't be countered. If a spell or
# ability you control would give -Might to a unit it chooses, it gives an
# additional -1 Might." (Mel, Newly Awakened)
EMPOWERED_SPELL_WARD: frozenset[str] = frozenset({"Mel, Newly Awakened"})
# [Empowered] "If a spell or ability that chooses me would stun me, give me
# -Might, or return me to hand, give me +3 Might this turn instead."
# (Gangplank, Naval)
EMPOWERED_CHOSEN_TO_MIGHT: frozenset[str] = frozenset({"Gangplank, Naval"})

# "This costs {2 energy} less if you choose a Bird, Cat, Dog, or Poro."
# (Undying Loyalty) -- a trash-card target's tags, read at finalization. Offered
# when only the discounted cost is affordable, and then only the qualifying
# choices are offered (`chain.tag_discount_targets`, RiftJudge #9780).
TRASH_TAG_DISCOUNT: dict[str, tuple[int, tuple[str, ...]]] = {
    "Undying Loyalty": (2, ("Bird", "Cat", "Dog", "Poro"))}

# "I cost {2 energy} less to play from anywhere other than your hand." (Void
# Drone, Drag Under) -- read by `cost.effective_energy` while a trash play is
# being costed (`cost.NONHAND`).
NONHAND_DISCOUNT: dict[str, int] = {"Void Drone": 2, "Drag Under": 2}


def empower_limit(table, card: int) -> int:
    """How many times `card` may be Empowered. 827.1.c.1 says once."""
    return EMPOWER_LIMIT.get(table.names[card], 1)


_SLOT_OP_FIELDS = ("target", "target_b", "loc_of_target", "n_from_might",
                   "n_from_spell_energy", "n_from_assault", "n_from_damage",
                   "except_target", "at", "cond_slot", "less_might_than_slot")
_SLOT_TS_FIELDS = ("rel_to", "distinct_from", "less_might_than", "move_dest_of",
                   "dest_has_ally_of", "same_ctrl_as")
MODE_SLOT = TargetSpec(kind=TK_MODE, locality=LOC_FREE)


def _shift(obj, fields, k: int):
    return obj._replace(**{f: getattr(obj, f) + k for f in fields
                           if getattr(obj, f) >= 0})


def compose_mode(spec, m: int):
    """The spec a modal card or ability resolves with once mode `m` is chosen:
    the TK_MODE slot, then the mode's own slots renumbered from 1."""
    mode = spec.modes[m]
    return spec._replace(
        targets=(MODE_SLOT,) + tuple(_shift(t, _SLOT_TS_FIELDS, 1)
                                     for t in mode.targets),
        ops=tuple(_shift(o, _SLOT_OP_FIELDS, 1) for o in mode.ops))


def _repeat_modes(base: tuple, costs: tuple):
    """Every [Repeat] combination of "choose one you haven't already chosen":
    each non-empty subset of `base` (resolved in order) as one mode, with the
    Repeat costs it takes -- one per extra execution, every assignment of the
    printed costs for that count. Returns (modes, mode_costs)."""
    from itertools import combinations, permutations
    modes, mcosts = [], []
    for size in range(1, len(base) + 1):
        for subset in combinations(range(len(base)), size):
            targets, ops = [], []
            for m in subset:
                off = len(targets)
                targets += [t._replace(allow_repeat=True) for t in base[m].targets]
                ops += [_shift(o, _SLOT_OP_FIELDS, off) for o in base[m].ops]
            spent = set()
            for pick in combinations(range(len(costs)), size - 1):
                e = sum(costs[i][0] for i in pick)
                p = sum(costs[i][1] for i in pick)
                if (e, p) in spent:
                    continue
                spent.add((e, p))
                modes.append(CardSpec(SPEED_MAIN, targets=tuple(targets),
                                      ops=tuple(ops)))
                mcosts.append((e, p))
    return tuple(modes), tuple(mcosts)


def modal(speed: int, *modes, **kw) -> CardSpec:
    return CardSpec(speed=speed, targets=(MODE_SLOT,), modes=tuple(modes), **kw)


SPECS: dict[str, CardSpec] = {

    # [Reaction] Give a unit -1 Might this turn, to a minimum of 1 Might. Draw 1.
    # The most-played spell in the corpus: 57 slots across 19 of 29 decks.
    "Stupefy": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-1, floor=1),
             Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Give a unit +2 Might this turn. Draw 1.
    "Discipline": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
             Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Give a unit -4 Might this turn, to a minimum of 1 Might.
    "Smoke Screen": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-4, floor=1),),
    ),

    # [Reaction] Counter a spell. Its controller can't play spells this turn.
    #
    # **"A spell" is exactly a spell.** Not a unit -- 337.2 resolves those
    # immediately and they never become a Chain Item, so there is nothing to
    # counter and this is not a Magic-style "counter target spell" that stops a
    # creature. And not an ability either: abilities do sit on the Chain
    # (383.3), so `chain_abilities` has to be opted into, and only Not So Fast
    # and Repulse ("spell or ability") print the words that would.
    # Deal 4 to a unit at a battlefield. If you control 7 or more runes, deal 7
    # to it instead. When it dies this turn, channel 1 rune exhausted.
    # The mark goes on FIRST so a death to this very damage counts.
    "Siphoning Strike": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_MARK, target=0),
             Op(OP_DAMAGE, target=0, n=4, cond=COND_RUNES_BELOW, level=7),
             Op(OP_DAMAGE, target=0, n=7, cond=COND_RUNES_AT_LEAST, level=7)),
    ),

    # Deal 3 to an enemy unit. When it dies this turn, play a Gold gear token
    # exhausted.
    "Deadly Flourish": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY),),
        ops=(Op(OP_MARK, target=0), Op(OP_DAMAGE, target=0, n=3)),
    ),

    # [Action] Give a friendly unit +3 Might this turn. When it wins a combat
    # this turn, gain 2 XP.
    "Grim Resolve": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=3), Op(OP_MARK, target=0)),
    ),

    # [Reaction] Choose a friendly unit. The next time it would die this turn,
    # heal it, exhaust it, and recall it instead.
    "Tactical Retreat": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_DEATH_SHIELD, target=0),),
    ),
    "Highlander": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_DEATH_SHIELD, target=0),),
    ),

    # [Action] Choose a unit. Kill it the next time it takes damage this turn.
    # [Legion] -- Kill it now instead.
    "Noxian Guillotine": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_KILL, target=0, cond=COND_LEGION),
             Op(OP_GUILLOTINE, target=0, cond=COND_NOT_LEGION)),
    ),

    # [Reaction] Give a unit +1 Might this turn.
    # [Level 6][>] Give it +3 Might this turn instead.
    "Combat Experience": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1, cond=COND_BELOW_LEVEL, level=6),
             Op(OP_MODIFY_MIGHT, target=0, n=3, cond=COND_LEVEL, level=6)),
    ),

    # Draw 2.  [Level 6] costs {2 energy} less; [Level 11] {4 energy} less
    # instead. (STATICS)
    "Concentrate": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_DRAW, n=2),),
    ),

    # [Action] Deal 2 to a unit at a battlefield. If you control a facedown
    # card, deal 4 to it instead.
    "Monster Harpoon": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=2, cond=COND_NO_FACEDOWN),
             Op(OP_DAMAGE, target=0, n=4, cond=COND_FACEDOWN_AT_BF)),
    ),

    # [Hidden] [Action] Deal 2 to a unit at a battlefield. If it's attacking,
    # deal 4 to it instead.
    "Sudden Storm": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=2, cond=COND_TARGET_NOT_ATTACKING),
             Op(OP_DAMAGE, target=0, n=4, cond=COND_TARGET_ATTACKING)),
    ),

    # [Action] [Repeat] {2 energy}  [Stun] an attacking enemy unit. If it's
    # already stunned, return it to its owner's hand instead.
    # Return first: stunning first would make "already stunned" true. With the
    # Repeat paid, the second pass returns the unit the first pass stunned.
    "Existential Dread": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ENEMY, attacking=True),),
        ops=(Op(OP_RETURN_TO_HAND, target=0, cond=COND_TARGET_STUNNED),
             Op(OP_STUN, target=0, cond=COND_TARGET_NOT_STUNNED)),
    ),

    # [Action] Deal 2 to a unit at a battlefield. This deals 1 Bonus Damage for
    # each card with this name in your trash.
    "Consuming Curse": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=2, plus_same_name_trash=True),),
    ),

    # Choose a friendly unit and a battlefield. Move all enemy units at that
    # battlefield with less Might than the chosen unit to their base. Gain 1 XP.
    "Stare Down": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),
                 TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY)),
        ops=(Op(OP_MOVE_ALL_TO_BASE, at=1, who=W_ENEMY, less_might_than_slot=0),
             Op(OP_GAIN_XP, n=1)),
    ),

    # [Reaction] Ignore [Deflect] while paying this spell's cost. Give an enemy
    # Body unit -5 Might this turn.
    "Decree of Insight": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ENEMY, domain=0),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-5),),
        ignore_deflect=True,
    ),

    # [Reaction] Choose a friendly unit. This turn, increase its Might to the
    # Might of another friendly unit.
    "Convergent Mutation": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_FRIENDLY, distinct_from=0, locality=LOC_FREE)),
        ops=(Op(OP_MIGHT_UP_TO, target=1, target_b=0),),
    ),

    # [Reaction] Choose a friendly unit and a spell. Counter that spell and give
    # that unit +Might equal to that spell's Energy cost this turn.
    # The Might is written first so the Energy cost is read while the spell is
    # still on the Chain; the two happen together either way.
    "Riposte": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(kind=TK_SPELL, who=W_ANY)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n_from_spell_energy=1),
             Op(OP_COUNTER, target=1)),
    ),

    # [Action] This spell's Energy cost is reduced by the highest Might among
    # units you control. (STATICS)  Deal 5 to a unit at a battlefield.
    "Sky Splitter": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=5),),
    ),

    # Move an enemy unit. Then do this: Choose another enemy unit at its
    # destination. They deal damage equal to their Mights to each other.
    # The second enemy is chosen with the rest, related to the destination
    # slot, and optional -- with nobody there the move still happens.
    "Dragon's Rage": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE,
                            move_dest_of=0),
                 TargetSpec(who=W_ENEMY, rel=REL_SAME_BF, rel_to=1,
                            distinct_from=0, optional=True, locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),
             Op(OP_FIGHT, target=0, target_b=2)),
    ),

    # Ready a unit and give it [Assault 3] this turn.  [Flow] {3 energy}{Fury}
    "Perfect Execution": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_READY, target=0),
             Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=3)),
    ),

    # [Action] Give a unit [Assault 2] and [Ganking] this turn.
    "Vault Breaker": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=2),
             Op(OP_GRANT_KEYWORD, target=0, keyword="Ganking")),
    ),

    # Move a unit with 3 Might or less.  [Flow] {4 energy}{Chaos}
    "Twilight Step": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, max_might=3),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE,
                            move_dest_of=0)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),),
    ),

    # [Action] Double a friendly unit's Might this turn. Give it [Temporary].
    # "Double" is +Might equal to its current effective Might; the Temporary
    # is not "this turn" -- it is what kills the unit next Beginning Phase.
    "Last Stand": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n_from_might=0),
             Op(OP_GRANT_KEYWORD, target=0, keyword="Temporary",
                grant_this_turn=False)),
    ),

    # [Action] Ready a friendly unit. It deals damage equal to its Might to an
    # enemy unit at a battlefield.
    "Last Breath": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_ENEMY, at_battlefield=True)),
        ops=(Op(OP_READY, target=0),
             Op(OP_DAMAGE, target=1, n_from_might=0)),
    ),

    # [Action] Give a friendly unit +3 Might this turn. Then choose an enemy
    # unit. They deal damage equal to their Mights to each other.
    "Gentlemen's Duel": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY), TargetSpec(who=W_ENEMY)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),
             Op(OP_FIGHT, target=0, target_b=1)),
    ),

    # [Action] [Repeat] {3 energy}  Choose a friendly unit anywhere and an
    # enemy unit at a battlefield. They deal damage equal to their Mights to
    # each other.
    "Marching Orders": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),
                 TargetSpec(who=W_ENEMY, at_battlefield=True)),
        ops=(Op(OP_FIGHT, target=0, target_b=1),),
    ),

    # Choose a unit. If it's [Empowered], disempower it. Then kill it if it has
    # 3 Might or less.  [Flow] {4 energy}{Order}{Order}
    "Lacerate": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DISEMPOWER, target=0, cond=COND_TARGET_EMPOWERED),
             Op(OP_KILL, target=0, cond=COND_TARGET_MAX_MIGHT, level=3)),
    ),

    # [Reaction] Choose a battlefield. Give friendly units there +1 Might this
    # turn and enemy units there -1 Might this turn, to a minimum of 1 Might.
    "Siphon Power": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT_ALL, n=1, at=0, who=W_FRIENDLY),
             Op(OP_MODIFY_MIGHT_ALL, n=-1, at=0, who=W_ENEMY, floor=1)),
    ),

    # Choose a friendly unit in your base. Deal damage equal to its Might to
    # all enemy units at a battlefield, then move your unit there.
    "Stormbringer": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY, at_base=True),
                 TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY)),
        ops=(Op(OP_DAMAGE_ALL, at=1, who=W_ENEMY, n_from_might=0),
             Op(OP_MOVE_TO, target=0, target_b=1)),
    ),

    # Move a friendly unit, then move an enemy unit.
    "Void Assault": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE,
                            move_dest_of=0),
                 TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE,
                            move_dest_of=2)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),
             Op(OP_MOVE_TO, target=2, target_b=3)),
    ),

    # [Hidden]  Friendly units enter ready this turn. Play a Gold gear token
    # exhausted.
    "Bushwhack": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_UNITS_ENTER_READY),
             Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1, token=GOLD_TOKEN)),
    ),

    # [Reaction] Prevent all spell and ability damage this turn.
    "Unyielding Spirit": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_PREVENT_EFFECT_DAMAGE),),
    ),

    # [Reaction] Choose a unit. Give it +1 Might this turn for each of the
    # following tags among your units -- Bird, Cat, Dog, and Poro.
    "Friendship": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1, n_from_count=CT_ANIMAL_TAGS),),
    ),

    # This costs {2 energy} less if you control a Mech. (STATICS)
    # Play a 3 Might Mech unit token to your base. Draw 1.
    "Production Surge": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_DRAW, n=1),
             Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1, token=MECH_TOKEN)),
    ),

    # [Action] This costs {2 energy} less if you control something that's
    # [Empowered]. (STATICS)  Deal 4 to a unit at a battlefield.
    "Shock Blast": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=4),),
    ),

    # [Reaction] If an enemy unit has died this turn, this costs {2 energy}
    # less. (STATICS)  Draw 2.
    "Spoils of War": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=2),),
    ),

    # [Reaction] Choose one -- Empower a unit. Disempower it at end of turn. /
    # Disempower a unit that's [Empowered]. Empower it at end of turn.
    "Sanction": modal(
        SPEED_REACTION,
        CardSpec(SPEED_REACTION, targets=(TargetSpec(who=W_ANY),),
                 ops=(Op(OP_EMPOWER, target=0, eot_revert=True),)),
        CardSpec(SPEED_REACTION,
                 targets=(TargetSpec(who=W_ANY, must_be_empowered=True),),
                 ops=(Op(OP_DISEMPOWER, target=0, eot_revert=True),))),

    # [Hidden] [Action] Buff a friendly unit. Buffs give an additional +1 Might
    # to friendly units this turn.
    "Stand United": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_BUFF_BONUS_TURN), Op(OP_BUFF, target=0)),
    ),

    # Choose a unit. Its base Might becomes 5 this turn.  [Flow] {3 energy}
    "Dragon Form": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_BASE_MIGHT, target=0, n=5),),
    ),

    # Move an enemy unit.  [Level 6] [Stun] an enemy unit.
    # The stun's slot exists only at Level 6 (`level_gate`), so below it the
    # card asks nothing more than the move.
    "Skyward Strike": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE, move_dest_of=0),
                 TargetSpec(who=W_ENEMY, level_gate=6, locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1), Op(OP_STUN, target=2)),
    ),

    # Move an enemy unit to a battlefield where you have units. If you have
    # exactly two units there, they each get +1 Might this turn.
    # [Flow] {5 energy}{any rune}{any rune}
    "Shadow Dash": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY, needs_own_units=True,
                            locality=LOC_FREE, move_dest_of=0)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),
             Op(OP_MODIFY_MIGHT_ALL, n=1, at=1, who=W_FRIENDLY,
                cond=COND_FRIENDLY_COUNT_AT_SLOT, cond_slot=1, level=2)),
    ),

    # [Repeat] {2 energy}  Move an enemy unit to a location where there's a unit
    # with the same controller.
    "Temptation": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE, move_dest_of=0,
                            dest_has_ally_of=0)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),),
    ),

    # Give a unit at a battlefield or a gear [Temporary].
    "Fading Memories": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, card_type=("Unit", "Gear"),
                            unit_at_battlefield=True),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Temporary",
                grant_this_turn=False),),
    ),

    # [Action] Choose an enemy unit at a battlefield. Take control of it and
    # recall it.
    "Possession": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
        ops=(Op(OP_TAKE_CONTROL, target=0, to_base=True),),
    ),

    # [Hidden] Take control of an enemy unit at a battlefield. Ready it. Lose
    # control of that unit and recall it at end of turn.
    "Hostile Takeover": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
        ops=(Op(OP_TAKE_CONTROL, target=0, then_ready=True, eot_revert=True),),
    ),

    # --- "Choose one --" --------------------------------------------------
    # [Reaction] Choose one -- Counter a spell. / Play four 1 Might Bird unit
    # tokens with [Deflect].
    "Flurry of Feathers": modal(
        SPEED_REACTION,
        CardSpec(SPEED_REACTION, targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
                 ops=(Op(OP_COUNTER, target=0),)),
        # No location: base or a battlefield you control (184.2, FAQ #4020).
        CardSpec(SPEED_REACTION, targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
                 ops=(Op(OP_CREATE_TOKEN, target=0, n=4,
                         token=BIRD_TOKEN),))),

    # [Reaction] Choose one -- Return a friendly unit to its owner's hand. /
    # Give an enemy unit -2 Might this turn.
    "Mesmerize": modal(
        SPEED_REACTION,
        CardSpec(SPEED_REACTION, targets=(TargetSpec(who=W_FRIENDLY),),
                 ops=(Op(OP_RETURN_TO_HAND, target=0),)),
        CardSpec(SPEED_REACTION, targets=(TargetSpec(who=W_ENEMY),),
                 ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2),))),

    # [Reaction] Choose one -- Choose up to 3 cards from opponents' trashes.
    # Their owners recycle them. / Draw 1.
    "Disposal Order": modal(
        SPEED_REACTION,
        CardSpec(SPEED_REACTION,
                 targets=tuple(TargetSpec(kind=TK_TRASH_CARD, who=W_ENEMY,
                                          optional=True, locality=LOC_FREE)
                               for _ in range(3)),
                 ops=tuple(Op(OP_RECYCLE_FROM_TRASH, target=k)
                           for k in range(3))),
        CardSpec(SPEED_REACTION, ops=(Op(OP_DRAW, n=1),))),

    # [Repeat] {4 energy}{Mind}  Choose one -- Deal 4 to a unit in a base. /
    # Kill a gear.  (The engine's Repeat re-runs the same choices.)
    "Rocket Barrage": modal(
        SPEED_MAIN,
        CardSpec(SPEED_MAIN, targets=(TargetSpec(who=W_ANY, at_base=True),),
                 ops=(Op(OP_DAMAGE, target=0, n=4),)),
        CardSpec(SPEED_MAIN, targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),),
                 ops=(Op(OP_KILL, target=0),))),

    # Deal 2 to a unit. (x6)  Each is its own choice, so the same unit may be
    # chosen more than once.
    "Icathian Rain": CardSpec(
        speed=SPEED_MAIN,
        targets=tuple(TargetSpec(who=W_ANY, allow_repeat=True) for _ in range(6)),
        ops=tuple(Op(OP_DAMAGE, target=k, n=2) for k in range(6)),
    ),

    # Return any number of enemy Order units with total Might 5 or less to their
    # owners' hands.  "Any number" is capped at four slots.
    "Decree of Discord": CardSpec(
        speed=SPEED_MAIN,
        targets=tuple(TargetSpec(who=W_ENEMY, domain=5, optional=True,
                                 max_total_might=5) for _ in range(4)),
        ops=tuple(Op(OP_RETURN_TO_HAND, target=k) for k in range(4)),
    ),

    # Move any number of enemy units with the same controller and a total Might
    # of 8 or less to a single location.  (Three unit slots, then the place.)
    "Tricksy Tentacles": CardSpec(
        speed=SPEED_MAIN,
        targets=tuple(TargetSpec(who=W_ENEMY, optional=True, max_total_might=8)
                      for _ in range(3))
        + (TargetSpec(kind=TK_LOCATION, who=W_ENEMY, locality=LOC_FREE),),
        ops=tuple(Op(OP_MOVE_TO, target=k, target_b=3) for k in range(3)),
    ),

    # [Hidden] [Action] Move any number of friendly units at a battlefield to
    # their base.  (Four slots, all at the first one's battlefield.)
    "Emperor's Divide": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True, optional=True),)
        + tuple(TargetSpec(who=W_FRIENDLY, at_battlefield=True, optional=True,
                           rel=REL_SAME_BF, rel_to=0) for _ in range(3)),
        ops=tuple(Op(OP_MOVE_TO, target=k, target_b=T_OWNER_BASE) for k in range(4)),
    ),

    # [Action] As an additional cost to play this, you may discard 1. Deal 3
    # to a unit at a battlefield. If you paid the additional cost, deal 5 to
    # it instead.
    "Ruthless Strike": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        opt_cost_discard=1,
        ops=(Op(OP_DAMAGE, target=0, n=3, cond=COND_NOT_PAID_ADDITIONAL),
             Op(OP_DAMAGE, target=0, n=5, cond=COND_PAID_ADDITIONAL)),
    ),

    # You may spend 5 XP as an additional cost to play this. Choose an enemy
    # unit at a battlefield with 3 Might or less. If you paid the additional
    # cost, choose any enemy unit at a battlefield instead. Take control of
    # it, exhaust it, and recall it.
    "Conscription": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True, max_might=3),),
        paid_targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
        opt_cost_xp=5,
        ops=(Op(OP_TAKE_CONTROL, target=0, to_base=True, then_exhaust=True),),
    ),

    # [Reaction] As an additional cost to play this, you may exhaust a
    # friendly unit. If you do, draw 2. Otherwise, draw 1.
    "Meditation": CardSpec(
        speed=SPEED_REACTION,
        cost_kill=TargetSpec(who=W_FRIENDLY, must_be_ready=True),
        cost_kill_optional=True, cost_exhaust_unit=True,
        ops=(Op(OP_DRAW, n=2, cond=COND_PAID_ADDITIONAL),
             Op(OP_DRAW, n=1, cond=COND_NOT_PAID_ADDITIONAL)),
    ),

    # As you play this, you may pay {Body rune} as an additional cost. Choose
    # a friendly unit and an enemy unit. If you paid the additional cost, give
    # the friendly unit +2 Might this turn. They deal damage equal to their
    # Mights to each other.
    "Rampage": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY), TargetSpec(who=W_ENEMY)),
        opt_cost_power=1,
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2, cond=COND_PAID_ADDITIONAL),
             Op(OP_FIGHT, target=0, target_b=1)),
    ),

    # [Reaction] As you play this, you may spend a buff as an additional cost.
    # If you do, ignore this spell's cost. Give a unit +3 Might this turn.
    "Call to Glory": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        cost_kill=TargetSpec(who=W_FRIENDLY, must_be_buffed=True),
        cost_kill_optional=True, cost_spend_buff=True, paid_ignores_cost=True,
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),),
    ),

    # [Action] As you play this, you may spend a buff as an additional cost.
    # If you do, ignore this spell's cost. Ready a unit.
    "Wallop": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        cost_kill=TargetSpec(who=W_FRIENDLY, must_be_buffed=True),
        cost_kill_optional=True, cost_spend_buff=True, paid_ignores_cost=True,
        ops=(Op(OP_READY, target=0),),
    ),

    # [Repeat] -- Discard 1. Give a unit [Assault 4] this turn.  (The Repeat
    # cost is a discard, so it rides the optional-cost path: paying it grants
    # the keyword a second time.)
    "Square Up": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        opt_cost_discard=1,
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=4),
             Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=4,
                cond=COND_PAID_ADDITIONAL)),
    ),

    # This costs {2 energy} less if you choose a Bird, Cat, Dog, or Poro
    # (TRASH_TAG_DISCOUNT). Play a unit with cost no more than {2 energy} and
    # no more than {any rune} from your trash, ignoring its cost.
    "Undying Loyalty": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                            card_type=("Unit",), max_energy=2, max_power=1,
                            playable=True, playable_cost=COST_FREE),),
        ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=T_MY_BASE,
                cost=COST_FREE),),
    ),

    # [Action] Move a friendly unit. You may attach up to one Equipment with
    # the same controller to it. This turn, that unit has "When I conquer, you
    # may move me to my base."  (The granted trigger is a marked Delayed
    # Ability.)
    "Relentless Pursuit": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),
                 TargetSpec(kind=TK_LOCATION, move_dest_of=0, locality=LOC_FREE),
                 TargetSpec(who=W_ANY, card_type=("Gear",), tags=("Equipment",),
                            same_ctrl_as=0, optional=True, locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),
             Op(OP_ATTACH, target=0, target_b=2),
             Op(OP_MARK, target=0)),
    ),

    # [Action] Choose a friendly unit. It deals damage equal to its Might split
    # among enemy units at battlefields. Then for each unit this kills, do
    # this: Gain 1 XP.
    "Alpha Strike": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_SPLIT_DAMAGE, n_from_might=0, xp_per_kill=True),),
    ),

    # Choose a unit. Play a ready Reflection unit token to your base. Then do
    # this: It becomes a copy of that unit. Give it [Temporary].
    "Mirror Image": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_COPY_PREP, target=0),
             Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1, token=REFLECTION_TOKEN,
                ready=True, then_key=FU_BECOME_COPY_TEMP)),
    ),

    # Deal 2 to a unit. Its controller may play this spell again for {any
    # rune}. If they do, this deals 1 additional Bonus Damage for each time
    # this spell has dealt damage this turn.
    "Dancing Grenade": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DAMAGE, target=0, n=2, grenade_bonus=True),
             Op(OP_ASK, target=0, power=1, domain=-1,
                then_key=FU_GRENADE_REPLAY)),
    ),

    # [Action] This turn, double a unit's Might and give it "{any rune}{any
    # rune}: Ready me."
    "Dominus": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n_from_might=0),
             Op(OP_GRANT_ABILITY, target=0)),
    ),

    # [Repeat] -- {1 energy} / {any rune} / {1 energy}{any rune}  Choose one
    # you haven't already chosen -- Draw 1. / Deal 2 to a unit at a
    # battlefield. / Deal 3 to a unit at a base. / Give a unit at a battlefield
    # -4 Might this turn.  (Each combination is one mode, priced by
    # `mode_costs`.)
    "Curtain Call": modal(
        SPEED_MAIN,
        *_repeat_modes(
            (CardSpec(SPEED_MAIN, ops=(Op(OP_DRAW, n=1),)),
             CardSpec(SPEED_MAIN, targets=(TargetSpec(at_battlefield=True),),
                      ops=(Op(OP_DAMAGE, target=0, n=2),)),
             CardSpec(SPEED_MAIN, targets=(TargetSpec(at_base=True),),
                      ops=(Op(OP_DAMAGE, target=0, n=3),)),
             CardSpec(SPEED_MAIN, targets=(TargetSpec(at_battlefield=True),),
                      ops=(Op(OP_MODIFY_MIGHT, target=0, n=-4),))),
            ((1, 0), (0, 1), (1, 1)))[0],
        mode_costs=_repeat_modes(
            (CardSpec(SPEED_MAIN, ops=(Op(OP_DRAW, n=1),)),
             CardSpec(SPEED_MAIN, targets=(TargetSpec(at_battlefield=True),),
                      ops=(Op(OP_DAMAGE, target=0, n=2),)),
             CardSpec(SPEED_MAIN, targets=(TargetSpec(at_base=True),),
                      ops=(Op(OP_DAMAGE, target=0, n=3),)),
             CardSpec(SPEED_MAIN, targets=(TargetSpec(at_battlefield=True),),
                      ops=(Op(OP_MODIFY_MIGHT, target=0, n=-4),))),
            ((1, 0), (0, 1), (1, 1)))[1],
    ),

    # [Reaction] Gain control of a spell. You may make new choices for it.
    "Mystic Reversal": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_STEAL_SPELL, target=0),),
    ),

    # [Reaction] Choose a spell with Energy cost no more than {4 energy}. You
    # may pay {any rune}. If you do, gain control of it and you may make new
    # choices for it. Otherwise, counter it.
    "Rebuttal": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY, max_energy=4),),
        ops=(Op(OP_STEAL_SPELL, target=0, power=1),),
    ),

    # Kill a unit at a battlefield. Then, if it had 3 Might or less, do this:
    # You may play this from your trash for {any rune}.
    "Death from Below": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_KILL, target=0),
             Op(OP_GRANT_FLOW, self_card=True, power=1, grant_this_turn=False,
                cond=COND_KILLED_MIGHT_AT_MOST, level=3)),
    ),

    # [Action] Pay any amount of {any rune} to deal that much damage to all
    # enemy units at a battlefield.  (Up to AMOUNT_CAP.)
    "Bullet Time": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, locality=LOC_FREE),),
        ops=(Op(OP_PAY_ANY_AMOUNT, target=0, n=AMT_DAMAGE_ENEMIES_AT),),
    ),

    # [Action] For each friendly unit, you may spend its buff to ready it.
    # Then buff all friendly units.  (Six slots.)
    "Overt Operation": CardSpec(
        speed=SPEED_ACTION,
        targets=tuple(TargetSpec(who=W_FRIENDLY, must_be_buffed=True,
                                 optional=True) for _ in range(6)),
        ops=tuple(o for k in range(6)
                  for o in (Op(OP_SPEND_BUFF, target=k), Op(OP_READY, target=k)))
        + (Op(OP_BUFF_ALL_AT, who=W_FRIENDLY),),
    ),

    # [Reaction] Choose a friendly unit that's in combat with an enemy Fury
    # unit or that's being chosen by an enemy Fury spell. Give it +4 Might
    # this turn.
    "Decree of Focus": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY, fury_threatened=True),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=4),),
    ),

    # [Reaction] Choose a friendly unit at a battlefield. Counter an enemy
    # spell or ability that chooses it and no other friendly unit.
    "Repulse": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),
                 TargetSpec(kind=TK_SPELL, who=W_ENEMY, chain_abilities=True,
                            chooses_only=0)),
        ops=(Op(OP_COUNTER, target=1),),
    ),

    # Choose an equipped friendly unit. It deals damage equal to its Might to
    # an enemy unit. Then detach an Equipment from it.
    "Strike Down": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY, equipped=True),
                 TargetSpec(who=W_ENEMY)),
        ops=(Op(OP_DAMAGE, target=1, n_from_might=0),
             Op(OP_DETACH_ONE, target=0)),
    ),

    # Move a unit you control to a battlefield you control. Then, choose an
    # opponent. They move a unit they control to the same battlefield.
    "Call to Battle": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(kind=TK_BATTLEFIELD, who=W_FRIENDLY, locality=LOC_FREE,
                            move_dest_of=0)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),
             Op(OP_EACH_KILLS_OWN, cull_mode=CULL_MOVE_OWN_TO, who=W_ENEMY,
                target_b=1)),
    ),

    # [Action] Discard 1. Deal its Energy cost as damage to a unit at a
    # battlefield. (Ignore its Power cost.)
    "Get Excited!": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DISCARD_CHOOSE, n=1, target=0,
                branch_key=DB_ENERGY_DAMAGE),),
    ),

    # [Action] I cost {2 energy} less to play from anywhere other than your
    # hand. (NONHAND_DISCOUNT)  Kill a unit at a battlefield.
    "Drag Under": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # [Hidden] [Action] You may play a unit from hand to a battlefield you
    # control, reducing its cost by {3 energy}.
    "Here to Help": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_PLAY_FROM_HAND, pick_types=("Unit",), pick_optional=True,
                cost=COST_PRINTED, n=3, target_b=-2, level=-1),),
    ),

    # [Hidden] [Action] Kill any number of units at a battlefield with total
    # Might 4 or less.  (Four slots, all at the first one's battlefield.)
    "Fox-Fire": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True, optional=True,
                            max_total_might=4),)
        + tuple(TargetSpec(who=W_ANY, at_battlefield=True, optional=True,
                           max_total_might=4, rel=REL_SAME_BF, rel_to=0)
                for _ in range(3)),
        ops=tuple(Op(OP_KILL, target=k) for k in range(4)),
    ),

    # Ready up to 4 units, gear, and/or runes.  (Up to four exhausted
    # permanents; runes take whatever is left.)
    "Acceleration Gate": CardSpec(
        speed=SPEED_MAIN,
        targets=tuple(TargetSpec(who=W_ANY, card_type=("Unit", "Gear"),
                                 must_be_exhausted=True, optional=True,
                                 locality=LOC_FREE) for _ in range(4)),
        ops=tuple(Op(OP_READY, target=k) for k in range(4))
        + (Op(OP_READY_RUNES, n=4, n_less_filled=True),),
    ),

    # You may kill a friendly gear as an additional cost to play me.
    "Zaun Punk": CardSpec(
        speed=SPEED_MAIN,
        cost_kill=TargetSpec(who=W_FRIENDLY, card_type=("Gear",)),
        cost_kill_optional=True,
    ),

    # You may kill a friendly unit as an additional cost to play me. If you do,
    # I cost {1 energy} less for each Energy it costs and {Order rune} less for
    # each Power it costs.
    "Atakhan": CardSpec(
        speed=SPEED_MAIN,
        cost_kill=TargetSpec(who=W_FRIENDLY),
        cost_kill_optional=True, cost_kill_discount=KD_KILLED_COST,
    ),

    # [Accelerate] [Assault]  As you play me, you may spend any number of buffs
    # as an additional cost. Reduce my cost by {Body rune} for each buff you
    # spend.
    "Kraken Hunter": CardSpec(
        speed=SPEED_MAIN,
        cost_kill=TargetSpec(who=W_FRIENDLY, must_be_buffed=True),
        cost_kill_optional=True, cost_spend_buff=True,
        cost_kill_discount=KD_POWER_EACH,
    ),

    # As you play me, you may kill any number of friendly units as an
    # additional cost. Reduce my cost by {Order rune} for each killed this way.
    "Commander Ledros": CardSpec(
        speed=SPEED_MAIN,
        cost_kill=TargetSpec(who=W_FRIENDLY),
        cost_kill_optional=True, cost_kill_discount=KD_POWER_EACH,
    ),

    # As an additional cost to play me, return a friendly gear to its owner's
    # hand.
    "Legion Quartermaster": CardSpec(
        speed=SPEED_MAIN,
        cost_kill=TargetSpec(who=W_FRIENDLY, card_type=("Gear",)),
        cost_return=True,
    ),

    # Choose an opponent. They reveal their hand and you choose a Mind card from
    # it. They recycle that card.
    "Decree of Strength": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_REVEAL_HAND, domain=4, pick_dest=DEST_RECYCLE),),
    ),

    # [Reaction] Choose a unit and an Equipment with the same controller.
    # Attach that Equipment to that unit or detach that Equipment from that
    # unit. Draw 1.
    "Angle Shot": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),
                 TargetSpec(who=W_ANY, card_type=("Gear",), tags=("Equipment",),
                            same_ctrl_as=0)),
        ops=(Op(OP_TOGGLE_ATTACH, target=0, target_b=1), Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Choose a unit. The next time that unit would be dealt damage
    # this turn, prevent it. Draw 1.
    "Counter Strike": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DAMAGE_SHIELD, target=0, n=-1), Op(OP_DRAW, n=1)),
    ),
    # [Reaction] Choose a unit. Prevent the next 7 damage that would be dealt
    # to it this turn.
    "Ki Barrier": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DAMAGE_SHIELD, target=0, n=7),),
    ),
    # [Hidden] [Reaction] Choose a unit. Double all damage that would be dealt
    # to it this turn.
    "Lotus Trap": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DOUBLE_DAMAGE, target=0),),
    ),
    # [Action] Deal 3 to a unit at a battlefield. If it would die this turn,
    # banish it instead.  (The replacement goes on first, so this very damage
    # banishes it.)
    "Smite": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_BANISH_ON_DEATH, target=0), Op(OP_DAMAGE, target=0, n=3)),
    ),
    # [Action] Banish a friendly unit, then its owner plays it, ignoring its
    # cost. Deal 3 to an enemy unit at a battlefield. Banish this.
    "Arcane Shift": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_ENEMY, at_battlefield=True)),
        ops=(Op(OP_BLINK, target=0, to_base=True), Op(OP_DAMAGE, target=1, n=3)),
        banish_self=True,
    ),
    # [Reaction] Banish a friendly unit, then its owner plays it to any
    # battlefield, ignoring its cost.
    "Thrill of the Hunt": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY, locality=LOC_FREE)),
        ops=(Op(OP_BLINK, target=0, target_b=1),),
    ),
    # Take a turn after this one. Banish this.
    "Time Warp": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EXTRA_TURN),),
        banish_self=True,
    ),
    # [Burn 3]. Play a 0 Might Shadow Clone unit token.  [Flow] {1}{A}{A}
    "Death Mark": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
        ops=(Op(OP_BURN, n=3),
             Op(OP_CREATE_TOKEN, target=0, n=1, token="Shadow Clone")),
    ),

    # [Reaction] Choose an enemy unit. Deal 6 to it unless its controller has
    # you draw 2.  (Its controller answers: yes = you draw 2.)
    "Shakedown": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ENEMY),),
        ops=(Op(OP_ASK, target=0, then_key=FU_DRAW_2,
                ask_no_key=FU_DAMAGE_SUBJECT_6),),
    ),

    # Each other player chooses Cards or Runes. Cards: you and that player each
    # draw 1. Runes: you and that player each channel 1 rune exhausted.
    # (The opponent answers: yes = Cards, no = Runes.)
    "Party Favors": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_ASK, then_key=FU_BOTH_DRAW_1, ask_no_key=FU_BOTH_CHANNEL_1),),
    ),

    # [Action] Choose an enemy unit at a battlefield. Its owner places it on the
    # top or bottom of their Main Deck.  (Its owner answers: yes = top.)
    "Keeper's Verdict": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
        ops=(Op(OP_ASK, target=0, ask_owner=True, then_key=FU_SUBJECT_TO_TOP,
                ask_no_key=FU_SUBJECT_TO_BOTTOM),),
    ),

    # Deal 5 to a unit.  (Its trash ability is in ABILITIES.)
    "Super Mega Death Rocket!": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DAMAGE, target=0, n=5),),
    ),

    # Give a friendly unit +1 Might this turn. It can't be chosen by enemy
    # spells and abilities this turn.  [Flow] {2 energy}
    # The Flow half is parsed off the reminder text, like Brittle Steel's.
    "Twilight Shroud": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1),
             Op(OP_UNCHOOSABLE_TURN, target=0)),
    ),

    # Move an enemy unit from a battlefield to its base. Then, if there's an
    # enemy unit alone at that battlefield, draw 1.
    # "That battlefield" is where the unit was moved FROM -- remembered by the
    # resolution, since the unit is no longer there to ask.
    "Isolate": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
        ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),
             Op(OP_DRAW, n=1, cond=COND_ENEMY_ALONE_WHERE_MOVED)),
    ),

    # [Reaction]  Counter a spell if an opponent has played another spell this
    # turn.  The condition is read at resolution, so the card may be played
    # into a spell that does not qualify -- it simply does nothing.
    "Crumbling Sands": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_COUNTER, target=0, cond=COND_OPP_ANOTHER_SPELL),),
    ),

    "Lilting Lullaby": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_COUNTER, target=0), Op(OP_NO_SPELLS, target=0)),
    ),

    # [Reaction] Counter a spell that costs no more than {4 energy} and no
    # more than {any rune}.  "{any rune}" is one Power symbol of any domain.
    #
    # The cost limit is another reason abilities are out: an ability has no
    # printed cost, so the only number to compare would be its SOURCE card's,
    # which the ability never paid.
    "Defy": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY,
                            max_energy=4, max_power=1),),
        ops=(Op(OP_COUNTER, target=0),),
    ),

    # [Reaction][Repeat {2 energy}] Counter a spell unless its controller
    # pays {2 energy}.
    #
    # A "soft" counter, and the difference from Defy is entirely in WHO
    # decides. Defy resolves and the spell is gone. This resolves and hands a
    # choice to the spell's controller, mid-resolution -- so it cannot be
    # written as ops in sequence: `resolve` does not stop at a pending
    # decision, it carries on down the list (see OP_DISCARD_CHOOSE). The
    # counter is what happens when they REFUSE, so it lives in the resume path
    # (`actions._finish_tax`), not in a following op.
    #
    # `who=W_ANY` because "a spell" is unqualified -- 355.5 scopes by omission,
    # so it reaches your own spells too. Countering your own is legal and
    # occasionally right (a Flow spell you would rather banish than resolve).
    #
    # [Repeat] needs nothing here: `chain.resolve_top` executes the ops a
    # second time, which asks for a second, separate payment. That is correct
    # -- two Hard Bargains' worth of tax is exactly what paying the Repeat
    # cost buys.
    # [Action] When a friendly unit is played this turn, buff it. Draw 1.
    #
    # Two clauses on two mechanisms. "Draw 1" is ordinary; the first clause is
    # a Delayed Trigger (390.2) and is what the card is FOR, so it arms an
    # entry in `DELAYED_ABILITIES` rather than doing anything now.
    #
    # `OP_ARM_DELAYED` carries no argument: the ability it arms is looked up
    # by the CARD that is resolving, which the Chain Item already names and
    # which `resolve` now receives. So the op cannot drift out of sync with
    # `DELAYED_ABILITIES` -- there is nothing to keep in sync. Ordered before
    # the draw only for readability; neither can affect the other.
    "Rally the Troops": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_ARM_DELAYED), Op(OP_DRAW, n=1)),
    ),

    # [Action] If an opponent's score is within 3 points of the Victory Score,
    # this costs {2 energy} less. Draw 1 and channel 1 rune exhausted.
    #
    # The discount is a SELF-scoped cost static, not part of the effect -- it
    # is read as the card is played (`cost.energy_discounts`), and the ops run
    # long after. Both halves are ordinary: `OP_CHANNEL` already channels
    # exhausted by default (430.4.b; `ready_runes` is the opt-out).
    #
    # Its gate is the only new thing, and it is shared -- Leona - Zealot prints
    # the identical clause.
    # Deal 2 to up to one enemy unit at a battlefield, then move a friendly
    # unit.  [Flow] {3 energy}{any rune}
    #
    # [Flow] needs nothing here -- `chain.flow_playable` reads the cost off the
    # card and banishes it afterwards (829), so the spec is only the effect.
    #
    # **The destination slot comes BEFORE the unit slot**, which reads
    # backwards against the card and is not a style choice. `rel` is honoured
    # by `_matches`, and a TK_LOCATION slot never reaches `_matches` -- 
    # `_location_targets` returns its list directly. So "somewhere other than
    # where it already is" has to be expressed on the UNIT slot pointing back
    # at the location, exactly as Resonating Strike does it. Written the
    # intuitive way round the relation would be silently ignored and the card
    # would offer moving a unit to the spot it is standing on.
    #
    # `who=W_FRIENDLY` on the destination is the default and gives own base
    # plus every battlefield -- the legal Move destinations. The enemy base is
    # correctly absent: movement is base<->battlefield to a unit's OWN base.
    #
    # Slot 0 is "up to one", so it is `optional` and skipping it fizzles just
    # the damage op; the move is not optional and a board with no friendly unit
    # makes the card uncastable (355.8), which is the rule.
    # [Action] Each player kills one of their gear.
    #
    # Cull the Weak's op with a type on it. The type used to be hardcoded to
    # "Unit" in four places -- the resolve-time skip-ahead, the action offer,
    # `_has_cullable` and the walk to the next seat -- and this is the card
    # that differs, so it now rides on `state.pend_cull_type` and every site
    # asks the same question.
    #
    # A player with no gear is skipped rather than asked, exactly as a player
    # with no unit is: "each player kills one of their gear" asks nothing of
    # someone who has none, and an empty decision point would deadlock.
    "Acceptable Losses": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_EACH_KILLS_OWN, card_type="Gear"),),
    ),

    "Shuriken Flip": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True, optional=True),
                 TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY,
                            locality=LOC_FREE),
                 TargetSpec(who=W_FRIENDLY, rel=REL_DIFFERENT_LOC, rel_to=1,
                            locality=LOC_FREE)),
        ops=(Op(OP_DAMAGE, target=0, n=2),
             Op(OP_MOVE_TO, target=2, target_b=1)),
    ),

    "Find Your Center": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_DRAW, n=1), Op(OP_CHANNEL, n=1)),
    ),

    "Hard Bargain": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_COUNTER_UNLESS_PAYS, target=0, cost=2),),
    ),

    # --- battlefield slots: "choose a battlefield and ... there" -----------
    # [Action] Choose a battlefield and an enemy unit there. Deal 4 to that
    # unit and 1 to each other enemy unit there.
    #
    # **Two slots, and the second is relative to the first.** The battlefield
    # is itself a target -- chosen at finalization, respondable -- and
    # `REL_SAME_BF` against slot 0 is what "there" means. That relation used to
    # assume the slot it pointed at held a unit ROW; a battlefield slot holds a
    # LOCATION, and reading one as the other compares against whichever unit
    # happens to sit in row 0-3.
    #
    # The second op is not a target (355.10): "each other enemy unit there" has
    # no count and no choice, so the opponent cannot answer by making one of
    # them illegal. `except_target=1` is the "other" -- the chosen unit takes 4,
    # not 5.
    "Crescent Strike": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY),
                 TargetSpec(who=W_ENEMY, rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_DAMAGE, target=1, n=4),
             Op(OP_DAMAGE_ALL, n=1, at=0, who=W_ENEMY, except_target=1)),
    ),

    # [Hidden] [Reaction] Choose a battlefield you control and a unit you
    # control at a different location. Move that unit to that battlefield and
    # give it +2 Might this turn.
    #
    # "A battlefield YOU CONTROL" is `who=W_FRIENDLY` on the battlefield slot;
    # "at a different location" is REL_DIFFERENT_LOC against it, which reads
    # the location directly rather than through a unit. Both slots are LOC_FREE
    # because the card is [Hidden] and the whole point is reinforcing a
    # battlefield from somewhere else -- binding them to the hiding place would
    # make the card unplayable from hiding, which is the only way it is played.
    "Resonating Strike": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_FRIENDLY,
                            locality=LOC_FREE),
                 TargetSpec(who=W_FRIENDLY, rel=REL_DIFFERENT_LOC, rel_to=0,
                            locality=LOC_FREE)),
        ops=(Op(OP_MOVE_TO, target=1, target_b=0),
             Op(OP_MODIFY_MIGHT, target=1, n=2)),
    ),

    # [Action] Choose a battlefield where you have units. You may move up to
    # one enemy unit to that battlefield. Then give enemy units there -2 Might
    # this turn.
    #
    # The move is "up to one", so slot 1 is optional (355.14) -- the card is
    # still playable with no enemy to drag in, and then it is just a Might
    # reduction on whoever is already there. The Might sweep is scoped to the
    # battlefield and to enemies, and it happens AFTER the move, so a unit
    # pulled in by the first op is caught by the second.
    "Moonfall": CardSpec(
        speed=SPEED_ACTION,
        # "move up to one enemy unit TO that battlefield" -- one already there
        # has nowhere to be moved to (RiftJudge #11426).
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY,
                            needs_own_units=True),
                 TargetSpec(who=W_ENEMY, optional=True, rel=REL_DIFFERENT_LOC,
                            rel_to=0)),
        ops=(Op(OP_MOVE_TO, target=1, target_b=0),
             Op(OP_MODIFY_MIGHT_ALL, n=-2, at=0, who=W_ENEMY)),
    ),

    # --- granting a keyword ------------------------------------------------
    # [Action] Give a unit [Assault 3] this turn. (+3 Might while attacking.)
    #
    # The value is the keyword's, not a Might modifier: [Assault 3] is
    # conditional Might that exists only while the unit is an attacker
    # (807.1.c), so granting it is not the same as +3 Might and a unit that
    # never attacks gets nothing.
    "Cleave": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=3),),
    ),

    # [Hidden] [Action] Give a unit [Shield 3] and [Tank] this turn.
    #
    # Two grants, one card -- and the pairing is the point: [Shield 3] makes it
    # survive and [Tank] makes it the one that has to be dealt with, so the
    # damage lands where the Shield is.
    "Block": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Shield", n=3),
             Op(OP_GRANT_KEYWORD, target=0, keyword="Tank", n=1)),
    ),

    # Choose a friendly unit without [Temporary]. Give it [Temporary]. Draw 2.
    #
    # **The grant is NOT "this turn".** [Temporary] kills the unit at the start
    # of its controller's next Beginning Phase, so a grant that expired with
    # the turn would never fire at all -- the card would be a two-card draw
    # with no cost. `grant_this_turn=False` is what makes the drawback real.
    #
    # "Without [Temporary]" is a restriction rather than a condition, and it
    # reads the granted value too: a unit already given [Temporary] by another
    # copy is not a legal choice.
    "Shadow's Call": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY, lacks_keyword="Temporary"),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Temporary", n=1,
                grant_this_turn=False),
             Op(OP_DRAW, n=2)),
    ),

    # [Reaction] Kill a friendly unit to give +Might equal to its Might to
    # another friendly unit this turn. Draw 1.
    #
    # **The amount is read at resolution, not printed.** "Equal to its Might"
    # means whatever the sacrificed unit is worth when the spell resolves --
    # buffs, statics and this-turn modifiers included -- so `n_from_might`
    # points at the slot instead of `n` carrying a number. Feeding a Soul
    # Shepherd token is worth more than the token's printed Might, and that is
    # the card.
    #
    # The Might is the one `OP_KILL` records just before the unit dies (it
    # captures effective Might while the row still counts), so the buff can
    # follow the kill in sentence order and be gated on it.
    "Deathgrip": CardSpec(
        speed=SPEED_REACTION,
        # "ANOTHER friendly unit" is a different UNIT, not a different
        # location -- the two units are usually standing together, which is
        # the whole point. `legal_targets` already excludes rows an earlier
        # slot took, so no relation is needed to say "another".
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_FRIENDLY)),
        # "If you do" is a condition on the KILL (RiftJudge #11124): a death
        # replaced by Tactical Retreat or Zhonya's is no kill, so no Might.
        # The kill runs first and its Might is read from what it recorded.
        ops=(Op(OP_KILL, target=0),
             Op(OP_MODIFY_MIGHT, target=1, n_from_might=0,
                cond=COND_SLOT_DIED, cond_slot=0),
             Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Counter a spell.  The plain one, with no rider at all.
    "Wind Wall": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_COUNTER, target=0),),
    ),

    # [Hidden] [Action] Play a ready 3 Might Sprite unit token with [Temporary].
    # The token card carries [Temporary] itself, so it expires through the
    # existing Beginning-Phase path -- the conquer-vs-hold inversion.
    "Sprite Call": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=SPRITE_TOKEN, ready=True),),
    ),

    # Play two ready 3 Might Sprite unit tokens with [Temporary].
    "Sprite Burst": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=2, token=SPRITE_TOKEN, ready=True),),
    ),

    # [Action] Deal 6 to a unit at a battlefield.
    "Falling Comet": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=6),),
    ),

    # [Action] Deal 8 to a unit.
    # No location clause at all, unlike Falling Comet directly above -- this
    # one reaches a unit sitting safely in a base.
    "Final Spark": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_DAMAGE, target=0, n=8),),
    ),

    # Deal 3 to all enemy units at a battlefield.
    # "a battlefield" is singular and chosen, so it is a real slot; the sweep
    # then scopes to it with `at`. Not `at_battlefields`, which would mean
    # every battlefield at once.
    "Firestorm": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY),),
        ops=(Op(OP_DAMAGE_ALL, at=0, n=3, who=W_ENEMY),),
    ),

    # [Action] Give friendly units +5 Might this turn.  Decisive Strike's big
    # brother; same untargeted board-wide shape.
    "Grand Strategem": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_MODIFY_MIGHT_ALL, n=5, who=W_FRIENDLY),),
    ),

    # [Action] Look at the top 3 cards of your Main Deck. Put 1 into your hand
    # and recycle the rest.
    # The most-played uncovered card in the corpus, 22 slots across the decks.
    # Not "up to 1": the pick is mandatory, so `pick_optional` stays False and
    # the player always takes something.
    "Stacked Deck": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_LOOK_TOP, n=3,
                pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),),
    ),

    # Look at the top 3 cards of your Main Deck. You may choose a card from
    # among them and draw it. Put the rest into your trash.  [Flow]
    # "You MAY choose" -- declining is legal and all three go to the trash,
    # which is what `pick_optional` is for. The rest-destination is the trash
    # here and the deck bottom on Stacked Deck: same shape, different words.
    "Lightning Rush": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_LOOK_TOP, n=3, pick_optional=True,
                pick_dest=DEST_HAND, rest_dest=DEST_TRASH),),
    ),

    # [Hidden] Play a 2 Might Sand Soldier unit token. Then do this: You may pay
    # {Order rune} to ready it.
    "Guards!": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=SAND_SOLDIER_TOKEN,
                then_key=FU_GUARDS_READY),),
    ),

    # [Hidden] Choose a battlefield. An opponent reveals their hand. You may
    # choose a unit from it. They play that unit to that battlefield, ignoring
    # any and all costs. If they do, then do this: Stun it.
    "Bone Skewer": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_BATTLEFIELD),),
        ops=(Op(OP_REVEAL_HAND, pick_types=("Unit",), target_b=0,
                reveal_play_there=True),),
    ),

    # [Action] Each opponent reveals the top card of their Main Deck. Choose
    # one and banish it, then play it, ignoring its cost. Then recycle the
    # rest.  (One opponent, one card: nothing to choose between.)
    "Blind Fury": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_REVEAL_PLAY, from_opponent=True, cost=COST_FREE),),
    ),

    # Each player chooses 2 units, 2 gear, 2 runes, and 2 cards in their hands.
    # Recycle the rest.
    "Divine Judgment": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_DIVINE_JUDGMENT),),
    ),

    # Each player looks at the top 5 cards of their Main Deck, banishes one of
    # them, then recycles the rest. Starting with the next player, each player
    # plays those cards, ignoring Energy costs. (They must still pay Power.)
    "Promising Future": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_PROMISING_FUTURE),),
    ),

    # Reveal the top 2 cards of your Main Deck. You may banish one, then play
    # it, reducing its cost by {2 energy}. Draw any you didn't banish.
    "Void Rush": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_REVEAL_PLAY, n=2, pick_optional=True, rest_dest=DEST_HAND,
                cost=COST_PRINTED, play_discount=2),),
    ),

    # Look at the top 5 cards of your Main Deck. You may banish a unit from
    # among them, then play it, reducing its cost by {5 energy}. Recycle the
    # remaining cards.
    "Reinforce": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_REVEAL_PLAY, n=5, pick_optional=True, pick_types=("Unit",),
                rest_dest=DEST_RECYCLE, cost=COST_PRINTED, play_discount=5),),
    ),

    # Look at the top 5 cards of your Main Deck. You may banish a unit or gear
    # from among them and play it, reducing its Energy cost by {5 energy}.
    # Recycle the rest. Then you may do this: Empower it.
    "Wild Claw": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_REVEAL_PLAY, n=5, pick_optional=True,
                pick_types=("Unit", "Gear"), rest_dest=DEST_RECYCLE,
                cost=COST_PRINTED, play_discount=5, play_empower=True),),
    ),

    # [Action] [Repeat] {Chaos rune} Look at the top 2 cards of your Main
    # Deck. Draw one and recycle the other.  (A repeated look waits for the
    # first to be answered -- `state.pend_repeat_card`.)
    "Called Shot": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_LOOK_TOP, n=2, pick_dest=DEST_HAND,
                rest_dest=DEST_RECYCLE),),
    ),

    # [Repeat] {2 energy} Look at the top 3 cards of your Main Deck. You may
    # reveal a unit from among them and draw it. Recycle the rest.
    "Double Trouble": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_PICK, n=3, pick_optional=True, pick_types=("Unit",),
                pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),),
    ),

    # Kill a unit.  No restriction of any kind -- the whole card.
    "Vengeance": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # Choose a friendly unit. Kill an enemy unit with less Might than it.
    # The bar is a unit you picked rather than a printed number, so the card
    # scales with your own board -- and both readings are effective Might, so
    # pumping your chosen unit in response widens what it can kill.
    "Public Execution": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_ENEMY, less_might_than=0)),
        ops=(Op(OP_KILL, target=1),),
    ),

    # Kill a unit at a battlefield with 3 Might or less.
    "Soul Harvest": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True, max_might=3),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # [Reaction] Give a unit -4 Might this turn. [Predict].
    # 436.1 -- Predicting is "looking at a single card from the top of the Main
    # Deck and choosing whether or not to Recycle it", so it is exactly the
    # look mechanic with N=1: recycling is the "pick", and declining puts the
    # card back on TOP (DEST_TOP), which is what makes Predict information
    # rather than card selection. 436.3.a -- X omitted means 1.
    #
    # The look must be last, and it is: the -4 resolves, then you Predict.
    "Eclipse": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-4),
             Op(OP_LOOK_TOP, n=1, pick_optional=True,
                pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP)),
    ),

    # --- [Repeat] (820) -----------------------------------------------------
    # The Repeat COST is not transcribed here: it is parsed off the card by
    # `cardtable.repeat_cost` and paid by the action layer, exactly as the
    # [Flow] cost is. What these entries carry is the effect that gets executed
    # one additional time (820.1.d) when that cost is paid.

    # [Repeat] {2 energy}. Play a 2 Might Sand Soldier unit token.
    # The rulebook's own worked example of Repeat (820.1.d.1).
    "Desert's Call": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=SAND_SOLDIER_TOKEN),),
    ),

    # [Action] [Repeat] {1 energy}. Give a unit [Assault 2].
    # Cleave's shape with a Repeat rider: granted, not "this turn", so it lasts
    # until the unit leaves. Repeating it grants [Assault 2] twice, and 807.1.c
    # makes a granted instance an ADDITIONAL ability rather than a replacement,
    # so the values add to [Assault 4] on the same unit.
    "Blood Rush": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=2),),
    ),

    # [Reaction] [Repeat] {2 energy}. Give a unit -2 Might this turn.
    # No printed floor, so 143.2.b's general floor of 0 applies -- and repeated,
    # that is -4 on one unit for {4 energy}.
    "Frigid Touch": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2),),
    ),

    # [Repeat] {2 energy}. Ready a unit.
    # Repeating this readies the SAME unit twice, which does nothing the second
    # time -- 820.1.d re-executes the instructions, it does not re-target.
    "Upstage Comedy": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_READY, target=0),),
    ),

    # [Action] [Repeat] {1 energy}{Mind rune}. Deal 1 to up to three units at
    # the same location.
    # "up to three" is three optional slots (355.14), and "at the same
    # location" ties slots 1 and 2 to slot 0 -- not to a battlefield, so a base
    # qualifies as a location too.
    "Bellows Breath": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, optional=True),
                 TargetSpec(who=W_ANY, optional=True, rel=REL_SAME_BF, rel_to=0),
                 TargetSpec(who=W_ANY, optional=True, rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_DAMAGE, target=0, n=1),
             Op(OP_DAMAGE, target=1, n=1),
             Op(OP_DAMAGE, target=2, n=1)),
    ),

    # --- channelling (430.4.b) ----------------------------------------------
    # Every one of these says "EXHAUSTED": the rune joins the board but cannot
    # be spent this turn, which is what keeps them from being pure
    # acceleration. `ready_runes` stays False, unlike the two-per-turn of
    # 430.4.a which `phases.channel` brings in ready.

    # Channel 1 rune exhausted. If you can't, draw 1.
    "Mobilize": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_CHANNEL, n=1, draw_if_short=1),),
    ),

    # Channel 2 runes exhausted. If you couldn't channel 2 runes this way,
    # draw 1.  The rider pays out on a PARTIAL channel too -- one rune off an
    # almost-empty deck is still "couldn't channel 2".
    "Catalyst of Aeons": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_CHANNEL, n=2, draw_if_short=1),),
    ),

    # Choose an opponent. They reveal their hand. Choose a non-unit card from
    # it, and recycle that card.
    # "Choose an opponent" is forced at two seats, so it is not a target slot.
    # The pick is a decision made DURING resolution against a zone rather than
    # the board, so like the look mechanic it cannot use target slots (355.10)
    # -- it suspends and asks. Must be the card's last op for the same reason.
    "Sabotage": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_REVEAL_HAND, pick_types=("Spell", "Gear"),
                pick_dest=DEST_RECYCLE),),
    ),

    # Each player kills one of their units.
    # Each player chooses their OWN casualty, so there is no target slot -- the
    # caster does not pick the opponent's. Sequential, starting with the
    # resolving player, and a seat with no units simply skips.
    # Starting with the next player, each player may return a unit to its
    # owner's hand.
    "Whirlwind": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EACH_KILLS_OWN, cull_mode=CULL_RETURN_ANY, start_next=True),),
    ),
    # Each player chooses a unit they control. Kill the rest.
    "Cataclysmic Duel": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EACH_KILLS_OWN, cull_mode=CULL_KEEP_OWN),),
    ),
    # Starting with the next player, each other player chooses a unit you don't
    # control that hasn't been chosen for this spell. Kill those units.
    # With two players "each other player" is the opponent and "a unit you
    # don't control" is one of theirs, so it is Cull the Weak for them alone.
    "King's Edict": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EACH_KILLS_OWN, start_next=True, who=W_ENEMY),),
    ),
    "Cull the Weak": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EACH_KILLS_OWN),),
    ),

    # [Action] When any unit takes damage this turn, kill it.
    # "ANY unit" -- both players', including the caster's own, which is what
    # makes this a board-wipe enabler rather than removal. A turn-scoped
    # modifier on lethality, not a trigger with a target.
    "Imperial Decree": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_ANY_DAMAGE_KILLS),),
    ),

    # [Reaction] Counter an enemy spell or ability that chooses a friendly unit
    # or gear.
    # `chain_abilities` because this is one of only two cards that says "or
    # ability"; `chooses_friendly_perm` is the "that chooses a friendly unit or
    # gear" clause, which is a restriction on the item's own targets. A slot
    # with no legal item is simply unplayable (355.8).
    "Not So Fast": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ENEMY, chain_abilities=True,
                            chooses_friendly_perm=True),),
        ops=(Op(OP_COUNTER, target=0),),
    ),

    # [Hidden] [Action] Swap the Might of two units at the same battlefield
    # this turn.
    # Unqualified "two units", so either side's -- swapping your big unit's
    # Might onto their small one is as legal as the reverse. The second slot is
    # tied to the first by location, which is what "at the same battlefield"
    # means, and `not_self` keeps it from naming the same unit twice.
    "Switcheroo": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),
                 TargetSpec(who=W_ANY, at_battlefield=True, not_self=True,
                            rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_SWAP_MIGHT, target=0, target_b=1),),
    ),

    # [Reaction] [Repeat] {2 energy}. Give two friendly units each +1 Might
    # this turn.  Two slots, so repeating it gives each of them +2.
    "Bonds of Strength": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_FRIENDLY, not_self=True)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1),
             Op(OP_MODIFY_MIGHT, target=1, n=1)),
    ),

    # [Reaction] [Repeat] {2 energy}. Draw 1.
    "Downstage Dramatics": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=1),),
    ),

    # [Reaction] [Repeat] {2 energy}. Give a unit +2 Might this turn.
    "Feral Strength": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),),
    ),

    # Kill an enemy Chaos ({Chaos rune}) unit or gear.
    # The domain is a restriction on the TARGET's own printed domain, not on
    # what this costs. "unit or gear" is the `card_type` tuple, as ever.
    "Decree of Unity": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ENEMY, domain=2,          # 2 == Chaos
                            card_type=("Unit", "Gear")),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # [Action] Kill all gear.
    # Both players', and gear only -- units are untouched. The sweep has always
    # been units-only because every wipe before this one was.
    "Thermo Beam": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_KILL_ALL, card_type="Gear"),),
    ),

    # [Action] [Repeat] {2 energy}. Stun an attacking unit.
    # Only legal during a Showdown -- 459 is what makes a unit "attacking", and
    # outside one there is nothing to choose, so the card cannot be played.
    "Thwonk!": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, attacking=True),),
        ops=(Op(OP_STUN, target=0),),
    ),

    # [Repeat] {2 energy}{Fury rune}. Deal 2 to a unit at a battlefield, then
    # deal 2 to up to one OTHER unit.
    # The second slot is "up to one" (355.14, so it may be left empty) and
    # "other" (not the first) -- but carries no location clause of its own, so
    # it can reach a unit sitting in a base.
    "Piercing Light": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),
                 TargetSpec(who=W_ANY, optional=True, distinct_from=0)),
        ops=(Op(OP_DAMAGE, target=0, n=2),
             Op(OP_DAMAGE, target=1, n=2)),
    ),

    # Draw 1, then draw 1 for each battlefield you or allies control.
    # Two ops: the flat draw, then the counted one. At two seats "you or
    # allies" is just you.
    "Right of Conquest": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_DRAW, n=1),
             Op(OP_DRAW, n=1, n_from_count=CT_MY_BATTLEFIELDS)),
    ),

    # [Action] Stun an enemy unit at a battlefield. You may move a friendly
    # unit to that enemy unit's battlefield.
    # The destination is slot 0's LOCATION -- not the caster's, and not a place
    # the player picks -- which is what `loc_of_target` says.
    "Zenith Blade": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),
                 TargetSpec(who=W_FRIENDLY, optional=True)),
        ops=(Op(OP_STUN, target=0),
             Op(OP_MOVE_TO, target=1, loc_of_target=0)),
    ),

    # Buff a friendly unit in your base, then move it to a battlefield.
    # Two slots: the unit (restricted to YOUR base by `at_base` plus
    # W_FRIENDLY) and the battlefield it goes to. `Op.target_b` points at the
    # location slot, so the destination is the one the player chose.
    "Showstopper": CardSpec(
        speed=SPEED_MAIN,
        # "...then move it to a BATTLEFIELD" -- never back to the base.
        targets=(TargetSpec(who=W_FRIENDLY, at_base=True),
                 TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY, locality=LOC_FREE)),
        ops=(Op(OP_BUFF, target=0),
             Op(OP_MOVE_TO, target=0, target_b=1)),
    ),

    # [Reaction] Give a friendly unit at a battlefield +2 Might this turn FOR
    # EACH enemy unit there.  `n` is the rate and the count multiplies it, so
    # this is +2 per enemy rather than a flat +2.
    "Against the Odds": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2,
                n_from_count=CT_ENEMIES_AT_TARGET),),
    ),

    # [Reaction] Return a friendly unit to its owner's hand. Its owner channels
    # 1 rune exhausted.
    # The slot is friendly, so "its owner" is the caster -- the two only come
    # apart on a card that can bounce an enemy unit, and this one cannot.
    "Retreat": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        # "ITS owner channels" refers to the returned unit: a linked
        # instruction, ignored when the return was (359.3.e.14.a, RiftJudge #10939).
        ops=(Op(OP_RETURN_TO_HAND, target=0),
             Op(OP_CHANNEL, n=1, cond=COND_SLOT_FRIENDLY, cond_slot=0)),
    ),

    # [Reaction] Draw 3.
    "Premonition": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=3),),
    ),

    # [Action] Give a unit +7 Might this turn.
    "Primal Strength": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=7),),
    ),

    # [Reaction] Give a unit -10 Might this turn.
    # No printed floor, unlike Stupefy's "to a minimum of 1" -- so the general
    # floor of 0 in 143.2.b applies and this is lethal to anything under 10.
    "Moonlight Affliction": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=-10),),
    ),

    # [Action] Play four 1 Might Recruit unit tokens.
    # The reminder text spells out 806.3's ordinary destination rule, so this
    # is one location slot for all four rather than four separate choices.
    "Recruit the Vanguard": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=4, token=RECRUIT_TOKEN),),
    ),

    # [Action] Deal 2 to a unit at a battlefield.
    "Incinerate": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=2),),
    ),

    # [Action] Return a gear to its owner's hand.
    # `card_type` overrides the slot's default: gear are permanents on the
    # board like any other, so this is a unit slot pointed at a gear.
    "Factory Recall": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),),
        ops=(Op(OP_RETURN_TO_HAND, target=0),),
    ),

    # [Action] Give friendly units +2 Might this turn.
    # Untargeted (355.10) and unscoped by location, so it reaches the whole
    # board including the base.
    "Decisive Strike": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_MODIFY_MIGHT_ALL, n=2, who=W_FRIENDLY),),
    ),

    # [Hidden] [Action] Move a unit from a battlefield to its base.
    # "a unit", not "an enemy unit" -- this retreats your own as readily as it
    # sends theirs home, which is what the card's name is about.
    "Fight or Flight": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),),
    ),

    # [Hidden] [Action] Deal 3 to a unit at a battlefield. Play a Gold gear
    # token exhausted.  The damage slot is unqualified -- "a unit", not "an
    # enemy unit" -- so it may point at your own, which is what makes this
    # playable as a Hidden answer to a unit you need dead whoever owns it.
    "Wages of Pain": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=3),
             Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1, token=GOLD_TOKEN)),
    ),

    # Play a 3 Might Mech unit token.  [Flow] {2 energy}{Mind rune}
    # A token spell names no destination, so the destination is the ordinary
    # one 806.3 gives any unit -- base or a battlefield you control -- and that
    # is a CHOICE, hence a TK_LOCATION slot rather than a silent default to
    # base. [Flow] is read off the card's own printed cost, not from here.
    "Iterative Design": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, token=MECH_TOKEN),),
    ),

    # Play two 1 Might Tentacle unit tokens from Bilgewater.  [Flow] {3 energy}
    # "from Bilgewater" names the tag the tokens carry (187.10), which the
    # Tentacle card already has -- it is not a second destination.
    "Up from the Deep": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=2, token=TENTACLE_TOKEN),),
    ),

    # [Action] Move a friendly unit and ready it.
    "Ride The Wind": CardSpec(
        speed=SPEED_ACTION,
        # 355.4.a -- a move destination is somewhere other than where the unit
        # already is: its own base or a battlefield (RiftJudge #10933).
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE, move_dest_of=0)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1, then_ready=True),),
    ),

    # Move an enemy unit.  Moving an enemy INTO your units stages a Combat by
    # presence (461) -- the engine already handles that, so this is removal.
    "Charm": CardSpec(
        speed=SPEED_MAIN,
        # The enemy unit goes to ITS base or a battlefield, never where it is.
        targets=(TargetSpec(who=W_ENEMY),
                 TargetSpec(kind=TK_LOCATION, locality=LOC_FREE, move_dest_of=0)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=1),),
    ),

    # [Reaction] Return a unit at a battlefield with 3 Might or less to its
    # owner's hand.  "with 3 Might or less" is a RESTRICTION (355.9.b), so a
    # 4-Might unit was never a legal choice and buffing in response saves it.
    "Gust": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True, max_might=3),),
        ops=(Op(OP_RETURN_TO_HAND, target=0),),
    ),

    # [Reaction] Return a friendly unit and an enemy unit to their owners' hands.
    "Star-Crossed": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY), TargetSpec(who=W_ENEMY)),
        ops=(Op(OP_RETURN_TO_HAND, target=0),
             Op(OP_RETURN_TO_HAND, target=1)),
    ),

    # [Reaction] Give a friendly unit +1 Might this turn, then an additional
    # +1 Might this turn if it is the only unit you control there.
    "En Garde": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1),
             Op(OP_MODIFY_MIGHT, target=0, n=1, cond=COND_ONLY_UNIT_THERE)),
    ),

    # [Hidden] [Action] Kill a unit at a battlefield. Its controller draws 2.
    # The draw goes to the TARGET's controller, not the caster -- a different
    # recipient from every other draw in the pool, hence its own op.
    "Hidden Blade": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_KILL, target=0),
             Op(OP_DRAW_CONTROLLER, target=0, n=2)),
    ),

    # Deal 3 to a unit. Deal 3 to a unit.  Two separate instances, so two
    # target slots -- and they may be the same unit, which 6 damage on one
    # body is often the point of.
    # Two separate instructions, each with its own choice, and nothing stops
    # both naming the same unit (RiftJudge #11379, #12539 -- Deflect is paid
    # twice, and at Void Gate each instance gets its +1).
    "Falling Star": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY), TargetSpec(who=W_ANY, allow_repeat=True)),
        ops=(Op(OP_DAMAGE, target=0, n=3), Op(OP_DAMAGE, target=1, n=3)),
    ),

    # [Hidden] [Action] [Stun] a unit.
    # If you played this from your hand, draw 1.
    "Back Off": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_STUN, target=0),
             Op(OP_DRAW, n=1, cond=COND_FROM_HAND)),
    ),

    # [Hidden] [Action] Stun a friendly unit and an enemy unit at the same
    # battlefield.
    "Facebreaker": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),
                 TargetSpec(who=W_ENEMY, at_battlefield=True,
                            rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_STUN, target=0), Op(OP_STUN, target=1)),
    ),

    # --- transcribed one by one from the card database ---------------------
    # These need no mechanism the DSL did not already have. Kept together so
    # the batch is legible; the ordering tool is `rl/tools/triage.py`.

    # [Hidden] Banish a unit, then its owner plays it to the same location,
    # ignoring its cost.
    #
    # The unit comes back as a NEW game object: damage gone, Buff gone (705),
    # "this turn" modifiers gone, entering exhausted (359.2.c) and firing its
    # own "when you play me" triggers. That is the whole card -- it resets a
    # buffed attacker and re-triggers a friendly one.
    "Temporal Breach": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_BLINK, target=0),),
    ),

    # [Action] Banish a friendly unit, then play it to base, ignoring its cost.
    "Portal Rescue": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),),
        ops=(Op(OP_BLINK, target=0, to_base=True),),
    ),

    # [Reaction] Move up to 2 friendly units to base.
    "Flash": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY, optional=True),
                 TargetSpec(who=W_FRIENDLY, optional=True)),
        ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),
             Op(OP_MOVE_TO, target=1, target_b=T_OWNER_BASE)),
    ),

    # Deal 6 to each of up to two units.
    "Singularity": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, optional=True),
                 TargetSpec(who=W_ANY, optional=True)),
        ops=(Op(OP_DAMAGE, target=0, n=6), Op(OP_DAMAGE, target=1, n=6)),
    ),

    # [Action] Return a unit at a battlefield to its owner's hand.
    "Rebuke": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_RETURN_TO_HAND, target=0),),
    ),

    # [Hidden][Reaction] Draw 2.
    "Consult the Past": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=2),),
    ),

    # [Action] Kill a unit at a battlefield.
    "Blast of Power": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_KILL, target=0),),
    ),

    # [Action] You may kill a gear. Draw 1.
    #
    # "You may" on a spell is 355.14's optional slot, not a resolution-time
    # choice: declining is simply choosing no target, and the draw is
    # unconditional either way. `card_type` retargets the slot at gear --
    # they are permanents on the board like any other, so this is the same
    # slot machinery rather than a parallel kind.
    # Play a 2 Might Sand Soldier unit token for each Equipment you control.
    # Then do this: Ready up to two of them.   (ERRATA text -- the printed
    # `cards.json` wording is "Then ready two of them", which cannot be
    # satisfied when fewer than two arrive.)
    #
    # The first card to COUNT Equipment, and it needs none of the missing
    # Might Bonus data to do it -- which is why it is scriptable now while
    # Long Sword is not. 718.5/718.5.a keep an Attached card's Types and Tags,
    # so an equipped sword counts exactly as a loose one does.
    #
    # "Ready UP TO two of them" rides the same op rather than following as a
    # second one, for two reasons: a token op must be its card's last (see the
    # TOKEN_DOUBLERS assertion below), and neither half of the choice is real.
    # WHICH two is arithmetic -- the tokens are made by one op, from one card,
    # at one location, so they are indistinguishable. HOW MANY is what "up to"
    # opens, and it exists to make the clause work when fewer than two arrive
    # rather than to offer a decision: readying a 2-Might token you just played
    # costs nothing and no card in the pool pays you for leaving it exhausted.
    # `ready_n` is therefore a cap, and `made[:ready_n]` satisfies "up to" for
    # a board of zero, one or many.
    "Arise!": CardSpec(
        speed=SPEED_MAIN,
        # No location: base or a battlefield you control (RiftJudge #10855).
        targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
        ops=(Op(OP_CREATE_TOKEN, target=0, n=1, n_from_count=CT_MY_EQUIPMENT,
                token="Sand Soldier", ready_n=2),),
    ),

    # [Action] Deal 3 to a unit at a battlefield. If this kills it, do this:
    # draw 1.
    #
    # "If this kills it" is read off slot 0's row after the damage op, so a
    # unit that survives -- or was already gone -- draws nothing.
    "Disintegrate": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=3),
             Op(OP_DRAW, n=1, cond=COND_SLOT_DIED, cond_slot=0)),
    ),

    # Give a unit +6 Might this turn.  [Flow] {4 energy}
    "Onslaught": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, locality=LOC_FREE),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=6),),
    ),

    # [Action] This can't be countered. Deal 4 to an enemy Calm unit.
    "Decree of Rage": CardSpec(
        speed=SPEED_ACTION, uncounterable=True,
        targets=(TargetSpec(who=W_ENEMY, domain=1, locality=LOC_FREE),),
        ops=(Op(OP_DAMAGE, target=0, n=4),),
    ),

    # Choose two units. They deal damage equal to their Mights to each other.
    #
    # Challenge without the sides: any two units, including two of your own or
    # two of the opponent's. `distinct_from` keeps it from choosing one unit
    # twice, and OP_FIGHT keeps the exchange simultaneous.
    "Clash of Giants": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY), TargetSpec(who=W_ANY, distinct_from=0)),
        ops=(Op(OP_FIGHT, target=0, target_b=1),),
    ),

    # [Action] Units you play this turn enter ready. Draw 1.
    #
    # A standing promise for the rest of the turn, stamped on the player
    # (`units_enter_ready_turn`), so it covers units played after it resolves
    # from any zone, and tokens too -- a token unit is played (187).
    "Confront": CardSpec(
        speed=SPEED_ACTION,
        ops=(Op(OP_UNITS_ENTER_READY), Op(OP_DRAW, n=1)),
    ),

    # Ready your units.
    "On the Hunt": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_READY_ALL, who=W_FRIENDLY),),
    ),

    # Kill a gear. Its controller draws 2.
    #
    # "A gear", unqualified. The draw goes to the gear's CONTROLLER -- the
    # opponent when it is theirs, which is the price; you when it is yours,
    # which makes it a cantrip that cashes in your own spent gear. The draw is
    # listed first so it reads the controller off a live row: the kill that
    # follows it cannot change who that was.
    "Detonate": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),),
        ops=(Op(OP_DRAW_CONTROLLER, target=0, n=2), Op(OP_KILL, target=0)),
    ),

    # Return all units and gear to their owners' hands.
    #
    # Every player's, and to each card's OWNER (P_OWNER), so a unit Kharox dug
    # out of your trash goes back to YOUR hand. Tokens cease to exist instead
    # (185.3). A bounce is a leaving, so leaves-the-board watchers fire, and an
    # Equipment returns alongside the unit it was attached to rather than being
    # left detached on an empty board.
    "Downwell": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_RETURN_ALL),),
    ),

    # [Reaction] Counter a spell. Return it to its owner's hand instead of
    # putting it in their trash. [Predict].
    #
    # A soft counter: the opponent keeps the card and loses the tempo and the
    # runes they spent. The Predict is the look's usual N=1 and must be the
    # card's last op, which it already is.
    "Abandon": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(kind=TK_SPELL, who=W_ANY),),
        ops=(Op(OP_COUNTER, target=0, counter_to_hand=True),
             Op(OP_LOOK_TOP, n=1, pick_optional=True,
                pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP)),
    ),

    # [Action] Kill a unit at a battlefield with 2 Might or less. If it was an
    # enemy unit, play a Gold gear token exhausted. If it was a friendly unit,
    # play two Gold gear tokens exhausted.
    #
    # "A unit", unqualified -- your own is legal, and it pays DOUBLE, which is
    # the card's real use: cash in a spent 2-drop for two Gold. The two token
    # ops are exact complements on slot 0's side, read off the dead row
    # (`COND_SLOT_*`), so exactly one runs.
    #
    # Two token ops on one card are allowed only because Gold is a GEAR token
    # (NON_UNIT_TOKENS): the last-op rule exists for Zilean's doubling, which
    # only ever applies to token units.
    "Blood Money": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True, max_might=2),),
        ops=(Op(OP_KILL, target=0),
             Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1, token=GOLD_TOKEN,
                cond=COND_SLOT_ENEMY, cond_slot=0),
             Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=2, token=GOLD_TOKEN,
                cond=COND_SLOT_FRIENDLY, cond_slot=0)),
    ),

    # Give a gear [Temporary].
    #
    # "A gear", unqualified, so either player's (targets scope by omission) --
    # and pointed at your own it is a way to cash in a gear with a death
    # trigger on your own schedule. The grant does NOT expire at end of turn:
    # [Temporary] is the delayed kill, so a "this turn" grant would remove
    # itself before it ever fired. 722.2 is the reason it cannot hit an
    # ATTACHED gear's printed [Temporary] either way -- but a GRANTED one stays
    # Active while attached (135.4.b), so this does kill an equipped sword.
    "Turn to Dust": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),),
        ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Temporary", n=1,
                grant_this_turn=False),),
    ),

    # [Action] Choose a friendly unit and an enemy unit. They deal damage equal
    # to their Mights to each other.
    #
    # `OP_FIGHT` rather than two OP_DAMAGEs, because the exchange is
    # SIMULTANEOUS: both Mights are read before either is marked, so an even
    # trade kills both instead of letting whichever op ran first survive.
    "Challenge": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY), TargetSpec(who=W_ENEMY)),
        ops=(Op(OP_FIGHT, target=0, target_b=1),),
    ),

    # Each player discards their hand, then draws 4.
    #
    # "Their hand" is `n=-1`, the hand's size read at resolution -- so a
    # player who has cast this is discarding a hand one card smaller than the
    # opponent's. Symmetric on paper, a card-advantage swing toward whoever is
    # behind in practice.
    "Invert Timelines": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_DISCARD, n=-1, each_player=True),
             Op(OP_DRAW, n=4, each_player=True)),
    ),

    # [Reaction] [Predict 5]. Draw 2.
    #
    # "Draw 2" rides a follow-up because a look must be its card's last op --
    # the choice happens during resolution, and an op after it would run before
    # the player had chosen. The order is the card's value: the Predict filters
    # the top five, then the draw takes the best of what was kept.
    "Clairvoyance": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_LOOK_TOP, n=5, pick_optional=True, pick_multi=True,
                pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP,
                then_key=FU_DRAW_2),),
    ),

    # [Action] Choose a unit at a battlefield. If it has 3 Might or less,
    # banish it. Otherwise, return it to its owner's hand.
    #
    # One sentence, two ops, and the pair PARTITIONS: the conditions are exact
    # complements on the same threshold, so precisely one of them runs. A
    # target that vanished during the response window runs neither, which is
    # 383.2.c.2 rather than a gap.
    #
    # Both halves read EFFECTIVE Might at resolution, so pumping the target in
    # the response window flips which one happens -- turning a banish into a
    # bounce, which is the difference between losing the card and replaying it.
    # That is the counterplay the card offers, and reading the printed corner
    # would delete it.
    #
    # 427.2.a is why the two halves are worth this much care: a banish is not a
    # kill, so a [Deathknell] unit is answered cleanly below the line and
    # merely inconvenienced above it.
    "Wind and Ghosts": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_BANISH, target=0, cond=COND_TARGET_MAX_MIGHT, level=3),
             Op(OP_RETURN_TO_HAND, target=0,
                cond=COND_TARGET_OVER_MIGHT, level=3)),
    ),

    # Kill a gear.  [Flow] {4 energy}{Fury rune}
    #
    # Salvage's required sibling: no "you may", so the slot is not optional and
    # 355.8 refuses the play outright when the board has no gear at all. That
    # matters more here than it looks, because [Flow] gives the card a SECOND
    # life out of the trash (829.1.b) -- and a replay has to fill its own slot
    # too, so a board that has been cleared of gear cannot be Flow-ed into.
    #
    # The Flow cost itself needs nothing here: `table.flow_energy`/`flow_power`
    # are parsed off the printed reminder text and `chain.flow_playable` offers
    # it, so a spec only has to describe the effect.
    "Brittle Steel": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),),
        ops=(Op(OP_KILL, target=0),),
    ),

    "Salvage": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, card_type=("Gear",), optional=True),),
        ops=(Op(OP_KILL, target=0), Op(OP_DRAW, n=1)),
    ),

    # --- trash recursion ---------------------------------------------------
    # Every card below names a card in a TRASH rather than on the board, which
    # is what TK_TRASH_CARD is for. Read the note beside it in this file before
    # adding another: the slot holds a packed (owner, card), and `who` decides
    # WHICH trash -- most of these say "your trash", but not all of them do.

    # Return up to 2 units from trashes to their owners' hands.
    #
    # **"From trashes", not "from your trash"** -- so both piles are in scope,
    # which is the whole reason `who` reaches TK_TRASH_CARD at all. And "their
    # owners' hands" is the matching half: pulling an opponent's unit out of
    # their trash hands it back to THEM. That makes the enemy-facing mode a
    # denial play rather than a theft -- you take a unit out of reach of their
    # own Soulgorger and pay them a card for it.
    "Shadows of the Past": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_ANY,
                            card_type=("Unit",), optional=True),
                 TargetSpec(kind=TK_TRASH_CARD, who=W_ANY,
                            card_type=("Unit",), optional=True)),
        ops=(Op(OP_TRASH_TO_HAND, target=0),
             Op(OP_TRASH_TO_HAND, target=1)),
    ),

    # [Action] Return a unit from your trash to your hand.
    "Morbid Return": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",)),),
        ops=(Op(OP_TRASH_TO_HAND, target=0),),
    ),

    # Play a unit from your trash, ignoring its Energy cost. (You must still
    # pay its Power cost.)
    #
    # A UNIT, not a spell, and that changes the shape completely: 337.2 resolves
    # a unit immediately, so there is no Chain Item, nothing to respond to, and
    # no destination to record afterwards. What it needs instead is a place to
    # stand, and 806.3 restricts that to your base or a Battlefield you control
    # -- `play_destination` is what stops the slot offering contested ground
    # that would be a free Conquer.
    "The Harrowing": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                            playable=True, playable_cost=COST_NO_ENERGY),
                 TargetSpec(kind=TK_LOCATION, play_destination=True,
                            locality=LOC_FREE)),
        ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                cost=COST_NO_ENERGY),),
    ),

    # [Reaction] As an additional cost to play this, kill a friendly unit.
    # Play a unit from your trash that costs no more Energy and no more
    # Power than the killed unit, ignoring its cost.
    # The Harrowing's shape (a unit reanimation needs a destination slot, not
    # a Chain item -- see its own comment), with two differences: the trash
    # unit's cost ceiling is READ off `cost_kill` rather than printed
    # (`capped_by_cost_kill`), and "ignoring its cost" waives BOTH halves
    # (COST_FREE) rather than only Energy.
    "Heedless Resurrection": CardSpec(
        speed=SPEED_REACTION,
        cost_kill=TargetSpec(who=W_FRIENDLY),
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                            card_type=("Unit",), playable=True,
                            playable_cost=COST_FREE,
                            capped_by_cost_kill=True),
                 TargetSpec(kind=TK_LOCATION, play_destination=True,
                            locality=LOC_FREE)),
        ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                cost=COST_FREE),),
    ),

    # Return up to two cards with [Hidden] from your trash to your hand.
    #
    # The second sentence parses as "you can [hide] [while] ignoring costs" --
    # the verb is Hide and 811.1.b's {any rune} is what is ignored (RiftJudge
    # #6655) -- so it is a turn-scoped modifier on the Hide action, not on
    # playing anything: OP_FREE_HIDE.
    "Guerilla Warfare": CardSpec(
        speed=SPEED_MAIN,
        targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, has_keyword="Hidden",
                            optional=True),
                 TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, has_keyword="Hidden",
                            optional=True)),
        ops=(Op(OP_TRASH_TO_HAND, target=0),
             Op(OP_TRASH_TO_HAND, target=1),
             Op(OP_FREE_HIDE)),
    ),

    # [Action] Deal 4 to a unit at a battlefield. Draw 1.
    "Void Seeker": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=4), Op(OP_DRAW, n=1)),
    ),

    # Kill all units.  Untargeted and total -- ours too.
    "The Ruination": CardSpec(speed=SPEED_MAIN, ops=(Op(OP_KILL_ALL),)),

    # Exhaust all friendly units, then deal 12 to ALL units at battlefields.
    # The exhaust is not a cost, it is the first instruction, so it happens
    # even if the damage kills nothing.
    "Unchecked Power": CardSpec(
        speed=SPEED_MAIN,
        ops=(Op(OP_EXHAUST_ALL), Op(OP_DAMAGE_ALL, n=12, at_battlefields=True)),
    ),

    # [Reaction] Discard 1, then draw 2.
    "Lunar Boon": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=2)),
    ),

    # Draw 1.  [Flow] {2 energy}
    # The Flow cost and the "then banish it" rider are keyword behaviour
    # (829), not DSL -- the spec is just the printed effect.
    "Dredge Up": CardSpec(speed=SPEED_MAIN, ops=(Op(OP_DRAW, n=1),)),

    # [Action] Give a unit +5 Might this turn.
    "Punch First": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=5),),
    ),

    # [Action] Stun a unit.
    "Rune Prison": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_STUN, target=0),),
    ),

    # Draw 4.
    "Progress Day": CardSpec(speed=SPEED_MAIN, ops=(Op(OP_DRAW, n=4),)),

    # [Action] Deal 3 to a unit at a battlefield.
    "Hextech Ray": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
        ops=(Op(OP_DAMAGE, target=0, n=3),),
    ),

    # [Reaction] Give two friendly units each +2 Might this turn.
    # "two friendly units" is two slots; `legal_targets` already refuses to
    # fill a slot with a permanent an earlier slot took, so they are distinct.
    "Back to Back": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_FRIENDLY), TargetSpec(who=W_FRIENDLY)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
             Op(OP_MODIFY_MIGHT, target=1, n=2)),
    ),

    # [Reaction] Give a unit +2 Might this turn and another unit -2 Might this
    # turn.  No printed floor, so the general 143.2.b floor of 0 applies.
    "Defiant Dance": CardSpec(
        speed=SPEED_REACTION,
        targets=(TargetSpec(who=W_ANY), TargetSpec(who=W_ANY)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
             Op(OP_MODIFY_MIGHT, target=1, n=-2)),
    ),

    # [Reaction] Deal 1 to all units at battlefields.
    # Untargeted and unbounded, so no slots -- the same shape as Thousand-
    # Tailed Watcher's mass Might reduction, and it hits BOTH sides.
    "Flurry of Blades": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DAMAGE_ALL, n=1, at_battlefields=True),),
    ),

    # [Hidden] [Action] Choose a unit you control and another unit you control
    # at a different location. If at least one of them has [Temporary], move
    # each to the other's location. Draw 1.
    #
    # "Choose", not "target" (355.10.a): the units are NOT targets, so the
    # locality rule does not bind them and this is playable from hiding at a
    # battlefield that is not the one being attacked. Both slots are LOC_FREE
    # for exactly that reason -- it is the case the project owner used to
    # correct an earlier reading, and the reason locality is per slot.
    "Smoke and Mirrors": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),
                 TargetSpec(who=W_FRIENDLY, locality=LOC_FREE,
                            rel=REL_DIFFERENT_LOC, rel_to=0)),
        ops=(Op(OP_SWAP_LOC, target=0, target_b=1,
                cond=COND_ANY_TARGET_TEMPORARY),
             Op(OP_DRAW, n=1)),
    ),

    # [Reaction] Deal 2 to all enemy units in combat.
    #
    # **"In combat" is a place, not a designation.** 459 makes every unit at
    # the contested battlefield an Attacker or a Defender the moment Combat
    # begins, so "in combat" is exactly "at `showdown_bf`" -- which is why this
    # is a location-scoped sweep and not the `attacking` flag. The flag would
    # have spared every defender, and the card kills defenders.
    #
    # Untargeted (355.10), so the opponent cannot answer by making one of them
    # illegal; the only answer is to change what is standing there.
    "Cannon Barrage": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DAMAGE_ALL, n=2, at=T_COMBAT, who=W_ENEMY),),
    ),

    # [Reaction] [Repeat] {1 energy}{any rune} Give your Mechs +1 Might
    # this turn.
    #
    # [Repeat] is already machinery: `table.repeat_energy`/`repeat_power` carry
    # the additional cost and `chain.resolve_top` runs the ops a second time
    # (820.1.d), so the card only has to say what one execution does. What was
    # missing is the kin restriction -- `tag` -- because every mass Might
    # effect before this one reached all of a side's units.
    #
    # No location clause, so it reaches your Mechs at bases too.
    "Danger Zone": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_MODIFY_MIGHT_ALL, n=1, who=W_FRIENDLY, tag="Mech"),),
    ),

    # [Reaction] Draw 1 for each of your [Mighty] units.
    # 740.2's 5+ Might, counted live at resolution -- so a Might trick played
    # in response to this genuinely draws another card, which is the whole
    # reason the card is a Reaction.
    "Show of Strength": CardSpec(
        speed=SPEED_REACTION,
        ops=(Op(OP_DRAW, n=1, n_from_count=CT_MY_MIGHTY_UNITS),),
    ),

    # [Action] Give a unit +2 Might this turn. If IT'S [Empowered], give it
    # +4 Might this turn instead.
    #
    # "Instead" as two ops that add, the same arithmetic Rage Amplifier and
    # Tools of Empire use -- and the condition is about the TARGET here rather
    # than the source, which is the whole reason COND_TARGET_EMPOWERED exists.
    #
    # A condition, not a restriction (355.9.b): any unit is a legal choice and
    # the bonus half is decided at resolution, so an opponent holding a
    # disempower has a real answer in the response window.
    "Guttural Roar": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_ANY),),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
             Op(OP_MODIFY_MIGHT, target=0, n=2,
                cond=COND_TARGET_EMPOWERED)),
    ),

    # [Action] Give a friendly unit +1 Might this turn and [Stun] an enemy
    # unit at its location.
    #
    # "At ITS location" relates the second slot to the first, and it is a
    # LOCATION relation rather than a battlefield one: two friendly and enemy
    # units can share a base as easily as a battlefield, and REL_SAME_BF
    # compares the two locations without requiring either to be a battlefield.
    #
    # Both are targets, chosen at finalization, so growing the friendly unit
    # commits to which enemy can be stunned before the opponent responds.
    "Heroic Charge": CardSpec(
        speed=SPEED_ACTION,
        targets=(TargetSpec(who=W_FRIENDLY),
                 TargetSpec(who=W_ENEMY, rel=REL_SAME_BF, rel_to=0)),
        ops=(Op(OP_MODIFY_MIGHT, target=0, n=1),
             Op(OP_STUN, target=1)),
    ),

    # [Reaction] As an additional cost to play this, kill a friendly [Mighty]
    # unit. (A unit is Mighty while it has 5+ Might.) Draw 2 and channel 1
    # rune exhausted.
    # The card's own text is entirely the cost plus two counted ops -- no
    # slot in `targets` at all, since nothing else needs choosing.
    "Sacrifice": CardSpec(
        speed=SPEED_REACTION,
        cost_kill=TargetSpec(who=W_FRIENDLY, min_might=5),
        ops=(Op(OP_DRAW, n=2), Op(OP_CHANNEL, n=1)),
    ),

    # As an additional cost to play me, kill a friendly unit.
    # A UNIT with a `cost_kill` -- 337.2 gives it no Chain and no priority
    # window, so `speed` is inert here (see `actions._apply_one`'s A_PLAY
    # branch, which routes any card with `cost_kill` through the unit-play
    # cost decision before it consults this at all). No ops: the card's
    # entire printed text is the cost.
    "Cruel Patron": CardSpec(
        speed=SPEED_MAIN,
        cost_kill=TargetSpec(who=W_FRIENDLY),
    ),

    # [Ambush] As an additional cost to play me, kill a Bird, Cat, Dog, or
    # Poro you control. You may play me to its battlefield (even if you
    # don't have other units there).
    # The "(even if...)" reminder describes what `PLAY_TO_COST_KILL_LOC`
    # already does -- that destination is added unconditionally, with no
    # ally-presence check the way [Ambush]'s own destinations need one.
    "Stalking Wolf": CardSpec(
        speed=SPEED_MAIN,          # inert for a unit; see Cruel Patron
        cost_kill=TargetSpec(who=W_FRIENDLY,
                             tags=("Bird", "Cat", "Dog", "Poro")),
    ),
}


# --- static abilities -----------------------------------------------------
# A trigger is an *event*: it fires, goes on the Chain, resolves, and is done.
# A static is a *continuous* property of the board -- Petal Pixie's Might
# changes the instant a Sprite arrives beside her, with nothing on the Chain and
# no window to respond in. So it cannot be an Op, and it is not recomputed at
# any particular moment: `combat.might` derives it on every read.
#
# The consequence that is easy to miss: because 143.2.a is itself a continuous
# check ("if a Unit EVER has damage equalling or exceeding its Might"), a static
# going away can kill. Killing Soul Shepherd shrinks every token she was pumping
# and any of them already carrying damage dies with her.
(ST_MIGHT, ST_COST_ENERGY, ST_KEYWORD, ST_UNCHOOSABLE,
 ST_NO_PLAY, ST_DAMAGE_BONUS, ST_NO_DAMAGE,
 ST_COST_POWER, ST_COST_ENERGY_UP, ST_COST_POWER_UP,
 ST_PLAY_OPEN, ST_NO_MOVE_TO_BASE,
 ST_ENTERS_READY, ST_NO_COMBAT_DAMAGE, ST_NO_ENEMY_MOVE,
 ST_PLAY_ENEMY_ALONE) = range(16)
ST_NAMES = ("might", "cost_energy", "keyword", "unchoosable", "no_play",
            "damage_bonus", "no_damage", "cost_power",
            "cost_energy_up", "cost_power_up", "play_open", "no_move_to_base",
            "enters_ready", "no_combat_damage", "no_enemy_move",
            "play_enemy_alone")
# ST_NO_ENEMY_MOVE -- "I can't be moved by enemy spells and abilities" (Jagged
# Cutlass). ST_PLAY_ENEMY_ALONE -- "Friendly units can be played to an occupied
# battlefield if an enemy unit is alone there" (Arachnoid Horror).
# ST_NO_COMBAT_DAMAGE -- "I don't deal combat damage" (Galio, Ezreal - Dashing),
# and scoped: "enemy units here with less Might than me don't deal combat
# damage" (Vilemaw). Read by `combat.might_for_pool`, the one place a unit's
# contribution to its side's pool is decided -- the same place Stun blanks it.

# ST_PLAY_OPEN is Miss Fortune - Buccaneer's "Friendly units may be played to
# open battlefields" -- the first printed exception to 806.3 granted by a
# permanent rather than printed on the card being played. It takes
# SC_YOUR_CARDS for the same reason a cost discount does: the unit it applies
# to is still in hand and has no row on the board to reach.

# The *_UP kinds are cost INCREASES, and they are separate kinds rather than a
# negative `n` because the rules apply them in a separate step: 356.3 raises
# costs and 356.4 lowers them, in that order. Folding them together would let
# an increase be cancelled by a floor that was never meant to see it --
# `apply_discounts` is explicitly one-way ("Never increases it").

# ST_COST_POWER is the Power half of a cost discount -- "{1 energy}{any rune}
# less". It is a SEPARATE kind from ST_COST_ENERGY rather than another field on
# it because 356.4.d orders discounts per COMPONENT: a card reducing only Power
# and one reducing only Energy are different effects that happen to be printed
# on one line, and `apply_discounts` has to run over each component's own list.

# ST_NO_DAMAGE is Ambessa's "can't be dealt damage unless I'm in combat", and
# it is NOT `ST_UNCHOOSABLE` with different words. Unchoosable restricts who may
# POINT at the unit (355.10) and so does nothing against a board-wide sweep that
# chooses nothing; this stops the damage itself, however it arrives. A card can
# print either without the other, and Ambessa prints this one.

# ST_DAMAGE_BONUS is Void Gate's "spells and abilities affecting units here each
# deal 1 Bonus Damage". Read in `combat.mark_damage`, which is exactly the
# spell-and-ability damage path -- combat damage writes `P_DMG` directly in the
# damage step and so is untouched, which is what the card says. "Each INSTANCE"
# is per call, and `mark_damage` is called once per instance, so the wording
# falls out rather than needing to be arranged.

# ST_NO_PLAY is Rockfall Path's "Units can't be played here" -- the first
# static that REMOVES a permission rather than granting or modifying something.
# It reaches `actions.play_destinations`, not the board scan every other kind
# uses, because the thing it applies to is not on the board yet.
#
# 806.3 already restricts a unit to its controller's base or a battlefield they
# control, and four printed permissions WIDEN that (see `PLAY_PERMISSIONS`).
# This narrows it, and it must narrow the widened set too: an [Ambush] unit is
# still a unit being played here.

# Who a static applies to.
#   SC_UNITS_HERE -- printed on a BATTLEFIELD, reaching units standing on it.
#                    "Units here" carries no ownership clause, so it reaches
#                    BOTH players (targets scope by omission); narrow with
#                    `who` when a card says "your".
SC_SELF, SC_FRIENDLY_UNITS, SC_UNITS_HERE, SC_YOUR_CARDS, \
    SC_ENEMY_CARDS, SC_ALL_UNITS, SC_ENEMY_UNITS = range(7)
# SC_ENEMY_UNITS -- the other player's units on the board, narrowed like
# SC_FRIENDLY_UNITS by `scope_same_loc` etc. (Vilemaw).
# SC_ALL_UNITS -- "Units can't move to base" (Minotaur Reckoner): every unit on
# the board, either player's, wherever it stands. Targets and statics alike
# scope by omission, so an unqualified "units" reaches both sides.

# SC_YOUR_CARDS is the scope a COST discount needs and no Might static does:
# "Your spells cost {1 energy}{any rune} less" is printed on a permanent and
# applies to cards still in their owner's HAND. Every other scope here asks
# about permanents on the board, which is why the discount walk could not just
# reuse one -- `cost.py` documented this as an unimplemented second source.

# What a "for each ..." clause COUNTS. The board is the obvious source and was
# the only one; a zone is the other, and it is a different kind of number --
# Rhasa reads a pile that grows all game and never shrinks on its own, so her
# cost falls monotonically rather than swinging with the board.
CNT_NONE, CNT_BOARD, CNT_TRASH, CNT_EMPOWER, CNT_POINTS, \
    CNT_CARDS_PLAYED, CNT_BUFFED_HERE, CNT_MIGHTY, CNT_ANIMAL_TAGS, \
    CNT_HIGHEST_MIGHT, CNT_HOLD_POINTS = range(11)
# CNT_HOLD_POINTS -- points you scored from holding this turn.
# CNT_MIGHTY -- your [Mighty] units (Jaull-Fish). CNT_ANIMAL_TAGS -- how many of
# Bird/Cat/Dog/Poro are among your units (Daisy!). CNT_HIGHEST_MIGHT -- the
# highest Might among units you control (Sky Splitter).
# CNT_BUFFED_HERE -- "for each buffed friendly unit at my battlefield" (Sett,
# Kingpin). A STATUS count, not a keyword one: `per_keyword="Buff"` would
# ask whether a card PRINTS [Buff], which is a different and rarer thing.
# CNT_CARDS_PLAYED -- "for each card you've played this turn" (Battering
# Ram), read live from `cards_played`, which the card being costed has not
# yet joined.
# CNT_POINTS -- "My Might is increased by your points" (Draven, Showboat): the
# static's controller's score, read live, so every point he helps win makes
# him bigger for the next one.

# CNT_EMPOWER counts how many times the SOURCE has been Empowered -- "I have
# +2 Might for each time I'm Empowered". The only counting clause that asks
# about the source's own row rather than about the board or a zone, which is
# why `static_count` had to start taking that row.


class Static(NamedTuple):
    """One continuous ability.

    Flat when `per_keyword` is None ("Your token units have +1 Might"), and
    scaled by a board count when it is not ("I have +1 Might for each of your
    units with [Temporary] at my battlefield").
    """
    kind: int = ST_MIGHT
    n: int = 0
    scope: int = SC_SELF
    scope_token: bool = False        # ...and only token units
    # Narrowing for SC_FRIENDLY_UNITS. "OTHER friendly units HERE have
    # [Assault]" (Captain Farron) is both of these; "your token units have
    # [Tank]" (Lillia) is neither, and reaches the whole board.
    scope_not_self: bool = False
    scope_same_loc: bool = False
    # For ST_KEYWORD: which keyword this grants, and its value. `n` carries the
    # value the same way it carries a Might amount, so a bare keyword is n=1.
    keyword: str | None = None
    # "Units here WITH [Temporary] have [Shield]" (Black Flame Altar) -- a
    # keyword the AFFECTED unit must already have. Distinct from `keyword`
    # (what is granted) and from `per_keyword` (what is counted).
    requires_keyword: str | None = None
    # "Your units that are [Empowered] have +2 Might (including me)" (Aurok
    # General). A requirement on the AFFECTED unit's 441.1.a status, the mirror
    # of `requires_keyword` for a status rather than a keyword -- and distinct
    # from `cond=COND_EMPOWERED`, which asks about the SOURCE. Aurok General
    # needs both readings in one sentence: the static only exists while HE is
    # Empowered, and it then reaches only units that are.
    requires_empowered: bool = False
    # SC_UNITS_HERE only: whose units. W_ANY is the unqualified "units here",
    # which reaches both players.
    who: int = W_ANY
    # Counting clause. `per_same_loc` is "at my battlefield"; `per_friendly`
    # is the "of your units" in the same sentence.
    per_keyword: str | None = None
    per_friendly: bool = True
    per_same_loc: bool = True
    # What the "for each" clause counts. CNT_BOARD is implied whenever
    # `per_keyword` or `per_card_type` is set, so existing entries keep working
    # without saying so; CNT_TRASH is the new one.
    per: int = CNT_NONE
    per_card_type: str | None = None   # "for each gear you control"
    # For SC_YOUR_CARDS: which card TYPE the discount reaches. "Your SPELLS
    # cost less" is `applies_to_type="Spell"`. Distinct from `per_card_type`,
    # which COUNTS things on the board rather than filtering what is discounted.
    applies_to_type: str | None = None
    # "Your DRAGONS' Energy costs are reduced" (Herald of Scales) -- a tag the
    # card being costed must carry, alongside `applies_to_type`.
    applies_to_tag: str | None = None
    # "Your MECHS have [Deflect] and [Ganking]" (Breakneck Mech) -- a tag the
    # AFFECTED unit must carry. Distinct from `applies_to_tag`, which narrows
    # the card being COSTED rather than the unit a Might or keyword static
    # reaches.
    scope_tag: str | None = None
    # The AFFECTED unit must have less Might than the static's source: "your
    # units here with less Might than me" (Alpha Wildclaw), "enemy units here
    # with less Might than me" (Vilemaw).
    requires_less_might: bool = False
    # "While a friendly unit DEFENDS ALONE, it gets +2 Might" (Master Yi - Wuju
    # Bladesman). A requirement on the AFFECTED unit, like the three above --
    # not `cond=COND_DEFENDING_ALONE`, which a battlefield uses to ask the same
    # question from the other side (there the ground has no controller to ask
    # about, so the gate lives at the affected unit either way).
    requires_defending_alone: bool = False
    # "Your EQUIPMENT each give [Assault]" (Lucian - Purifier) -- a requirement
    # that the affected unit is carrying one. Counted as one instance however
    # many gears it wears; see the note in `decks.PARTIAL` about the stacking.
    requires_equipped: bool = False
    # "Your SAND SOLDIERS have [Weaponmaster]" (Azir) -- a scope by card NAME.
    # The token carries no "Sand Soldier" tag to match on (its only tag is
    # Shurima), so the name is what the card is actually naming.
    scope_name: str | None = None
    # The affected unit must carry a Buff: "other BUFFED friendly units at my
    # battlefield" (Lee Sin - Centered).
    requires_buffed: bool = False
    # The affected unit must be STUNNED: "stunned enemy units here have -8
    # Might, to a minimum of 1 Might" (Leona - Zealot).
    requires_stunned: bool = False
    # The affected unit must NOT PRINT this keyword: "Friendly buffed units
    # have [Deflect] if they didn't already" (Spirit's Refuge).
    lacks_printed_keyword: str | None = None
    # For COND_CONTROL_TAG on a static: "if you control a Mech" (Production
    # Surge's discount).
    cond_tag: str | None = None
    # Counting clause: count only the OTHER player's permanents ("the number
    # of ENEMY units here", Ancient Warmonger). Requires `per_friendly=False`.
    per_enemy: bool = False
    # Counting clause: not the source itself -- "each OTHER unit you control
    # here with my name" (Spiderling). With `per_same_name` on a BOARD count.
    per_not_self: bool = False
    # Counting clause: token units only ("for each token unit you control",
    # Illaoi).
    per_token: bool = False
    # CNT_TRASH only: "for each card with MY NAME in your trash" narrows the
    # pile to copies of the static's own card (Shadowblade Lurker), where the
    # bare form counts every card in it (Rhasa).
    per_same_name: bool = False
    # 356.4.e -- "to a minimum of {N energy}". The floor binds only THIS
    # discount, which is why it rides here and not on the total; see
    # `cost.order_discounts` for why that makes the ordering matter.
    floor: int = 0
    # Gate. A static that does not apply right now contributes nothing at all,
    # which for a cost discount means the card simply costs its printed price.
    cond: int = COND_NONE
    level: int = 0            # the N in COND_LEVEL's "[Level N]"


# Statics printed on a BATTLEFIELD rather than on a permanent. Kept in its own
# table because a battlefield is not a permanent: it occupies a slot
# (`state.bf_card`), has no row, no controller of its own, and cannot be killed
# -- so it can never be the SUBJECT of a static, only the source of one.
#
# Every one of these is SC_UNITS_HERE, which is the only scope a battlefield
# has: the units standing on it. "Units here" prints no ownership clause, so it
# reaches both players.
# Cost rules printed on a BATTLEFIELD. Each is a clause no static scope can
# express, because it asks something about the PAYMENT rather than about a
# permanent: which card type is being played, whether it is the first one this
# turn, whether the spell chooses a unit standing here. They are keyed by name
# for the same reason the ~30 other behaviour registries are -- the alternative
# is a Static field per card.
#
#   kind        what the rule modifies
#   "card"      the Energy of a CARD being played
#   "ability"   the Energy of an ACTIVATED ABILITY being used
#   "repeat"    a [Repeat] additional cost
#   "empower"   an [Empower] cost
#   "choose"    a spell that chooses a friendly unit HERE (Power)
#   "reaction"  a [Reaction] card played during a showdown here (Power, a TAX)
#
# `control` -- only while the battlefield's controller is the payer.
# `first_each_turn` -- the deck's one discount per turn, stamped per seat.
BF_COST_RULES: dict[str, dict] = {
    "Ornn's Forge": dict(kind="card", n=1, card_type="Gear", nontoken=True,
                         control=True, first_each_turn=True),
    "Piltovan Forge": dict(kind="ability", n=1, card_type="Gear",
                           control=True, first_each_turn=True),
    "Marai Spire": dict(kind="repeat", n=1, control=True),
    "Risen Altar": dict(kind="empower", n=1, here=True),
    "Sandswept Tomb": dict(kind="choose", n=1, power=True, here=True),
    "Mystic Vortex": dict(kind="reaction", n=1, power=True, tax=True,
                          here=True),
}
# "Players ignore [Deflect] while paying for spells and abilities choosing
# something here" (Heisho, Shell of the World) -- a surcharge that stops
# existing, which `resolve.deflect_cost` asks about per chosen unit.
BF_IGNORE_DEFLECT: frozenset[str] = frozenset({"Heisho, Shell of the World"})
# "Any player may pay {any rune}{any rune} as an additional cost to play a
# Dragon. If they do, they play it to this battlefield." (Dragon Roost)
#
# Expressed as a paid DESTINATION rather than as an optional additional cost
# of the usual kind: the cost and the battlefield are one decision ("if they
# do, they play it to this battlefield"), so choosing the ground IS choosing
# to pay. That also keeps it composable -- a Dragon with its own [Accelerate]
# may still pay that too, which a second `A_PLAY_AT_FAST` meaning could not
# express. `any_player` is what makes it a ground rule rather than a
# controller's privilege: 806.3's restriction is lifted for everybody.
# "If a unit here would die during combat, its controller may pay N Power to
# heal it, exhaust it, and recall it instead." (Altar of Blood) -- name -> the
# Power it charges. A death REPLACEMENT with a cost, which is why it is not in
# the ability tables: it is decided at the moment of death (`combat.
# altar_offer`), not put on the Chain.
BF_DEATH_REPLACEMENT: dict[str, int] = {"Altar of Blood": 3}
# "You may hide an ADDITIONAL card here." (Bandle Tree) -- name -> how many
# facedown cards the ground holds beyond 107.3.f's one. The whole reason
# `state` has `N_FD_PER_BF` slots per battlefield rather than one.
BF_EXTRA_HIDE: dict[str, int] = {"Bandle Tree": 1}
BF_PLAY_COSTS: dict[str, dict] = {
    "Dragon Roost": dict(tag="Dragon", energy=0, power=2, any_player=True),
}
# Battlefields that change the SCORING rules rather than the board. Neither is
# expressible as an ability or a static: one moves the Victory Score itself and
# the other forbids scoring at one battlefield for the first two turns.
#
#   victory_plus         add this to the points needed to win, while in play
#   no_score_before_turn a player may not score here until this turn of theirs
BF_SCORE_RULES: dict[str, dict] = {
    "Aspirant's Climb": dict(victory_plus=1),
    "Forgotten Monument": dict(no_score_before_turn=3),
}


BF_STATICS: dict[str, tuple[Static, ...]] = {

    # Units here have +1 Might. (This includes attackers.)
    "Trifarian War Camp": (
        Static(ST_MIGHT, n=1, scope=SC_UNITS_HERE),
    ),

    # Units here have [Ganking].
    "Windswept Hillock": (
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_UNITS_HERE),
    ),

    # Units here with [Temporary] have [Shield].
    # The requirement is on the AFFECTED unit, which is what makes this a
    # narrow reward for a token board rather than a blanket buff.
    "Black Flame Altar": (
        Static(ST_KEYWORD, keyword="Shield", n=1, scope=SC_UNITS_HERE,
               requires_keyword="Temporary"),
    ),

    # While a unit here is defending alone, it has -2 Might.
    # Reaches BOTH players' units, like every "units here" clause, so it is as
    # much a reason not to leave your own lone defender as it is a weapon. The
    # gate is live: a second friendly unit arriving at the battlefield turns it
    # off mid-combat.
    "Forbidding Waste": (
        Static(ST_MIGHT, n=-2, scope=SC_UNITS_HERE, cond=COND_DEFENDING_ALONE),
    ),

    # Spells and abilities affecting units here each deal 1 Bonus Damage.
    # Reaches BOTH players' spells, like every unqualified "units here" clause,
    # so it makes the ground dangerous to stand on rather than being a weapon
    # for whoever controls it.
    "Void Gate": (
        Static(ST_DAMAGE_BONUS, n=1, scope=SC_UNITS_HERE),
    ),

    # Units can't be played here.
    # The one static in the pool that takes a permission away. `scope` is
    # SC_UNITS_HERE because that is who it speaks about -- units at this
    # battlefield -- even though it is read before any of them exists.
    "Rockfall Path": (
        Static(ST_NO_PLAY, scope=SC_UNITS_HERE),
    ),

    # Bird, Cat, Dog, Poro, and Ivern units here have +1 Might.
    # One static per tag, which is exact rather than merely convenient: no card
    # in the pool carries two of these five, so nothing can be counted twice.
    "Brush": tuple(
        Static(ST_MIGHT, n=1, scope=SC_UNITS_HERE, scope_tag=_t)
        for _t in ("Bird", "Cat", "Dog", "Poro", "Ivern")),

    # Units can't move from here to base.
    # The ground that keeps what walks onto it: a unit here has to win the
    # fight or die in it, because retreating is a Move to base (455).
    "Vilemaw's Lair": (
        Static(ST_NO_MOVE_TO_BASE, scope=SC_UNITS_HERE),
    ),

    # Units here with [Tank] have +1 Might.
    # The same shape as Black Flame Altar with a different kind: the
    # requirement is on the affected unit either way, so nothing new was
    # needed to express it.
    "Kinkou Temple": (
        Static(ST_MIGHT, n=1, scope=SC_UNITS_HERE, requires_keyword="Tank"),
    ),
}


# Triggered abilities printed on a BATTLEFIELD. Separate from `ABILITIES` for
# the reason `BF_STATICS` is separate from `STATICS`: a battlefield is not a
# permanent, so it has no row for `T_SELF` to name and no controller of its own.
# Both facts are handled at the firing site (`combat._queue_bf_trigger`, which
# carries the seat) and in `resolve._slot` (which fizzles `T_SELF` and answers
# `T_HERE` with the battlefield's own location).
#
# **These fire ONCE, for the player, where a unit's fire once per unit.** "When
# you conquer here" on the ground is one trigger no matter how many units took
# it; the same words on a unit are one per unit standing there. Getting that
# backwards is the easy mistake, and it is invisible in a test with one unit.
BF_ABILITIES: dict[str, tuple[Ability, ...]] = {

    # When you conquer here, draw 1 for each other battlefield you or allies
    # control. ("Or allies" is a multiplayer clause; in a two-player game it
    # reads as "you".)
    "Seat of Power": (
        Ability(TR_CONQUER, ops=(
            Op(OP_DRAW, n=1, n_from_count=CT_MY_OTHER_BATTLEFIELDS),)),
    ),

    # When you hold here, draw 1.
    "Grove of the God-Willow": (
        Ability(TR_HOLD, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you conquer here, you may pay {1 energy} to ready your legend.
    # `optional` plus `opt_cost_energy` is 383.3.b's cost-within-instructions:
    # the choice and the payment both happen at finalization, so declining
    # removes the ability from the chain entirely (383.3.a.2).
    "Hall of Legends": (
        Ability(TR_CONQUER, optional=True, opt_cost_energy=1,
                ops=(Op(OP_READY_LEGEND),)),
    ),

    # At the start of each player's first Beginning Phase, that player gains
    # 1 point.
    # Fires for BOTH players, once each, on their own first Beginning Phase --
    # so it is symmetric and nets nothing, but it moves both players two points
    # closer to the Victory Score, which shortens the game for whoever is
    # ahead on tempo.
    "The Arena's Greatest": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_SCORE, n=1, cond=COND_FIRST_TURN),)),
    ),

    # When you conquer here, you may pay {1 energy} and return a unit you
    # control here to its owner's hand. If you do, play a 2 Might Sand Soldier
    # unit token here.
    #
    # Pickpocket's shape: the whole ability is one "you may", so declining
    # removes it (383.3.a.2) and accepting performs both halves -- "if you do"
    # needs no separate condition. `same_loc_as_source` is what "here" means
    # for a battlefield's own target slot, and it is also what makes 355.8
    # decline to offer the ability when nothing of yours is standing there.
    #
    # The trade is a real one: a conquered battlefield is held by the units on
    # it (190.4.c), so bouncing one to replace it with a token risks the ground
    # unless the token lands first -- which it does, both ops resolving
    # together.
    "Emperor's Dais": (
        Ability(TR_CONQUER, optional=True, opt_cost_energy=1,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),
                     Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SAND_SOLDIER_TOKEN))),
    ),

    # When you defend here, reveal the top card of your Main Deck. If it's a
    # spell, put it in your hand. Otherwise, recycle it.
    #
    # `pick_optional=False` because the card gives no choice: a spell GOES to
    # hand, anything else IS recycled. The look machinery still routes it
    # through an A_PICK, but with a type restriction and no opt-out there is
    # exactly one legal action either way -- a forced choice, not a decision.
    # `rest_dest` is RECYCLE rather than Diana's TOP, which is the whole
    # difference between digging and filtering.
    "Ravenbloom Conservatory": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_DEFEND,
                ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_ALL, n=1, pick_optional=False,
                        pick_types=("Spell",), pick_dest=DEST_HAND,
                        rest_dest=DEST_RECYCLE),)),
    ),

    # When you conquer here, ready 2 runes at the end of this turn.
    # The only delayed effect in the pool -- one card of 937 -- so it is banked
    # on a per-seat counter that `phases.ending` pays out, rather than a general
    # delayed-trigger queue built for a single user. Delayed is the whole point:
    # readying now would refund the runes you spent taking the ground, while
    # readying at end of turn refunds them for the OPPONENT's turn, which is
    # when they matter ([[riftbound-tapping-out-costs-the-opponents-turn]]).
    "Targon's Peak": (
        Ability(TR_CONQUER,
                ops=(Op(OP_READY_RUNES, n=2, at_end_of_turn=True),)),
    ),

    # At the start of your Beginning Phase, you may kill a unit you control
    # here to draw 1. (This happens before scoring.)
    #
    # Pickpocket's shape -- one "you may" covering cost and effect, so declining
    # removes the whole ability (383.3.a.2) and accepting does both.
    #
    # **"Before scoring" is the entire card, and it is why the Beginning Phase
    # had to learn to suspend.** 315.2.a is a step and 315.2.b is a later one,
    # but `start_turn` used to run both without stopping and drain the trigger
    # queue afterwards -- so killing your last unit here banked the Hold AND
    # drew the card. Now the ability resolves first, `control_cleanup` sees an
    # empty battlefield (190.4.c) and the Hold is gone: a real trade every turn
    # rather than a free draw.
    "Dusk Rose Lab": (
        Ability(TR_BEGINNING, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True),),
                ops=(Op(OP_KILL, target=0), Op(OP_DRAW, n=1))),
    ),

    # When you score here, you may replace this with the battlefield it
    # replaced. (The token half of Ivern - Green Father.)
    # Both ways of scoring: 470 calls a Conquer and a Hold both "scoring here",
    # and the swap-back should be available either way.
    "Brush": (
        Ability(TR_CONQUER, optional=True, ops=(Op(OP_RESTORE_BF),)),
        Ability(TR_HOLD, optional=True, ops=(Op(OP_RESTORE_BF),)),
    ),

    # When you hold here, play a 1 Might Recruit unit token in your base.
    "Altar to Unity": (
        Ability(TR_HOLD, ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                                 token=RECRUIT_TOKEN),)),
    ),

    # When you hold here, you may move a unit at a battlefield to its base.
    # Unqualified "a unit": pulling an ENEMY off contested ground is usually
    # the better half, and 449 makes it an effect Move, so nothing exhausts.
    "Amateur Recital": (
        Ability(TR_HOLD, optional=True,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # When you conquer here, put the top 2 cards of your Main Deck into your
    # trash.
    "Minefield": (
        Ability(TR_CONQUER, ops=(Op(OP_BURN, n=2),)),
    ),

    # When you hold here, [Burn 3].
    "Shadow Temple": (
        Ability(TR_HOLD, ops=(Op(OP_BURN, n=3),)),
    ),

    # When you conquer here, you may spend a buff to draw 1.
    # Written as an optional ability that CHOOSES the buffed unit and spends
    # its buff in the same resolution, rather than as an `opt_cost_*`: the
    # spend is on a unit the player picks, which is a target, and declining
    # the whole ability (383.3.a.2) is the same decision the cost would be.
    "Monastery of Hirana": (
        Ability(TR_CONQUER, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, must_be_buffed=True),),
                ops=(Op(OP_SPEND_BUFF, target=0), Op(OP_DRAW, n=1))),
    ),

    # When you hold here, you may channel 1 rune exhausted.
    "Startipped Peak": (
        Ability(TR_HOLD, optional=True, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # When you hold here, each player channels 1 rune exhausted.
    # Symmetric, and that is the point: it accelerates the board while the
    # holder is the one who chose to stand here.
    "The Papertree": (
        Ability(TR_HOLD, ops=(Op(OP_CHANNEL, n=1, each_player=True),)),
    ),

    # When you hold here, you may pay {any rune}{any rune}{any rune}{any rune}
    # to score 1 point.
    # Four Power for a point on top of the Hold's own -- the fastest clock in
    # the pool, paid for by recycling four runes off the board.
    "Power Nexus": (
        Ability(TR_HOLD, optional=True, opt_cost_power=4,
                ops=(Op(OP_SCORE, n=1),)),
    ),

    # When you conquer here, if you control 4 or fewer runes, you may pay
    # {1 energy} to draw 1.
    "Protective Sands": (
        Ability(TR_CONQUER, cond=COND_FEW_RUNES, cond_level=4, optional=True,
                opt_cost_energy=1, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you conquer here, you may pay {1 energy} to play a Gold gear token
    # exhausted.
    "Treasure Hoard": (
        Ability(TR_CONQUER, optional=True, opt_cost_energy=1,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When you hold here, buff a unit here.
    "Navori Fighting Pit": (
        Ability(TR_HOLD,
                targets=(TargetSpec(who=W_ANY, same_loc_as_source=True),),
                ops=(Op(OP_BUFF, target=0),)),
    ),

    # When you defend here, you may move a friendly unit here to base.
    # A retreat offered at the start of the Combat Showdown -- before damage,
    # which is the whole value of it.
    "Reaver's Row": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_DEFEND, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # When you defend here, choose a unit. It gains [Shield 2] this combat.
    "Fortified Position": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_DEFEND,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Shield", n=2,
                        grant_this_turn=True),)),
    ),

    # When you conquer here, you must recycle one of your runes.
    # Not optional and not a choice: the card says so, and the cost is what
    # balances a battlefield that is otherwise free to take.
    "Sigil of the Storm": (
        Ability(TR_CONQUER, ops=(Op(OP_RECYCLE_RUNE, n=1),)),
    ),

    # When you conquer here, look at the top two cards of your Main Deck. You
    # may recycle one or both of them. Put those you don't back in any order.
    "The Candlelit Sanctum": (
        Ability(TR_CONQUER, ops=(Op(OP_LOOK_TOP, n=2, pick_optional=True,
                                    pick_multi=True, pick_dest=DEST_RECYCLE,
                                    rest_dest=DEST_TOP),)),
    ),

    # When you conquer here, you may ready a friendly gear. If it's an
    # Equipment, you may detach it.
    "Veiled Temple": (
        Ability(TR_CONQUER, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, card_type=("Gear",)),),
                ops=(Op(OP_READY, target=0), Op(OP_DETACH_ONE, target=0))),
    ),

    # When you conquer here, if you assigned 3 or more excess damage, play a
    # 1 Might Bird unit token with [Deflect].
    "Trapping Grounds": (
        Ability(TR_CONQUER, cond=COND_EXCESS_AT_LEAST, cond_level=3,
                targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
                ops=(Op(OP_CREATE_TOKEN, target=0, n=1,
                        token=BIRD_TOKEN),)),
    ),

    # When you hold here, if you have 7+ units here, you win the game.
    # The only alternate win condition on a battlefield, and it asks for a
    # board no ordinary curve reaches -- seven units standing on one square.
    "The Grand Plaza": (
        Ability(TR_HOLD, cond=COND_UNITS_AT_CTX, cond_level=7,
                ops=(Op(OP_WIN),)),
    ),

    # When a player plays a spell, they may give a unit they control here
    # +1 Might this turn.
    # Fires for BOTH players, each on their own spell -- the ground is not
    # anybody's while it is being fought over.
    "Abandoned Hall": (
        Ability(TR_PLAY_SPELL, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=1,
                        grant_this_turn=True),)),
    ),

    # While you control this battlefield, when you play a spell, if you spent
    # {4 energy} or more, [Predict].
    # 436.1 -- Predicting is a look at one card that may be recycled, so it is
    # `OP_LOOK_TOP` with DEST_TOP for the card you keep.
    "Forgotten Library": (
        Ability(TR_PLAY_SPELL, subject_min_spent=4, cond=COND_HELD_HERE,
                ops=(Op(OP_LOOK_TOP, n=1, pick_optional=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP),)),
    ),

    # When a unit moves from here, give it +1 Might this turn.
    # The subject IS the unit that left, so nothing is chosen.
    "Back-Alley Bar": (
        Ability(TR_MOVE, ops=(Op(OP_MODIFY_MIGHT, target=T_SUBJECT, n=1,
                                 grant_this_turn=True),)),
    ),

    # When a player plays a unit here, they may pay {1 energy} to [Buff] it.
    "Valley of Idols": (
        Ability(TR_PLAY_UNIT, optional=True, opt_cost_energy=1,
                ops=(Op(OP_BUFF, target=T_SUBJECT),)),
    ),

    # The first time a player plays a non-token unit here each turn, they may
    # move another unit they control here to its base.
    "Star Spring": (
        Ability(TR_PLAY_UNIT, subject_nontoken=True, once_each_turn=True,
                optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True,
                                    not_subject=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # When a player chooses a friendly unit here with a spell for the first
    # time each turn, they draw 1.
    "The Dreaming Tree": (
        Ability(TR_CHOSEN, subject_card_type="Unit", subject_by_spell=True,
                once_each_turn=True, ops=(Op(OP_DRAW, n=1),)),
    ),

    # At the start of each player's Beginning Phase, deal 1 to each unit here.
    # (This happens before scoring.) -- which is what makes it a real clock on
    # a garrison rather than chip damage: a 1 Might token dies before it Holds.
    "Frozen Fortress": (
        Ability(TR_BEGINNING, ops=(Op(OP_DAMAGE_ALL, n=1, at=T_HERE),)),
    ),

    # At the start of each player's first Beginning Phase, that player channels
    # 1 rune.
    "Obelisk of Power": (
        Ability(TR_BEGINNING, ops=(Op(OP_CHANNEL, n=1, ready_runes=True,
                                      cond=COND_FIRST_TURN),)),
    ),

    # When combat starts here, the attacker and defender each [Add]
    # {1 energy}.
    # Fired once per seat with a role, which is exactly "the attacker and the
    # defender" -- and each gets the Energy in their own Rune Pool.
    "Threshold of the Gray": (
        Ability(TR_ATTACK_OR_DEFEND, ops=(Op(OP_ADD_ENERGY, n=1),)),
    ),

    # When you hold here, give your next spell this turn [Repeat] equal to its
    # base cost.
    "The Academy": (
        Ability(TR_HOLD, ops=(Op(OP_NEXT_SPELL_REPEAT),)),
    ),

    # When you conquer here with one or more [Mighty] units, you may pay
    # {1 energy} to draw 1.
    "Sunken Temple": (
        Ability(TR_CONQUER, cond=COND_MIGHTY_AT_CTX, optional=True,
                opt_cost_energy=1, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you hold here, activate the conquer effects of units here.
    # A Hold that pays like a Conquer -- the garrison's "when I conquer"
    # abilities fire without a fight, which is why this ground rewards leaving
    # units on it rather than moving them.
    "Reckoner's Arena": (
        Ability(TR_HOLD, ops=(Op(OP_ACTIVATE_CONQUERS),)),
    ),

    # When you hold here, your non-token units cost {1 energy} more to play
    # this turn.
    # A cost the HOLDER pays: the ground is worth a point and taxes the board
    # that took it.
    "Vaults of Helia": (
        Ability(TR_HOLD, ops=(Op(OP_UNIT_TAX),)),
    ),

    # When you hold here, you may return your Chosen Champion from your trash
    # to your Champion Zone if it is empty.
    # The Champion Zone is not modelled as a zone of its own -- a champion is
    # played from hand like any unit -- so the card returns to HAND, which is
    # the same permission one step later. Credited in
    # `decks.PARTIAL_TRANSCRIPTIONS`.
    "Hallowed Tomb": (
        Ability(TR_HOLD, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Unit",), champion_only=True),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When a unit here is returned to a player's hand, that player may pay
    # {1 energy} to channel 1 rune exhausted.
    "Ripper's Bay": (
        Ability(TR_LEAVES_BOARD, optional=True, opt_cost_energy=1,
                ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # When you conquer here, discard 1, then draw 1.
    # The draw is a FOLLOW-UP, not a second op: ops after a discard run before
    # the player has picked, so writing it plainly would let them pitch the
    # card they just drew. "Then" is sequencing and not a condition, so an
    # empty hand still draws -- which `OP_DISCARD_CHOOSE` handles by running
    # the follow-up inline when there is nothing to discard.
    "Zaun Warrens": (
        Ability(TR_CONQUER, ops=(
            Op(OP_DISCARD_CHOOSE, n=1, then_key=FU_DRAW_1),)),
    ),
}


# Abilities printed on a Champion Legend (103.1). In the Legend Zone from turn
# 1 and never leaving it, so unlike everything else in these tables a legend's
# ability is available on EVERY turn of the game from the first -- which is why
# most of them charge an Exhaust, and why the Awaken Phase recharging it
# (315.1.b) is what makes them engines rather than one-shots.
LEGEND_ABILITIES: dict[str, tuple[Ability, ...]] = {

    # {4 energy}, Exhaust: Play a ready 3 Might Sprite unit token with
    # [Temporary]. This ability costs {1 energy} less for each friendly unit
    # with [Temporary].
    #
    # The most-played legend in the corpus by a distance (17 of 36 decks), and
    # the discount is the whole card: a wide Temporary board pays for the next
    # Sprite, so the ability gets cheaper exactly as the deck does what it
    # wants. The scaling lives in LEGEND_STATICS, where a cost discount
    # belongs; this half is only the effect.
    "Lillia - Bashful Bloom": (
        Ability(TR_ACTIVATED, cost_energy=4, cost_exhaust=True,
                targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
                ops=(Op(OP_CREATE_TOKEN, target=0, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # When you win a combat, draw 1. (You win if only your units remain after
    # combat.)
    "Draven - Glorious Executioner": (
        Ability(TR_WIN_COMBAT, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you win a combat, gain 1 XP.
    # Spend 1 XP, Exhaust: [Buff] a unit.
    # Spend 2 XP, Exhaust: Move an exhausted friendly unit from a battlefield
    # to its base.
    #
    # The two activated abilities share one Exhaust, so the XP the win gives is
    # spent on one or the other each turn, never both. "A unit" for the Buff is
    # unqualified (either player's); the retreat names "friendly" and
    # "exhausted", and `must_be_exhausted` keeps it from being spent on a unit
    # that could simply walk home itself.
    "Kha'Zix - Voidreaver": (
        Ability(TR_WIN_COMBAT, ops=(Op(OP_GAIN_XP, n=1),)),
        Ability(TR_ACTIVATED, cost_xp=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_BUFF, target=0),)),
        Ability(TR_ACTIVATED, cost_xp=2, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True,
                                    must_be_exhausted=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # {1 energy}, Exhaust: Play a 1 Might Recruit unit token.
    # No location clause: your base or a battlefield you control (FAQ #4020).
    "Viktor - Herald of the Arcane": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
                ops=(Op(OP_CREATE_TOKEN, target=0, n=1,
                        token=RECRUIT_TOKEN),)),
    ),

    # [Reaction] Exhaust: [Add] {1 energy}. Spend this Energy only during
    # showdowns.
    # The restriction is the card: a rune exhausted on your own turn is gone on
    # the opponent's ([[riftbound-tapping-out-costs-the-opponents-turn]]), so
    # Energy that only exists inside a showdown is Energy you could not have
    # held otherwise. `immediate` because 337.2 resolves an [Add] without the
    # Chain, which is also why the reminder says it cannot be reacted to.
    "Diana - Scorn of the Moon": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_SPELL_ENERGY, n=1, level=RK_SHOWDOWN),)),
    ),

    # [Reaction] Exhaust: [Add] {any rune}. Use only to play gear or use gear
    # abilities.
    # "{any rune}" is POWER of any domain (164.2), not Energy -- `power` on the
    # op rather than `n`, which is the difference between paying a rune symbol
    # and paying a number.
    "Ornn - Fire Below the Mountain": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_SPELL_ENERGY, power=1, level=RK_GEAR),)),
    ),

    # Exhaust: [Reaction] — [Add] {any rune}. Use only to play spells.
    "Kai'Sa - Daughter of the Void": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_SPELL_ENERGY, power=1, level=RK_SPELL),)),
    ),

    # [Reaction] {any rune}{any rune}, Exhaust: [Add] {2 energy}. Spend this
    # Energy only to play units or activated abilities of units.
    # A rune cost for a rune's worth of Energy: the profit is in the CONVERSION
    # (two Power into two Energy) and in the timing, not in the count.
    "Renekton - Butcher of the Sands": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_power=2,
                cost_exhaust=True, immediate=True,
                ops=(Op(OP_ADD_SPELL_ENERGY, n=2, level=RK_UNIT),)),
    ),

    # Exhaust: [Reaction], [Legion] — [Add] {1 energy}.
    # 822 -- [Legion] is a condition on the EFFECT, not on the activation, so
    # the ability may be used with nothing played this turn and simply adds
    # nothing. That is why it is an op condition rather than `Ability.cond`.
    "Darius - Hand of Noxus": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_ENERGY, n=1, cond=COND_LEGION),)),
    ),

    # At the start of your Beginning Phase, draw 1 if you have one or fewer
    # cards in your hand.
    "Jinx - Loose Cannon": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_DRAW, n=1, cond=COND_HAND_AT_MOST, level=1),)),
    ),

    # When you play a spell that costs {5 energy} or more, draw 1.
    "Lux - Lady of Luminosity": (
        Ability(TR_PLAY_SPELL, subject_min_energy=5,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # {1 energy}, Exhaust: Buff a friendly unit.
    "Lee Sin - Blind Monk": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY),),
                ops=(Op(OP_BUFF, target=0),)),
    ),

    # Exhaust: Give a unit [Ganking] this turn.
    # Unqualified "a unit", so it may be pointed at an enemy -- which is not
    # the gift it looks like: [Ganking] lets a unit move battlefield to
    # battlefield (449), and moving is what starts a combat you chose.
    "Miss Fortune - Bounty Hunter": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Ganking",
                        grant_this_turn=True),)),
    ),

    # [Action] Exhaust: Give a friendly unit [Tank] this turn.
    # [Action] speed, so it is playable in a showdown -- which is the whole
    # card: [Tank] reorders combat damage assignment (810), and the moment to
    # decide who takes it is after the fight is staged.
    "Shen - Eye of Twilight": (
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY),),
                ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Tank",
                        grant_this_turn=True),)),
    ),

    # When you hold, gain 1 XP.
    # Spend 3 XP, Exhaust: Draw 1.
    "Poppy - Keeper of the Hammer": (
        Ability(TR_HOLD, ops=(Op(OP_GAIN_XP, n=1),)),
        Ability(TR_ACTIVATED, cost_xp=3, cost_exhaust=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you or an ally hold, you may exhaust me to draw 1.
    # "Or an ally" is a multiplayer clause; in a two-player game it is "you".
    # The Exhaust is an OPTIONAL cost inside the trigger (383.3.b), so
    # declining leaves the champion ready for something else.
    "Vex - Gloomist": (
        Ability(TR_HOLD, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you conquer, if you have 4+ units at that battlefield, draw 2.
    # The count is about the ground that was taken (`ctx`), not about wherever
    # the champion is -- a legend stands nowhere.
    "Garen - Might of Demacia": (
        Ability(TR_CONQUER, cond=COND_UNITS_AT_CTX, cond_level=4,
                ops=(Op(OP_DRAW, n=2),)),
    ),

    # When you play a unit, give a unit +1 Might this turn.
    # Mandatory and unqualified: with only enemies on the board the +1 has to
    # go to one of them, which is 355.8 rather than a choice.
    "Rengar - Pridestalker": (
        Ability(TR_PLAY_UNIT, targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=1,
                        grant_this_turn=True),)),
    ),

    # When you stun one or more enemy units, buff a friendly unit.
    # "One or more" is the event, not a count: one Stun of three units fires
    # this once, which is what a watcher on the STUN event already does.
    "Leona - Radiant Dawn": (
        Ability(TR_STUN, subject_enemy=True, once_each_turn=False,
                targets=(TargetSpec(who=W_FRIENDLY),),
                ops=(Op(OP_BUFF, target=0),)),
    ),

    # When you play a [Mighty] unit, you may exhaust me to channel 1 rune
    # exhausted. (A unit is Mighty while it has 5+ Might.)
    "Volibear - Relentless Storm": (
        Ability(TR_PLAY_UNIT, subject_min_power=5, optional=True,
                opt_cost_exhaust_self=True,
                ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # When one of your units becomes [Mighty], you may exhaust me to channel 1
    # rune exhausted.
    "Fiora - Grand Duelist": (
        Ability(TR_BECOME_MIGHTY, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # When you empower something else, empower me.
    # Disempower me, {any rune}, Exhaust: Ready a unit.
    # The loop is closed by `chain.fire_empowered`, which never fires a
    # watcher on its own Empower -- otherwise she would empower herself off
    # her own trigger forever.
    "Ambessa - Matriarch of War": (
        Ability(TR_BECOME_EMPOWERED, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_disempower_self=True, cost_power=1,
                cost_exhaust=True, targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # When you empower something else, empower me.
    # Disempower me, Exhaust: Give a unit at a battlefield -2 Might this turn.
    "Mel - Soul's Reflection": (
        Ability(TR_BECOME_EMPOWERED, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_disempower_self=True, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2,
                        grant_this_turn=True),)),
    ),

    # [Empower] {3 energy}{any rune}
    # [Action] Exhaust: If it's your turn, move a friendly unit in a showdown
    # to base and if I'm [Empowered], ready it.
    #
    # The retreat is the card and the Empower is its upgrade: pulling a unit
    # out of a fight it would lose costs it the turn, unless she is Empowered,
    # in which case it comes home ready to move again. `own_turn` is the
    # printed "if it's your turn", which matters because [Action] speed would
    # otherwise let it happen inside the opponent's showdown.
    "Akali - Rogue Assassin": (
        Ability(TR_ACTIVATED, cost_energy=3, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_exhaust=True,
                own_turn=True,
                targets=(TargetSpec(who=W_FRIENDLY, in_showdown=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),
                     Op(OP_READY, target=0, cond=COND_EMPOWERED))),
    ),

    # [Empower] {2 energy}{any rune}{any rune}
    # {1 energy}, Exhaust: Ready a gear.
    # [Empowered] > {1 energy}, Exhaust: Ready 2 gear.
    #
    # Two activated abilities sharing one Exhaust, so the Empowered line
    # REPLACES the plain one for the turn rather than adding to it -- which is
    # what "[Empowered] >" means on a cost that is already once per turn.
    "Jayce - Defender of Tomorrow": (
        Ability(TR_ACTIVATED, cost_energy=2, cost_power=2,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),),
                ops=(Op(OP_READY, target=0),)),
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                cond=COND_EMPOWERED,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",)),
                         TargetSpec(who=W_ANY, card_type=("Gear",),
                                    distinct_from=0, optional=True)),
                ops=(Op(OP_READY, target=0), Op(OP_READY, target=1))),
    ),

    # {1 energy}, Exhaust: Play a 2 Might Sand Soldier unit token to your base.
    # Use only if you've played an Equipment this turn.
    # The gate is the deck: Azir wants Equipment for the Weaponmaster half of
    # his text anyway, and this makes the two halves one plan.
    "Azir - Emperor of the Sands": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                cond=COND_PLAYED_EQUIPMENT,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=SAND_SOLDIER_TOKEN),)),
    ),

    # When an enemy unit attacks a battlefield you control, give it -1 Might
    # this turn, to a minimum of 1 Might.
    # The subject is the attacker (the trigger carries it), and the battlefield
    # test is on the CAPTURED location -- she stands nowhere herself.
    "Ahri - Nine-Tailed Fox": (
        Ability(TR_ATTACK_OR_DEFEND, subject_enemy=True,
                subject_role=ROLE_ATTACK, cond=COND_CTX_BF_MINE,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SUBJECT, n=-1, floor=1,
                        grant_this_turn=True),)),
    ),

    # When you play a unit, gear, or activated ability with Energy cost
    # {7 energy} or more, you may exhaust me to ready up to 2 runes.
    # The ability half is not reachable: `TR_PLAY_UNIT` fires for permanents,
    # and an activated ability is not one. Credited in
    # `decks.PARTIAL_TRANSCRIPTIONS`.
    "Nasus - Curator of the Sands": (
        Ability(TR_PLAY_UNIT, subject_card_type="Unit", subject_min_energy=7,
                optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_READY_RUNES, n=2),)),
    ),

    # When you choose a friendly unit, you may exhaust me and pay {any rune}
    # to ready it.
    # When you conquer, you may pay {1 energy} to ready me.
    #
    # The first is why she is played: every spell that chooses one of your
    # units becomes half a ready, and `TR_CHOSEN` is the same event Irelia,
    # Fervent watches from the board.
    "Irelia - Blade Dancer": (
        Ability(TR_CHOSEN, subject_card_type="Unit", optional=True,
                opt_cost_exhaust_self=True, opt_cost_power=1,
                ops=(Op(OP_READY, target=T_SUBJECT),)),
        Ability(TR_CONQUER, optional=True, opt_cost_energy=1,
                ops=(Op(OP_READY_LEGEND),)),
    ),

    # When you conquer, if you assigned 3 or more excess damage, you may
    # exhaust me to ready a unit.
    "Vi - Piltover Enforcer": (
        Ability(TR_CONQUER, cond=COND_EXCESS_AT_LEAST, cond_level=3,
                optional=True, opt_cost_exhaust_self=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # {2 energy}, Exhaust: Move a friendly unit to or from its base.
    # One slot for the unit and one for where it goes: 449 makes this an effect
    # Move, so it conquers, forces a fight and does not exhaust the unit.
    "Yasuo - Unforgiven": (
        Ability(TR_ACTIVATED, cost_energy=2, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),
                         TargetSpec(kind=TK_LOCATION, move_dest_of=0,
                                    locality=LOC_FREE)),
                ops=(Op(OP_MOVE_TO, target=0, target_b=1),)),
    ),

    # {1 energy}, Exhaust: Return a friendly unit at a battlefield to its
    # owner's hand. Play a Gold gear token exhausted.
    # The bounce is the cost of the Gold in practice -- and with a unit whose
    # "when you play me" is worth repeating, it is the whole engine.
    "Pyke - Bloodharbor Ripper": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),
                     Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN))),
    ),

    # {1 energy}, Exhaust: Attach a detached Equipment you control to a unit
    # you control.
    # Exhaust: Attach an attached Equipment you control to a unit you control.
    # Two abilities sharing one Exhaust: the free one only MOVES a gear that is
    # already on a unit, and the paid one brings a loose one into play on a
    # body -- which is the difference between fixing a bad attachment and
    # making a new one.
    "Jax - Grandmaster At Arms": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY),
                         TargetSpec(who=W_FRIENDLY, card_type=("Gear",),
                                    tags=("Equipment",), equipped=False)),
                ops=(Op(OP_ATTACH, target=0, target_b=1),)),
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY),
                         TargetSpec(who=W_FRIENDLY, card_type=("Gear",),
                                    tags=("Equipment",), equipped=True)),
                ops=(Op(OP_ATTACH, target=0, target_b=1),)),
    ),

    # When you recycle a rune, you may exhaust me to play a Gold gear token
    # exhausted.
    # When one or more enemy units die, ready me.
    # The two halves are a loop: the Gold pays a Power cost, paying it recycles
    # a rune, and the enemy deaths that come out of the fight ready her to do
    # it again.
    "Sivir - Battle Mistress": (
        Ability(TR_RUNE_RECYCLED, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
        Ability(TR_OTHER_DIES, subject_enemy=True,
                ops=(Op(OP_READY_LEGEND),)),
    ),

    # When you banish a card you own, empower me.
    # [Action] Disempower me, Exhaust: Discard 1, then draw 1.
    # The draw is a FOLLOW-UP and not a second op, for the reason Zaun Warrens
    # documents: ops after a discard run before the player has chosen, so a
    # plain second op would let them pitch the card they just drew.
    "Zed - Master of Shadows": (
        Ability(TR_BANISHED, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_disempower_self=True,
                cost_exhaust=True,
                ops=(Op(OP_DISCARD_CHOOSE, n=1, then_key=FU_DRAW_1),)),
    ),

    # When you play a card from anywhere other than your hand, empower me.
    # [Action] Disempower me, Exhaust: Give a unit [Assault 2] this turn.
    "Yordle, Kennen - Heart of the Tempest": (
        Ability(TR_PLAY_NONHAND, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_disempower_self=True,
                cost_exhaust=True, targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Assault", n=2,
                        grant_this_turn=True),)),
    ),

    # Exhaust: [Reaction] — Draw 1. Use only if you've chosen enemy units
    # and/or gear twice this turn with spells or unit abilities.
    # The count is per TURN and is kept beside the stamp that says which turn
    # it belongs to, so it needs no reset of its own.
    "Ezreal - Prodigal Explorer": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                cond=COND_CHOSE_ENEMY_TWICE, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you or an ally hold, you may exhaust me to play a Gold gear token
    # exhausted.
    # The second sentence ("while your score is within 3 points of the Victory
    # Score, your Gold [Add] an additional {1 energy}") modifies the TOKEN's
    # own ability, which nothing can reach yet. Credited in
    # `decks.PARTIAL_TRANSCRIPTIONS`.
    "Renata Glasc - Chem-Baroness": (
        Ability(TR_HOLD, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When you conquer, you may exhaust me to reveal the top 2 cards of your
    # Main Deck. You may banish one, then play it. Recycle the rest.
    "Rek'sai - Void Burrower": (
        Ability(TR_CONQUER, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_REVEAL_PLAY, n=2, pick_optional=True,
                        rest_dest=DEST_RECYCLE, cost=COST_PRINTED),)),
    ),

    # When you conquer or hold, you may discard 1 and exhaust me to play a
    # ready Reflection unit token there. Then do this: It becomes a copy of
    # another unit there. Give it [Temporary].
    #
    # "There" is the battlefield the trigger captured, which is what `T_CTX`
    # names -- the token joins the ground that was just taken, so it holds it
    # next turn even though it expires at the start of the one after.
    "LeBlanc - Deceiver": (
        Ability(TR_CONQUER, optional=True, opt_cost_exhaust_self=True,
                opt_cost_discard=1,
                targets=(TargetSpec(who=W_ANY, rel=REL_SAME_BF, rel_to=-1,
                                    at_battlefield=True),),
                ops=(Op(OP_COPY_PREP, target=0),
                     Op(OP_CREATE_TOKEN, target=T_CTX, n=1,
                        token=REFLECTION_TOKEN, ready=True,
                        then_key=FU_BECOME_COPY_TEMP))),
        Ability(TR_HOLD, optional=True, opt_cost_exhaust_self=True,
                opt_cost_discard=1,
                targets=(TargetSpec(who=W_ANY, rel=REL_SAME_BF, rel_to=-1,
                                    at_battlefield=True),),
                ops=(Op(OP_COPY_PREP, target=0),
                     Op(OP_CREATE_TOKEN, target=T_CTX, n=1,
                        token=REFLECTION_TOKEN, ready=True,
                        then_key=FU_BECOME_COPY_TEMP))),
    ),

    # {1 energy}, Exhaust: Put a Teemo unit you own into your hand from your
    # Champion Zone or the board.
    # The board half only: a Champion Zone is not modelled, and the card in it
    # is `state.champion`. Credited in `decks.PARTIAL_TRANSCRIPTIONS`, together
    # with the hide-cost line ("you may pay {1 energy} to hide a card with
    # [Hidden] instead of {any rune}"), which is a cost substitution nothing
    # reads yet.
    "Teemo - Swift Scout": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, tags=("Teemo",)),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # When you conquer, ready me.
    # The other half ("if a buffed unit you control would die, you may pay
    # {any rune}, exhaust me, and spend its buff to heal it, exhaust it, and
    # recall it instead") is a death REPLACEMENT that charges a cost at the
    # moment of death -- the engine's `death_guard` is a promise made in
    # advance and asks for nothing. Credited in
    # `decks.PARTIAL_TRANSCRIPTIONS`.
    "Sett - The Boss": (
        Ability(TR_CONQUER, ops=(Op(OP_READY_LEGEND),)),
    ),

    # When you conquer or hold, you may exhaust me to replace that battlefield
    # with a Brush battlefield token.
    # The ground keeps everything except its card: control, the units standing
    # there and the contested status are properties of the LOCATION.
    "Ivern - Green Father": (
        Ability(TR_CONQUER, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_REPLACE_BF, tag="Brush"),)),
        Ability(TR_HOLD, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_REPLACE_BF, tag="Brush"),)),
    ),

    # When you play a spell, if you spent {4 energy} or more, you may banish
    # it. Then, if there are four spells banished with me, put each in its
    # trash, channel 4 runes, and draw 1.
    #
    # 419.4.a -- the trigger waits for the spell to resolve, so the spell's
    # effect happens and it is then banished out of the trash. The four are
    # remembered on the champion
    # (`state.legend_pile`), because Banishment holds cards from every source
    # and only these four come back.
    "Jhin - Virtuoso": (
        Ability(TR_PLAY_SPELL, subject_min_spent=4, optional=True,
                ops=(Op(OP_BANISH_SPELL_PILE),)),
    ),

    # At the end of your turn, ready 2 runes.
    # Not an activated ability and costs no exhaust, so it pays out every turn
    # whatever the legend did -- which is why tapping out costs this deck less
    # than any other ([[riftbound-tapping-out-costs-the-opponents-turn]]).
    "Annie - Dark Child": (
        Ability(TR_END_OF_TURN, ops=(Op(OP_READY_RUNES, n=2),)),
    ),
}


LEGEND_STATICS: dict[str, tuple[Static, ...]] = {

    # Your Mechs have [Shield]. (+1 Might while they're defenders.)
    "Rumble - Mechanized Menace": (
        Static(ST_KEYWORD, keyword="Shield", n=1, scope=SC_FRIENDLY_UNITS,
               scope_tag="Mech"),
    ),

    # Your Sand Soldiers have [Weaponmaster].
    # By NAME: the token's only tag is Shurima, and "Sand Soldiers" is what the
    # card says -- every one of them is the token this deck makes.
    "Azir - Emperor of the Sands": (
        Static(ST_KEYWORD, keyword="Weaponmaster", n=1,
               scope=SC_FRIENDLY_UNITS, scope_name="Sand Soldier"),
    ),

    # Your Equipment each give [Assault]. (+1 Might while the equipped unit is
    # an attacker.)
    # One instance per equipped UNIT rather than per Equipment: a unit wearing
    # two gears should get [Assault 2] and gets [Assault 1] here. Credited in
    # `decks.PARTIAL_TRANSCRIPTIONS`.
    "Lucian - Purifier": (
        Static(ST_KEYWORD, keyword="Assault", n=1, scope=SC_FRIENDLY_UNITS,
               requires_equipped=True),
    ),

    # [Level 6] > Your units have +1 Might.
    # [Level 11] > Your units enter ready.
    # XP never resets, so both read live -- the deck's whole plan is to climb
    # past 6 and then past 11 in one game.
    "Master Yi - Wuju Master": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, cond=COND_LEVEL,
               level=6),
        Static(ST_ENTERS_READY, scope=SC_FRIENDLY_UNITS, cond=COND_LEVEL,
               level=11),
    ),

    # While a friendly unit defends alone, it gets +2 Might.
    # A requirement on the AFFECTED unit (`requires_defending_alone`), not a
    # gate on the legend: the +2 follows whichever unit is standing alone, and
    # switches off the moment a second defender walks in.
    "Master Yi - Wuju Bladesman": (
        Static(ST_MIGHT, n=2, scope=SC_FRIENDLY_UNITS,
               requires_defending_alone=True),
    ),

    # "This ability costs {1 energy} less for each friendly unit with
    # [Temporary]" -- the scaling half of Lillia - Bashful Bloom.
    "Lillia - Bashful Bloom": (
        Static(ST_COST_ENERGY, n=1, per_keyword="Temporary",
               per_friendly=True, per_same_loc=False, per=CNT_BOARD),
    ),
}


STATICS: dict[str, tuple[Static, ...]] = {

    # You may play me to an open battlefield.
    # Friendly units may be played to open battlefields.
    #
    # Only the SECOND sentence is a static -- the first is in
    # PLAY_PERMISSIONS, because it has to apply while she is still in hand and
    # this static is not on the board yet. They say the same thing about two
    # different moments, which is why the card prints both.
    #
    # SC_YOUR_CARDS: what it affects is a card in hand, not a permanent, so no
    # board-walking scope could express it. `combat.grants_open_play` reads it.
    #
    # This is the card that makes playing onto empty ground a real strategy
    # rather than a rules mistake: 806.3 forces a Move to take new ground, and
    # a Move is what starts a Combat, so she is the deck's way of conquering
    # without ever fighting for it.
    "Miss Fortune - Buccaneer": (
        Static(ST_PLAY_OPEN, scope=SC_YOUR_CARDS),
    ),

    # [Empowered][>] I have +3 Might and can't be dealt damage unless I'm in
    # combat. See the ABILITIES entry for why this is two statics.
    "Ambessa, The Wolf": (
        Static(ST_MIGHT, n=3, scope=SC_SELF, cond=COND_EMPOWERED),
        Static(ST_NO_DAMAGE, scope=SC_SELF, cond=COND_EMPOWERED),
    ),

    # "Your spells cost {1 energy}{any rune} less, to a minimum of {1 energy}."
    #
    # Two statics, one per COMPONENT: 356.4.d applies discounts to Energy and
    # to Power separately, so a single line of card text that reduces both is
    # two effects. `applies_to_type="Spell"` is the filter -- her own units and
    # gear pay full price.
    #
    # The floor rides on the ENERGY half only, because that is what the card
    # says: "a minimum of {1 energy}" names Energy, and 356.4.e binds a minimum
    # to its own discount rather than to the whole cost. Power needs no floor;
    # a cost cannot go below zero anyway.
    # [Empower] {4 energy}{Calm rune}
    # Opponents' spells cost {1 energy} more. If this is [Empowered], they cost
    # {1 energy}{any rune} more INSTEAD.
    #
    # "Instead" as two statics that ADD, the same route Rage Amplifier takes --
    # and here it is exact rather than merely equivalent: the ENERGY half is
    # {1 energy} in both readings, so the only thing the Empowered clause adds
    # is the Power symbol. An ungated +1 Energy plus an Empowered-gated +1
    # Power reads {1 energy} before and {1 energy}{any rune} after, never
    # {2 energy}{any rune}.
    "Helm of Suppression": (
        Static(ST_COST_ENERGY_UP, n=1, scope=SC_ENEMY_CARDS,
               applies_to_type="Spell"),
        Static(ST_COST_POWER_UP, n=1, scope=SC_ENEMY_CARDS,
               applies_to_type="Spell", cond=COND_EMPOWERED),
    ),

    # While I'm in combat, friendly spells cost {1 energy}{any rune} less to a
    # minimum of {1 energy}, and enemy spells cost {1 energy}{any rune} more.
    #
    # Four statics for one sentence, and the split is the rules': 356.3 raises
    # costs and 356.4 lowers them in separate steps, and 356.4.c applies a
    # discount per COMPONENT. So this is {down, up} x {Energy, Power}, and the
    # stated minimum binds only the Energy discount it is printed on (356.4.e).
    #
    # `SC_ENEMY_CARDS` is read off HER controller: the static lives on her, and
    # the seat it taxes is whoever is not her controller.
    "Vex - Cheerless": (
        Static(ST_COST_ENERGY, n=1, scope=SC_YOUR_CARDS,
               applies_to_type="Spell", cond=COND_IN_COMBAT, floor=1),
        Static(ST_COST_POWER, n=1, scope=SC_YOUR_CARDS,
               applies_to_type="Spell", cond=COND_IN_COMBAT),
        Static(ST_COST_ENERGY_UP, n=1, scope=SC_ENEMY_CARDS,
               applies_to_type="Spell", cond=COND_IN_COMBAT),
        Static(ST_COST_POWER_UP, n=1, scope=SC_ENEMY_CARDS,
               applies_to_type="Spell", cond=COND_IN_COMBAT),
    ),

    "Applied Researchers": (
        Static(ST_COST_ENERGY, n=1, scope=SC_YOUR_CARDS,
               applies_to_type="Spell", cond=COND_EMPOWERED, floor=1),
        Static(ST_COST_POWER, n=1, scope=SC_YOUR_CARDS,
               applies_to_type="Spell", cond=COND_EMPOWERED),
    ),

    # "+2 Might for each time I'm [Empowered]", and at three a pair of granted
    # keywords. `per=CNT_EMPOWER` scales off her own row; the two keyword
    # statics gate on `COND_EMPOWERED_N` with `level=3`, which is "at least
    # three" the same way `COND_LEVEL` reads XP.
    "Kayle, Justified": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, per=CNT_EMPOWER),
        Static(ST_KEYWORD, keyword="Deflect", n=3, scope=SC_SELF,
               cond=COND_EMPOWERED_N, level=3),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED_N, level=3),
    ),

    # [Empowered][>] I have +2 Might.
    "Mournful Witness": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_EMPOWERED),
    ),

    # [Empowered][>] I have +2 Might.
    "Escaped Grayback": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_EMPOWERED),
    ),

    # If an opponent's score is within 3 points of the Victory Score, this
    # costs {2 energy} less. A catch-up discount: read live off the scoreboard
    # as the card is played, so it switches on the moment the opponent gets
    # there and off again if they somehow fall back.
    "Find Your Center": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_OPP_NEAR_VICTORY),
    ),

    # I have +1 Might for each of your units with [Temporary] at my battlefield.
    "Petal Pixie": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per_keyword="Temporary",
               per_friendly=True, per_same_loc=True),
    ),

    # [Hunt 2] [Level 3][>] I have +1 Might and enter ready.
    #
    # Two halves on two different mechanisms, which is the whole reason this
    # card was not simply a transcription. The Might is continuous and read
    # live, so it is a static gated on COND_LEVEL -- XP never resets (see
    # `_condition_holds`), so crossing 3 XP mid-turn turns it on at once. The
    # readiness is a one-shot replacement decided as the unit is played
    # (359.2.c) and cannot be a static at all; it lives in `ENTERS_READY_IF`.
    #
    # [Hunt 2] is synthesised from the keyword and needs no entry here -- it
    # is what BANKS the XP this gate then spends, so the card is a closed
    # loop: Score to level up, and every later copy arrives ready.
    "Scorchclaw": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_LEVEL, level=3),
    ),

    # --- [Empowered] dependent abilities (828.1.b.1) -----------------------
    # "While I have the Empowered status, this card gains '[Text]'", so each of
    # these is an ordinary self-static with COND_EMPOWERED as its gate. Read
    # live: the status can be gained mid-turn and the bonus applies the instant
    # it is.

    "Solari Sunhawk": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Deflect", n=2, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    # [Empowered][>] I have +1 Might. The other half of the card is the
    # [Empower] cost and the "when I become Empowered" Predict, both in
    # ABILITIES -- 828.1.b.1's dependent ability is a static like any other.
    "Apprentice Mage": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_EMPOWERED),
    ),
    # While I'm buffed, I have an additional +1 Might.
    # "Additional" -- on top of the +1 the Buff itself gives (703).
    "Wizened Elder": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_SRC_BUFFED),
    ),
    # While you have 8+ runes, I have +4 Might.
    # Runes you control, ready OR exhausted -- a rune does not stop being
    # yours by being spent.
    "Master Yi - Meditative": (
        Static(ST_MIGHT, n=4, scope=SC_SELF, cond=COND_RUNES_AT_LEAST, level=8),
    ),
    # While you have another unit here, I have +1 Might.
    "Trusty Ramhound": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_ANOTHER_FRIENDLY_HERE),
    ),
    # My Might is increased by your points.
    "Draven, Showboat": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per=CNT_POINTS),
    ),
    # Other friendly units have +1 Might here.
    # "Here" is HIS location, base included -- the card does not say
    # battlefield.
    "Garen - Commander": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, scope_not_self=True,
               scope_same_loc=True),
    ),
    # [Hidden]  I have +1 Might for each other unit you control here with my
    # name.
    "Spiderling": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per_card_type="Unit",
               per_same_name=True, per_not_self=True),
    ),
    # [Hunt 2]  (play permission in PLAY_PERMISSIONS)  Friendly units can be
    # played to an occupied battlefield if an enemy unit is alone there.
    "Arachnoid Horror": (
        Static(ST_PLAY_ENEMY_ALONE, scope=SC_YOUR_CARDS),
    ),

    # I must be assigned combat damage last.  (The replacement for smaller
    # allies here is SMALLER_ALLY_GUARDS.)  "Assigned combat damage last" is
    # [Backline]'s own reminder text, so it is that keyword, granted to me.
    "Soraka - Wanderer": (
        Static(ST_KEYWORD, keyword="Backline", n=1, scope=SC_SELF),
    ),
    # I have +1 Might for each token unit you control.
    "Illaoi, Prophet of the Great Kraken": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per_card_type="Unit",
               per_token=True, per_same_loc=False),
    ),
    # [Deflect 2] [Weaponmaster]  I have +1 Might for each friendly gear.
    "Ornn - Forge God": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per_card_type="Gear",
               per_same_loc=False),
    ),
    "Punching Poro": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_EMPOWERED),
    ),
    # While I'm [Mighty], I have [Deflect], [Ganking], and [Shield].
    "Fiora - Victorious": tuple(
        Static(ST_KEYWORD, keyword=kw, n=1, scope=SC_SELF, cond=COND_SRC_MIGHTY)
        for kw in ("Deflect", "Ganking", "Shield")),
    # [Accelerate]  If you've spent at least {any rune}{any rune} this turn, I
    # have +2 Might and [Ganking].
    "Sivir - Mercenary": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_POWER_SPENT_2),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_POWER_SPENT_2),
    ),
    # [Shield 5] [Tank]  I cost {2 energy}{Calm rune} less for each point you
    # scored from holding this turn.
    "Needlessly Large Yordle": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, per=CNT_HOLD_POINTS),
        Static(ST_COST_POWER, n=1, scope=SC_SELF, per=CNT_HOLD_POINTS),
    ),
    # Friendly buffed units have [Deflect] if they didn't already.
    "Spirit's Refuge": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_FRIENDLY_UNITS,
               requires_buffed=True, lacks_printed_keyword="Deflect"),
    ),
    "Concentrate": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_LEVEL, level=6),
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_LEVEL, level=11),
    ),
    # [Level 3] I cost {2 energy}{Calm} less. [Level 6] {4}{Calm}{Calm} instead.
    # [Level 11] {6}{Calm x3} instead. [Level 16] I can't be chosen by enemy
    # spells and abilities.  "Instead" steps are written as increments.
    "Master Yi - Unstoppable": tuple(
        Static(kind, n=n, scope=SC_SELF, cond=COND_LEVEL, level=lv)
        for lv in (3, 6, 11)
        for kind, n in ((ST_COST_ENERGY, 2), (ST_COST_POWER, 1))) + (
        Static(ST_UNCHOOSABLE, scope=SC_SELF, cond=COND_LEVEL, level=16),
    ),
    "Frostcoat Mother": (
        Static(ST_MIGHT, n=3, scope=SC_SELF, cond=COND_EMPOWERED),
    ),
    "Grumpy Rockbear": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Shield", n=3, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Baccai Sandspinner": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Assault", n=2, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Darius - Executioner": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, scope_not_self=True,
               scope_same_loc=True),
    ),

    # If you've spent {4 energy} or more to play a spell this turn, I have
    # +4 Might.
    "Prepared Neophyte": (
        Static(ST_MIGHT, n=4, scope=SC_SELF, cond=COND_BIG_SPELL_THIS_TURN),
    ),
    # I cost {2 energy}{Order rune} less if you control a battlefield with
    # exactly two units there.
    "Keeper of Law": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_BF_EXACTLY_TWO_UNITS),
        Static(ST_COST_POWER, n=1, scope=SC_SELF, cond=COND_BF_EXACTLY_TWO_UNITS),
    ),
    # [Accelerate]  I cost {2 energy} less for each of your [Mighty] units.
    "Jaull-Fish": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, per=CNT_MIGHTY),
    ),
    "Daisy!": (
        Static(ST_COST_ENERGY, n=1, scope=SC_SELF, per=CNT_ANIMAL_TAGS),
    ),
    "Sky Splitter": (
        Static(ST_COST_ENERGY, n=1, scope=SC_SELF, per=CNT_HIGHEST_MIGHT),
    ),

    # [Temporary]  Friendly units have [Deflect].
    "Petricite Monument": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_FRIENDLY_UNITS),
    ),
    # [Deflect]  While I'm at a battlefield, your other units here have
    # [Deflect].
    "Allay, Eager Admirer": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_FRIENDLY_UNITS,
               scope_not_self=True, scope_same_loc=True, cond=COND_SRC_AT_BF),
    ),
    # [Hidden]  I have [Shield 3] while I'm at a battlefield with exactly one
    # other unit you control.
    "Disciple of Shen": (
        Static(ST_KEYWORD, keyword="Shield", n=3, scope=SC_SELF,
               cond=COND_AT_BF_N_OTHERS, level=1),
    ),
    # I have +2 Might while I'm attacking with another unit.
    "Crimson Pigeons": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_ATTACKING_WITH_ANOTHER),
    ),
    # While I'm attacking or defending alone, I have +2 Might.
    "Wielder of Water": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_COMBAT_ALONE),
    ),
    # [Empowered] I have [Deflect] and [Ganking].
    "Renekton, Brute": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    # [Hunt] [Level 6] I have +1 Might.  (The printed text ends in a stray
    # "ambush" with no brackets or reminder -- data noise, not [Ambush].)
    "Gemhand Hunter": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_LEVEL, level=6),
    ),
    # If you've spent {4 energy} or more to play a spell this turn, you may
    # play me for {Mind rune}: his {4 energy} is waived and {Mind rune} added.
    "Jhin - Meticulous Killer": (
        Static(ST_COST_ENERGY, n=4, scope=SC_SELF, cond=COND_BIG_SPELL_THIS_TURN),
        Static(ST_COST_POWER_UP, n=1, scope=SC_SELF,
               cond=COND_BIG_SPELL_THIS_TURN),
    ),
    # Your Mechs each have [Assault].
    "Rumble - Hotheaded": (
        Static(ST_KEYWORD, keyword="Assault", n=1, scope=SC_FRIENDLY_UNITS,
               scope_tag="Mech"),
    ),
    # [Empowered] I have +1 Might.
    "Akali, Deadly Weapon": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_EMPOWERED),
    ),
    # [Deflect]  Your Equipment everywhere have [Quick-Draw].
    # (GRANTED_ABILITIES["Jax - Unmatched"], applied in `chain.fire_play_unit`.)
    "Jax - Unmatched": (),
    # Your opponents' [Hidden] cards can't be revealed here. (HIDDEN_LOCKS)
    # I have [Assault] equal to the number of gear you control.
    "Repair Specialist": (
        Static(ST_KEYWORD, keyword="Assault", n=1, scope=SC_SELF,
               per_card_type="Gear", per_same_loc=False),
    ),
    # [Accelerate]  I have [Assault] equal to the number of enemy units here.
    "Ancient Warmonger": (
        Static(ST_KEYWORD, keyword="Assault", n=1, scope=SC_SELF,
               per_card_type="Unit", per_friendly=False, per_enemy=True),
    ),
    # If you've discarded a card this turn, I have [Assault] and [Ganking].
    "Raging Soul": (
        Static(ST_KEYWORD, keyword="Assault", n=1, scope=SC_SELF,
               cond=COND_DISCARDED_THIS_TURN),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_DISCARDED_THIS_TURN),
    ),
    "Kennen, Keeper of Balance": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_STUNNED_ENEMY_HERE),
    ),
    # [Accelerate]  Other buffed friendly units at my battlefield have +2 Might.
    "Lee Sin - Centered": (
        Static(ST_MIGHT, n=2, scope=SC_FRIENDLY_UNITS, scope_not_self=True,
               scope_same_loc=True, requires_buffed=True, cond=COND_SRC_AT_BF),
    ),
    # [Deflect] [Tank]  I don't deal combat damage.
    "Galio - Indefatigable": (
        Static(ST_NO_COMBAT_DAMAGE, scope=SC_SELF),
    ),
    "Ezreal - Dashing": (
        Static(ST_NO_COMBAT_DAMAGE, scope=SC_SELF),
    ),
    # I don't deal combat damage unless I'm at a battlefield with exactly one
    # other unit you control.
    "Sacred Protector": (
        Static(ST_NO_COMBAT_DAMAGE, scope=SC_SELF,
               cond=COND_NOT_AT_BF_N_OTHERS, level=1),
    ),
    "Vilemaw": (
        Static(ST_NO_COMBAT_DAMAGE, scope=SC_ENEMY_UNITS, scope_same_loc=True,
               requires_less_might=True),
    ),
    # [Tank]  Your units here with less Might than me can't be chosen by enemy
    # spells and abilities.
    "Alpha Wildclaw": (
        Static(ST_UNCHOOSABLE, scope=SC_FRIENDLY_UNITS, scope_same_loc=True,
               requires_less_might=True),
    ),
    "Production Surge": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_CONTROL_TAG,
               cond_tag="Mech"),
    ),
    "Shock Blast": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_CONTROL_EMPOWERED),
    ),
    "Spoils of War": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_ENEMY_DIED_THIS_TURN),
    ),

    # Stunned enemy units here have -8 Might, to a minimum of 1 Might.
    # A Might static with a FLOOR: `combat.might` applies it after everything
    # else, so the minimum is on the unit's effective Might.
    "Leona - Zealot": (
        Static(ST_MIGHT, n=-8, scope=SC_ENEMY_UNITS, scope_same_loc=True,
               requires_stunned=True, floor=1),
    ),
    # If an opponent controls a stunned unit, I cost {2 energy} less and enter
    # ready.  (The readiness half is in ENTERS_READY_IF.)
    "Monch": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF,
               cond=COND_OPP_CONTROLS_STUNNED),
    ),
    # If you've gained XP this turn, I have +1 Might and [Ganking].
    "Wily Newtfish": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_GAINED_XP_THIS_TURN),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_GAINED_XP_THIS_TURN),
    ),
    # [Tank]  I get +1 Might for each buffed friendly unit at my battlefield.
    # Himself included when he is buffed -- "each buffed friendly unit".
    "Sett - Kingpin": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per=CNT_BUFFED_HERE),
    ),
    # While I'm at a battlefield, the Energy costs for spells you play is
    # reduced by {1 energy}, to a minimum of {1 energy}.
    "Eager Apprentice": (
        Static(ST_COST_ENERGY, n=1, scope=SC_YOUR_CARDS, applies_to_type="Spell",
               cond=COND_SRC_AT_BF, floor=1),
    ),
    # Your Mechs have +1 Might (including me).
    "Rumble - Scrapper": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, scope_tag="Mech"),
    ),
    # Your Mechs have [Deflect] and [Ganking].
    "Breakneck Mech": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_FRIENDLY_UNITS,
               scope_tag="Mech"),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_FRIENDLY_UNITS,
               scope_tag="Mech"),
    ),
    # While I'm buffed, I have [Ganking].
    "Bilgewater Bully": (
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_SRC_BUFFED),
    ),
    # I cost {1 energy} less for each card you've played this turn, to a
    # minimum of {1 energy}.
    "Battering Ram": (
        Static(ST_COST_ENERGY, n=1, scope=SC_SELF, per=CNT_CARDS_PLAYED,
               floor=1),
    ),
    # Your Dragons' Energy costs are reduced by {2 energy}, to a minimum of
    # {1 energy}. A floored discount, so 356.4.e binds only this one.
    "Herald of Scales": (
        Static(ST_COST_ENERGY, n=2, scope=SC_YOUR_CARDS, applies_to_tag="Dragon",
               floor=1),
    ),
    # Other friendly units enter ready.
    "Magma Wurm": (
        Static(ST_ENTERS_READY, scope=SC_YOUR_CARDS),
    ),
    # Your tokens enter ready.
    "Renata Glasc - Industrialist": (
        Static(ST_ENTERS_READY, scope=SC_YOUR_CARDS, scope_token=True),
    ),
    # I can't move to base.
    #
    # A Move to base -- the retreat, or an effect that moves it there (449.1).
    # NOT a Recall, which 456.1 says is not a Move: losing a combat still sends
    # him home. The restriction is what makes him a permanent garrison once he
    # reaches a battlefield.
    "Determined Sentry": (
        Static(ST_NO_MOVE_TO_BASE, scope=SC_SELF),
    ),
    # Units can't move to base.
    #
    # Every unit, both players' (SC_ALL_UNITS). Nobody retreats while he stands;
    # combat losses are still recalled, because a Recall is not a Move.
    "Minotaur Reckoner": (
        Static(ST_NO_MOVE_TO_BASE, scope=SC_ALL_UNITS),
    ),
    # "Ganking (I can move from battlefield to battlefield.)" printed without
    # its brackets, so `keyword_mask` never sees it; granted here instead.
    "Laurent Bladekeeper": (
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF),
    ),
    # "I must be assigned combat damage last." -- [Backline] as prose.
    "Caitlyn - Patrolling": (
        Static(ST_KEYWORD, keyword="Backline", n=1, scope=SC_SELF),
    ),
    "Brutal Hunter": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Ambessa, Respected and Feared": (
        Static(ST_KEYWORD, keyword="Assault", n=2, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Shadow Fiend": (
        Static(ST_KEYWORD, keyword="Assault", n=3, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    # I have +7 Might. The [Deflect] beside it is PRINTED, not dependent, so it
    # is a read keyword rather than a static.
    "Steel Paws": (
        Static(ST_MIGHT, n=7, scope=SC_SELF, cond=COND_EMPOWERED),
    ),
    "Kinkou Lifeblade": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    # I have [Deflect] and [Shield 3]. A bare keyword is n=1 (809.1: the
    # Deflect Value defaults to one), a numbered one carries its number.
    "Serene Ascetic": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_EMPOWERED),
        Static(ST_KEYWORD, keyword="Shield", n=3, scope=SC_SELF,
               cond=COND_EMPOWERED),
    ),
    "Baccai Witherclaw": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_EMPOWERED),
    ),
    # Your units have +1 Might. If I'm [Empowered], they have +2 INSTEAD --
    # written as two statics that add to the same number. Note this one reaches
    # every friendly unit including himself, and unlike the self-statics above
    # the FIRST is ungated: the gear is worth something the turn it lands.
    "Rage Amplifier": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS),
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, cond=COND_EMPOWERED),
    ),
    # Your units THAT ARE [Empowered] have +2 Might (including me).
    # Both readings of the status in one sentence: `cond` asks about the
    # SOURCE -- the static exists only while the General himself is Empowered
    # -- and `requires_empowered` asks the same question of each unit it
    # reaches. "(Including me)" needs no clause: he is a friendly unit, and by
    # the time the static is live he is Empowered by definition.
    "Aurok General": (
        Static(ST_MIGHT, n=2, scope=SC_FRIENDLY_UNITS,
               requires_empowered=True, cond=COND_EMPOWERED),
    ),

    # Your token units have +1 Might.  No location clause: it reaches the whole
    # board, which is what makes it the payoff for a token deck.
    "Soul Shepherd": (
        Static(ST_MIGHT, n=1, scope=SC_FRIENDLY_UNITS, scope_token=True),
    ),

    # [Legion] - I cost {2 energy} less.
    # (Get the effect if you've played another card this turn.)
    #
    # A 4-drop that is a 2-drop whenever it is not the first thing you do. The
    # condition is read LIVE here rather than off a snapshot, and that is the
    # whole subtlety of [Legion]: a cost is worked out as the card is played,
    # so this card has not been counted yet and any nonzero count is "another
    # card". The op side reads the snapshot instead, because by the time an
    # ability resolves the source HAS been counted.
    "Noxus Hopeful": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, cond=COND_LEGION),
    ),

    # --- costs that count a zone -------------------------------------------
    # I cost {1 energy} less for each card in your trash.
    #
    # A 10-Energy unit that no one ever pays 10 for. The count only goes UP:
    # a trash is the one zone that fills as a game runs and never empties on
    # its own, so unlike a board-counting discount this one cannot be answered
    # by killing anything. It is the payoff for a deck that was filling its
    # trash anyway -- and it is why Forge of the Future recycling an opponent's
    # trash is a real answer rather than a nuisance.
    "Rhasa the Sunderer": (
        Static(ST_COST_ENERGY, n=1, scope=SC_SELF, per=CNT_TRASH),
    ),

    # I cost {2 energy} less for each card with my name in your trash.
    #
    # "With my name", so it counts only the other copies of Shadowblade Lurker
    # -- at 3 in a deck this is at most -4, and it rewards trading the early
    # ones away. `per_same_name` is the difference between that and Rhasa.
    "Shadowblade Lurker": (
        Static(ST_COST_ENERGY, n=2, scope=SC_SELF, per=CNT_TRASH,
               per_same_name=True),
    ),

    # I cost {1 energy} less for each gear you control.
    #
    # A BOARD count rather than a zone one, and `per_card_type` instead of
    # `per_keyword` -- "gear" is a type, not a keyword. No location clause:
    # "you control" is the whole board, so `per_same_loc` is off.
    "Plaza Guardian": (
        Static(ST_COST_ENERGY, n=1, scope=SC_SELF, per_card_type="Gear",
               per_friendly=True, per_same_loc=False),
    ),

    # [Level 11][>] I have +4 Might. (While you have 11+ XP, get the effect.)
    #
    # A static gated on a threshold, and read LIVE rather than snapshotted:
    # XP never resets, so there is no past moment to capture, and 143.2.a means
    # the +4 arriving can save a damaged unit exactly as losing it could kill
    # one. Eleven XP is most of a game away, which is the card.
    "Targonian Visionary": (
        Static(ST_MIGHT, n=4, scope=SC_SELF, cond=COND_LEVEL, level=11),
    ),

    # The other half of Lillia - Protector of Dreams. `scope_token` is what
    # makes it "your TOKEN units": without it she hands [Tank] to every unit
    # you control, which is a different card.
    "Lillia - Protector of Dreams": (
        Static(ST_KEYWORD, keyword="Tank", n=1, scope=SC_FRIENDLY_UNITS,
               scope_token=True),
    ),

    # --- statics that grant a KEYWORD ---------------------------------------
    # [Hunt 2] [Level 3][>] I have +1 Might and [Deflect].
    #
    # Two statics from one sentence, both gated on the same level -- "+1 Might
    # AND [Deflect]" is a Might static beside a keyword static, not one thing.
    # [Hunt 2] is absent because `abilities_for` synthesises it.
    "Mosstomper": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_LEVEL, level=3),
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=3),
    ),

    # [Hunt 2] [Level 3][>] I have +1 Might and [Ganking].
    "Gustwalker": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_LEVEL, level=3),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=3),
    ),

    # [Hunt 2] [Level 6][>] I have [Deflect] and [Ganking].
    "Master Yi - Tempered": (
        Static(ST_KEYWORD, keyword="Deflect", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=6),
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_SELF,
               cond=COND_LEVEL, level=6),
    ),

    # Other friendly units here have [Assault]. (+1 Might while attacking.)
    #
    # "OTHER ... HERE" is both narrowings at once: it never pumps Farron
    # himself, and it reaches only the battlefield he is standing on. Without
    # `scope_same_loc` this would buff units at the other battlefield and at
    # base, which is a different and much better card.
    "Captain Farron": (
        Static(ST_KEYWORD, keyword="Assault", n=1, scope=SC_FRIENDLY_UNITS,
               scope_not_self=True, scope_same_loc=True),
    ),

    # I can't be chosen by enemy spells and abilities.
    # Not [Deflect], which prices the choice -- this removes it. Nothing here
    # protects against damage or a sweep, neither of which chooses (355.10),
    # so a board wipe still answers it.
    "Ruin Runner": (
        Static(ST_UNCHOOSABLE, scope=SC_SELF),
    ),

    # As you play me, add the Baron Pit battlefield token to the board if it's
    # not there already. If you do, I enter there (BARON_PIT_MAKERS, into the
    # third battlefield slot). I can't be chosen by enemy spells and abilities.
    # Other friendly units have +2 Might -- a static, so only while he is on
    # the board.
    "Baron Nashor": (
        Static(ST_UNCHOOSABLE, scope=SC_SELF),
        Static(ST_MIGHT, n=2, scope=SC_FRIENDLY_UNITS, scope_not_self=True),
    ),

    # Other friendly units here have [Shield]. Farron's shape on the defending
    # side: his own printed [Shield] and [Tank] are engine keywords and need no
    # entry, so the granted one is the whole card.
    "Taric - Protector": (
        Static(ST_KEYWORD, keyword="Shield", n=1, scope=SC_FRIENDLY_UNITS,
               scope_not_self=True, scope_same_loc=True),
    ),

    # My Might is increased by the number of cards in your trash.
    "Dr. Mundo - Expert": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, per=CNT_TRASH),
    ),

    # (Historical) Dr. Mundo - Expert wanted exactly this shape on the Might side -- "My
    # Might is increased by the number of cards in your trash" is `Static(
    # ST_MIGHT, n=1, scope=SC_SELF, per=CNT_TRASH)` and works today. He is
    # deliberately NOT here, because his second sentence ("At the start of your
    # Beginning Phase, recycle 3 from your trash") has no Beginning Phase
    # trigger to hang on, and presence in this table is what tells
    # `decks.plays_as_printed` a card's whole text is transcribed. Half a card
    # listed here would silently inflate the coverage number.
    #
    # The combination is worth reaching, though, and `test_statics` drives it
    # directly: a static that reads a ZONE moves when nothing on the board
    # moved, and 143.2.a is continuous -- so Mundo's own recycle shrinks him by
    # 3 and can kill him where he stands.
}


def statics_for(table, card: int) -> tuple[Static, ...]:
    """Every static ability printed on a card id."""
    return STATICS.get(table.names[card], ())


# --- Might Bonus (137.3, 718.4) -------------------------------------------
# **The data exists.** `data/errata.json`'s `gaps` section carries every
# Equipment card's "Attached:" band, transcribed from the card images because
# upstream's API never had the field -- and `cardtable.might_bonus` parses the
# number straight out of it. There is deliberately no registry here: a dict
# would be a second copy of a number the card text already states, and the two
# would drift the first time the overlay was corrected.
#
# What is NOT yet read is the other half of the band, the ABILITY granted while
# attached (136.2, 718.3): "When I hold, score 1 point" on Trinity Force, "+2
# Might while I'm an attacker" on Serrated Dirk. 718.3 appends those to the
# Top-Most Card's Rules Text, which is a mechanism rather than a lookup, so
# `decks.EQUIP_NEEDS_DATA` still withholds the cards that print one.


# --- Inactive text (718.2, 720-725) ---------------------------------------
# `statics_for` and `abilities_for` answer "what is printed on this CARD".
# These two answer "what is ACTIVE on this ROW", which is not the same question
# the moment attachment exists: 718.2 makes an Attached card's printed Rules
# Text Inactive, and 721.2 spells out the consequence -- "Inactive abilities do
# not trigger, do not apply, and cannot be activated".
#
# **Every board walk that reads a permanent's text must go through these.** A
# walk that calls `statics_for` on a row directly will happily apply a static
# the rules have switched off; there were eleven such walks when attachment
# landed, and naming them individually is how the twelfth gets missed.
#
# 722 is the deliberate other half: Inactive text is still PRESENT. A card's
# keywords are still visible to anything that asks (722.1), and 722.2 keeps a
# Spinning Axe choosable by "destroy a gear with [Temporary]" even while its
# own [Temporary] is switched off. So this suppresses the DSL entries, never
# `table.has` or `kw_mask`.
#
# Not yet implemented, and both would be exceptions HERE rather than anywhere
# else: 725.1/725.2 keep a card's Attach- and Detach-triggered abilities alive
# while Attached, and 718.3 appends its Effect Text to the Top-Most card. No
# card in the pool needs either yet -- `cards.json` carries no Effect Text at
# all (see `EQUIP_MIGHT`) -- so an unconditional suppression is currently exact.


# --- 718.3: abilities APPENDED by an Attached card -------------------------
# "While in this state, Abilities in the card's Effect Text are appended to the
# Rules Text of the Top-Most Card." So Trinity Force's "When I hold, score 1
# point" is an ability of the UNIT -- 136.2.c settles the pronoun: Effect Text's
# "I" means the object the card is attached to, never the Equipment.
#
# That is why these cannot be ordinary `ABILITIES` entries. An ABILITIES entry
# fires from the row it is printed on; these have to fire from a DIFFERENT row,
# with "me" and "here" resolving to the unit. The Chain Item carries that as
# `C_SRC` = the unit's row and `C_CARD` = the EQUIPMENT's card, which is also
# how `chain.item_spec` knows to look the index up in here rather than in
# `ABILITIES` -- for every other permanent ability those two agree.
#
# Keyed by the Equipment's name, and the entry must transcribe the whole
# "Attached:" band beyond its Might Bonus, exactly as an ABILITIES entry must
# transcribe a card's whole text. `decks.plays_as_printed` credits the card on
# membership here.
EQUIP_ABILITIES: dict[str, tuple[Ability, ...]] = {
    # Attached: +2 Might. [Deathknell] -- Banish me.
    "The Zero Drive": (
        Ability(TR_DEATH, ops=(Op(OP_ZERO_BANISH),)),
    ),
    # [Equip] (its Energy less by the chosen unit's Might: EQUIP_LESS_CHOSEN_MIGHT)
    # Attached: +3 Might. When I conquer, if you assigned 3 or more excess
    # damage, draw 1.
    "Hextech Gauntlets": (
        Ability(TR_CONQUER, ops=(Op(OP_DRAW, n=1, cond=COND_EXCESS_AT_LEAST,
                                    level=3),)),
    ),


    # Every entry below is read with "I" meaning THE UNIT (136.2.c), so
    # `T_SELF` and `T_HERE` resolve to the Top-Most card's row and not to the
    # gear's. That is the whole reason these are not `ABILITIES` entries.

    # At the end of your turn, if I didn't conquer this turn, unattach this and
    # deal 4 to me.
    "Blighted Battleaxe": (
        Ability(TR_END_OF_TURN,
                ops=(Op(OP_DETACH_THIS, cond=COND_NOT_CONQUERED_THIS_TURN),
                     Op(OP_DAMAGE, target=T_SELF, n=4,
                        cond=COND_NOT_CONQUERED_THIS_TURN))),
    ),

    # When I attack or defend, deal 2 to all enemy units here.
    "Forgefire Cape": (
        Ability(TR_ATTACK_OR_DEFEND,
                ops=(Op(OP_DAMAGE_ALL, n=2, at=T_HERE, who=W_ENEMY),)),
    ),

    # When I attack or defend, deal 2 to an enemy unit here.
    "Recurve Bow": (
        Ability(TR_ATTACK_OR_DEFEND,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n=2),)),
    ),

    # [Deathknell] -- Draw 1.
    # The UNIT's Deathknell (136.2.c). `combat._destroy` queues it with the
    # gear as subject, because 719.5 detaches the gear as the unit dies.
    "Sacred Shears": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When I hold, score 1 point.
    # An Equipment that wins the game, and 471.1.b exempts a Hold from the
    # "every battlefield Scored" rule the final point otherwise needs.
    "Trinity Force": (
        Ability(TR_HOLD, ops=(Op(OP_SCORE, n=1),)),
    ),

    # When I conquer, discard 1, then draw 1.
    # "Then" fixes the order: the discard happens first, so a card drawn is
    # never a candidate to be discarded.
    "Doran's Ring": (
        Ability(TR_CONQUER, ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=1))),
    ),

    # When I conquer, channel 1 rune exhausted.
    "Boneshiver": (
        Ability(TR_CONQUER, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # When I conquer, buff me.
    # 426.1.b.1 caps a unit at one Buff, which `OP_BUFF` already enforces, so
    # conquering twice does not stack.
    "Warmog's Armor": (
        Ability(TR_CONQUER, ops=(Op(OP_BUFF, target=T_SELF),)),
    ),

    # When I conquer, play a Gold gear token exhausted.
    "Cull": (
        Ability(TR_CONQUER,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When I hold, play two Gold gear tokens exhausted.
    "World Atlas": (
        Ability(TR_HOLD,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=2,
                        token=GOLD_TOKEN),)),
    ),

    # When I move to a battlefield, give me +2 Might this turn.
    # `at_battlefield` narrows the TRIGGER (359.3.f) rather than conditioning
    # the effect: a move back to base is not a move to a battlefield and never
    # reaches the Chain.
    "Pendulum Blade": (
        Ability(TR_MOVE, at_battlefield=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # When I move, play a 1 Might Recruit unit token here.
    #
    # "Here" is T_HERE, a LIVE read of the unit's own row, which on a move
    # trigger is the destination -- the unit has already arrived by the time
    # the trigger resolves. The CAPTURED `C_CTX` would be the location it LEFT,
    # which is what the other kind of card means ("play a Sprite THERE",
    # Lillia). Reading one where you meant the other is the easy mistake here.
    #
    # Unlike Pendulum Blade this is not narrowed to a battlefield: the card
    # says "when I move", and a retreat to base is a Move (455/456.1), so the
    # Recruit arrives at base.
    "Eye of the Herald": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=RECRUIT_TOKEN),)),
    ),

    # When I conquer or hold, you may play a unit from your trash.
    # (You still pay its costs.)
    #
    # Its [Equip] cost recycles two cards from the same trash this replays
    # from, which is what makes the recycle a real choice: pay with the
    # spells, keep the units. `COST_PRINTED` is "you still pay its costs",
    # and a destination slot because a unit played this way still needs
    # somewhere 806.3 allows. Two abilities rather than one, because a
    # conquer and a hold are different events and a card that says "or"
    # triggers on each.
    "Last Rites": (
        Ability(TR_CONQUER, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Unit",), playable=True,
                                    playable_cost=COST_PRINTED),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_PRINTED),)),
        Ability(TR_HOLD, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Unit",), playable=True,
                                    playable_cost=COST_PRINTED),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_PRINTED),)),
    ),
}


def _assert_equip_tables_disjoint() -> None:
    """`chain.item_spec` tells an APPENDED ability from a BORROWED one by
    asking whether the card has an `EQUIP_ABILITIES` entry. Both store a card
    that disagrees with the source row's, so a name in both tables would make
    that test ambiguous and silently resolve the wrong ability.
    """
    clash = set(EQUIP_ABILITIES) & set(ABILITY_BORROWERS)
    assert not clash, (
        f"{sorted(clash)} is both an appended-ability Equipment and an ability "
        f"borrower; `chain.item_spec` cannot tell the two apart")


# 718.3's third shape: a CONTINUOUS ability in the band rather than a triggered
# one or a bare keyword. Same rule, same append, but a static is not a Chain
# Item -- it is read wherever the board is walked -- so it needs its own table
# and `row_statics` rather than `chain.push`.
#
# `SC_SELF` here means the UNIT, because that is what 136.2.c makes "I" mean in
# Effect Text. An entry is written exactly as if the sentence were printed on
# the unit, which is what 718.3 says it now is.
EQUIP_STATICS: dict[str, tuple[Static, ...]] = {

    # Your units here have [Ganking].  ("Here" is the unit's location.)
    "Shurelya's Requiem": (
        Static(ST_KEYWORD, keyword="Ganking", n=1, scope=SC_FRIENDLY_UNITS,
               scope_same_loc=True),
    ),
    # I can't be moved by enemy spells and abilities.
    "Jagged Cutlass": (
        Static(ST_NO_ENEMY_MOVE, scope=SC_SELF),
    ),

    # If this was attached to me this turn, I have an additional +2 Might.
    #
    # The most-played Equipment in the corpus at 6 slots, and the reason
    # `P_ATTACH_TURN` exists: `P_ATTACHED_TO` says the link is there and not
    # when it was made. "This" is the Equipment naming itself, which is the one
    # place Effect Text does NOT mean the Top-Most card -- see
    # `combat.static_applies`. `SC_SELF` still means the unit, so the Might
    # lands on the body.
    #
    # A one-turn window makes it a tempo card rather than a permanent buff: the
    # +2 is there for the attack you equip into and gone the following turn.
    "Brutalizer": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_ATTACHED_THIS_TURN),
    ),

    # [Level 3] I have an additional +1 Might.
    #
    # A DEPENDENT keyword (727): [Level 3] is short for "while you have 3+ XP",
    # and the clause after it is the dependent ability. COND_LEVEL asks the
    # controller's XP, which never resets, so this is read live rather than
    # snapshotted.
    "Soul Sword": (
        Static(ST_MIGHT, n=1, scope=SC_SELF, cond=COND_LEVEL, level=3),
    ),

    # I have +2 Might while I'm at a battlefield with exactly one other unit
    # you control.
    #
    # EXACTLY one -- a pair holding a battlefield together, and a third body
    # switches it off. Read of the UNIT's location (136.2.c), live.
    "Hand Hammer": (
        Static(ST_MIGHT, n=2, scope=SC_SELF, cond=COND_AT_BF_N_OTHERS, level=1),
    ),
}


# 718.3's fourth shape: a REPLACEMENT in the band. Guardian Angel's "If I would
# die, kill Guardian Angel instead. Heal me, exhaust me, and recall me." is not
# a trigger (nothing reaches the Chain) and not a static (nothing is read
# continuously) -- it intercedes in the death itself (369.1, 370.1.c), so it is
# implemented inside `combat._destroy`, and membership here is what credits it.
EQUIP_DEATH_REPLACEMENT: frozenset[str] = frozenset({"Guardian Angel"})


def equip_statics_for(table, card: int) -> tuple[Static, ...]:
    """The statics `card` appends to its Top-Most Card while Attached."""
    return EQUIP_STATICS.get(table.names[card], ())


def equip_abilities_for(table, card: int) -> tuple[Ability, ...]:
    """The abilities `card` appends to its Top-Most Card while Attached."""
    return EQUIP_ABILITIES.get(table.names[card], ())


def appended_abilities(state, table,
                       perm: int) -> tuple[tuple[int, int, Ability], ...]:
    """(equipment card id, index, ability) triples 718.3 appends to `perm`.

    The card id and the index travel together because the two halves of a row's
    abilities are numbered in DIFFERENT tables: a permanent's own in
    `ABILITIES`, an appended one in `EQUIP_ABILITIES` under the Equipment's
    name. A Chain Item stores an index, so it has to store which table too --
    `chain.push` writes the card and `chain.item_spec` reads both back.
    """
    out = []
    gc = int(state.granted_card[perm])
    if gc >= 0 and int(state.granted_ply[perm]) == int(state.ply):
        for k, ab in enumerate(GRANTED_ABILITIES.get(table.names[gc], ())):
            out.append((gc, k, ab))
    # "Units HERE have 'Exhaust: ...'" (Gardens of Becoming). The ground
    # appends to every unit standing on it, exactly as an Equipment appends to
    # the unit wearing it (718.3), and it is numbered under the battlefield's
    # name in `GRANTED_ABILITIES` for the same reason.
    from rl.engine.state import P_LOC, bf_index, is_battlefield
    _loc = int(state.perms[perm, P_LOC])
    if is_battlefield(_loc):
        _bc = int(state.bf_card[bf_index(_loc)])
        if _bc >= 0 and table.names[_bc] in BF_GRANTS_UNITS:
            for k, ab in enumerate(GRANTED_ABILITIES.get(table.names[_bc], ())):
                out.append((_bc, k, ab))
    for i in state.attachments(perm):
        acard = int(state.perms[i, P_CARD])
        for k, ab in enumerate(equip_abilities_for(table, acard)):
            out.append((acard, k, ab))
        if table.names[acard] in TEXT_COPIERS:
            # Svellsongur copies the unit's own TRIGGERED text; it is numbered
            # in the unit's own table, which is what `item_spec` reads when
            # the pushed card is the source row's card.
            ucard = state.eff_card(perm)
            for k, ab in enumerate(abilities_for(table, ucard)):
                if ab.trigger != TR_ACTIVATED:
                    out.append((ucard, k, ab))
    return tuple(out)


def row_statics(state, table, perm: int) -> tuple[Static, ...]:
    """Statics ACTIVE on permanent row `perm` (718.2, 718.3).

    Its own, silenced while it is itself Attached, plus the ones 718.3 appends
    from whatever is attached to it. Unlike `row_abilities` no card id has to
    travel alongside: a static is never addressed by index -- it is read where
    the board is walked and never becomes a Chain Item -- so there is nothing
    to look up again later.
    """
    return tuple(st for st, _ in row_statics_sourced(state, table, perm))


def row_statics_sourced(state, table,
                        perm: int) -> tuple[tuple[Static, int], ...]:
    """`row_statics` with the ROW each static is printed on.

    For a permanent's own statics that row is `perm` itself; for one 718.3
    appended by an Attached card it is the ATTACHED card's row. The pair is
    needed because the two halves of a static's reading point at different
    cards: 136.2.c makes "I" in Effect Text the Top-Most card, so a condition
    about Might or Empowered status asks about `perm` -- but Brutalizer's "if
    THIS was attached to me this turn" asks about the gear, and nothing else on
    the board can answer it.
    """
    own = () if state.is_attached(perm) else statics_for(
        table, state.eff_card(perm))
    out = [(st, perm) for st in own]
    for i in state.attachments(perm):
        for st in equip_statics_for(table, int(state.perms[i, P_CARD])):
            out.append((st, i))
        if table.names[int(state.perms[i, P_CARD])] in TEXT_COPIERS:
            # Svellsongur: the unit's text, again, as the gear's effect text.
            out.extend((st, perm) for st in statics_for(table, state.eff_card(perm)))
    return tuple(out)


# Abilities a BATTLEFIELD grants to things that are not it. Two shapes, and
# they differ in who gets the ability:
#   BF_GRANTS_UNITS  -- "units HERE have ..."  (Gardens of Becoming)
#   BF_GRANTS_LEGEND -- "while you control this battlefield, friendly LEGENDS
#                       have ..." (Forge of the Fluft)
# The abilities themselves live in `GRANTED_ABILITIES` under the battlefield's
# name, so a Chain Item can look them up again from the card id it stores --
# the same route Dominus's grant already takes.
BF_GRANTS_UNITS: frozenset[str] = frozenset({"Gardens of Becoming"})
BF_GRANTS_LEGEND: frozenset[str] = frozenset({"Forge of the Fluft"})


def legend_abilities_live(state, table, seat: int) -> tuple:
    """(card id, index, ability) for everything `seat`'s legend can use now.

    Its own printed abilities, plus any a battlefield it controls grants it.
    The card id travels because the granted ones are numbered in
    `GRANTED_ABILITIES` under the BATTLEFIELD's name, not the champion's.
    """
    lcard = int(state.legend[seat])
    if lcard < 0:
        return ()
    out = [(lcard, k, ab)
           for k, ab in enumerate(legend_abilities_for(table, lcard))]
    for i in state.live_bfs():
        bcard = int(state.bf_card[i])
        if bcard < 0 or int(state.bf_ctrl[i]) != seat:
            continue
        if table.names[bcard] not in BF_GRANTS_LEGEND:
            continue
        for k, ab in enumerate(GRANTED_ABILITIES.get(table.names[bcard], ())):
            out.append((bcard, k, ab))
    return tuple(out)


def row_abilities(state, table, perm: int) -> tuple[Ability, ...]:
    """Abilities ACTIVE on permanent row `perm` (718.2, 721.2, 718.3).

    Its own, silenced while it is itself Attached, PLUS the ones 718.3 appends
    to it from whatever is attached. Callers asking "does this row have a
    trigger for X" want both and get both.

    **A caller that needs to ADDRESS one of them must not use this**, because
    the two halves index different tables and a position here says nothing
    about which. `appended_abilities` keeps the card id alongside for that.
    """
    own = () if state.is_attached(perm) else abilities_for(
        table, state.eff_card(perm))
    return own + tuple(ab for _, _, ab in appended_abilities(state, table, perm))


# ---------------------------------------------------------------------------
# Unit abilities. Same shape as SPECS, keyed the same way; a card may have
# several, which is why the value is a tuple.
# ---------------------------------------------------------------------------
RECRUIT_TOKEN = "Recruit (271) // Buff"   # 1 Might domainless unit token
BIRD_TOKEN = "Bird"                       # 1 Might with [Deflect], rule 187.7
MECH_TOKEN = "Mech"                       # 3 Might, rule 187.4

ABILITIES: dict[str, tuple[Ability, ...]] = {

    # [Tank] When you play me, move a unit from a battlefield to its base.
    # "its base" is the TARGET's owner's base, not the caster's -- moving an
    # enemy unit sends it home, not to yours.
    "Maddened Marauder": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # When you play me, if you control 3 or more other gear, draw 1.
    # A CONDITION, not a restriction: the card is played regardless and the
    # draw simply fails when the board does not support it.
    "Patched Porobot": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_CONTROL_N_GEAR, floor=3),)),
    ),

    # [Reaction] When you play me, heal your units here, then move UP TO ONE
    # enemy unit from here to its base.
    #
    # **"up to one" is the errata**; the printed text says "move an enemy unit",
    # which is a required slot and 355.8 would refuse the whole play when no
    # enemy stands here. That is the wrong answer for a [Reaction] whose FIRST
    # half is a board-wide heal: Janna exists to be dropped into a fight to save
    # units, and the printed reading made her unplayable exactly when the
    # opponent had nothing left at the battlefield. `optional=True` is 355.14's
    # optional slot, so declining fizzles the move and leaves the heal.
    "Janna - Savior": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True,
                                    optional=True),),
                ops=(Op(OP_HEAL_AT, target=T_HERE),
                     Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE))),
    ),

    # [Tank] When you play me, draw 1.
    # [Tank] is a keyword flag the damage-assignment tiers already read, so the
    # DSL only owns the second sentence.
    "Lecturing Yordle": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you play me, draw 1.
    "Cloud Drake": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Deathknell] If I died alone, draw 1.
    # 808.1 makes [Deathknell] short for "When I die, [Effect]", so the keyword
    # is TR_DEATH and the card's own text is the whole ability. "Alone" is a
    # CONDITION -- checked on resolution, nothing to target -- and the card's
    # reminder defines it: "no other friendly units here".
    "Lonely Poro": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=1, cond=COND_DIED_ALONE),)),
    ),

    # When you play me, ready ANOTHER friendly Mech. A tag restriction plus
    # `not_self` -- Bubble Bot is itself a Mech, and would otherwise be the
    # obvious pick for its own trigger.
    "Bubble Bot": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_FRIENDLY, tags=("Mech",),
                                    not_self=True),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # [Hidden] When you play me, give a unit -2 Might this turn, to a minimum
    # of 1 Might. The floor is printed on the card, stricter than 143.2.b's
    # general floor of 0, so it rides on the Op rather than being a rule.
    "Blastcone Fae": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2, floor=1),)),
    ),

    # When you play me, you may kill a gear.
    "Disarming Rake": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",),
                                    optional=True),),
                ops=(Op(OP_KILL, target=0),)),
    ),

    # --- trash recursion, on a trigger -------------------------------------
    # 355.8 makes the empty-trash case free: an ability whose only slot has no
    # legal choice is never put on the Chain at all, so none of these deadlock
    # on turn one. That is already enforced centrally in `chain.fire`.

    # When you play me, return a unit from your trash to your hand.
    "Cemetery Attendant": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a spell from your trash to your hand.
    "Annie - Stubborn": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Spell",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a gear from your trash to your hand.
    "Aspiring Engineer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Gear",)),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, return a Bird, Cat, Dog, or Poro from your trash to
    # your hand. A TAG list, not a type list -- the card says nothing about
    # whether the thing it returns is a unit.
    "Starhound": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    tags=("Bird", "Cat", "Dog", "Poro")),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, you may play a spell from your trash with Energy cost
    # no more than {3 energy}, ignoring its Energy cost. Recycle that spell
    # after you play it. (You must still pay its Power cost.)
    #
    # The most-played unencoded card in the corpus, and it needs every piece of
    # the trash cluster at once: a trash slot, a cost restriction on it, an
    # alternate cost, and a third destination.
    #
    # **"Recycle that spell" is not "banish" and not "trash".** It goes to the
    # BOTTOM of Fizz's controller's own Main Deck (416.1.a), so the spell comes
    # back around and can be drawn again -- unlike [Flow], which banishes what
    # it replays. The two cards do the same thing and dispose of it differently,
    # which is exactly why the destination rides on the Chain Item rather than
    # being read off the card.
    #
    # `playable` makes the Power cost part of target LEGALITY: a spell whose
    # Power Fizz's controller cannot pay was never a legal choice.
    "Fizz - Trickster": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Spell",),
                                    max_energy=3, playable=True,
                                    playable_cost=COST_NO_ENERGY),),
                ops=(Op(OP_PLAY_FROM_TRASH, target=0, dest=DEST_RECYCLE,
                        cost=COST_NO_ENERGY),)),
    ),

    # When you play me, you may play a unit from your trash, ignoring its
    # Energy cost. (You must still pay its Power cost.)
    "Soulgorger": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                                    playable=True,
                                    playable_cost=COST_NO_ENERGY),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_NO_ENERGY),)),
    ),

    # When you play me, you may play a unit costing no more than {3 energy} and
    # no more than {any rune} from your trash, ignoring its cost.
    #
    # "Ignoring its COST", not "its Energy cost" -- both halves are waived, and
    # Soulgorger three entries up is the same card with the other wording. The
    # cost restriction is on the PRINTED cost, which is what makes the two
    # numbers meaningful at all when nothing is being paid.
    # [Accelerate] [Ganking]
    # The first time I move each turn, you may ready something else that's
    # exhausted.
    #
    # `once_each_turn` is "the FIRST time", spent on the per-permanent turn
    # stamp -- a second move the same turn does nothing, which is exactly what
    # stops [Ganking] turning her into a free untapper.
    #
    # "SOMETHING else", not "a unit": gear counts, and `card_type=()` is how a
    # slot says it takes any permanent. `not_self` is the "else", and
    # `must_be_exhausted` is what keeps the "you may" from offering choices
    # that would do nothing -- readying a ready permanent is a no-op, and 355.8
    # would otherwise let the ability fire on a fully-ready board.
    #
    # **W_ANY, because the card prints no ownership word.** Targets scope by
    # omission: "a unit" reaches both players and only "enemy" or "your"
    # narrows it. Readying the opponent's permanent is a bad choice rather
    # than an illegal one, and writing W_FRIENDLY here would be inventing a
    # restriction the card does not have -- the same mistake as reading
    # "a unit" as "a friendly unit" anywhere else.
    "Miss Fortune - Captain": (
        Ability(TR_MOVE, once_each_turn=True, optional=True,
                targets=(TargetSpec(who=W_ANY, not_self=True,
                                    must_be_exhausted=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # When you play this, gain 1 XP.  [Equip] -- Spend 1 XP.
    #
    # The card funds its own first Equip, which is the design: the XP arrives
    # as it enters and the [Equip] ability (synthesised from the keyword, with
    # `cost_xp` parsed off the text) spends exactly that. Only the play trigger
    # needs an entry here.
    "Shepherd's Heirloom": (
        Ability(TR_PLAY_ME, ops=(Op(OP_GAIN_XP, n=1),)),
    ),

    # Exhaust: Buff an exhausted friendly unit.
    "Arena Bar": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, must_be_exhausted=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_BUFF, target=0),)),
    ),

    # [Deathknell] -- Play three 1 Might Recruit unit tokens into your base.
    "Machine Evangel": (
        Ability(TR_DEATH, ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=3,
                                  token=RECRUIT_TOKEN),)),
    ),

    # [Assault]  [Deathknell][>] Channel 1 rune exhausted.
    "Black Rose Dignitary": (
        Ability(TR_DEATH, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # When you play me, choose an enemy unit at a battlefield. We deal damage
    # equal to our Mights to each other.
    #
    # OP_FIGHT with himself as one side (`T_SELF`), simultaneous like Challenge.
    "Carnivorous Snapvine": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_FIGHT, target=T_SELF, target_b=0),)),
    ),

    # When you play me, choose an enemy unit. If it is stunned, kill it.
    # Otherwise, stun it.
    #
    # Complementary conditions on the same target, kill first: a stunned unit
    # dies and the stun then has nothing to act on, an unstunned one is skipped
    # by the kill and stunned.
    "Solari Chief": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, locality=LOC_FREE),),
                ops=(Op(OP_KILL, target=0, cond=COND_TARGET_STUNNED),
                     Op(OP_STUN, target=0, cond=COND_TARGET_NOT_STUNNED))),
    ),

    # When I attack, you may pay {Fury rune} to give me [Assault 2] this turn.
    "Baccai Reaper": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK, optional=True,
                opt_cost_power=1,
                ops=(Op(OP_GRANT_KEYWORD, target=T_SELF, keyword="Assault",
                        n=2),)),
    ),

    # [Deflect]  {2 energy}{Fury rune}: Double my Might this turn.
    #
    # "Double" is +Might equal to his current EFFECTIVE Might, read when it
    # resolves -- so activating twice doubles the doubled number.
    "Vi - Hotheaded": (
        Ability(TR_ACTIVATED, cost_energy=2, cost_power=1,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n_from_might=T_SELF),)),
    ),

    # Your Mechs have +1 Might (including me).
    # When I hold, play a 3 Might Mech unit token to your base.
    "Rumble - Scrapper": (
        Ability(TR_HOLD, ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                                 token=MECH_TOKEN),)),
    ),

    # Spend my buff: Choose one you've not chosen this turn -- Deal 2 to a unit
    # at a battlefield. / Stun a unit at a battlefield. / Ready me. / Give me
    # [Ganking] this turn.
    "Udyr - Wildman": (
        Ability(TR_ACTIVATED, cost_spend_buff_self=True, targets=(MODE_SLOT,),
                modes_once_per_turn=True,
                modes=(CardSpec(SPEED_MAIN,
                                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                                    locality=LOC_FREE),),
                                ops=(Op(OP_DAMAGE, target=0, n=2),)),
                       CardSpec(SPEED_MAIN,
                                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                                    locality=LOC_FREE),),
                                ops=(Op(OP_STUN, target=0),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_READY, target=T_SELF),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_GRANT_KEYWORD, target=T_SELF,
                                                    keyword="Ganking"),)))),
    ),
    # When you attach an Equipment to me, choose one that hasn't been chosen
    # this turn -- Ready 2 runes. / Channel 1 rune exhausted. / Buff a friendly
    # unit.
    "Aphelios - Exalted": (
        Ability(TR_EQUIPPED, targets=(MODE_SLOT,), modes_once_per_turn=True,
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_READY_RUNES, n=2),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_CHANNEL, n=1),)),
                       CardSpec(SPEED_MAIN,
                                targets=(TargetSpec(who=W_FRIENDLY,
                                                    locality=LOC_FREE),),
                                ops=(Op(OP_BUFF, target=0),)))),
    ),
    # [Hidden]  When you play me from face down, you may empower something
    # here. Disempower it at end of turn.
    "Tornado Warrior": (
        Ability(TR_PLAY_ME, from_hidden=True, optional=True,
                targets=(TargetSpec(who=W_ANY, card_type=("Unit", "Gear"),
                                    same_loc_as_source=True),),
                ops=(Op(OP_EMPOWER, target=0, eot_revert=True),)),
    ),

    # --- "Choose one --" abilities --------------------------------------
    # When I move to a battlefield, choose one -- Each player discards 1. /
    # Each player draws 1.
    "Minah Swiftfoot": (
        Ability(TR_MOVE, at_battlefield=True, targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_DISCARD, n=1,
                                                    each_player=True),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_DRAW, n=1,
                                                    each_player=True),)))),
    ),
    # [Deflect]  When I conquer, draw 1 or channel 1 rune exhausted.
    "Qiyana - Victorious": (
        Ability(TR_CONQUER, targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_DRAW, n=1),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_CHANNEL, n=1),)))),
    ),
    # When you play me, you may draw 1 or buff me.
    "Buhru Captain": (
        Ability(TR_PLAY_ME, optional=True, targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_DRAW, n=1),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_BUFF, target=T_SELF),)))),
    ),
    # When I become ready, choose one to give me this turn -- [Assault 2] /
    # [Deflect 2] / [Ganking].
    "Jayce, Hammer in Hand": (
        Ability(TR_READIED, subject_is_self=True, targets=(MODE_SLOT,),
                modes=tuple(
                    CardSpec(SPEED_MAIN, ops=(Op(OP_GRANT_KEYWORD, target=T_SELF,
                                                 keyword=kw, n=n),))
                    for kw, n in (("Assault", 2), ("Deflect", 2),
                                  ("Ganking", 1)))),
    ),
    # When you play me, choose a player. They discard 1.
    "Bewitching Spirit": (
        Ability(TR_PLAY_ME, targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_DISCARD, n=1),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_DISCARD, n=1,
                                                    who=W_ENEMY),)))),
    ),
    # The first time I move each turn, choose a player. They [Burn 1].
    "Blade Twirler": (
        Ability(TR_MOVE, once_each_turn=True, targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_BURN, n=1),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_BURN, n=1,
                                                    who=W_ENEMY),)))),
    ),

    # [Unique] [Equip] {any rune}  When you play this, ready your units.
    # (The "Attached:" band is in EQUIP_STATICS; this sentence is the gear's
    # own text, active while it is unattached -- i.e. as it is played.)
    "Shurelya's Requiem": (
        Ability(TR_PLAY_ME, ops=(Op(OP_READY_ALL),)),
    ),

    # When I move to a battlefield, look at the top 3 cards of your Main Deck.
    # You may reveal a unit from among them and draw it. Recycle the rest.
    # [Deathknell] Play a unit from your hand to your base, ignoring its Energy
    # cost.
    "Rift Herald": (
        Ability(TR_MOVE, at_battlefield=True,
                ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_PICK, n=3, pick_optional=True, pick_types=("Unit",),
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),)),
        Ability(TR_DEATH,
                ops=(Op(OP_PLAY_FROM_HAND, pick_types=("Unit",),
                        cost=COST_NO_ENERGY, target_b=T_MY_BASE, level=-1),)),
    ),
    # [Tank]  When I attack, you may play an Equipment with Energy cost no more
    # than {2 energy}, ignoring its cost. If you do, then do this: Attach it to
    # me.
    # When you play me, ready or exhaust a legend.  (Four modes: yours or the
    # opponent's, readied or exhausted.)
    "Royal Entourage": (
        Ability(TR_PLAY_ME, targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_READY_LEGEND),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_EXHAUST_LEGEND),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_READY_LEGEND,
                                                    who=W_ENEMY),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_EXHAUST_LEGEND,
                                                    who=W_ENEMY),)))),
    ),
    # When I attack or defend one on one, double my Might this combat.
    "Fiora - Peerless": (
        Ability(TR_ATTACK_OR_DEFEND,
                ops=(Op(OP_MIGHT_THIS_COMBAT, target=T_SELF, n_from_might=T_SELF,
                        cond=COND_ONE_ON_ONE),)),
    ),
    # [Shield 3] [Tank]  When an opponent moves to a battlefield other than
    # mine, draw 1.
    "Volibear - Imposing": (
        Ability(TR_UNIT_MOVES, subject_enemy=True, move_to_other_bf=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),
    # When a friendly unit moves from my location, I may be moved with it.
    "Stealthy Pursuer": (
        Ability(TR_UNIT_MOVES, move_from_my_loc=True, optional=True,
                ops=(Op(OP_MOVE_TO, target=T_SELF, target_b=T_CTX2),)),
    ),
    # At the start of your Beginning Phase, if you have exactly 4 cards in hand
    # and exactly 4 units at battlefields, you win the game.  Discard 1,
    # Exhaust: Play a 1 Might Bird unit token with [Deflect].
    "Gutter Palace": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_WIN, cond=COND_HAND_UNITS_AT_BF, level=4),)),
        Ability(TR_ACTIVATED, cost_discard=1, cost_exhaust=True,
                targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
                ops=(Op(OP_CREATE_TOKEN, target=0, n=1,
                        token=BIRD_TOKEN),)),
    ),
    # When I attack, reveal the top rune of your rune deck, then recycle it.
    # Do one of the following based on its domain: Fury -- Deal 2 to an enemy
    # unit here and 1 to all other enemy units here. Mind -- Draw 1. Order --
    # Stun an enemy unit.
    "Twisted Fate - Gambler": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_REVEAL_RUNE),)),
        Ability(TR_RUNE_FURY,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n=2),
                     Op(OP_DAMAGE_ALL, n=1, at=T_HERE, who=W_ENEMY,
                        except_target=0))),
        Ability(TR_RUNE_MIND, ops=(Op(OP_DRAW, n=1),)),
        Ability(TR_RUNE_ORDER,
                targets=(TargetSpec(who=W_ENEMY, locality=LOC_FREE),),
                ops=(Op(OP_STUN, target=0),)),
    ),
    # When you play me, you may disempower something you control to empower a
    # legend, unit, or gear.
    #
    # The LEGEND half is not offered: a legend has no status storage (see the
    # note above the LEGEND_ABILITIES asserts), and no scripted card reads a
    # legend's Empowered status, so empowering one would change nothing.
    "Profiteer": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, card_type=("Unit", "Gear"),
                                    must_be_empowered=True, locality=LOC_FREE,
                                    or_legend=True),
                         # The same one may be chosen again: it is no longer
                         # Empowered once disempowered (RiftJudge #11784).
                         TargetSpec(who=W_ANY, card_type=("Unit", "Gear"),
                                    locality=LOC_FREE, or_legend=True,
                                    allow_repeat=True)),
                ops=(Op(OP_DISEMPOWER, target=0),
                     Op(OP_EMPOWER, target=1, cond=COND_DISEMPOWERED))),
    ),
    # At the end of your turn, reveal cards from the top of your Main Deck
    # until you reveal a unit and banish it. Play it, ignoring its cost, and
    # recycle the rest.
    "Dazzling Aurora": (
        Ability(TR_END_OF_TURN,
                ops=(Op(OP_REVEAL_PLAY, until_type=True, pick_types=("Unit",),
                        cost=COST_FREE),)),
    ),
    # When I attack, you may reveal the top 2 cards of your Main Deck. You may
    # banish one, then play it. If it is a unit, you may play it here.
    # Recycle the rest.
    "Rek'Sai - Swarm Queen": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK, optional=True,
                ops=(Op(OP_REVEAL_PLAY, n=2, pick_optional=True,
                        rest_dest=DEST_RECYCLE, cost=COST_PRINTED,
                        play_here=True),)),
    ),
    # {1 energy}{Order rune}, Exhaust: Kill a friendly unit. Look at the top 5
    # cards of your Main Deck. You may banish a unit from among them that has
    # Might up to 1 more than the killed unit and play it, ignoring its cost.
    # Then recycle the rest.
    "Baited Hook": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_KILL, target=0),
                     Op(OP_REVEAL_PLAY, n=5, pick_optional=True,
                        pick_types=("Unit",), rest_dest=DEST_RECYCLE,
                        cost=COST_FREE, pick_max_might_killed=1))),
    ),
    # When you play me or when I hold, look at the top 3 cards of your Main
    # Deck. You may reveal a unit from among them and draw it. Recycle the
    # rest. Then if you revealed a Bird, Cat, Dog, or Poro, do this: [Buff] a
    # friendly unit.
    "Ivern - Nurturer": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_PICK, n=3, pick_optional=True, pick_types=("Unit",),
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE,
                        then_key=FU_IVERN),)),
        Ability(TR_HOLD,
                ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_PICK, n=3, pick_optional=True, pick_types=("Unit",),
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE,
                        then_key=FU_IVERN),)),
        Ability(TR_FOLLOWUP,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_BUFF, target=0),)),
    ),
    # [Hidden] When I defend, choose an enemy unit here and reveal the top 5
    # cards of your Main Deck. Deal 1 to that unit for each card with [Hidden]
    # revealed this way, then recycle the revealed cards.
    #
    # Nocturne's "as you reveal me" permission is not offered on this reveal:
    # it resolves without suspending (see PLAY_FROM_LOOK).
    "Teemo - Strategist": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_DEFEND,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_REVEAL_COUNT_DAMAGE, target=0, n=5,
                        keyword="Hidden"),)),
    ),
    # When you play me, choose an opponent. They reveal their hand. Choose a
    # card revealed this way and banish it. When they hold, return it to their
    # hand (even if I'm no longer on the board).
    "Ashe - Focused": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_REVEAL_HAND, pick_dest=DEST_BANISH, hold_return=True),)),
    ),
    # When a unit you control becomes [Mighty], you may pay {Order rune} to
    # ready it.
    "Fiora - Worthy": (
        Ability(TR_BECOME_MIGHTY, optional=True, opt_cost_power=1,
                ops=(Op(OP_READY, target=T_SUBJECT),)),
    ),
    # {1 energy}: Give me +1 Might this turn.  (When my Might becomes 10 or
    # more, empower me: EMPOWER_AT_MIGHT.)  [Empowered] I have [Deflect] and
    # [Ganking]: STATICS.
    "Renekton, Brute": (
        Ability(TR_ACTIVATED, cost_energy=1,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),
    # When you kill a stunned enemy unit, you may exhaust this to draw 1.
    "Solari Shrine": (
        Ability(TR_YOU_KILL, subject_enemy=True, subject_stunned=True,
                optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),
    # [Assault 2]  When you kill a unit with a spell, you may pay {1 energy}
    # {Fury rune} to play me from your trash.  (To your base.)
    "Immortal Phoenix": (
        Ability(TR_KILL_FROM_TRASH, subject_by_spell=True, optional=True,
                opt_cost_energy=1, opt_cost_power=1,
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, self_card=True,
                        target_b=T_MY_BASE, cost=COST_FREE),)),
    ),
    # When I hold, at the start of your next Main Phase, you may move an enemy
    # unit to this battlefield.  (The Hold is in the same turn's Beginning
    # Phase, so "next" is this turn's Main Phase.)
    "Iascylla": (
        Ability(TR_MAIN_START, optional=True, cond=COND_HELD_HERE,
                targets=(TargetSpec(who=W_ENEMY, different_loc_from_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_HERE),)),
    ),
    # At the start of your Main Phase, you may kill 3 other friendly units
    # and/or gear to score 1 point.
    "Bottled Constellation": (
        Ability(TR_MAIN_START, optional=True,
                targets=tuple(TargetSpec(who=W_FRIENDLY, not_self=True,
                                         card_type=("Unit", "Gear"),
                                         locality=LOC_FREE) for _ in range(3)),
                ops=tuple(Op(OP_KILL, target=k) for k in range(3))
                + (Op(OP_SCORE, n=1, cond=COND_KILLED_N, level=3),)),
    ),
    # At the start of your Beginning Phase, recycle 3 from your trash.  (Two
    # abilities: with 3+ cards you choose them; with fewer, all go.)  His Might
    # is in STATICS.
    "Dr. Mundo - Expert": (
        Ability(TR_BEGINNING,
                targets=tuple(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY)
                              for _ in range(3)),
                ops=tuple(Op(OP_RECYCLE_FROM_TRASH, target=k) for k in range(3))),
        Ability(TR_BEGINNING, cond=COND_TRASH_BELOW, cond_level=3,
                ops=(Op(OP_RECYCLE_TRASH_ALL),)),
    ),
    # When you draw your second card each turn, give a friendly unit +2 Might
    # this turn.
    "Frigid Jewel": (
        Ability(TR_SECOND_DRAW,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),)),
    ),
    # When you play me or the first time you play a non-token gear each turn,
    # you may ready something besides me that's exhausted.  ("Something": a
    # unit or gear.)
    "Jayce, Brilliant Inventor": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_ANY, card_type=("Unit", "Gear"),
                                    must_be_exhausted=True, not_self=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_READY, target=0),)),
        Ability(TR_PLAY_UNIT, subject_card_type="Gear", subject_nontoken=True,
                once_each_turn=True, optional=True,
                targets=(TargetSpec(who=W_ANY, card_type=("Unit", "Gear"),
                                    must_be_exhausted=True, not_self=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_READY, target=0),)),
    ),
    # Kill a friendly unit or gear, Exhaust: [Action] -- [Add] {any rune}
    # {any rune}.
    "Malzahar - Fanatic": (
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_exhaust=True,
                cost_kill=TargetSpec(who=W_FRIENDLY, card_type=("Unit", "Gear")),
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=2, domain=D_ANY),)),
    ),
    # [Action] Exhaust a unit you control, Exhaust: Move a different unit you
    # control to the location of the unit you exhausted to pay for this
    # ability.
    "Forgotten Signpost": (
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_exhaust=True,
                cost_kill=TargetSpec(who=W_FRIENDLY, must_be_ready=True),
                cost_exhaust_unit=True,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_CTX2),)),
    ),
    # [Deflect 2]  When I attack, deal 5 damage split among any number of
    # enemy units here.
    "Volibear - Furious": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_SPLIT_DAMAGE, n=5, at=T_HERE),)),
    ),
    # (enters ready: ENTERS_READY_IF)  When I attack, you may move any number
    # of enemy units here each with 5 Might or less to their base.
    "Corrupted Dragon": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=tuple(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                         max_might=5, optional=True,
                                         locality=LOC_FREE) for _ in range(4)),
                ops=tuple(Op(OP_MOVE_TO, target=k, target_b=T_OWNER_BASE)
                          for k in range(4))),
    ),
    # [Weaponmaster]  When I conquer a battlefield that was uncontrolled, deal
    # damage equal to my Might to an enemy unit in a base.
    "Yone - Blademaster": (
        Ability(TR_CONQUER, cond=COND_CONQUERED_UNCONTROLLED,
                targets=(TargetSpec(who=W_ENEMY, at_base=True, locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n_from_might=T_SELF),)),
    ),
    # Exhaust: [Reaction] -- [Add] {2 energy}. Spend this Energy only to play
    # spells.
    "Lux, Crownguard": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True, ops=(Op(OP_ADD_SPELL_ENERGY, n=2),)),
    ),
    # When you play me, spend any number of buffs. For each buff spent,
    # channel 1 rune exhausted.  (Four slots.)
    "Albus Ferros": (
        Ability(TR_PLAY_ME,
                targets=tuple(TargetSpec(who=W_FRIENDLY, must_be_buffed=True,
                                         optional=True, locality=LOC_FREE)
                              for _ in range(4)),
                ops=tuple(o for k in range(4)
                          for o in (Op(OP_SPEND_BUFF, target=k),
                                    Op(OP_CHANNEL, n=1, target=k)))),
    ),
    # [Vision]  When you recycle one or more cards to your Main Deck, buff a
    # friendly unit.
    "Karma - Channeler": (
        Ability(TR_RECYCLED,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_BUFF, target=0),)),
    ),
    # When you play me, draw 1.  [Empower] {3 energy}  ([Empowered]:
    # EMPOWERED_SPELL_WARD)
    "Mel, Newly Awakened": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
        Ability(TR_ACTIVATED, cost_energy=3, ops=(Op(OP_EMPOWER),)),
    ),
    # [Empower] {Body rune}{Body rune}  ([Empowered]: EMPOWERED_CHOSEN_TO_MIGHT)
    "Gangplank, Naval": (
        Ability(TR_ACTIVATED, cost_power=2, ops=(Op(OP_EMPOWER),)),
    ),
    # {Calm rune}: [Action] -- Choose a unit you control. Move me to its
    # location and it to my original location. If it's equipped, you may
    # attach one of its Equipment to me. Use only once per turn.
    "Azir - Ascendant": (
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_power=1,
                once_each_turn=True,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                    locality=LOC_FREE),
                         TargetSpec(who=W_ANY, card_type=("Gear",),
                                    tags=("Equipment",), attached_to_slot=0,
                                    optional=True, locality=LOC_FREE)),
                ops=(Op(OP_SWAP_LOC, target=T_SELF, target_b=0),
                     Op(OP_ATTACH, target=T_SELF, target_b=1))),
    ),
    # Exhaust: [Reaction] -- Pay any amount of Energy to [Add] that much
    # {any rune}.
    "Ancient Henge": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True, ops=(Op(OP_PAY_ANY_AMOUNT, n=AMT_ENERGY_TO_ANY),)),
    ),
    # Exhaust: [Reaction] -- Pay any amount of {any rune} to [Add] that much
    # Energy.
    "Hextech Anomaly": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True, ops=(Op(OP_PAY_ANY_AMOUNT, n=AMT_ANY_TO_ENERGY),)),
    ),
    # You may exhaust your legend as an additional cost to play me
    # (PLAY_COSTS_LEGEND). When you play me, if you paid the additional cost,
    # move any number of your units to an open battlefield.
    "Bard - Mercurial": (
        Ability(TR_PLAY_ME, cond=COND_PAID_ADDITIONAL,
                targets=(TargetSpec(kind=TK_BATTLEFIELD, open_bf=True,
                                    locality=LOC_FREE),)
                + tuple(TargetSpec(who=W_FRIENDLY, optional=True,
                                   locality=LOC_FREE) for _ in range(4)),
                ops=tuple(Op(OP_MOVE_TO, target=k, target_b=0)
                          for k in range(1, 5))),
    ),
    # When you play me, you may kill a friendly gear. If you do, you may play a
    # gear with Energy cost no more than {7 energy} from hand this turn,
    # ignoring its Energy cost.
    "Jayce, Man of Progress": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, card_type=("Gear",),
                                    locality=LOC_FREE),),
                ops=(Op(OP_KILL, target=0),
                     Op(OP_FREE_GEAR, cond=COND_KILLED_N, level=1))),
    ),
    # When you play this or at the start of your Beginning Phase, [Burn 1].
    # When you burn a unit this way, do this: Give a friendly unit +Might equal
    # to the burned card's Might this turn.
    "Forgotten Relic": (
        Ability(TR_PLAY_ME, ops=(Op(OP_BURN, n=1),
                                 Op(OP_QUEUE_FOLLOWUP, cond=COND_BURNED_UNIT))),
        Ability(TR_BEGINNING, ops=(Op(OP_BURN, n=1),
                                   Op(OP_QUEUE_FOLLOWUP, cond=COND_BURNED_UNIT))),
        Ability(TR_FOLLOWUP,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n_from_last_burned=True),)),
    ),
    # Discard 1, Exhaust: Choose a friendly unit. The next time it would die
    # this turn, you may pay {Fury rune} to heal it, exhaust it, and recall it
    # instead.
    "Unlicensed Armory": (
        Ability(TR_ACTIVATED, cost_discard=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_ARMORY, target=0),)),
    ),
    # When I attack, you may pay {Mind rune} to play a card with [Hidden] from
    # your hand, ignoring its cost. If it's a unit, play it here.
    "Ava Achiever": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK, optional=True,
                opt_cost_power=1,
                ops=(Op(OP_PLAY_FROM_HAND, keyword="Hidden", play_spells=True,
                        cost=COST_FREE, target_b=T_HERE, level=-1),)),
    ),
    # When you play me, [Burn 2]. When I conquer, give a spell in your trash
    # [Flow] equal to its cost this turn.
    "Kennen, Storm of Shuriken": (
        Ability(TR_PLAY_ME, ops=(Op(OP_BURN, n=2),)),
        Ability(TR_CONQUER,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Spell",)),),
                ops=(Op(OP_GRANT_FLOW, target=0, grant_this_turn=True,
                        ready=True),)),
    ),
    # [Empower] {any rune}{any rune}  Disempower this, Exhaust: Choose a player.
    # They gain control of this and recall it.  At the end of your turn, kill
    # this and deal 5 to all units you control.
    "Glowstone": (
        Ability(TR_ACTIVATED, cost_power=2, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_disempower_self=True, cost_exhaust=True,
                targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN, ops=(Op(OP_TAKE_CONTROL, target=T_SELF,
                                                    to_base=True),)),
                       CardSpec(SPEED_MAIN, ops=(Op(OP_TAKE_CONTROL, target=T_SELF,
                                                    to_base=True, who=W_ENEMY),)))),
        Ability(TR_END_OF_TURN,
                ops=(Op(OP_KILL, target=T_SELF),
                     Op(OP_DAMAGE_ALL, n=5, who=W_FRIENDLY))),
    ),
    # When you play this, banish all units from your trash. Exhaust: Play a
    # unit banished with this. (You must pay its costs.)
    "Cursed Sarcophagus": (
        Ability(TR_PLAY_ME, ops=(Op(OP_SARC_BANISH),)),
        Ability(TR_ACTIVATED, cost_exhaust=True, ops=(Op(OP_SARC_PLAY),)),
    ),
    # [Ganking]  When I attack, the defender must kill one of their units here.
    "Atakhan": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_EACH_KILLS_OWN, cull_mode=CULL_KILL_OWN, who=W_ENEMY,
                        target_b=T_HERE),)),
    ),
    # (Your Mechs each have [Assault]: STATICS.)  When I conquer, you may
    # recycle another friendly unit to play a Mech from your trash. Reduce its
    # Energy cost by the Might of the unit you recycled.  (To your base; the
    # Mech is still only offered when its full cost is affordable.)
    "Rumble - Hotheaded": (
        Ability(TR_CONQUER, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                    locality=LOC_FREE),
                         TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Unit",), tags=("Mech",),
                                    playable=True, playable_cost=COST_PRINTED)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=1, target_b=T_MY_BASE,
                        cost=COST_PRINTED, n_from_might=0),
                     Op(OP_TO_DECK, target=0, pick_dest=DEST_RECYCLE))),
    ),
    # [Empower] {2 energy}{Fury rune}  When I move, you may deal 1 to a unit at
    # a battlefield I moved to or from. If I'm [Empowered], deal 2 instead.
    # ([Empowered] +1 Might: STATICS)
    "Akali, Deadly Weapon": (
        Ability(TR_ACTIVATED, cost_energy=2, cost_power=1, ops=(Op(OP_EMPOWER),)),
        Ability(TR_MOVE, optional=True,
                targets=(TargetSpec(who=W_ANY, at_source_move_ends=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n=1, cond=COND_NOT_EMPOWERED),
                     Op(OP_DAMAGE, target=0, n=2, cond=COND_EMPOWERED))),
    ),
    # [Shield]  Exhaust: Buff me. I can have any number of buffs (MULTI_BUFF).
    "Lee Sin - Ascetic": (
        Ability(TR_ACTIVATED, cost_exhaust=True, ops=(Op(OP_BUFF, target=T_SELF),)),
    ),
    # As you play me, choose Bird, Cat, Dog, or Poro. I gain that tag.  When I
    # conquer or hold, score 1 point if your units have all of the following
    # tags among them -- Bird, Cat, Dog, and Poro.
    "Ivern - Friend to All": (
        Ability(TR_PLAY_ME, targets=(MODE_SLOT,),
                modes=tuple(CardSpec(SPEED_MAIN,
                                     ops=(Op(OP_GAIN_TAG, target=T_SELF, tag=tg),))
                            for tg in ("Bird", "Cat", "Dog", "Poro"))),
        Ability(TR_CONQUER, ops=(Op(OP_SCORE, n=1, cond=COND_ALL_ANIMAL_TAGS),)),
        Ability(TR_HOLD, ops=(Op(OP_SCORE, n=1, cond=COND_ALL_ANIMAL_TAGS),)),
    ),
    # As you play this, name a tag. Exhaust: Give a unit with the named tag -2
    # Might this turn.  (Named as it enters, from the tags its controller can
    # see on the opponent's side -- see OP_NAME.)
    "The List": (
        Ability(TR_PLAY_ME, ops=(Op(OP_NAME, n=NAME_TAG),)),
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, named_tag_of_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2),)),
    ),
    # When you play me, name a spell. (While I'm at a battlefield, opponents
    # can't play spells with that name: NAMED_SPELL_LOCKS.)
    "Fallen Feline": (
        Ability(TR_PLAY_ME, ops=(Op(OP_NAME, n=NAME_SPELL),)),
    ),
    # [Hidden] [Temporary]  When you play me, play two Reflection unit tokens
    # here. Then do this: They become copies of me.
    "Keeper of Masks": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_COPY_PREP, target=T_SELF),
                     Op(OP_CREATE_TOKEN, target=T_HERE, n=2, token=REFLECTION_TOKEN,
                        then_key=FU_BECOME_COPY))),
    ),
    # [Weaponmaster]  (optional {Body rune}{Body rune}: PLAY_COSTS)  When you
    # play me, if you paid the additional cost, move an enemy gear to your base.
    # You control it until I leave the board. If it's an Equipment, attach it
    # to me.
    "Akshan - Mischievous": (
        Ability(TR_PLAY_ME, cond=COND_PAID_ADDITIONAL,
                targets=(TargetSpec(who=W_ENEMY, card_type=("Gear",),
                                    locality=LOC_FREE),),
                ops=(Op(OP_TAKE_CONTROL, target=0, to_base=True),
                     Op(OP_LINK_CONTROL, target=0),
                     Op(OP_ATTACH, target=T_SELF, target_b=0))),
    ),
    # [Equip] {1 energy}{Mind rune}  {3 energy}{Mind rune}, Banish this: Play
    # all units banished with this, ignoring their costs. (Use only if
    # unattached.)  (Its band's Deathknell: EQUIP_ABILITIES.)
    "The Zero Drive": (
        Ability(TR_ACTIVATED, cost_energy=3, cost_power=1, unattached_only=True,
                ops=(Op(OP_ZERO_PLAY),)),
    ),
    # When you play this, banish your hand and trash, then [Burn 7]. Skip your
    # Draw Phase. You may play cards from your trash. If a card would go to
    # your trash from anywhere other than your Main Deck, banish it instead.
    # (The standing rules read `state.riches_on`.)
    "Endless Riches": (
        Ability(TR_PLAY_ME, ops=(Op(OP_ENDLESS_RICHES),)),
    ),
    "Rell - Magnetic": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_PLAY_FROM_HAND, pick_types=("Gear",), tag="Equipment",
                        pick_optional=True, cost=COST_FREE, level=2,
                        target_b=T_MY_BASE, attach_to_source=True),)),
    ),
    # Discard a gear, {1 energy}, Exhaust: Deal 4 to a unit at a battlefield.
    "Sky Cruiser": (
        Ability(TR_ACTIVATED, cost_discard=1, cost_discard_type="Gear",
                cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n=4),)),
    ),
    # When I attack, you may move any number of your token units to this
    # battlefield.  (Four slots.)
    "Azir - Sovereign": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=tuple(TargetSpec(who=W_FRIENDLY, token_only=True,
                                         different_loc_from_source=True,
                                         optional=True, locality=LOC_FREE)
                              for _ in range(4)),
                ops=tuple(Op(OP_MOVE_TO, target=k, target_b=T_HERE)
                          for k in range(4))),
    ),
    # When you play me, if you paid the additional cost, kill a gear.
    "Zaun Punk": (
        Ability(TR_PLAY_ME, cond=COND_PAID_ADDITIONAL,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",),
                                    locality=LOC_FREE),),
                ops=(Op(OP_KILL, target=0),)),
    ),
    # When a friendly unit dies, you may exhaust me to draw 1, then put a card
    # from your hand on the top or bottom of your Main Deck.
    "Altar of Memories": (
        Ability(TR_OTHER_DIES, optional=True, opt_cost_exhaust_self=True,
                ops=(Op(OP_DRAW, n=1),
                     Op(OP_DISCARD_CHOOSE, n=1, branch_key=DB_TO_DECK))),
    ),
    # Exhaust: Return another friendly gear, unit, or facedown card to its
    # owner's hand.  (Two modes: a permanent, or a facedown card.)
    "Pack of Wonders": (
        Ability(TR_ACTIVATED, cost_exhaust=True, targets=(MODE_SLOT,),
                modes=(CardSpec(SPEED_MAIN,
                                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                                    card_type=("Unit", "Gear"),
                                                    locality=LOC_FREE),),
                                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
                       CardSpec(SPEED_MAIN,
                                targets=(TargetSpec(kind=TK_BATTLEFIELD,
                                                    own_facedown=True,
                                                    locality=LOC_FREE),),
                                ops=(Op(OP_RETURN_FACEDOWN, target=0),)))),
    ),
    # When I conquer, if you assigned 3 or more excess damage, play two Gold
    # gear tokens exhausted.
    "Yeti Brawler": (
        Ability(TR_CONQUER, cond=COND_EXCESS_AT_LEAST, cond_level=3,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=2, token=GOLD_TOKEN),)),
    ),
    # When I conquer after an attack, if you assigned 5 or more excess damage
    # to enemy units, you score 1 point.
    "Tryndamere - Barbarian": (
        Ability(TR_CONQUER, cond=COND_EXCESS_AFTER_ATTACK, cond_level=5,
                ops=(Op(OP_SCORE, n=1),)),
    ),
    # [Deflect 2]  When I conquer after an attack, if you assigned 5 or more
    # excess damage to enemy units, you may deal that much to an enemy unit.
    "Sivir - Ambitious": (
        Ability(TR_CONQUER, cond=COND_EXCESS_AFTER_ATTACK, cond_level=5,
                optional=True,
                targets=(TargetSpec(who=W_ENEMY, locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n_from_excess=True),)),
    ),
    # If you play me to a battlefield, I enter ready. (ENTERS_READY_AT_BF)
    # [Action] {1 energy}{any rune}, Exhaust: [Stun] an enemy unit attacking here.
    "Shadow": (
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_energy=1, cost_power=1,
                cost_exhaust=True,
                targets=(TargetSpec(who=W_ENEMY, attacking=True,
                                    same_loc_as_source=True, locality=LOC_FREE),),
                ops=(Op(OP_STUN, target=0),)),
    ),
    # Exhaust: The next spell you play this turn deals 1 Bonus Damage.
    "Ravenborn Tome": (
        Ability(TR_ACTIVATED, cost_exhaust=True, ops=(Op(OP_NEXT_SPELL_BONUS),)),
    ),
    # {any rune}, Exhaust: Give the next spell you play this turn [Repeat] equal
    # to its cost.
    "Temporal Portal": (
        Ability(TR_ACTIVATED, cost_power=1, cost_exhaust=True,
                ops=(Op(OP_NEXT_SPELL_REPEAT),)),
    ),
    # [Vision]  Other friendly units have [Vision] -- a Vision trigger for each
    # other friendly unit you play while I'm on the board.
    "Gemcraft Seer": (
        Ability(TR_PLAY_UNIT, subject_not_self=True,
                ops=(Op(OP_LOOK_TOP, n=1, pick_optional=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP),)),
    ),
    # Your Mechs have [Vision].
    "Forecaster": (
        Ability(TR_PLAY_UNIT, subject_tag="Mech",
                ops=(Op(OP_LOOK_TOP, n=1, pick_optional=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP),)),
    ),

    # (additional cost in PLAY_COSTS)  When you play me, if you paid the
    # additional cost, banish a card from any trash to give a unit [Assault 2]
    # this turn.
    "Gust Monk": (
        Ability(TR_PLAY_ME, cond=COND_PAID_ADDITIONAL,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_ANY, locality=LOC_FREE),
                         TargetSpec(who=W_ANY, locality=LOC_FREE)),
                ops=(Op(OP_BANISH_FROM_TRASH, target=0),
                     Op(OP_GRANT_KEYWORD, target=1, keyword="Assault", n=2))),
    ),
    # (discard additional cost in PLAY_COSTS_DISCARD)  When you play me, if you
    # paid the additional cost, play a 0 Might Shadow Clone unit token.
    "Zed, From the Shadows": (
        Ability(TR_PLAY_ME, cond=COND_PAID_ADDITIONAL,
                targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
                ops=(Op(OP_CREATE_TOKEN, target=0, n=1,
                        token="Shadow Clone"),)),
    ),
    # When you play me, discard 1, then draw 2. (The additional-cost discount
    # is ADD_COST_REDUCERS.)
    "Ezreal, Prodigy": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=2))),
    ),
    # I can't be readied. (NEVER_READIED)  {Chaos rune}: Move me to an occupied
    # enemy battlefield if my Might is greater than the total Might of enemy
    # units there.
    "Maduli the Gatekeeper": (
        Ability(TR_ACTIVATED, cost_power=1,
                targets=(TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY,
                                    enemy_might_below_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_MOVE_TO, target=T_SELF, target_b=0),)),
    ),
    # [Deflect]  When I move to a battlefield, give another friendly unit my
    # keywords and +Might equal to my Might this turn.
    "Kato the Arm": (
        Ability(TR_MOVE, at_battlefield=True,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True, locality=LOC_FREE),),
                ops=(Op(OP_GRANT_MY_KEYWORDS, target=0),
                     Op(OP_MODIFY_MIGHT, target=0, n_from_might=T_SELF))),
    ),
    # When you defend at a battlefield, you may move me there.
    "Loyal Pup": (
        Ability(TR_ATTACK_OR_DEFEND, subject_any_friendly=True,
                subject_role=ROLE_DEFEND, once_per_combat=True, optional=True,
                ops=(Op(OP_MOVE_TO, target=T_SELF, target_b=T_CTX),)),
    ),

    # The Shadow Clone TOKEN: "When I attack, you may banish a unit from your
    # trash. If you do, give me [Assault 4] this turn."
    "Shadow Clone": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Unit",), locality=LOC_FREE),),
                ops=(Op(OP_BANISH_FROM_TRASH, target=0),
                     Op(OP_GRANT_KEYWORD, target=T_SELF, keyword="Assault", n=4))),
    ),
    # When I conquer, play a 0 Might Shadow Clone unit token to your base.
    # [Action] {1 energy}{Chaos rune}: Move me and a Shadow Clone you control to
    # each other's locations.
    "Zed, Without a Sound": (
        Ability(TR_CONQUER,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token="Shadow Clone"),)),
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_energy=1, cost_power=1,
                targets=(TargetSpec(who=W_FRIENDLY, card_name="Shadow Clone",
                                    locality=LOC_FREE),),
                ops=(Op(OP_SWAP_LOC, target=T_SELF, target_b=0),)),
    ),
    # [Empower] -- Discard 1.  [Empowered] I have +1 Might. (STATICS)
    "Punching Poro": (
        Ability(TR_ACTIVATED, cost_discard=1, ops=(Op(OP_EMPOWER),)),
    ),
    # [Empower] -- Discard a spell.  When I become [Empowered], banish an enemy
    # unit at a battlefield with 3 Might or less.
    "Mel, Defiant Soul": (
        Ability(TR_ACTIVATED, cost_discard=1, cost_discard_type="Spell",
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_BECOME_EMPOWERED, subject_is_self=True,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True, max_might=3,
                                    locality=LOC_FREE),),
                ops=(Op(OP_BANISH, target=0),)),
    ),
    # Exhaust: [Legion] -- The next unit you play this turn enters ready.
    "Sun Disc": (
        Ability(TR_ACTIVATED, cost_exhaust=True, cond=COND_PLAYED_CARD_THIS_TURN,
                ops=(Op(OP_NEXT_UNIT_READY),)),
    ),
    # When you play this, buff a friendly unit.  (Deflect static in STATICS.)
    "Spirit's Refuge": (
        Ability(TR_PLAY_ME, targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_BUFF, target=0),)),
    ),
    # (XP additional cost in PLAY_COSTS_XP)  When you play me, each player must
    # kill one of their units. If you paid my additional cost, you don't.
    "Safety Inspector": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_EACH_KILLS_OWN, cond=COND_NOT_PAID_ADDITIONAL),
                     Op(OP_EACH_KILLS_OWN, who=W_ENEMY, start_next=True,
                        cond=COND_PAID_ADDITIONAL))),
    ),
    # [Accelerate]  Your conquer effects for conquering here trigger an
    # additional time. (EXTRA_CONQUER_HERE)  When I conquer, [Buff] a friendly
    # unit.
    "Red Brambleback": (
        Ability(TR_CONQUER, targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_BUFF, target=0),)),
    ),
    # [Shield 2]  Your hold effects for holding here trigger an additional
    # time. (EXTRA_HOLD_HERE)  When I hold, [Add] {any rune} at the start of
    # your next Main Phase.
    "Blue Sentinel": (
        Ability(TR_HOLD, ops=(Op(OP_ADD_ANY_NEXT_MAIN, n=1),)),
    ),
    # The first time a friendly unit dies during your Beginning Phase each
    # turn, each opponent must kill one of their units.
    "Shard of Undoing": (
        Ability(TR_FIRST_BEGINNING_DEATH,
                ops=(Op(OP_EACH_KILLS_OWN, who=W_ENEMY, start_next=True),)),
    ),
    # [Shield] [Tank]  When you [Stun] an enemy unit at a battlefield, you may
    # move me to that battlefield.
    "Vex - Mocking": (
        Ability(TR_STUN, subject_enemy=True, subject_on_battlefield=True,
                optional=True,
                ops=(Op(OP_MOVE_TO, target=T_SELF, loc_of_target=T_SUBJECT),)),
    ),
    # Any amount of your damage is enough to kill enemy units.
    # (YOUR_DAMAGE_KILLS)  When you play me, choose up to one enemy unit at each
    # location. Deal 1 to them.
    "Elder Dragon": (
        Ability(TR_PLAY_ME,
                targets=tuple(TargetSpec(who=W_ENEMY, exact_loc=k, optional=True,
                                         locality=LOC_FREE) for k in range(4)),
                ops=tuple(Op(OP_DAMAGE, target=k, n=1) for k in range(4))),
    ),
    # When you play me, you and each opponent may play a Gold gear token
    # exhausted. For each opponent who did, you play a Gold gear token
    # exhausted.  You answer first, then the opponent (FOLLOWUPS).
    "Card Sharp": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_ASK, who=W_FRIENDLY,
                        then_key=FU_CARD_SHARP_MINE_THEN_OPP,
                        ask_no_key=FU_CARD_SHARP_ASK_OPP),)),
    ),
    # Deal 5 to a unit. (SPECS)  When you conquer, you may discard 1 to return
    # this from your trash to your hand.
    "Super Mega Death Rocket!": (
        Ability(TR_CONQUER_FROM_TRASH, optional=True, opt_cost_discard=1,
                ops=(Op(OP_TRASH_TO_HAND, self_card=True),)),
    ),
    # [Ganking]  When I conquer, you may play a spell from your trash with
    # Energy cost less than your points without paying its Energy cost. Then
    # recycle it.
    "Kai'Sa - Evolutionary": (
        Ability(TR_CONQUER, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Spell",), playable=True,
                                    playable_cost=COST_NO_ENERGY,
                                    energy_below_points=True),),
                ops=(Op(OP_PLAY_FROM_TRASH, target=0, dest=DEST_RECYCLE,
                        cost=COST_NO_ENERGY),)),
    ),
    # When you discard me, you may pay {1 energy} to give a friendly unit +2
    # Might this turn.
    "Mask Mother": (
        Ability(TR_DISCARD_ME, optional=True, opt_cost_energy=1,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),)),
    ),
    # When you discard me, you may pay {Fury rune} to play me.
    "Flame Chompers": (
        Ability(TR_DISCARD_ME, optional=True, opt_cost_power=1,
                targets=(TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, self_card=True, target_b=0,
                        cost=COST_FREE),)),
    ),
    # When this is played, discarded, or killed, draw 1.
    "Scrapheap": tuple(Ability(tr, ops=(Op(OP_DRAW, n=1),))
                       for tr in (TR_PLAY_ME, TR_DISCARD_ME, TR_DEATH)),

    # When I move, reveal the top card of your Main Deck. If it's a unit, draw
    # it. Otherwise, put it in your trash and give me +2 Might this turn.
    "Pakaa Protector": (
        Ability(TR_MOVE, ops=(Op(OP_REVEAL_TOP, pick_types=("Unit",),
                                 rest_dest=DEST_TRASH),
                              Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                                 cond=COND_REVEAL_MISSED))),
    ),
    # When I move, reveal the top card of your Main Deck. If it's a gear, draw
    # it. Otherwise, recycle it.
    "Apprentice Smith": (
        Ability(TR_MOVE, ops=(Op(OP_REVEAL_TOP, pick_types=("Gear",),
                                 rest_dest=DEST_RECYCLE),)),
    ),

    # --- batch 13 ----------------------------------------------------------
    # [Ganking]  The third time I move in a turn, you score 1 point.
    "Yasuo - Windrider": (
        Ability(TR_MOVE, subject_nth=3, ops=(Op(OP_SCORE, n=1),)),
    ),
    # [Shield]  When I hold, if there is exactly one other unit you control
    # here, you score 1 point.
    "Shen, Leader of the Kinkou Order": (
        Ability(TR_HOLD, ops=(Op(OP_SCORE, n=1, cond=COND_N_OTHERS_HERE,
                                 level=1),)),
    ),
    # When you play me or when I score, play a 1 Might Tentacle unit token.
    # ("When I score" is conquering or holding -- the two ways to score.)
    "Illaoi, Prophet of the Great Kraken": tuple(
        Ability(tr, ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                            token=TENTACLE_TOKEN),))
        for tr in (TR_PLAY_ME, TR_CONQUER, TR_HOLD)),

    # --- Weaponmaster ------------------------------------------------------
    # [Weaponmaster]  The first time I conquer each turn, ready me.
    "Lucian - Merciless": (
        Ability(TR_CONQUER, once_each_turn=True,
                ops=(Op(OP_READY, target=T_SELF),)),
    ),
    # [Weaponmaster]  When I attack, choose an enemy unit here. Deal 2 to it
    # for each Equipment attached to me.
    "Riven, Shattered": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n=2,
                        n_from_count=CT_SOURCE_EQUIPMENT),)),
    ),
    # [Weaponmaster]  When you attach an Equipment to me, you may pay
    # {1 energy} to draw 1.
    "Jax - Unrelenting": (
        Ability(TR_EQUIPPED, optional=True, opt_cost_energy=1,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # --- batch 10 ----------------------------------------------------------
    # (additional cost in PLAY_COSTS)  When you play me, if you paid the
    # additional cost, [Stun] an enemy unit.  When I hold, the next time you
    # play a unit this turn, ready it and [Buff] it. (DELAYED_ABILITIES)
    "Nami - Headstrong": (
        Ability(TR_PLAY_ME, cond=COND_PAID_ADDITIONAL,
                targets=(TargetSpec(who=W_ENEMY, locality=LOC_FREE),),
                ops=(Op(OP_STUN, target=0),)),
        Ability(TR_HOLD, ops=(Op(OP_ARM_DELAYED),)),
    ),
    # [Empower] {12 energy}, {1 energy} less per rune you control.
    # [Empowered] I have +3 Might. (STATICS)
    "Frostcoat Mother": (
        Ability(TR_ACTIVATED, cost_energy=12, energy_less_per_rune=1,
                ops=(Op(OP_EMPOWER),)),
    ),
    "Grumpy Rockbear": (
        Ability(TR_ACTIVATED, cost_energy=12, energy_less_per_rune=1,
                ops=(Op(OP_EMPOWER),)),
    ),
    # [Empower] {5 energy}, {3 energy} less if you control 4 or fewer runes.
    "Baccai Sandspinner": (
        Ability(TR_ACTIVATED, cost_energy=5,
                energy_less_if_runes_at_most=(4, 3),
                ops=(Op(OP_EMPOWER),)),
    ),
    # When I hold, you score 1 point.
    "Ahri - Alluring": (
        Ability(TR_HOLD, ops=(Op(OP_SCORE, n=1),)),
    ),
    # [Assault]  [Deathknell] Draw 1. If it's your Beginning Phase, draw 2
    # instead.
    "LeBlanc - Fragmented": (
        Ability(TR_DEATH,
                ops=(Op(OP_DRAW, n=2, cond=COND_MY_BEGINNING),
                     Op(OP_DRAW, n=1, cond=COND_NOT_MY_BEGINNING))),
    ),
    # [Legion] -- When you play me, ready me.  Other friendly units have
    # +1 Might here. (STATICS)
    "Darius - Executioner": (
        Ability(TR_PLAY_ME, ops=(Op(OP_READY, target=T_SELF, cond=COND_LEGION),)),
    ),
    # [Legion] -- When you play me, discard 2, then draw 2.
    "Scrapyard Champion": (
        Ability(TR_PLAY_ME, cond=COND_LEGION,
                ops=(Op(OP_DISCARD, n=2), Op(OP_DRAW, n=2))),
    ),
    # Spend 3 XP: Give your units here [Ganking] this turn.
    "Megatusk": (
        Ability(TR_ACTIVATED, cost_xp=3,
                ops=(Op(OP_GRANT_KEYWORD_ALL, at=T_HERE, who=W_FRIENDLY,
                        keyword="Ganking"),)),
    ),
    # [Ambush]  When I attack or defend, if an enemy unit is alone here, give me
    # +2 Might this turn and gain 2 XP.
    "Kha'Zix - Mutating Horror": (
        Ability(TR_ATTACK_OR_DEFEND, cond=COND_ENEMY_ALONE_HERE,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),
                     Op(OP_GAIN_XP, n=2))),
    ),
    # [Hunt]  When I attack, you may spend 3 XP to deal damage equal to my
    # Might to an enemy unit here.
    "Kha'Zix, Evolving Hunter": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK, optional=True,
                opt_cost_xp=3,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n_from_might=T_SELF),)),
    ),
    # [Hidden]  When you play this from face down, attach it to a unit you
    # control here.  [Equip] {Chaos}  Attached: +2 Might.
    "Edge of Night": (
        Ability(TR_PLAY_ME, from_hidden=True,
                targets=(TargetSpec(who=W_FRIENDLY, same_loc_as_source=True),),
                ops=(Op(OP_ATTACH, target=0),)),
    ),

    # --- batch 9 -----------------------------------------------------------
    # When you play a card with Power cost {any rune}{any rune} or more, draw 1.
    "Yordle Explorer": (
        Ability(TR_NTH_CARD, subject_nth=0, subject_min_power=2,
                ops=(Op(OP_DRAW, n=1),)),
    ),
    # When you play this, you may move an enemy unit.
    # When you move an enemy unit, you may exhaust this to [Stun] it.
    "Blast Cone": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_ENEMY, locality=LOC_FREE),
                         TargetSpec(kind=TK_LOCATION, locality=LOC_FREE,
                                    move_dest_of=0)),
                ops=(Op(OP_MOVE_TO, target=0, target_b=1),)),
        Ability(TR_MOVED_ENEMY, subject_enemy=True, optional=True,
                opt_cost_exhaust_self=True,
                ops=(Op(OP_STUN, target=T_SUBJECT),)),
    ),
    # [Assault]  When I attack, deal damage equal to my [Assault] to an enemy
    # unit here.
    "Lucian - Gunslinger": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n_from_assault=T_SELF),)),
    ),
    # [Deflect] [Ganking]  When I move, [Add] {1 energy}{any rune}.
    "Jhin - Murderous Artist": (
        Ability(TR_MOVE, ops=(Op(OP_ADD_ENERGY, n=1),
                              Op(OP_ADD_POWER, n=1, domain=D_ANY))),
    ),
    # When you play me, the next spell you play this turn costs {5 energy} less.
    "Raging Firebrand": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DISCOUNT_NEXT_SPELL, n=5),)),
    ),
    # When you play me, buff up to four friendly units.
    # When you spend a buff, play a Gold gear token exhausted.
    "Fae Dragon": (
        Ability(TR_PLAY_ME,
                targets=tuple(TargetSpec(who=W_FRIENDLY, optional=True,
                                         locality=LOC_FREE) for _ in range(4)),
                ops=tuple(Op(OP_BUFF, target=k) for k in range(4))),
        Ability(TR_SPEND_BUFF,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),
    # When you play me, you may spend a buff to buff me and ready me.
    "Wildclaw Shaman": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, must_be_buffed=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_SPEND_BUFF, target=0), Op(OP_BUFF, target=T_SELF),
                     Op(OP_READY, target=T_SELF))),
    ),

    # --- batch 8b ----------------------------------------------------------
    # When you play me, look at the top 4 cards of your Main Deck. You may
    # reveal a spell with Energy cost {4 energy} or more from among them and
    # draw it. Recycle the rest.
    "Fate Weaver": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_PICK, n=4, pick_optional=True,
                        pick_types=("Spell",), pick_min_energy=4,
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),)),
    ),
    # When an opponent plays a gear, you may banish me to banish it.
    "Ravenbloom Prefect": (
        Ability(TR_PLAY_UNIT, subject_enemy=True, subject_card_type="Gear",
                optional=True, opt_cost_banish_self=True,
                ops=(Op(OP_BANISH, target=T_SUBJECT),)),
    ),
    # {Order rune}: Ready me and give me +1 Might this turn. Use only if you've
    # chosen an enemy unit this turn and only once each turn.
    "Hungry Wolf": (
        Ability(TR_ACTIVATED, cost_power=1, once_each_turn=True,
                cond=COND_CHOSE_ENEMY_THIS_TURN,
                ops=(Op(OP_READY, target=T_SELF),
                     Op(OP_MODIFY_MIGHT, target=T_SELF, n=1))),
    ),
    # I enter ready. (ENTERS_READY_IF)  Reduce my cost by {1 energy} for each of
    # Bird, Cat, Dog, Poro among your units. (STATICS)  When I attack while your
    # units have all 4 tags, [Stun] an enemy unit here.
    "Daisy!": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                cond=COND_ALL_ANIMAL_TAGS,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_STUN, target=0),)),
    ),
    # When you play me, if you control 7 or more runes, choose an enemy gear.
    # If it's [Empowered], disempower it. Otherwise, kill it.
    # Kill first: disempowering first would make the kill's condition true.
    "Tomb-Raider Barbara": (
        Ability(TR_PLAY_ME, cond=COND_RUNES_AT_LEAST, cond_level=7,
                targets=(TargetSpec(who=W_ENEMY, card_type=("Gear",),
                                    locality=LOC_FREE),),
                ops=(Op(OP_KILL, target=0, cond=COND_TARGET_NOT_EMPOWERED),
                     Op(OP_DISEMPOWER, target=0, cond=COND_TARGET_EMPOWERED))),
    ),
    # [Ganking]  When you play a spell, if you spent {4 energy} or more, ready
    # me.
    "Revna the Lorekeeper": (
        Ability(TR_PLAY_SPELL, subject_min_spent=4,
                ops=(Op(OP_READY, target=T_SELF),)),
    ),

    # --- batch 8a ----------------------------------------------------------
    # [Assault 3]  If an opponent controls a battlefield, I enter ready.
    # When I conquer, you may pay {1 energy} to return me to my owner's hand.
    "Vayne - Hunter": (
        Ability(TR_CONQUER, optional=True, opt_cost_energy=1,
                ops=(Op(OP_RETURN_TO_HAND, target=T_SELF),)),
    ),
    # I enter ready.  When I attack, kill all damaged enemy units here.
    "Warwick - Hunter": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_KILL_ALL, at=T_HERE, who=W_ENEMY,
                        damaged_only=True),)),
    ),
    # [Ambush]  When you play me, deal damage to a unit equal to the damage
    # marked on it.
    "Morgana, Vindictive": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n_from_damage=0),)),
    ),
    # [Ambush]  When you play me, give your other units here [Shield] this turn.
    "Chakram Dancer": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_GRANT_KEYWORD_ALL, at=T_HERE, who=W_FRIENDLY,
                        except_target=T_SELF, keyword="Shield"),)),
    ),
    # [Ambush]  When you play me, give your other units here [Assault] this
    # turn.
    "Lord Broadmane": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_GRANT_KEYWORD_ALL, at=T_HERE, who=W_FRIENDLY,
                        except_target=T_SELF, keyword="Assault"),)),
    ),
    # [Deflect]  When you play me, choose an opponent. They play a 1 Might
    # Bird unit token with [Deflect].
    # Two players, so "an opponent" is not a choice.
    "Walking Roost": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, n=1, token=BIRD_TOKEN, who=W_ENEMY),)),
    ),
    # When you buff me, ready me.
    "Simian Ancestor": (
        Ability(TR_BUFFED, subject_is_self=True,
                ops=(Op(OP_READY, target=T_SELF),)),
    ),
    # When you buff a friendly unit, you may pay {Body rune} and exhaust this
    # to ready it.
    "Mistfall": (
        Ability(TR_BUFFED, optional=True, opt_cost_power=1,
                opt_cost_exhaust_self=True,
                ops=(Op(OP_READY, target=T_SUBJECT),)),
    ),
    # [Hidden]  When you play me or I attack, you may pay {2 energy} to [Stun]
    # a unit.  While there's a stunned enemy unit here, I have +2 Might.
    "Kennen, Keeper of Balance": (
        Ability(TR_PLAY_ME, optional=True, opt_cost_energy=2,
                targets=(TargetSpec(who=W_ANY, locality=LOC_FREE),),
                ops=(Op(OP_STUN, target=0),)),
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK, optional=True,
                opt_cost_energy=2,
                targets=(TargetSpec(who=W_ANY, locality=LOC_FREE),),
                ops=(Op(OP_STUN, target=0),)),
    ),
    # When I attack or defend, deal damage equal to my Might to an enemy unit
    # here.  I don't deal combat damage. (STATICS)
    # {Mind rune}: [Action] -- Move me to your base.
    "Ezreal - Dashing": (
        Ability(TR_ATTACK_OR_DEFEND,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n_from_might=T_SELF),)),
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_power=1,
                ops=(Op(OP_MOVE_TO, target=T_SELF, target_b=T_MY_BASE),)),
    ),
    # [Ambush]  Enemy units here with less Might than me don't deal combat
    # damage. (STATICS)  When I hold, draw 1.
    "Vilemaw": (
        Ability(TR_HOLD, ops=(Op(OP_DRAW, n=1),)),
    ),

    # --- watchers and optional exhausts ------------------------------------
    # When you stun an enemy unit, ready me and give me +1 Might this turn.
    "Eclipse Herald": (
        Ability(TR_STUN, subject_enemy=True,
                ops=(Op(OP_READY, target=T_SELF),
                     Op(OP_MODIFY_MIGHT, target=T_SELF, n=1))),
    ),
    # When you play a card on an opponent's turn, play a 1 Might Recruit unit
    # token to your base.
    "Viktor, Innovator": (
        Ability(TR_NTH_CARD, subject_nth=0, opp_turn=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=RECRUIT_TOKEN),)),
    ),
    # When you play a spell on an opponent's turn, you may exhaust me to play
    # a Gold gear token exhausted.
    "Chemtech Cask": (
        Ability(TR_PLAY_SPELL, opp_turn=True, optional=True,
                opt_cost_exhaust_self=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),
    # When you play a spell that costs {5 energy} or more, give me +3 Might
    # this turn.
    "Lux - Illuminated": (
        Ability(TR_PLAY_SPELL, subject_min_energy=5,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=3),)),
    ),
    # When you play a unit during a showdown, you may exhaust this to draw 1.
    "Fresh Beans": (
        Ability(TR_PLAY_UNIT, in_showdown=True, optional=True,
                opt_cost_exhaust_self=True, ops=(Op(OP_DRAW, n=1),)),
    ),
    # When you choose a friendly unit, you may pay {1 energy} and exhaust this
    # to draw 1.
    "Spirit Wheel": (
        Ability(TR_CHOSEN, optional=True, opt_cost_energy=1,
                opt_cost_exhaust_self=True, ops=(Op(OP_DRAW, n=1),)),
    ),
    # When a combat that I was in ends, if I haven't been dealt damage this
    # turn, draw 1.
    "Affectionate Poro": (
        Ability(TR_COMBAT_ENDS,
                ops=(Op(OP_DRAW, n=1, cond=COND_NOT_DAMAGED_THIS_TURN),)),
    ),
    # When I conquer, you may kill a gear with Energy cost no more than my
    # Might.
    "Noxian Demolitionist": (
        Ability(TR_CONQUER,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",),
                                    optional=True, locality=LOC_FREE,
                                    max_energy_source_might=True),),
                ops=(Op(OP_KILL, target=0),)),
    ),
    # When I move, you may move an enemy unit here with less Might than me to a
    # different battlefield.
    # A free "may" on the ability with REQUIRED slots, so an empty board never
    # triggers it (355.8) and declining costs one decision, not two.
    "Imposing Challenger": (
        Ability(TR_MOVE, optional=True,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    less_might_than_source=True,
                                    locality=LOC_FREE),
                         TargetSpec(kind=TK_BATTLEFIELD, who=W_ANY,
                                    different_loc_from_source=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_MOVE_TO, target=0, target_b=1),)),
    ),
    # When I move to a battlefield, you may pay {Chaos rune} to move a unit you
    # control to the same battlefield.
    "Fae Porter": (
        Ability(TR_MOVE, at_battlefield=True, optional=True, opt_cost_power=1,
                targets=(TargetSpec(who=W_FRIENDLY,
                                    different_loc_from_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_HERE),)),
    ),

    # --- XP -------------------------------------------------------------------
    # [Accelerate]  When I move to a battlefield, gain 2 XP.
    "Mister Root": (
        Ability(TR_MOVE, at_battlefield=True, ops=(Op(OP_GAIN_XP, n=2),)),
    ),
    # [Accelerate] [Ganking]  When I move, gain 1 XP.
    "Nilah - Joyful Ascetic": (
        Ability(TR_MOVE, ops=(Op(OP_GAIN_XP, n=1),)),
    ),
    # When another friendly unit dies, gain 1 XP.
    "Vicious Snapjaws": (
        Ability(TR_OTHER_DIES, ops=(Op(OP_GAIN_XP, n=1),)),
    ),
    # When you play me, gain 1 XP for each friendly unit.
    "Scrutinizing Sergeant": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_GAIN_XP, n=1, n_from_count=CT_MY_UNITS),)),
    ),
    # [Deflect]  When you play me, if an opponent's score is within 3 points of
    # the Victory Score, ready me and gain 3 XP.
    "Poppy - Paragon": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_READY, target=T_SELF, cond=COND_OPP_NEAR_VICTORY),
                     Op(OP_GAIN_XP, n=3, cond=COND_OPP_NEAR_VICTORY))),
    ),
    # When you play a unit, you may pay {1 energy} to gain 1 XP.
    # Spend 3 XP, Exhaust: Ready a unit.
    "Blood Rose": (
        Ability(TR_PLAY_UNIT, optional=True, opt_cost_energy=1,
                ops=(Op(OP_GAIN_XP, n=1),)),
        Ability(TR_ACTIVATED, cost_xp=3, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, locality=LOC_FREE),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # --- Buff ----------------------------------------------------------------
    # When you play another unit, buff me.
    "Cithria of Cloudfield": (
        Ability(TR_PLAY_UNIT, subject_not_self=True,
                ops=(Op(OP_BUFF, target=T_SELF),)),
    ),
    # When you play me, buff up to two other friendly units.
    # Two OPTIONAL slots, the second distinct from the first, so "up to two"
    # includes one and none.
    "Kinkou Monk": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True, optional=True,
                                    locality=LOC_FREE),
                         TargetSpec(who=W_FRIENDLY, not_self=True, optional=True,
                                    distinct_from=0, locality=LOC_FREE)),
                ops=(Op(OP_BUFF, target=0), Op(OP_BUFF, target=1))),
    ),
    # When you play me, buff me. Then, if I am at a battlefield, buff all other
    # friendly units there.
    "Peak Guardian": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_BUFF, target=T_SELF),
                     Op(OP_BUFF_ALL_AT, target=T_HERE, who=W_FRIENDLY,
                        except_target=T_SELF, cond=COND_SELF_AT_BF))),
    ),
    # When you play me, if you control a Poro, buff me and draw 1.
    "Poro Herder": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_BUFF, target=T_SELF, cond=COND_CONTROL_TAG,
                        cond_tag="Poro"),
                     Op(OP_DRAW, n=1, cond=COND_CONTROL_TAG, cond_tag="Poro"))),
    ),
    # When you play me or when I conquer, buff me.
    # Spend my buff: Give me +4 Might this turn.
    "Sett, Brawler": (
        Ability(TR_PLAY_ME, ops=(Op(OP_BUFF, target=T_SELF),)),
        Ability(TR_CONQUER, ops=(Op(OP_BUFF, target=T_SELF),)),
        Ability(TR_ACTIVATED, cost_spend_buff_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=4),)),
    ),
    # When I conquer, you may kill a gear. If you do, buff me.
    "Adaptatron": (
        Ability(TR_CONQUER,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",), optional=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_KILL, target=0),
                     Op(OP_BUFF, target=T_SELF, cond=COND_SLOT_DIED, cond_slot=0))),
    ),
    # When a buffed friendly unit dies, buff another friendly unit.
    "Vanguard Helm": (
        Ability(TR_OTHER_DIES, subject_buffed=True,
                targets=(TargetSpec(who=W_FRIENDLY, locality=LOC_FREE),),
                ops=(Op(OP_BUFF, target=0),)),
    ),

    # When you play a card from [Hidden], give me +2 Might this turn.
    "Ember Monk": (
        Ability(TR_PLAY_FROM_HIDDEN,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # [Assault 2]  When you play me, discard 1.
    "Chemtech Enforcer": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DISCARD, n=1),)),
    ),

    # [Reaction][>] Exhaust: [Add] {1 energy}.
    "Dragonsoul Sage": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True, ops=(Op(OP_ADD_ENERGY, n=1),)),
    ),

    # If you have two or fewer cards in your hand, I enter ready.
    # When I hold, draw 2.
    "Dunebreaker": (
        Ability(TR_HOLD, ops=(Op(OP_DRAW, n=2),)),
    ),

    # When you play me, return all units with 2 Might or less to their owners'
    # hands.
    #
    # Every player's, and EFFECTIVE Might -- a pumped 2-drop survives it, a
    # shrunk one does not. He is 5 Might himself, so he is never caught.
    "Angler Beast": (
        Ability(TR_PLAY_ME, ops=(Op(OP_RETURN_ALL, sweep_max_might=2),)),
    ),

    # When you play me, return another friendly unit and an enemy unit to
    # their owners' hands.
    #
    # Both slots are required, so 355.8 keeps the trigger off the Chain unless
    # BOTH exist -- he will not bounce an enemy on a board where you have no
    # other unit to reset.
    "Beast Below": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                    locality=LOC_FREE),
                         TargetSpec(who=W_ENEMY, locality=LOC_FREE)),
                ops=(Op(OP_RETURN_TO_HAND, target=0),
                     Op(OP_RETURN_TO_HAND, target=1))),
    ),

    # Once each turn, when an enemy unit here dies, channel 1 rune exhausted.
    "Nasus, Guardian of Knowledge": (
        Ability(TR_OTHER_DIES, subject_enemy=True, subject_here=True,
                once_each_turn=True, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # At the start of your Beginning Phase, if you control a facedown card at
    # a battlefield, draw 1.
    "Mushroom Pouch": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_DRAW, n=1, cond=COND_FACEDOWN_AT_BF),)),
    ),

    # [Accelerate] [Assault 2]  When you play me, discard 2.
    "Jinx, Demolitionist": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DISCARD, n=2),)),
    ),

    # When you play me, if you control two or more gear, ready me.
    #
    # Checked on RESOLUTION, as a condition -- the gear count can change in the
    # response window. `floor` is COND_CONTROL_N_GEAR's threshold, and the
    # source is excluded, which costs nothing here: he is a unit, not a gear.
    "Dropboarder": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_READY, target=T_SELF, cond=COND_CONTROL_N_GEAR,
                        floor=2),)),
    ),

    # When I attack, deal damage equal to my Might to an enemy unit here.
    #
    # Both halves are read on execution (359.3.f.2), and the rulebook's own
    # examples use this card: if he is moved back to base in response, "here"
    # no longer holds the target and the trigger mistargets; if he is Stupefied,
    # he deals his CURRENT Might. `same_loc_as_source` is re-checked at
    # resolution and `n_from_might=T_SELF` reads effective Might then.
    "Yasuo - Remorseful": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_DAMAGE, target=0, n_from_might=T_SELF),)),
    ),

    # I enter ready.  Exhaust: Give a unit +3 Might this turn.
    #
    # Entering ready is what makes the Exhaust usable the turn he lands.
    "Arena Kingpin": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, locality=LOC_FREE),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),)),
    ),

    # --- "Use this ability only while I'm at a battlefield" ----------------
    # `use_at_battlefield` gates the offer on the source's location. These are
    # the units whose activated ability is a reason to fight for ground: each
    # is inert at base, which is where a player would otherwise keep them safe.

    # {Fury rune}, Exhaust: Deal 3 to a unit. Use this ability only while I'm
    # at a battlefield.
    "Xerath - Freed": (
        Ability(TR_ACTIVATED, cost_power=1, cost_exhaust=True,
                use_at_battlefield=True,
                targets=(TargetSpec(who=W_ANY, locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n=3),)),
    ),

    # Exhaust: Play two 1 Might Bird unit tokens with [Deflect]. Use this
    # ability only while I'm at a battlefield.
    #
    # The export prints "two {1 energy} Might Bird" -- a rendering glitch for
    # "1 Might", which is what the reminder text and the Bird token (187.7)
    # both say. No location: base or a battlefield you control (FAQ #4020).
    "Ultrasoft Poro": (
        Ability(TR_ACTIVATED, cost_exhaust=True, use_at_battlefield=True,
                targets=(TargetSpec(kind=TK_LOCATION, who=W_FRIENDLY, play_destination=True),),
                ops=(Op(OP_CREATE_TOKEN, target=0, n=2,
                        token=BIRD_TOKEN),)),
    ),

    # {1 energy}{Mind rune}: Draw 1.
    # {4 energy}{Mind rune}{Mind rune}{Mind rune}{Mind rune}, Exhaust: Score 1
    # point.  Use my abilities only while I'm at a battlefield.
    #
    # "MY abilities", plural, so the gate is on both. The draw has no Exhaust
    # and can be used as often as it is paid for; the point costs eight runes
    # and a whole turn standing on contested ground.
    "Renata Glasc - Mastermind": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=1,
                use_at_battlefield=True, ops=(Op(OP_DRAW, n=1),)),
        Ability(TR_ACTIVATED, cost_energy=4, cost_power=4, cost_exhaust=True,
                use_at_battlefield=True, ops=(Op(OP_SCORE, n=1),)),
    ),

    # I must be assigned combat damage last.
    # Exhaust: Deal damage equal to my Might to a unit at a battlefield. Use
    # this ability only while I'm at a battlefield.
    #
    # The first sentence is [Backline]'s reminder printed WITHOUT the keyword
    # (814-style prose), so `keyword_mask` never sees a bracket and the STATICS
    # entry grants it. "Equal to my Might" reads EFFECTIVE Might at resolution
    # through `n_from_might=T_SELF`, so pumping her first raises the damage.
    "Caitlyn - Patrolling": (
        Ability(TR_ACTIVATED, cost_exhaust=True, use_at_battlefield=True,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_DAMAGE, target=0, n_from_might=T_SELF),)),
    ),

    # --- gear that "enters exhausted" (ENTERS_EXHAUSTED) -------------------
    # Each of these is a resource or trick gear whose ability Exhausts, so
    # entering exhausted is a full turn's delay before first use -- the whole
    # point of the sentence. It is read at every play site through
    # `actions._permanent_enters_ready`.

    # This enters exhausted.
    # Kill this, {1 energy}, Exhaust: [Predict 2], then draw 1. Gain 1 XP.
    #
    # The look must be the op's LAST, so "then draw 1. Gain 1 XP." rides a
    # follow-up. Paid by killing itself (204.1.b), so the source is already in
    # the trash while the Predict resolves -- nothing after it reads the gear.
    "Scryer's Bloom": (
        Ability(TR_ACTIVATED, cost_kill_self=True, cost_energy=1,
                cost_exhaust=True,
                ops=(Op(OP_LOOK_TOP, n=2, pick_optional=True, pick_multi=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP,
                        then_key=FU_DRAW_1_XP_1),)),
    ),

    # This enters exhausted.
    # [Empower] -- {1 energy}, Exhaust.
    # [Reaction][>] Exhaust: [Add] {1 energy}. If this is [Empowered], [Add]
    # {2 energy} instead.
    #
    # "Instead" partitions the two amounts -- the Empowered egg adds 2, not
    # 1+2 -- which is why the base op needs COND_NOT_EMPOWERED rather than
    # running unconditionally with a bonus op beside it.
    #
    # Both abilities Exhaust, so the egg cannot Empower and pay out in the same
    # turn: the Empower is an investment that returns one extra Energy per turn
    # from the turn after.
    "Platewyrm Egg": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_ENERGY, n=1, cond=COND_NOT_EMPOWERED),
                     Op(OP_ADD_ENERGY, n=2, cond=COND_EMPOWERED))),
    ),

    # This enters exhausted.
    # [Reaction][>] Exhaust: [Add] {any rune}.
    # [Level 6][>] [Reaction][>] Exhaust: [Add] {1 energy}{any rune}.
    # (Use this ability only while you have 6+ XP.)
    #
    # Two abilities sharing one Exhaust, so at 6 XP they are alternatives and
    # never both -- the Level ability strictly dominates, but the base one is
    # still legal and offering both costs nothing but a duplicate option.
    "Honeyfruit": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=D_ANY),)),
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True, min_xp=6,
                ops=(Op(OP_ADD_ENERGY, n=1),
                     Op(OP_ADD_POWER, n=1, domain=D_ANY))),
    ),

    # This enters exhausted.  Exhaust: Empower another gear.
    #
    # "Another gear" carries no ownership word, so it reaches the opponent's
    # gear as well (targets scope by omission) -- a bad choice, not an illegal
    # one. `not_self` is "another".
    "Hextech Formula": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",),
                                    not_self=True, locality=LOC_FREE),),
                ops=(Op(OP_EMPOWER, target=0),)),
    ),

    # This enters exhausted.  Exhaust: Deal 2 to a unit at a battlefield.
    "Iron Ballista": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True),),
                ops=(Op(OP_DAMAGE, target=0, n=2),)),
    ),

    # --- "Recycle N from your trash" as a COST (3956) ----------------------
    # The recycled cards are "of the instructed player's choice" and not
    # targets, so they are picked one at a time through `pend_cost_recycle`
    # before the ability finalizes. The choice matters more than it looks: a
    # recycle is the one destination that gives a card BACK (416.1.c), and
    # trash-counting and trash-replaying cards read the pile these empty.

    # Recycle 3 from your trash, {1 energy}, Exhaust: Draw 1.
    "Garbage Grabber": (
        Ability(TR_ACTIVATED, cost_recycle_trash=3, cost_energy=1,
                cost_exhaust=True, ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Ganking]  Recycle 1 from your trash: Give me +1 Might this turn.
    #
    # No Exhaust, so this is the repeatable one: the trash is the only limit,
    # and each activation is a separate Chain Item the opponent can answer.
    "Vi, Destructive": (
        Ability(TR_ACTIVATED, cost_recycle_trash=1,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # {1 energy}{Fury rune}, Recycle a unit from your trash, Exhaust:
    # Play a 3 Might Mech unit token to your base.
    #
    # "a UNIT" is what `cost_recycle_type` is for -- a trash full of spells
    # cannot pay it, and the offer gate counts only units.
    "Assembly Rig": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=1,
                cost_recycle_trash=1, cost_recycle_type="Unit",
                cost_exhaust=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=MECH_TOKEN),)),
    ),

    # --- [Empower] spent as a COST (441.2) ---------------------------------
    # "Disempower this, Exhaust: [Effect]". The status is the fuel, so these
    # are a CYCLE and not an engine: each use costs the Empower, which has to
    # be bought back through the [Empower] ability before the payoff is
    # available again. `cost_disempower_self` is what makes the action layer
    # withhold the ability until the status is actually held.

    # [Empower] -- Exhaust.  Disempower this, {1 energy}, Exhaust: Draw 1.
    #
    # Both halves Exhaust, and a permanent can only be exhausted once -- so the
    # Empower and the draw cannot happen on the same turn. That readying gap is
    # the card's whole rate limit, and it falls out of `cost_exhaust` rather
    # than needing a once-per-turn stamp.
    "Questionable Tome": (
        Ability(TR_ACTIVATED, cost_exhaust=True, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_disempower_self=True, cost_energy=1,
                cost_exhaust=True, ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Empower] -- Exhaust.
    # Disempower this, {1 energy}, Exhaust: Play a 3 Might Mech unit token to
    # your base.
    "Hextech Disc": (
        Ability(TR_ACTIVATED, cost_exhaust=True, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_disempower_self=True, cost_energy=1,
                cost_exhaust=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=MECH_TOKEN),)),
    ),

    # [Empower] {6 energy}{Chaos rune}{Chaos rune}
    # When I become [Empowered], choose an opponent. They [Burn 3]. Then you
    # may do this: Choose a unit in their trash and play it, ignoring its cost.
    #
    # **The ordering is the whole card**, and it is why `OP_DIG_TRASH` had to
    # exist. The trash he digs in is the one HIS OWN BURN just filled, so the
    # choice cannot be a target slot: 355.8 fixes every target at finalization,
    # which is before any of this resolves. A slot would read the pile as it
    # stood before the Burn, and would refuse the whole ability against an
    # opponent whose trash happened to be empty -- exactly the opponent Kharox
    # is best against.
    #
    # "Choose an opponent" is not a target either (355.10): a two-player game
    # has one, so `who=W_ENEMY` names the side and no choice is announced.
    #
    # The Burn is theirs and the dig is yours, which is the other thing the two
    # `who` fields are saying: `OP_BURN`'s W_ENEMY mills THEM, `OP_DIG_TRASH`'s
    # W_ENEMY reads THEIR pile while the unit arrives under YOUR control.
    "Kharox": (
        Ability(TR_ACTIVATED, cost_energy=6, cost_power=2,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_BECOME_EMPOWERED, subject_is_self=True,
                ops=(Op(OP_BURN, n=3, who=W_ENEMY),
                     Op(OP_DIG_TRASH, who=W_ENEMY))),
    ),

    # [Empower] {2 energy}{Chaos rune}
    # When I become [Empowered], you may choose a unit in your trash with
    # Energy cost no more than {3 energy} and Power cost no more than
    # {any rune}. Play it to your base, ignoring its cost.
    #
    # Spectral Matron's effect on a different trigger, which is the point of
    # `TR_BECOME_EMPOWERED` being a trigger rather than a special case: the
    # Empower is what fires it, and everything after that is machinery the
    # engine already had.
    #
    # **To BASE, not to a chosen location.** The card names the destination, so
    # unlike Spectral Matron there is no location slot -- `T_MY_BASE` says it.
    "Tail-Cloaked Matriarch": (
        Ability(TR_ACTIVATED, cost_energy=2, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_BECOME_EMPOWERED, subject_is_self=True, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Unit",),
                                    max_energy=3, max_power=1, playable=True,
                                    playable_cost=COST_FREE),),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0,
                        target_b=T_MY_BASE, cost=COST_FREE),)),
    ),

    # [Empower] {2 energy}
    # When I become [Empowered], [Predict 2].
    # [Empowered][>] I have +1 Might.
    #
    # 436.1.a -- Predict at N=2: look at the top 2, recycle ANY NUMBER of them,
    # put the rest back on top. `pick_multi` is what "any number" needs; the
    # first transcription used a single optional pick, which capped the recycle
    # at one card and made it a different, weaker card.
    "Apprentice Mage": (
        Ability(TR_ACTIVATED, cost_energy=2, ops=(Op(OP_EMPOWER),)),
        Ability(TR_BECOME_EMPOWERED, subject_is_self=True,
                ops=(Op(OP_LOOK_TOP, n=2, pick_optional=True, pick_multi=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP),)),
    ),

    # [Deathknell][>] [Predict 2].
    "Dramatic Visionary": (
        Ability(TR_DEATH,
                ops=(Op(OP_LOOK_TOP, n=2, pick_optional=True, pick_multi=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP),)),
    ),

    "Spectral Matron": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                                    max_energy=3, max_power=1, playable=True,
                                    playable_cost=COST_FREE),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_FREE),)),
    ),

    # [Deathknell] You may play a unit with cost no more than {3 energy} and no
    # more than {any rune} from your trash, ignoring its cost.
    #
    # Spectral Matron's ability on a death trigger instead of an entry one, so
    # it pays off trading her away -- and by then the trash is fuller.
    "Glasc Mixologist": (
        Ability(TR_DEATH, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY, card_type=("Unit",),
                                    max_energy=3, max_power=1, playable=True,
                                    playable_cost=COST_FREE),
                         TargetSpec(kind=TK_LOCATION, play_destination=True,
                                    locality=LOC_FREE)),
                ops=(Op(OP_PLAY_UNIT_FROM_TRASH, target=0, target_b=1,
                        cost=COST_FREE),)),
    ),

    # When I hold, you may return a unit or gear from your trash to your hand.
    # A Hold trigger, so it pays off a battlefield that survived the opponent's
    # whole turn -- and "unit or gear" is why `card_type` is a tuple.
    "Guardian of the Passage": (
        Ability(TR_HOLD, optional=True,
                targets=(TargetSpec(kind=TK_TRASH_CARD, who=W_FRIENDLY,
                                    card_type=("Unit", "Gear")),),
                ops=(Op(OP_TRASH_TO_HAND, target=0),)),
    ),

    # When you play me, play a ready 3 Might Sprite unit token with [Temporary]
    # here.  "here" is my location -- not a choice, so not a target slot.
    "Sprite Mother": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # When you play me, play a 1 Might Recruit unit token here.
    "Faithful Manufactor": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=RECRUIT_TOKEN),)),
    ),

    # When you play me, play a 2 Might Sand Soldier unit token here.
    "Royal Guard": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SAND_SOLDIER_TOKEN),)),
    ),

    # [Deathknell] Play a 1 Might Bird unit token with [Deflect] to your base.
    # T_MY_BASE, not T_HERE: 808.1 fires the Deathknell as I die, and "your
    # base" is the controller's, which is where the token goes however far
    # forward I died. The Bird card carries [Deflect] itself.
    "Carrion Dredger": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=BIRD_TOKEN),)),
    ),

    # When you play me, deal 6 to an enemy unit at a battlefield.
    "Riptide Rex": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True),),
                ops=(Op(OP_DAMAGE, target=0, n=6),)),
    ),

    # When you play me, ready another unit.
    # "another" excludes me, which `REL_DIFFERENT` cannot express -- the
    # relation is to the SOURCE, not to an earlier slot -- so the slot carries
    # `not_self` and `_matches` checks it against the ability's source.
    "First Mate": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, not_self=True),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # [Accelerate] When I move from a location, play a 3 Might Sprite unit
    # token with [Temporary] there.
    #
    # "there" is the location she LEFT, and by the time this resolves she is
    # somewhere else -- so it cannot be read off her row and must come from
    # `ctx`, captured when the trigger fired (359.3.f.3). No "ready": unlike
    # Sprite Mother's token this one enters exhausted.
    "Lillia - Fae Fawn": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, target=T_CTX, n=1,
                        token=SPRITE_TOKEN),)),
    ),

    # [Accelerate] When you play me, give enemy units -3 Might this turn, to a
    # minimum of 1 Might.
    #
    # "enemy units" with no count and no choice: not targets (355.10), so no
    # slot and no restriction -- it simply applies to all of them.
    "Thousand-Tailed Watcher": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_MODIFY_MIGHT_ALL, n=-3, floor=1, who=W_ENEMY),)),
    ),

    # [Shield] When I hold, play a ready 3 Might Sprite unit token with
    # [Temporary] here.
    "Trevor Snoozebottom": (
        Ability(TR_HOLD,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # When you play a spell, give me +1 Might this turn.
    # "me" is the source, which is not a target -- hence T_SELF.
    "Ravenbloom Student": (
        Ability(TR_PLAY_SPELL,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # [Accelerate] When I conquer, draw 1.
    "Kai'Sa, Survivor": (
        Ability(TR_CONQUER, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When I move, draw 1.
    "Stellacorn Herder": (
        Ability(TR_MOVE, ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Deathknell][>] Play a 1 Might Bird unit token with [Deflect] to your base.
    "Carrion Dredger": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, n=1, token=BIRD_TOKEN),)),
    ),

    # When you play me, play a 1 Might Bird unit token with [Deflect] here.
    "Frisky Hunter": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=BIRD_TOKEN),)),
    ),

    # [Deathknell] - Play two 3 Might Mech unit tokens to your base.
    # Unblocked by the rule-187 token supplement; target -1 defaults to the
    # controller's base, which is what the card says.
    "Ferrous Forerunner": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, n=2, token=MECH_TOKEN),)),
    ),

    # When you play me, buff another friendly unit.
    "Pit Rookie": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True),),
                ops=(Op(OP_BUFF, target=0),)),
    ),

    # [Legion] - When you play me, buff me.  [Legion] is unread, so this is
    # listed but will not count as printed until the keyword lands.
    "Trifarian Gloryseeker": (
        Ability(TR_PLAY_ME, ops=(Op(OP_BUFF, target=T_SELF),)),
    ),

    # [Backline] When I hold, [Buff] all units here.
    # "all units here" is untargeted and hits both sides.
    "Enthusiastic Promoter": (
        Ability(TR_HOLD, ops=(Op(OP_BUFF_ALL_AT, target=T_HERE),)),
    ),

    # When a friendly unit attacks or defends alone, give it +1 Might this turn.
    #
    # **The first trigger that fires for a permanent other than its own
    # source.** Every trigger before this one was about itself -- "when I die",
    # "when I conquer" -- so C_SRC did both jobs. This gear sits at a base and
    # watches a battlefield, so the ability's source and its subject are
    # different permanents: T_SELF is the Mask, T_SUBJECT is the unit that
    # attacked, and "give IT +1" means the latter.
    #
    # A TRIGGER, not a static, and the card is worded to say so. Master Yi -
    # Wuju Bladesman's "WHILE a friendly unit defends alone, it gets +2" is a
    # static that evaporates the moment a second unit arrives; this one gives
    # +1 "this turn", so it is banked at the moment of the attack and survives
    # reinforcements, the end of the Combat, and the unit walking home.
    #
    # 740.2.a defines alone as "no other friendly units at the same location",
    # checked when the Combat begins -- part of the trigger condition, so a
    # unit that is not alone never triggers at all.
    "Mask of Foresight": (
        Ability(TR_ATTACK_OR_DEFEND, subject_alone=True,
                subject_any_friendly=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SUBJECT, n=1),)),
    ),

    # When I move, discard 1, then draw 1.
    # The mirror of Undercover Agent's "discard 2, then draw 2", and the same
    # reason the order is written down: discarding first means the card drawn
    # was never a candidate to be discarded.
    "Traveling Merchant": (
        Ability(TR_MOVE,
                ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=1))),
    ),

    # When you play me OR when I hold, look at the top 4 cards of your Main
    # Deck. You may reveal a gear from among them and draw it. Then recycle the
    # rest.
    # "or when I hold" is two triggers on one effect, which is two Ability
    # entries -- the DSL has no disjunction and does not need one. `pick_types`
    # is the "a GEAR from among them" restriction; "you may" makes it optional,
    # which it has to be anyway since four cards need contain no gear at all.
    "Ornn - Blacksmith": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_PICK, n=4, pick_optional=True,
                        pick_types=("Gear",),
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),)),
        Ability(TR_HOLD,
                ops=(Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_PICK, n=4, pick_optional=True,
                        pick_types=("Gear",),
                        pick_dest=DEST_HAND, rest_dest=DEST_RECYCLE),)),
    ),

    # When you play me, deal 3 to all units at battlefields.
    # `at_battlefields` is the plural clause the card actually prints -- every
    # battlefield, sparing only what sits in a base. Untargeted (355.10), and
    # unscoped by `who`, so it hits my own units too.
    "Tibbers": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DAMAGE_ALL, n=3, at_battlefields=True),)),
    ),

    # When you play me, stun a unit.
    "Solari Shieldbearer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_STUN, target=0),)),
    ),

    # [Hidden] When you play me, give me +3 Might this turn.
    "Teemo - Scout": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=3),)),
    ),

    # When I attack, ready another friendly unit.
    # `not_self` is "another": I am attacking, so I am a friendly unit at this
    # location and would otherwise be a legal choice for my own ability.
    "Twilight Reveler": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True),),
                ops=(Op(OP_READY, target=0),)),
    ),

    # {1 energy}, Exhaust: Move a friendly unit at a battlefield to your base.
    # T_MY_BASE, not T_OWNER_BASE: the card says "YOUR base" and the slot is
    # friendly anyway, so the two agree here -- but the words are what is
    # transcribed, and a later card saying "its base" needs the other one.
    # {1 energy}, Exhaust: Move a friendly unit at a battlefield to its base.
    #
    # **"ITS base", not "your base"** -- the errata wording; the printed text
    # says "your base". Rule 5031 fixes what "its base" means: a unit is
    # recalled to its CONTROLLER's base, which is what T_OWNER_BASE reads
    # (despite the name -- see `resolve.py`'s OP_MOVE_TO). The slot is
    # W_FRIENDLY, so the chosen unit's controller is always the caster and the
    # two sentinels agree for this card under any board state; the errata
    # changes the wording, not the behaviour.
    "The Syren": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # [Deathknell] Discard 2, then draw 2.
    # Order matters and "then" is what fixes it: the discard happens first, so
    # the cards drawn are never candidates to be discarded.
    "Undercover Agent": (
        Ability(TR_DEATH,
                ops=(Op(OP_DISCARD, n=2), Op(OP_DRAW, n=2))),
    ),

    # When you play me, kill an enemy unit with 3 Might or less.
    # A RESTRICTION, not a condition (355.9.b): a 4-Might unit was never a
    # legal choice, so growing one in response does not make this fizzle -- it
    # was never pointed there. Contrast "kill a unit IF it has 3 or less".
    "Sandshifter": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, max_might=3),),
                ops=(Op(OP_KILL, target=0),)),
    ),

    # [Deathknell] Deal 4 to an enemy unit.
    # No location clause, so it reaches across the board from wherever I died.
    "Ruined Rex": (
        Ability(TR_DEATH,
                targets=(TargetSpec(who=W_ENEMY),),
                ops=(Op(OP_DAMAGE, target=0, n=4),)),
    ),

    # Exhaust: Give a unit -1 Might this turn, to a minimum of 1 Might.
    # A gear, so 151.2 restricts the ability to its controller's Main Phase in
    # an Open State -- which is what SPEED_MAIN already means.
    "Orb of Regret": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-1, floor=1),)),
    ),

    # When you play me, kill an enemy unit.
    "Harnessed Dragon": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY),),
                ops=(Op(OP_KILL, target=0),)),
    ),

    # When I conquer, give a friendly unit +8 Might this turn.
    "Inviolus Vox": (
        Ability(TR_CONQUER,
                targets=(TargetSpec(who=W_FRIENDLY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=8),)),
    ),

    # --- [Empower] (827) ---------------------------------------------------
    # 827.1.c.1 -- "[Cost]: Empower this. Play only if not Empowered." The
    # "only if not Empowered" half is NOT written on each card: the action
    # layer reads it off OP_EMPOWER, because it is part of what the keyword
    # abbreviates rather than something these cards each chose to print.
    # The payoff is a STATIC gated on COND_EMPOWERED -- see STATICS below.

    # [Empower] {2 energy}. [Empowered] I have +1 Might and [Deflect 2].
    "Solari Sunhawk": (
        Ability(TR_ACTIVATED, cost_energy=2, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {3 energy}. [Empowered] I have +2 Might and [Ganking].
    "Brutal Hunter": (
        Ability(TR_ACTIVATED, cost_energy=3, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {2 energy}{Fury rune}. [Empowered] I have [Assault 3].
    "Shadow Fiend": (
        Ability(TR_ACTIVATED, cost_energy=2, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {1 energy}{Order rune}.
    # [Empowered] [Deathknell] Play two 1 Might Recruit unit tokens to your
    # base. ("When I die while Empowered, get the effect.")
    # A dependent ability that is itself a TRIGGER (828.1.d), so the gate rides
    # on the OP rather than on a static -- and it is checked against the corpse:
    # by the time a Deathknell resolves the source is dead, and the status it
    # held when it died is what the card asked about.
    "Noxian Emissary": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=2,
                        token=RECRUIT_TOKEN, cond=COND_EMPOWERED),)),
    ),

    # [Deflect] [Empower] {7 energy}. [Empowered] I have +7 Might.
    # The largest single static in the pool, and the cost says so.
    "Steel Paws": (
        Ability(TR_ACTIVATED, cost_energy=7, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {2 energy}. [Empowered] I have +1 Might and [Ganking].
    "Kinkou Lifeblade": (
        Ability(TR_ACTIVATED, cost_energy=2, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {3 energy}. [Empowered] I have [Deflect] and [Shield 3].
    "Serene Ascetic": (
        Ability(TR_ACTIVATED, cost_energy=3, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {1 energy}{any rune}{any rune}. [Empowered] I have +2 Might.
    # [Empowered] [Deathknell] Channel 2 runes exhausted.
    # Two rune symbols is cost_power=2 -- "{any rune}" is one Power of any
    # domain, and `plan_ability_cost` reads the count, not the symbol.
    "Baccai Witherclaw": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=2,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_DEATH,
                ops=(Op(OP_CHANNEL, n=2, cond=COND_EMPOWERED),)),
    ),

    # [Empower] {3 energy}. [Empowered] When I move, draw 1.
    # A dependent ability that is a TRIGGER (828.1.d), so the gate rides on
    # the op: he moves either way and the draw is what the status buys.
    "Covert Informant": (
        Ability(TR_ACTIVATED, cost_energy=3, ops=(Op(OP_EMPOWER),)),
        Ability(TR_MOVE, ops=(Op(OP_DRAW, n=1, cond=COND_EMPOWERED),)),
    ),

    # [Deflect 2] [Empower] {8 energy}. [Empowered] When I conquer, you score
    # 1 point.  Eight Energy for a second point per Conquer -- and 471.1.b
    # still applies to the Conquer that carries it, not to this.
    "Nasus, Ascended": (
        Ability(TR_ACTIVATED, cost_energy=8, ops=(Op(OP_EMPOWER),)),
        Ability(TR_CONQUER, ops=(Op(OP_SCORE, n=1, cond=COND_EMPOWERED),)),
    ),

    # [Empower] - {1 energy} OR {Body rune}. [Empowered] I have +1 Might.
    #
    # **"Pay either cost" is two activated abilities, not one with a choice.**
    # 827.1.c.1 expands [Empower Cost] into "[Cost]: Empower this", and a card
    # printing two costs expands into two of those. The action layer already
    # offers each activated ability separately and prices each on its own, so
    # the player picks by picking which to activate -- and a seat that can
    # afford only one is offered only that one, which a single ability with an
    # internal choice would have got wrong.
    "Legion Marauder": (
        Ability(TR_ACTIVATED, cost_energy=1, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_power=1, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {6 energy}{Fury rune}. Your units have +1 Might. If I'm
    # [Empowered], they have +2 Might INSTEAD.
    #
    # "Instead" is expressed as a second static that ADDS, which is the same
    # number by a different route: +1 always, +1 more while Empowered, so the
    # board reads +2 and never +3. Writing it as a replacement would need the
    # static layer to know that one entry supersedes another, which nothing
    # else in the pool asks for.
    "Rage Amplifier": (
        Ability(TR_ACTIVATED, cost_energy=6, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {2 energy}. Exhaust: Give a unit +2 Might this turn. If this
    # is [Empowered], give that unit +4 Might this turn INSTEAD.
    #
    # The same "instead" arithmetic, on ops rather than statics: +2, then +2
    # more while Empowered. Both point at the one slot, so the unit that was
    # chosen is the unit that grows.
    "Tools of Empire": (
        Ability(TR_ACTIVATED, cost_energy=2, ops=(Op(OP_EMPOWER),)),
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),
                     Op(OP_MODIFY_MIGHT, target=0, n=2,
                        cond=COND_EMPOWERED))),
    ),

    # [Empower] {3 energy}{Order rune}. [Empowered] Your units that are
    # [Empowered] have +2 Might (including me).
    "Aurok General": (
        Ability(TR_ACTIVATED, cost_energy=3, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {1 energy}{Order rune}{Order rune}.
    # [Empowered] I have [Assault 2].
    # [Empowered] When I attack, kill an enemy unit here with LESS MIGHT THAN
    # ME.  The second dependent ability, which was missing: the [Assault 2]
    # static was transcribed and this was not, so the card was on the board
    # doing half of what it prints.
    "Ambessa, Respected and Feared": (
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=2,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True,
                                    less_might_than_source=True),),
                ops=(Op(OP_KILL, target=0, cond=COND_EMPOWERED),)),
    ),

    # [Deathknell] Channel 1 rune exhausted.
    "Soaring Scout": (
        Ability(TR_DEATH, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # [Accelerate] [Deathknell] Channel 2 runes exhausted and draw 1.
    # The draw is unconditional here -- contrast Catalyst of Aeons, where it is
    # a consolation for coming up short.
    "Tasty Faefolk": (
        Ability(TR_DEATH, ops=(Op(OP_CHANNEL, n=2), Op(OP_DRAW, n=1))),
    ),

    # [Tank] When you play me, channel 1 rune exhausted.
    "Stormclaw Ursine": (
        Ability(TR_PLAY_ME, ops=(Op(OP_CHANNEL, n=1),)),
    ),

    # [Hidden] The next time a friendly unit would die, kill this instead.
    # Recall that unit exhausted.
    # A delayed replacement, registered as the gear resolves (337.2 puts a gear
    # on the board immediately) and consumed by the next friendly death.
    # No heal: Guardian Angel's effect text says "Heal me" where this one does
    # not (136.2.d), so a unit recalled with lethal damage still marked dies
    # again on the next continuous check. That is the card -- it answers
    # targeted removal, not damage.
    "Zhonya's Hourglass": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DEATH_GUARD),)),
    ),

    # [Vision] When I conquer, if you've played a non-token unit, a non-token
    # gear, and a spell this turn, you score 1 point.
    # [Vision] is synthesised from the keyword, so only the conquer clause is
    # written here. The trio is a CONDITION checked at resolution, not a
    # restriction: it can be satisfied (or not) after the trigger fires.
    "Swain, Visionary": (
        Ability(TR_CONQUER,
                ops=(Op(OP_SCORE, n=1, cond=COND_PLAYED_TRIO),)),
    ),

    # [Deflect] When an opponent plays a unit while I'm at a battlefield,
    # [Stun] it. They can't move it this turn.
    # `subject_enemy` flips TR_PLAY_UNIT to watch the OTHER seat, and the
    # subject is the permanent just played -- not a target, so the opponent
    # gets no say and [Deflect] never enters into it.
    #
    # "while I'm at a battlefield" is a condition on Vex, not on the unit
    # played: a Vex sitting in a base watches nothing.
    "Vex - Apathetic": (
        Ability(TR_PLAY_UNIT, subject_enemy=True, subject_at_battlefield=True,
                ops=(Op(OP_STUN, target=T_SUBJECT),
                     Op(OP_NO_MOVE, target=T_SUBJECT))),
    ),

    # When I move, draw 1, then discard 1. Then, do the following based on the
    # discarded card's type: Spell - Draw 1. Gear - Ready up to 2 runes.
    # Unit - Give me +3 Might this turn.
    #
    # The discard is a real CHOICE and that is the whole card: which card you
    # pitch is how you pick the mode. `phases.discard`'s take-the-oldest rule
    # would have chosen the mode for the player.
    "Hwei - Brooding Painter": (
        Ability(TR_MOVE,
                ops=(Op(OP_DRAW, n=1),
                     Op(OP_DISCARD_CHOOSE, branch_key=DB_HWEI))),
    ),

    # [Accelerate] [Deathknell] Recycle me to ready your runes.
    # "Recycle me" is a cost WITHIN the instructions (383.3.b) but not an
    # optional one -- the card does not say "you may" -- so it is simply the
    # first op. By the time a Deathknell resolves the card is already in the
    # trash (808.1.d.2), which is where the recycle takes it from.
    #
    # "your runes", unbounded: every spent rune readies, which is what makes
    # this a whole extra turn's worth of resources.
    "Ekko - Recurrent": (
        Ability(TR_DEATH,
                ops=(Op(OP_RECYCLE_SELF),
                     Op(OP_READY_RUNES, n=MAX_DECK))),
    ),

    # When you play me, discard 1, then draw 1.
    # "discard 1" with no choice of card, unlike Hwei -- so this is
    # `phases.discard`'s take-the-oldest rule, which is what the card means
    # when it names no chooser. Discard first: the drawn card is never a
    # candidate to be pitched.
    "Evershade Stalker": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DISCARD, n=1), Op(OP_DRAW, n=1))),
    ),

    # [Vision] [Action] Kill this, Exhaust: Give a unit +2 Might this turn.
    # Two costs at once (204.1.b), and [Vision] is synthesised from the
    # keyword, so only the activated ability is written here.
    "Divining Shells": (
        Ability(TR_ACTIVATED, speed=SPEED_ACTION, cost_exhaust=True,
                cost_kill_self=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=2),)),
    ),

    # [Accelerate] When I move, if you control 4 or fewer runes, draw 1.
    # A CONDITION checked at resolution, not a restriction: the move has
    # already happened and the rune board can change in the response window.
    "Eclipse Dragon": (
        Ability(TR_MOVE,
                ops=(Op(OP_DRAW, n=1, cond=COND_FEW_RUNES, level=4),)),
    ),

    # [Deathknell] If I didn't die alone, draw 1.
    # The mirror of Lonely Poro, reading the same F_DIED_ALONE snapshot the
    # other way round. Past tense either way: recorded at the moment of death,
    # because a priority window sits between dying and the ability resolving.
    "Loyal Poro": (
        Ability(TR_DEATH,
                ops=(Op(OP_DRAW, n=1, cond=COND_NOT_DIED_ALONE),)),
    ),

    # When I move FROM a battlefield, give me +2 Might this turn.
    # TR_MOVE's captured `ctx` is the location left behind, so this asks about
    # where the unit came from and not where it is now -- a unit walking home
    # to its base qualifies, one leaving its base does not.
    "Harpoon Squad": (
        Ability(TR_MOVE,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_CTX_BATTLEFIELD),)),
    ),

    # [Hidden] When you play me TO A BATTLEFIELD, deal 2 to an enemy unit here.
    # [Hidden] is what makes the condition reachable: a unit played from hand
    # normally lands at a base, and 811.1.d.3 puts a hidden one at the
    # battlefield it was hidden at.
    # [Tank] When you play me to a battlefield, you may move an enemy unit to
    # here.  When I hold, return me to my owner's hand.
    #
    # [Tank] is `combat._tiers` and needs nothing here.
    #
    # The play trigger is narrowed with `at_battlefield` rather than gated with
    # `COND_SELF_AT_BF` -- the difference matters precisely because this one
    # says "you MAY". Marai's is not optional, so firing and fizzling on a base
    # play costs nothing; this one would open a "you may" the player cannot act
    # on. 359.3.f makes it a trigger question either way.
    #
    # The target is LOC_FREE: the enemy unit is dragged from wherever it
    # stands, which is the whole card. `T_HERE` is where Blitzcrank landed.
    #
    # "When I hold" returning him to hand is a real drawback, not an upside --
    # 469 Scores the battlefield and then he leaves it, so he cannot hold the
    # same ground twice without being replayed.
    "Blitzcrank - Impassive": (
        Ability(TR_PLAY_ME, optional=True, at_battlefield=True,
                targets=(TargetSpec(who=W_ENEMY, locality=LOC_FREE),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_HERE),)),
        Ability(TR_HOLD, ops=(Op(OP_RETURN_TO_HAND, target=T_SELF),)),
    ),

    "Mischievous Marai": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_DAMAGE, target=0, n=2, cond=COND_SELF_AT_BF),)),
    ),

    # When I move to a battlefield, play a 1 Might Recruit unit token here.
    # "to a battlefield" gates on where I landed; "here" is that same place.
    "Noxian Drummer": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=1,
                        token=RECRUIT_TOKEN, cond=COND_SELF_AT_BF),)),
    ),

    # When I move to a battlefield, give ANOTHER friendly unit +1 Might this
    # turn.  `not_self` is the "another": I am a friendly unit too.
    "Ribbon Dancer": (
        Ability(TR_MOVE,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=1,
                        cond=COND_SELF_AT_BF),)),
    ),

    # [Accelerate] When I attack, if you control 4 or fewer runes, deal 2 to
    # all enemy units here.  Three pieces that already existed: the attack-only
    # role, the rune-board count, and a sweep scoped to one location and side.
    "Renekton, Rage Fueled": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_DAMAGE_ALL, at=T_HERE, n=2, who=W_ENEMY,
                        cond=COND_FEW_RUNES, level=4),)),
    ),

    # When you play ANOTHER unit, give me +2 Might this turn.
    # `subject_not_self` is the "another": without it this would grow by 2 the
    # moment it arrived, off its own play.
    "Reluctant Leader": (
        Ability(TR_PLAY_UNIT, subject_not_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # When you play me, draw 1.
    # [Deathknell] Choose an opponent. They reveal their hand. You can look at
    # their facedown cards this turn. Gain 1 XP.
    #
    # The first card whose payload is PURE INFORMATION -- nothing moves, no
    # choice is carried, and its whole value is what the policy can see
    # afterwards. "Choose an opponent" is not a choice in a two-player game
    # (there is one), so it is resolved rather than offered, the same way
    # Sabotage does it. The 0-Might reminder needs no entry: 469/470 never
    # asked about Might, so a 0-Might unit already conquers and holds.
    # When you play me, choose an opponent. They reveal their hand. Choose a
    # card from it, and they discard that card.
    #
    # Sabotage's op with two differences, and both are in the op's parameters
    # rather than in new machinery: no `pick_types` at all -- "a card" is
    # unrestricted, and an empty filter is what `legal_actions` reads as "any"
    # -- and `DEST_TRASH`, because this DISCARDS where Sabotage recycles.
    #
    # "Choose an opponent" is not a target slot: at two seats it is forced, so
    # offering it would be a decision with one option. `OP_REVEAL_HAND` takes
    # `1 - seat` for the same reason Sabotage does.
    #
    # Last op on the ability, like every pick-from-a-zone effect: the choice is
    # made DURING resolution against a zone rather than the board (355.10), so
    # it suspends, and anything written after it would run before the answer.
    # When this leaves the board, draw 1 and channel 1 rune exhausted.
    # {Chaos rune}, Exhaust: Kill this.
    #
    # A Gear, so it enters ready (359.2.d) and can pay its own Exhaust the turn
    # it lands. The two halves are built to combine: the activated ability is
    # how you cash the gear in on your own terms, and the trigger is why the
    # opponent removing it is not a clean answer.
    #
    # `TR_LEAVES_BOARD` rather than `TR_DEATH` is the whole card. A Deathknell
    # is denied by a Banish (427.2.a) and by a bounce; "leaves the board" is
    # denied by neither, so all three paths queue it -- see
    # `combat.queue_leaves_board`.
    #
    # `cost_power=1` is the {Chaos rune}: an ability's Power is paid in its
    # SOURCE's domains (`cost.plan_ability_cost`), and this card is mono-Chaos,
    # so the symbol and the count say the same thing.
    # [Empower] {3 energy}{Body rune}
    # [Empowered][>] I have +3 Might and can't be dealt damage unless I'm in
    # combat.
    #
    # The Empower half is pure transcription: 827.1.c.1's "use only if not
    # Empowered" is read off `OP_EMPOWER` in `actions.legal_actions` rather
    # than written on each of the ~35 cards that print it, and the {Body rune}
    # is `cost_power=1` paid in her own domain.
    #
    # The dependent half is two statics rather than one, because 828.1.b.1
    # makes the whole clause the Empowered Ability and its two halves are
    # different KINDS of continuous effect -- a Might bonus and a damage
    # prevention. Both carry `cond=COND_EMPOWERED`, which is what ties them to
    # the status (828.1.c) rather than to the card.
    "Ambessa, The Wolf": (
        Ability(TR_ACTIVATED, cost_energy=3, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {3 energy}
    # [Empowered][>] Your spells cost {1 energy}{any rune} less, to a minimum
    # of {1 energy}.
    "Applied Researchers": (
        Ability(TR_ACTIVATED, cost_energy=3, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] {4 energy}{Calm rune} -- see STATICS for the tax it turns on.
    "Helm of Suppression": (
        Ability(TR_ACTIVATED, cost_energy=4, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
    ),

    # When a combat that I was in ends, empower me.
    # [Empowered][>] I have +2 Might.
    #
    # A COMBAT, not a Showdown: 344.2 opens a Non-Combat Showdown that ends the
    # same way and must not pay this out, which is why the trigger is gated on
    # `showdown_combat` rather than on the showdown closing.
    #
    # "That I was in" is read as still being at the battlefield when it ends --
    # a unit that died in the combat is not there to be Empowered, and
    # `OP_EMPOWER` would no-op on it anyway (it checks P_ALIVE).
    #
    # Unlike every other Empower in the pool this one is free and automatic, so
    # there is no 827.1.c.1 "use only if not Empowered" gate to apply: 441.1.b
    # makes re-Empowering a no-op, which setting a flag already is, and the
    # card's own reminder text says exactly that.
    "Mournful Witness": (
        Ability(TR_COMBAT_ENDS, ops=(Op(OP_EMPOWER),)),
    ),

    # When you play me, give your OTHER units +2 Might this turn.
    # As I'm revealed from your deck, [Add] {2 energy}.
    #
    # "Other" is `except_target=T_SELF` on the sweep, not a separate op: 355.10
    # makes this untargeted, so there is no slot to exclude him from and the
    # exclusion has to ride on the sweep itself.
    #
    # The second clause fires from the LOOK BUFFER, where he is off the deck
    # and in no zone at all. `immediate` is what makes that expressible -- a
    # resource add resolves without touching the Chain (337.2), which is the
    # only way an ability can resolve for a card that has no source to put
    # there. `resolve.OP_LOOK_TOP` asserts that, so a future card printing a
    # non-immediate reveal ability fails loudly instead of silently doing
    # nothing.
    # When you play me, opponents can't play cards this turn.
    #
    # `OP_NO_CARDS` and not `OP_NO_SPELLS`: Lilting Lullaby's lock is on
    # spells, and 337.2 leaves units off the Chain entirely, so a spell lock
    # never touched them. "Cards" reaches everything a player can play --
    # units, gear, a Flow spell out of the trash, a card played back from face
    # down -- but still not HIDING, which 811.1.c.1 says is not a Play.
    #
    # Untargeted (355.10): it names "opponents" as a side, announces no count
    # and offers no choice. `who=W_ENEMY` says which side rather than a slot.
    "Brynhir Thundersong": (
        Ability(TR_PLAY_ME, ops=(Op(OP_NO_CARDS, who=W_ENEMY),)),
    ),

    # [Empower] {5 energy}{Body rune}
    # [Empowered][>] When I attack or defend, choose a unit here. Increase my
    # Might to its Might this turn, then give me +1 Might this turn.
    #
    # She fights the biggest thing in the room at its own size plus one. The
    # target is "a unit HERE", either player's -- your own largest unit is as
    # good a yardstick as the enemy's. "INCREASE my Might to its Might" only
    # raises (`OP_MIGHT_UP_TO`): choosing something smaller changes nothing
    # before the +1, it does not shrink her.
    "Dame the Despoiler": (
        Ability(TR_ACTIVATED, cost_energy=5, cost_power=1,
                ops=(Op(OP_EMPOWER),)),
        Ability(TR_ATTACK_OR_DEFEND, while_empowered=True,
                targets=(TargetSpec(who=W_ANY, same_loc_as_source=True,
                                    not_self=True),),
                ops=(Op(OP_MIGHT_UP_TO, target=0),
                     Op(OP_MODIFY_MIGHT, target=T_SELF, n=1))),
    ),

    # --- "win a combat" (466.3.a/c) ----------------------------------------
    # Fired by `combat.queue_win_combat` for each of the winner's units still
    # at the battlefield. A unit that died in the exchange inherited nothing.

    # [Ambush]  When I win a combat, draw 1. (I win if I remain after combat.)
    "Nidalee - Cat Form": (
        Ability(TR_WIN_COMBAT, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When I move to a battlefield, discard 1.  When I win a combat, draw 1.
    #
    # The discard pays for the draw a turn in advance: it happens as he
    # arrives, the draw only if he survives the fight he walked into.
    "Corrupt Enforcer": (
        Ability(TR_MOVE, at_battlefield=True, ops=(Op(OP_DISCARD, n=1),)),
        Ability(TR_WIN_COMBAT, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When I win a combat, play a Gold gear token exhausted.
    # When I attack or defend, you may pay {Fury rune} to give me +2 Might this
    # turn.
    #
    # The +2 is an optional COST inside the instructions (383.3.b), decided at
    # finalization, so it is paid before the damage it is meant to win.
    "Draven - Vanquisher": (
        Ability(TR_WIN_COMBAT,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
        Ability(TR_ATTACK_OR_DEFEND, optional=True, opt_cost_power=1,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # [Deflect]  The first time I win a combat each turn, you score 1 point.
    # When I die in combat, choose an opponent. They score 1 point.
    #
    # A point either way, and which way is the whole card: survive and it is
    # yours, die fighting and it is theirs. `once_each_turn` is stamped at
    # `queue_win_combat`, a direct queueing site -- the lesson Miss Fortune -
    # Captain taught, where a gate only `fire_watchers` honoured was ignored.
    # `died_in_combat` narrows the Deathknell to the F_DIED_IN_COMBAT snapshot,
    # so a death to a spell outside combat hands the opponent nothing.
    "Draven - Audacious": (
        Ability(TR_WIN_COMBAT, once_each_turn=True,
                ops=(Op(OP_SCORE, n=1),)),
        Ability(TR_DEATH, died_in_combat=True,
                ops=(Op(OP_SCORE, n=1, who=W_ENEMY),)),
    ),

    # You may play me to an open battlefield.
    # When you play me, you may return a non-Dragon unit to its owner's hand.
    #
    # The first sentence is PLAY_PERMISSIONS; this is the second. "A unit",
    # unqualified, reaches either player's -- including your own, which resets
    # a play trigger -- and `lacks_tag` is "non-Dragon", so he cannot bounce
    # another Drake or himself (he is a Dragon).
    "Ocean Drake": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_ANY, lacks_tag="Dragon",
                                    locality=LOC_FREE),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # When you play your first card each turn, if I'm at a battlefield, your
    # next card costs {2 energy}{any rune}{any rune} less.
    #
    # The first cost modification in the pool with no source to read it off at
    # payment time: it is PROMISED by a trigger and held on the player, so the
    # Heron can be killed in response to her own trigger and the discount still
    # lands. That is why `state.next_discount` exists and why it is spent by
    # the next card PLAYED rather than by the next card paid for.
    #
    # "if I'm at a battlefield" narrows the TRIGGER (359.3.f), not the effect:
    # a Heron at base never reaches the Chain. `subject_nth=1` is an exact
    # match on the ordinal, so a third card in the same turn promises nothing.
    "Astral Heron": (
        Ability(TR_NTH_CARD, subject_nth=1, subject_at_battlefield=True,
                ops=(Op(OP_DISCOUNT_NEXT, n=2, power=2),)),
    ),

    # When you play your second card in a turn, give me +2 Might this turn and
    # ready me.
    #
    # The other half of what TR_NTH_CARD is for, and the reason the ordinal is
    # a field rather than a trigger per number. Readying himself is the real
    # clause: he is a 5 Might body that can move again the turn he lands, so
    # the second card is what turns him on.
    "Darius - Trifarian": (
        Ability(TR_NTH_CARD, subject_nth=2,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),
                     Op(OP_READY, target=T_SELF))),
    ),

    "Undertitan": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_MODIFY_MIGHT_ALL, n=2, who=W_FRIENDLY,
                        except_target=T_SELF),)),
        Ability(TR_REVEALED_FROM_DECK, immediate=True,
                ops=(Op(OP_ADD_ENERGY, n=2),)),
    ),

    # When I move, you may [Burn 1] to give me +1 Might this turn.
    #
    # 383.3.b -- an optional COST, paid at finalization, not a "you may" over
    # the effect. Unlike a rune cost it is always affordable: an empty deck
    # does not refuse it, it makes paying it a Burn Out, and 431.2 charges an
    # opponent's point for that. So the offer is unconditional and the price
    # is sometimes very high, which is the card.
    "Shadow Order Disciple": (
        Ability(TR_MOVE, optional=True, opt_cost_burn=1,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # [Empower] {3 energy}. I can be [Empowered] up to three times.
    # I have +2 Might for each time I'm [Empowered].
    # While I'm [Empowered] three times, I have [Deflect 3] and [Ganking].
    #
    # The card that made Empowered a COUNT rather than a flag: her reminder
    # text omits 827.1.c.1's "use only if not Empowered", and `EMPOWER_LIMIT`
    # is where that exception lives.
    "Kayle, Justified": (
        Ability(TR_ACTIVATED, cost_energy=3, ops=(Op(OP_EMPOWER),)),
    ),

    # [Empower] -- Kill a friendly unit
    # [Empowered][>] I have +2 Might.
    #
    # The cost is a body rather than runes, and it is a CHOSEN one, so it is
    # `cost_kill` (820) and not `cost_kill_self`. Paid at finalization through
    # the same `pend_cost_kill` path a printed "as an additional cost to play
    # me" uses -- 151.2.a makes activating an ability like playing a card, so
    # there was nothing to add but the field.
    #
    # She is herself a legal choice: "a friendly unit" does not exclude the
    # source, and 827.1.b.1 keeps the source off the target list only for the
    # EFFECT, not for the cost. Paying that way empowers a corpse -- OP_EMPOWER
    # checks P_ALIVE and does nothing -- which is legal and simply bad.
    "Escaped Grayback": (
        Ability(TR_ACTIVATED, cost_kill=TargetSpec(who=W_FRIENDLY),
                ops=(Op(OP_EMPOWER),)),
    ),

    "Treasure Trove": (
        Ability(TR_LEAVES_BOARD, ops=(Op(OP_DRAW, n=1), Op(OP_CHANNEL, n=1))),
        Ability(TR_ACTIVATED, cost_power=1, cost_exhaust=True,
                ops=(Op(OP_KILL, target=T_SELF),)),
    ),

    "Mindsplitter": (
        Ability(TR_PLAY_ME, ops=(Op(OP_REVEAL_HAND, pick_dest=DEST_TRASH),)),
    ),

    # When you play me, choose an opponent. They reveal their hand. You may pay
    # 2 XP to choose a card from their hand. If you do, they discard that card
    # and draw 1.
    #
    # Mindsplitter with a price on the CHOICE. Three things follow from where
    # the price sits, and all three are printed:
    #
    #   the reveal is unconditional   -- you see the hand whether or not you
    #                                    can pay, so the information is free
    #   "IF YOU DO"                   -- declining costs nothing and discards
    #                                    nothing, which is why the XP rides
    #                                    `pend_reveal_xp` rather than being a
    #                                    cost on the ability itself
    #   "and draw 1"                  -- THEY draw, not you. The card they lost
    #                                    is replaced, so this is tempo and
    #                                    information rather than card advantage
    #
    # "Choose an opponent" is not a target (355.10): a two-player game has one.
    "Insightful Investigator": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_REVEAL_HAND, pick_dest=DEST_TRASH, cost_xp=2,
                        then_key=FU_THEY_DRAW_1),)),
    ),

    "Scuttle Crab": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
        Ability(TR_DEATH, ops=(Op(OP_SEE_HAND),
                               Op(OP_SEE_FACEDOWN),
                               Op(OP_GAIN_XP, n=1))),
    ),

    # When you choose or ready me, give me +1 Might this turn.
    # Two triggers on one card, both narrowed to the card itself. Awaken counts
    # as readying, so she grows once a turn for free on top of anything you
    # point at her -- and [Deflect] is an engine keyword, so it needs no entry.
    "Irelia, Fervent": (
        Ability(TR_READIED, subject_is_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
        Ability(TR_CHOSEN, subject_is_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # When you ready a friendly unit, give IT +1 Might this turn.
    # The other side of the same trigger: the subject is whatever was readied,
    # not the watcher. On a wide board Awaken fires this once per exhausted
    # unit, which is what makes it a payoff for attacking with everything.
    "Pirate's Haven": (
        Ability(TR_READIED, ops=(Op(OP_MODIFY_MIGHT, target=T_SUBJECT, n=1),)),
    ),

    # When you choose me with a spell, draw 1. An ability that chooses is still
    # a choice (355.7), so "with a spell" is a real narrowing rather than
    # flavour text.
    "Jae Medarda": (
        Ability(TR_CHOSEN, subject_is_self=True, subject_by_spell=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # [Reaction] [Temporary] When an OPPONENT scores, draw 1.
    # A gear rather than a unit, which the watcher does not care about --
    # `fire_watchers` walks permanents, and only statics restrict themselves to
    # units. [Temporary] caps it at one turn, so it reads the opponent's next
    # scoring window and then dies before your own Beginning Phase scores.
    "Sumpworks Map": (
        Ability(TR_OPPONENT_SCORES, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you play a GEAR, ready me. The same watcher Reluctant Leader uses,
    # pointed at the other card type -- and the card that made the missing
    # `subject_card_type` filter visible, since without it every unit watcher
    # was already firing on gear.
    "Pit Crew": (
        Ability(TR_PLAY_UNIT, subject_card_type="Gear",
                ops=(Op(OP_READY, target=T_SELF),)),
    ),

    # When another friendly unit dies, give me +2 Might this turn.
    "Spectral Centaur": (
        Ability(TR_OTHER_DIES,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # When you use an activated ability of a gear, give me +1 Might this turn.
    "Prize of Progress": (
        Ability(TR_GEAR_ABILITY,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # When you discard ONE OR MORE cards, ready me and give me +1 Might this
    # turn.  "one or more" is one trigger per discard EVENT, not per card: a
    # card that pitches two fires this once.
    "Jinx - Rebel": (
        Ability(TR_DISCARD,
                ops=(Op(OP_READY, target=T_SELF),
                     Op(OP_MODIFY_MIGHT, target=T_SELF, n=1))),
    ),

    # [Hunt] [Level 6] When you play me, draw 1.
    # [Hunt] is synthesised from the keyword; the draw is gated on 6+ XP, which
    # COND_LEVEL already expresses.
    "Wuju Apprentice": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_LEVEL, level=6),)),
    ),

    # When you play me, return ANOTHER unit at a battlefield to its owner's
    # hand.  Unqualified by side, so it can bounce your own -- and `not_self`
    # is the "another", since an Ambushed Bouncer is itself at a battlefield.
    "Zaunite Bouncer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    not_self=True),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # The first time a friendly unit dies each turn, draw 1.
    # A watcher for another's death with a once-per-turn gate. "A friendly
    # unit" includes this one, but a watcher never sees its own death -- it is
    # already gone -- so the practical reading matches TR_OTHER_DIES.
    "Wraith of Echoes": (
        Ability(TR_OTHER_DIES, once_each_turn=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # When a showdown begins here, you may pay {1 energy}. If you do,
    # [Predict], then reveal the top card of your Main Deck. If it's a spell,
    # draw it.
    #
    # "When a showdown begins HERE" is TR_ATTACK_OR_DEFEND on herself: 459
    # designates every unit at the battlefield the moment a Combat begins, so
    # a showdown starting at Diana's battlefield is exactly when she is an
    # attacker or a defender.
    #
    # Two deferred decisions in sequence, which is what `then_key` is for --
    # the Predict suspends, and its follow-up suspends again for the reveal.
    "Diana - Lunari": (
        Ability(TR_SHOWDOWN_HERE, optional=True, opt_cost_energy=1,
                ops=(Op(OP_LOOK_TOP, n=1, pick_optional=True,
                        pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP,
                        then_key=FU_DIANA_REVEAL),)),
    ),

    # When I attack, you may pay {1 energy} to give a unit here -1 Might this
    # turn.  383.3.b again: an optional COST, so the offer only appears when
    # the energy is there. "a unit here" is unqualified -- it may point at your
    # own, which is occasionally what you want against a damage check.
    "Icevale Archer": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                optional=True, opt_cost_energy=1,
                targets=(TargetSpec(who=W_ANY, same_loc_as_source=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-1),)),
    ),

    # When I move to a battlefield, you may move an enemy unit to that
    # battlefield.  A free "you may" (383.3.a), decided at finalization -- no
    # cost, unlike Icevale Archer directly above.
    #
    # **"THAT battlefield", not "this" -- so the destination is `T_CTX2`, the
    # one captured when she moved, and the ability does not need her alive.**
    # Written first as `T_HERE` + `COND_SELF_AT_BF`, which read her row at
    # resolution and so was really "move an enemy unit to wherever I am
    # standing". Both halves of that fail to the same response: Gust her in
    # answer to the trigger (she is 1 Might, so she is always a legal Gust) and
    # the ability resolved doing nothing. 383.2.c.2 says an ability whose
    # source has left resolves WITHOUT it -- it does not fizzle -- and 359.3.f.3
    # says the battlefield it names was pinned when it triggered. Compare
    # Noxian Drummer two entries down, whose "play a Recruit token HERE" is
    # genuinely a live read of her own square and IS meant to do nothing once
    # she is gone.
    "Irresistible Faefolk": (
        Ability(TR_MOVE, optional=True,
                targets=(TargetSpec(who=W_ENEMY),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_CTX2,
                        cond=COND_CTX2_BATTLEFIELD),)),
    ),

    # When I hold, if there is exactly one other unit you control here, draw 1.
    # EXACTLY one -- a second friendly unit at the battlefield turns it off,
    # which is what makes it a condition rather than a threshold.
    "Shen, Scourge of Shadows": (
        Ability(TR_HOLD,
                ops=(Op(OP_DRAW, n=1, cond=COND_N_OTHERS_HERE, level=1),)),
    ),

    # When you play me, draw 1 if your other units have total Might 5 or more.
    # "OTHER units" excludes me, and the total is EFFECTIVE Might -- statics
    # and buffs count, which is the number the player can actually see.
    "Kinkou Initiate": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_OTHERS_MIGHT, level=5),)),
    ),

    # When you play me, you may kill a gear with Energy cost no more than
    # {1 energy}. If you do, play a Gold gear token exhausted.
    # The "you may" (383.3.a) is decided at finalization, but accepting is not
    # the same as succeeding: the gear can be spent in answer to the trigger,
    # and then the kill has nothing to kill and the token is not played
    # (RiftJudge #6498). COND_SLOT_DIED asks whether THIS resolution killed it.
    "Pickpocket": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_ANY, card_type=("Gear",),
                                    max_energy=1),),
                ops=(Op(OP_KILL, target=0),
                     Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN, cond=COND_SLOT_DIED, cond_slot=0))),
    ),

    # When you play me, draw 1 for each of your [Mighty] units.
    # 5+ Might is Mighty, and it is EFFECTIVE Might -- statics and buffs count,
    # which is what the player sees on the board. Kadregrin is on the board by
    # the time this resolves (359.2.b), so it counts itself if it qualifies.
    "Kadregrin the Infernal": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, n_from_count=CT_MY_MIGHTY_UNITS),)),
    ),

    # When you play me, give a unit +8 Might this turn.
    "Whiteflame Protector": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=8),)),
    ),

    # When I attack, you may pay {1 energy} to move an enemy unit here to its
    # base.  383.3.b optional cost; "here" is my battlefield, and "ITS base"
    # is the moved unit's owner's, not mine.
    "Sinister Poro": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                optional=True, opt_cost_energy=1,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # When I DEFEND, you may kill me to move an attacking unit to its base.
    # Sinister Poro's shape from the other side of the fight, and the first
    # ability whose optional cost is a body rather than runes. "An attacking
    # unit" carries no ownership clause, but 459 only designates the Attacker's
    # units as attacking, so `attacking` already scopes it to the enemy side
    # and to the contested battlefield.
    "Overzealous Fan": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_DEFEND,
                optional=True, opt_cost_kill_self=True,
                targets=(TargetSpec(who=W_ANY, attacking=True),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_OWNER_BASE),)),
    ),

    # [Hidden] When you play me, you may return ANOTHER unit at a battlefield
    # with 3 Might or less to its owner's hand.
    # `max_might` is a restriction (355.9.b) read against EFFECTIVE Might and
    # re-checked at resolution (359.3.e), so growing the target during the
    # response window takes it out of range and this does nothing to it.
    "Windsinger": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    not_self=True, max_might=3),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # When another NON-RECRUIT unit you control dies, play a 1 Might Recruit
    # unit token into your base.
    # The tag exclusion is load-bearing: Viktor makes Recruits, so without it
    # each token's death would make another one, forever.
    "Viktor - Leader": (
        Ability(TR_OTHER_DIES, subject_lacks_tag="Recruit",
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=RECRUIT_TOKEN),)),
    ),

    # When you play me OR at the start of your Beginning Phase, play a ready
    # 3 Might Sprite unit token with [Temporary] to your base.
    # "or" is two triggers on one effect, which is two entries. The token
    # carries [Temporary] itself, so it expires through the existing path.
    "Sprite Queen": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
        Ability(TR_BEGINNING,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=SPRITE_TOKEN, ready=True),)),
    ),

    # When I attack, give me +2 Might this turn if there is a READY enemy unit
    # here.  Exhausted enemies do not count -- the card pays you for attacking
    # into something that can still fight back.
    "Dune Drake": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_READY_ENEMY_HERE),)),
    ),

    # I can't be chosen by enemy spells and abilities unless I'm in combat.
    # When I move to a battlefield, give me +2 Might this turn.
    # The first clause is a targeting restriction and lives in
    # SAFE_UNLESS_IN_COMBAT; only the trigger is written here.
    "Akali, Silent": (
        Ability(TR_MOVE,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_SELF_AT_BF),)),
    ),

    # [Ambush] When I attack, [Stun] an enemy unit here.
    # Leona's shape exactly, and both were unreachable until the attack/defend
    # trigger learned to tell attacking from defending (459) and "here" from
    # "anywhere".
    "Vi - Peacekeeper": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_STUN, target=0),)),
    ),

    # [Shield] When I attack, stun an enemy unit here.
    "Leona, Determined": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_STUN, target=0),)),
    ),

    # [Deathknell] Deal 4 to all units at my battlefield.
    # "all units", unscoped by `who`: it takes friendly units with it, which is
    # the cost of the effect rather than an oversight. T_HERE on a death
    # trigger is the location the source died at -- 808.1 fires as I die, and
    # the row keeps its P_LOC.
    "Kog'Maw - Caustic": (
        Ability(TR_DEATH,
                ops=(Op(OP_DAMAGE_ALL, at=T_HERE, n=4),)),
    ),

    # When you play me, give a unit +3 Might this turn.
    # "a unit" is unqualified, so it may point at an enemy -- pointless here,
    # but the slot is what the card prints and W_ANY is that word's absence.
    "Field Musicians": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),)),
    ),

    # [Ambush] When you play a spell, give me +2 Might this turn.
    # TR_PLAY_SPELL fires on FINALIZATION (349), so the +2 lands while the
    # spell is still on the Chain and applies even if the spell is countered.
    "Diana, No Longer Human": (
        Ability(TR_PLAY_SPELL,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # [Ambush] When you play me, you may return a friendly unit at a
    # battlefield to its owner's hand.
    # "a friendly unit", not "another": Ambush plays me straight to a
    # battlefield, so I am one of the legal choices and bouncing myself is a
    # real (if usually bad) line. `not_self` would be a card the printer did
    # not print.
    "Grim Apothecary": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, at_battlefield=True),),
                ops=(Op(OP_RETURN_TO_HAND, target=0),)),
    ),

    # When you play this, draw 1.
    # {1 energy}{Calm rune}, Exhaust, Kill this: Draw 1.
    # A gear with both halves: an ETB and an activated ability whose base cost
    # (204.1.b) is three things at once -- runes, an exhaust, and its own life.
    # The Power symbol is paid in the card's own domain, which `cost_power`
    # leaves to `plan_ability_cost` to read off the card.
    "Poro Snax": (
        Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),)),
        Ability(TR_ACTIVATED, cost_energy=1, cost_power=1,
                cost_exhaust=True, cost_kill_self=True,
                ops=(Op(OP_DRAW, n=1),)),
    ),

    # --- the Gold makers (187.5) -------------------------------------------
    # All of these print "exhausted", which is `Op.ready` left False, and all
    # of them put the gear at the controller's base under 149.2.

    # When I conquer, play a Gold gear token exhausted.
    "Plundering Poro": (
        Ability(TR_CONQUER,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # [Deathknell] Play a Gold gear token exhausted.
    "Honest Broker": (
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When I move, play a Gold gear token exhausted.
    "Treasure Hunter": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When I hold, play two Gold gear tokens exhausted.
    "Eminent Benefactor": (
        Ability(TR_HOLD,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=2,
                        token=GOLD_TOKEN),)),
    ),

    # When you play me, play four Gold gear tokens exhausted.
    "Trove Golem": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=4,
                        token=GOLD_TOKEN),)),
    ),

    # NOT transcribed: Pyke - Bloodharbor Ripper, whose "{1 energy}, Exhaust:
    # Return a friendly unit at a battlefield to its owner's hand. Play a Gold
    # gear token exhausted" is otherwise ordinary. It is a LEGEND, and the
    # engine parses Legends out of a decklist but never puts one into play, so
    # the ability could never fire -- `decks.includable` excludes the type
    # outright and the coverage gate in test_triggers catches the spec as
    # uncounted. Encode it with the rest of the Legends once they exist.

    # When I attack, deal 3 to all enemy units here.
    # T_HERE is my own location; "here" on an attack trigger is the contested
    # battlefield because that is where I must be to be attacking from it.
    "Anivia - Primal": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                ops=(Op(OP_DAMAGE_ALL, at=T_HERE, n=3, who=W_ENEMY),)),
    ),

    # When I attack, deal 1 to an enemy unit here.
    "Crackshot Corsair": (
        Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_DAMAGE, target=0, n=1),)),
    ),

    # When I attack or defend, give an enemy unit here -2 Might this turn, to a
    # minimum of 1 Might.  No role restriction -- this is the card that names
    # both sides, and the one the old unconditional `is_alone` gate would have
    # silently narrowed to units standing by themselves.
    "Ahri, Inquisitive": (
        Ability(TR_ATTACK_OR_DEFEND,
                targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2, floor=1),)),
    ),

    # --- XP ---------------------------------------------------------------
    # [Hunt] is NOT transcribed on any of these: it is synthesised from the
    # keyword in `abilities_for`, because its effect is fixed by the keyword
    # rather than written on the card. Repeating it here would double it.

    # When you play me, gain 1 XP.
    "Demacian Diplomat": (
        Ability(TR_PLAY_ME, ops=(Op(OP_GAIN_XP, n=1),)),
    ),

    # [Hunt] When you play me, gain 2 XP.
    "Herald of Spring": (
        Ability(TR_PLAY_ME, ops=(Op(OP_GAIN_XP, n=2),)),
    ),

    # [Hunt] Spend 2 XP: [Buff] me.
    # (Give me a +1 Might buff if I don't have one.)
    #
    # The XP loop closed: Hunt banks it on a Score, this spends it. 702.3 caps
    # a unit at one Buff counter, which `OP_BUFF` already enforces -- so the
    # second activation is legal, costs the XP, and does nothing.
    "Crowd Favorite": (
        Ability(TR_ACTIVATED, cost_xp=2,
                ops=(Op(OP_BUFF, target=T_SELF),)),
    ),
    "Enthralling Protector": (
        Ability(TR_ACTIVATED, cost_xp=2,
                ops=(Op(OP_BUFF, target=T_SELF),)),
    ),

    # [Hidden] When you play me, you may choose a friendly unit. Move me to
    # its location and it to my original location.
    #
    # A swap, which `OP_SWAP_LOC` already does -- the interesting half is the
    # "you may". 383.3.a puts a "you may" that OPENS an effect at finalization,
    # so it is `optional` on the Ability and not an optional slot: declining
    # removes the trigger from the Chain entirely and it counts as never having
    # triggered (383.3.a.2), rather than resolving into nothing. The slot
    # itself is required, so 355.8 stops the ability firing at all when there
    # is no other friendly unit to trade places with.
    #
    # `not_self` matters here in a way it usually does not: without it "a
    # friendly unit" includes Tideturner, and swapping a unit with itself is a
    # legal-looking no-op that would still burn the trigger.
    #
    # **"at another location" is the errata, and it is load-bearing.** The
    # printed text is the unrestricted "a friendly unit"; the errata narrows it,
    # and 811.1.d.2's own worked example is this card -- Tideturner is the
    # rulebook's illustration of "a targeting restriction that can never be
    # fulfilled by a unit at its battlefield", which is why a hidden Tideturner
    # may choose freely instead of being pinned to where it was hidden. Without
    # the restriction that example does not apply and the swap can be a no-op
    # between two units already standing together.
    "Tideturner": (
        Ability(TR_PLAY_ME, optional=True,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                    different_loc_from_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_SWAP_LOC, target=T_SELF, target_b=0),)),
    ),

    # When you play me, give a unit [Ganking] this turn.
    "Gem Jammer": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_GRANT_KEYWORD, target=0, keyword="Ganking", n=1),)),
    ),

    # [Deathknell] - Draw 1.
    "Watchful Sentry": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=1),)),
    ),

    # When you play a token unit, give me +1 Might this turn.
    # Your token units have [Tank].
    #
    # Both halves, and they are different mechanisms: the first is a TRIGGER
    # that banks +1 for the turn each time a token arrives, the second is a
    # continuous STATIC. The trigger watches another permanent being played, so
    # it is a watcher like Ravenbloom Student's "when you play a spell" rather
    # than an ETB -- and "give ME" means the source, not the token, so it needs
    # no subject.
    "Lillia - Protector of Dreams": (
        Ability(TR_PLAY_UNIT, subject_token=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1),)),
    ),

    # --- [Legion]: "get the effect if you've played another card this turn" --
    # These read the F_LEGION SNAPSHOT taken when the unit was played, not the
    # live counter. Two things would go wrong live: the unit has itself been
    # counted by the time its own ETB resolves, and the trigger sits on the
    # Chain through a priority window in which the count can move again. The
    # ability still goes on the Chain and still needs a legal target (355.8);
    # it is a conditional effect, not an optional one, so an un-Legioned copy
    # resolves and does nothing.

    # [Legion] - When you play me, give a unit +2 Might this turn.
    "Dangerous Duo": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=2, cond=COND_LEGION),)),
    ),

    # [Legion] - When you play me, play two 1 Might Recruit unit tokens here.
    "Vanguard Captain": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_HERE, n=2,
                        token=RECRUIT_TOKEN, cond=COND_LEGION),)),
    ),

    # [Legion] - When you play me, buff me.
    # (If I don't have a buff, I get a +1 Might buff.)
    "Trifarian Gloryseeker": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_BUFF, target=T_SELF, cond=COND_LEGION),)),
    ),

    # When you play this, play a 1 Might Recruit unit token at your base.
    # Kill this: Recycle up to 4 cards from trashes.
    #
    # **"From trashes" reaches BOTH piles, and 416.1.c sends each card to its
    # own owner's deck.** That is what makes the enemy-facing half a real mode
    # rather than a rounding error: their [Flow] cards are banished on use and
    # never come back, but everything else in their trash is live ammunition for
    # a Soulgorger or a Fizz, and putting it on the bottom of their deck is the
    # only answer in the pool that does not require killing the recursion
    # engine first. Pointing it at your OWN trash is the opposite play -- it
    # refills a deck that is running out of cards.
    #
    # `T_MY_BASE`, not `T_HERE`: Gear is base-only under 149.2, but a Gear
    # played from a Facedown Zone stands at a battlefield, and the token still
    # goes to the base.
    "Forge of the Future": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=RECRUIT_TOKEN),)),
        Ability(TR_ACTIVATED, cost_kill_self=True,
                targets=tuple(TargetSpec(kind=TK_TRASH_CARD, who=W_ANY,
                                         optional=True) for _ in range(4)),
                ops=tuple(Op(OP_RECYCLE_FROM_TRASH, target=i)
                          for i in range(4))),
    ),


    # --- the Seal cycle: "Exhaust: [Reaction] - [Add] {X rune}" -------------
    # 337.2 makes a resource-adding ability resolve immediately, so `immediate`
    # keeps it off the Chain entirely.
    "Seal of Strength": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=0),)),
    ),
    "Seal of Focus": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=1),)),
    ),
    "Seal of Discord": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=2),)),
    ),
    "Seal of Rage": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=3),)),
    ),
    "Seal of Insight": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=4),)),
    ),
    "Seal of Unity": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=5),)),
    ),

    # Exhaust: [Reaction] - [Add] {1 energy}.
    "Energy Conduit": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                immediate=True, ops=(Op(OP_ADD_ENERGY, n=1),)),
    ),

    # 187.5, the Gold gear token: "Kill this, Exhaust: [Reaction] - [Add] [A]."
    # [A] is Power of ANY Domain (135.2.e.5), so it goes to the D_ANY column of
    # the Rune Pool rather than to one domain's -- the Seal cycle above adds a
    # FIXED domain and this is the wildcard.
    #
    # Two costs, both paid at finalization: the token is killed AND exhausted,
    # which together make it a one-shot ritual rather than a rune. It is a
    # token, so it ceases to exist rather than reaching a trash (185.3).
    # `immediate` keeps it off the Chain (337.2) -- the card says so itself:
    # "Abilities that add resources can't be reacted to."
    "Gold // Buff": (
        Ability(TR_ACTIVATED, speed=SPEED_REACTION, cost_exhaust=True,
                cost_kill_self=True, immediate=True,
                ops=(Op(OP_ADD_POWER, n=1, domain=D_ANY),)),
    ),

    # Exhaust: Play three 1 Might Recruit unit tokens.
    "Vanguard Armory": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                ops=(Op(OP_CREATE_TOKEN, n=3, token=RECRUIT_TOKEN),)),
    ),

    # Exhaust: Give a unit +3 Might this turn.
    # The cost is the whole "Exhaust:" clause; the effect follows the colon.
    "Heart of Dark Ice": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_ANY),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),)),
    ),

    # [Temporary]
    # When you play this, play a ready 3 Might Sprite unit token with
    # [Temporary] to your base.
    # [Deathknell][>] Repeat this gear's play effect.
    #
    # The single most-played card in the corpus (39 slots) and the engine of
    # every Sprite deck: [Temporary] kills it at the start of each Beginning
    # Phase, its Deathknell repeats the play effect, so it makes a Sprite when
    # it lands and another one every time it expires. "Repeat this gear's play
    # effect" is the same op, which is why both abilities are literally the
    # same line -- no Repeat machinery involved (820 is a paid additional cost;
    # this is printed text).
    "Sprite Fountain": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_CREATE_TOKEN, n=1, token=SPRITE_TOKEN, ready=True),)),
        Ability(TR_DEATH,
                ops=(Op(OP_CREATE_TOKEN, n=1, token=SPRITE_TOKEN, ready=True),)),
    ),

    # When I become ready, give me +2 Might this turn.
    #
    # TR_READIED is the exhausted -> ready TRANSITION, and the Awaken Phase is
    # the reliable source of one: a unit that spent the turn exhausted wakes up
    # bigger every turn ([[riftbound-awaken-counts-as-readying]]). A unit that
    # was already ready has not become ready and this does not fire, which is
    # what keeps it from being a free +2 every turn regardless.
    #
    # `subject_is_self` because `fire_watchers` walks the whole board: without
    # it the card would read "when a friendly unit becomes ready".
    "Fretful Feline": (
        Ability(TR_READIED, subject_is_self=True,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2),)),
    ),

    # When I attack or defend, give one of your OTHER units HERE +3 Might and
    # [Tank] this turn.
    #
    # The pair is the point: [Tank] makes the target take combat damage first
    # (807) and +3 Might is what lets it survive doing so, so the two ops are
    # one effect and both point at the same slot. Yuumi herself is excluded by
    # `not_self`, and `same_loc_as_source` is "here" -- the contested
    # battlefield, since she has to be standing there to be attacking from it.
    "Yuumi - Magical Cat": (
        Ability(TR_ATTACK_OR_DEFEND,
                targets=(TargetSpec(who=W_FRIENDLY, not_self=True,
                                    same_loc_as_source=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=3),
                     Op(OP_GRANT_KEYWORD, target=0, keyword="Tank", n=1))),
    ),

    # [Accelerate] When I move to a battlefield, play three 1 Might Recruit
    # unit tokens here.
    #
    # "Here" on a move trigger is where she ARRIVED, which is `T_CTX2` and not
    # `T_HERE`: the trigger sits on the Chain through a response window, and if
    # she is answered before it resolves the tokens still land on the ground
    # she was moving to. COND_CTX2_BATTLEFIELD is the "to a battlefield" half --
    # a retreat to base fires nothing.
    "Corina Veraza": (
        Ability(TR_MOVE,
                ops=(Op(OP_CREATE_TOKEN, n=3, token=RECRUIT_TOKEN,
                        target=T_CTX2, cond=COND_CTX2_BATTLEFIELD),)),
    ),

    # At the end of your turn, if I'm at a battlefield, ready up to 4 friendly
    # runes.
    #
    # End of YOUR turn, so the runes come back before the opponent's -- the
    # same reason Targon's Peak defers its readying rather than performing it
    # ([[riftbound-tapping-out-costs-the-opponents-turn]]). The condition is
    # what she costs: holding ground is the price of the refund.
    "Sona, Harmonious": (
        Ability(TR_END_OF_TURN,
                ops=(Op(OP_READY_RUNES, n=4, cond=COND_SELF_AT_BF),)),
    ),

    # [Hidden] [Backline] Once each turn, when an ENEMY unit dies while I'm at
    # a battlefield, play a Gold gear token exhausted.
    #
    # The first watcher in the pool that wants the other side's deaths. A death
    # fires TR_OTHER_DIES for both seats and each watcher states which side it
    # meant, so "when another friendly unit dies" and this one are the same
    # trigger read from opposite ends.
    #
    # Both of its own clauses are about PYKE, not about the unit that died:
    # `subject_at_battlefield` is "while I'm at a battlefield", and
    # `once_each_turn` is spent only when everything else has already matched.
    "Pyke - Returned": (
        Ability(TR_OTHER_DIES, subject_enemy=True, subject_at_battlefield=True,
                once_each_turn=True,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When you play me OR ANOTHER DRAGON, ready up to 2 runes.
    #
    # Two abilities for one sentence, because "me" and "another Dragon" are two
    # different events: the first is TR_PLAY_ME, the second is a watcher on the
    # plays that follow. `subject_not_self` on the watcher is what keeps her own
    # arrival from paying twice.
    "Gentle Gemdragon": (
        Ability(TR_PLAY_ME, ops=(Op(OP_READY_RUNES, n=2),)),
        Ability(TR_PLAY_UNIT, subject_tag="Dragon", subject_not_self=True,
                ops=(Op(OP_READY_RUNES, n=2),)),
    ),

    # [Deathknell] If I was [Mighty], draw 2.
    #
    # Past tense, and that is the whole implementation question: 740.2 makes
    # Mighty 5+ EFFECTIVE Might, so a combat trick can supply it -- and the
    # trick expires with the turn while the Deathknell waits on the Chain. The
    # answer is snapshotted as he dies, the same way "died alone" is.
    "Unsung Hero": (
        Ability(TR_DEATH, ops=(Op(OP_DRAW, n=2, cond=COND_WAS_MIGHTY),)),
    ),

    # If you control fewer runes than an opponent at the start of your
    # Beginning Phase, give me +1 Might this turn.
    #
    # A catch-up clause: it compares two rune boards rather than testing a
    # threshold, so it switches off the moment you draw level. Phase-timed, so
    # it asks the question once a turn and the answer holds for that turn even
    # if the counts move afterwards.
    "Forsaken Baccai": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=1,
                        cond=COND_FEWER_RUNES_THAN_OPP),)),
    ),

    # If you control fewer runes than an opponent at the start of your
    # Beginning Phase, give me +2 Might and [Ganking] this turn.
    #
    # The same clause paying out twice as much, plus the keyword that makes it
    # matter: [Ganking] lets him move battlefield-to-battlefield, so the turn
    # you are behind on runes is the turn he can reach the ground you need.
    "Oasis Raider": (
        Ability(TR_BEGINNING,
                ops=(Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_FEWER_RUNES_THAN_OPP),
                     Op(OP_GRANT_KEYWORD, target=T_SELF, keyword="Ganking",
                        n=1, cond=COND_FEWER_RUNES_THAN_OPP))),
    ),

    # --- printed optional additional costs (see PLAY_COSTS) ---------------
    # Each of these is one sentence: "you may pay X as an additional cost to
    # play me", then "when you play me, IF YOU PAID the additional cost, ...".
    # The cost is in `PLAY_COSTS` and is paid through `A_PLAY_AT_FAST`, the
    # same action [Accelerate] uses; the ability here reads the snapshot the
    # payment left. Nothing is conditional about the TRIGGER -- it fires
    # either way and the ops fizzle, which is 355.9.b's distinction between a
    # restriction and a condition, and it matters because a target is still
    # chosen for a Masa played without the rune.
    #
    # ...deal 2 to a unit at a battlefield.
    "Blast Corps Cadet": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, at_battlefield=True,
                                    optional=True),),
                ops=(Op(OP_DAMAGE, target=0, n=2,
                        cond=COND_PAID_ADDITIONAL),)),
    ),

    # ...draw 1.
    "Clockwork Keeper": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_DRAW, n=1, cond=COND_PAID_ADDITIONAL),)),
    ),

    # ...give a unit -2 Might this turn. No printed floor, so 143.2.b's general
    # floor of 0 applies rather than Stupefy's stricter minimum of 1.
    "Frostcoat Cub": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ANY, optional=True),),
                ops=(Op(OP_MODIFY_MIGHT, target=0, n=-2,
                        cond=COND_PAID_ADDITIONAL),)),
    ),

    # ...[Stun] an enemy unit at a battlefield.
    "Masa, Crashing Thunder": (
        Ability(TR_PLAY_ME,
                targets=(TargetSpec(who=W_ENEMY, at_battlefield=True,
                                    optional=True),),
                ops=(Op(OP_STUN, target=0, cond=COND_PAID_ADDITIONAL),)),
    ),

    # [Hidden] [Ganking] ...ready me and give me +2 Might this turn.
    # Both halves are conditional, so each op carries the condition: a Pyke
    # played without the rune is an ordinary 3-Might body that entered
    # exhausted, which is the whole choice the card offers.
    "Pyke - Dockside Butcher": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_READY, target=T_SELF, cond=COND_PAID_ADDITIONAL),
                     Op(OP_MODIFY_MIGHT, target=T_SELF, n=2,
                        cond=COND_PAID_ADDITIONAL))),
    ),

    # ...buff me. 702.3 caps a unit at one Buff counter, which OP_BUFF already
    # enforces, so paying twice over two copies is not a stacking play.
    "Sea Monkey": (
        Ability(TR_PLAY_ME,
                ops=(Op(OP_BUFF, target=T_SELF,
                        cond=COND_PAID_ADDITIONAL),)),
    ),

    # [Hidden] [Backline] When you play me from face down on your turn, you
    # may move an enemy unit at a different location to my battlefield.
    #
    # Both halves of "from face down on your turn" narrow the TRIGGER rather
    # than gating the effect -- see `Ability.from_hidden`. Played from hand
    # this card does nothing at all, which is what the printed wording says.
    #
    # `locality=LOC_FREE` is 811.1.d.2's Tideturner ruling, not a shortcut:
    # a slot restricted to "a DIFFERENT location" can never be satisfied at
    # the battlefield she was hidden at, so the rule hands the choice back
    # rather than making the ability uncastable. Without it `different_loc_
    # from_source` and the automatic bound-battlefield narrowing would
    # contradict each other and the trigger would never fire.
    #
    # `T_HERE` is "my battlefield": 811.1.d.1 put her on the battlefield she
    # was hidden at, and `from_hidden` means she cannot have arrived any
    # other way, so her location IS that battlefield.
    "Evelynn - Entrancing": (
        Ability(TR_PLAY_ME, optional=True, from_hidden=True, own_turn=True,
                targets=(TargetSpec(who=W_ENEMY,
                                    different_loc_from_source=True,
                                    locality=LOC_FREE),),
                ops=(Op(OP_MOVE_TO, target=0, target_b=T_HERE),)),
    ),

    # When you play a card from face down, play a Gold gear token exhausted.
    # A bystander watching the Facedown Zone -- it has no [Hidden] of its own,
    # so `TR_PLAY_FROM_HIDDEN` rather than `Ability.from_hidden`. "A card", so
    # a hidden spell counts as much as a hidden permanent.
    "Black Market Broker": (
        Ability(TR_PLAY_FROM_HIDDEN,
                # `n=1` is not decoration: `Op.n` defaults to 0, so without it
                # the Broker played no Gold token at all (RiftJudge #8138).
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),

    # When you hide a card, ready me.
    # When you play a card from face down, deal 2 to an enemy unit.
    #
    # Two abilities, not one: 811.1.c.1 makes Hide and Play different events
    # ("Hide is not a subset of Play"), which is exactly why the card prints
    # both clauses. Hiding readies her; playing the card back shoots.
    "Katarina - Reckless": (
        Ability(TR_HIDE, ops=(Op(OP_READY, target=T_SELF),)),
        Ability(TR_PLAY_FROM_HIDDEN,
                targets=(TargetSpec(who=W_ENEMY),),
                ops=(Op(OP_DAMAGE, target=0, n=2),)),
    ),

    # Tornado Warrior ("[Hidden] When you play me from face down, you may
    # empower something HERE. Disempower it at end of turn") is deliberately
    # absent. Its trigger is expressible -- `from_hidden` covers it -- but its
    # EFFECT is not: 827.1.b.1 makes Empower act on the ability's own source
    # and never on a target, so `OP_EMPOWER` reads no slot, and nothing in the
    # engine disempowers anything. Both are [Empower] work, not [Hidden] work.

    # Ferrous Forerunner, Carrion Dredger and Honest Broker used to be listed
    # here as deliberately absent: their Deathknells play Mech, Bird and Gold
    # tokens and `data/cards.json` shipped only Recruit and Sprite. That gap is
    # closed -- `data/tokens.json` supplies rule 187's eleven tokens -- and all
    # three are scripted above.
}


def spec_for(table, card: int) -> CardSpec | None:
    """The spec for a card id, or None if it is not implemented yet."""
    return SPECS.get(table.names[card])


# [Hunt N] -- 823: "When I conquer or hold, gain N XP." Unlike [Deathknell],
# whose effect is whatever the card says, Hunt's effect is fixed by the keyword
# and identical on every card carrying it. So it is SYNTHESISED from the
# keyword rather than transcribed twelve times: `keyword_value` already reads
# the N, and TR_CONQUER/TR_HOLD already exist because Scoring needed them.
#
# Two abilities, not one with a shared trigger: 469/470 make Conquer and Hold
# separate ways to Score, and a card can only take one of them in a turn.
def _hunt_abilities(table, card: int) -> tuple[Ability, ...]:
    n = int(table.hunt[card])
    if n <= 0:
        return ()
    return (Ability(TR_CONQUER, ops=(Op(OP_GAIN_XP, n=n),)),
            Ability(TR_HOLD, ops=(Op(OP_GAIN_XP, n=n),)))


def _deploy_abilities(table, card: int) -> tuple[Ability, ...]:
    """[Deploy]'s second half -- "When an opponent holds here, kill this."

    The first half ("Play this only to a battlefield") is a play restriction,
    not an ability, and lives in `actions.play_destinations` beside 806.3's.

    Synthesised like [Temporary]'s self-kill (816), which is the closest
    analogue in the pool: a keyword whose entire effect is "kill me at this
    specific moment", fixed by the keyword rather than written on the card.
    Going through the Chain rather than sweeping the board directly is what
    makes it a real triggered ability -- it can be responded to, and it lands
    in the Scoring Step where 315.2's ordering already applies.
    """
    if not table.has(card, "Deploy"):
        return ()
    return (Ability(TR_ENEMY_HOLDS_HERE, ops=(Op(OP_KILL, target=T_SELF),)),)


def _disarm_abilities(table, card: int) -> tuple[Ability, ...]:
    """[Disarm] -- "When I attack, give an enemy unit here -1 Might this turn."

    Synthesised from the keyword rather than transcribed per card, for the same
    reason [Hunt] and [Vision] are: the effect is fixed by the keyword, not
    written on the card, so transcribing it on each printing would be one more
    chance to write it differently.

    `subject_role=ROLE_ATTACK` because the reminder says "when I ATTACK" and
    not "attack or defend" -- Ahri, Inquisitive prints the two-sided version and
    leaves `subject_role` off, which is the contrast worth noticing.

    **No Might floor**, deliberately. Ahri's card prints "to a minimum of 1
    Might" and passes `floor=1`; [Disarm]'s reminder prints no minimum, so
    143.2.b's general floor of 0 applies instead. Copying Ahri's floor here
    would be inventing text the keyword does not have.
    """
    if not table.has(card, "Disarm"):
        return ()
    return (Ability(TR_ATTACK_OR_DEFEND, subject_role=ROLE_ATTACK,
                    targets=(TargetSpec(who=W_ENEMY, same_loc_as_source=True),),
                    ops=(Op(OP_MODIFY_MIGHT, target=0, n=-1),)),)


def _vision_abilities(table, card: int) -> tuple[Ability, ...]:
    """[Vision] (817) -- "functionally short for 'When this is played, predict'".

    817.1.b spells the whole keyword out, and Predict is already the look
    mechanic at N=1 (436.1: look at the top card, choose whether to Recycle
    it). So Vision is synthesised rather than transcribed, exactly like [Hunt]:
    its effect is fixed by the keyword instead of written on the card, and
    repeating it on each of the nine cards that print it would be nine chances
    to write it differently.

    817.1.c makes the trigger the permanent ENTERING THE BOARD, which is what
    TR_PLAY_ME already means. 817.2's "multiple instances trigger separately"
    is not reachable: no card in the pool prints Vision twice.
    """
    if not table.has(card, "Vision"):
        return ()
    return (Ability(TR_PLAY_ME,
                    ops=(Op(OP_LOOK_TOP, n=1, pick_optional=True,
                            pick_dest=DEST_RECYCLE, rest_dest=DEST_TOP),)),)


def _equip_abilities(table, card: int) -> tuple[Ability, ...]:
    """[Equip] (818) -- "functionally short for '[Cost]: Attach this gear to a
    unit you control'" (818.1.c.2).

    Synthesised rather than transcribed, like [Hunt] and [Vision]: the effect
    is fixed by the keyword and only the cost differs per card, so writing it
    out 39 times would be 39 chances to write it differently.

    818.1.b.1 -- "Equip's choice is a Target", which is why this has a real
    `TargetSpec` and not a `T_*` sentinel. W_FRIENDLY because the keyword says
    "a unit you control"; 718.5.e's different-controllers case arises from
    control CHANGING later, never from the Equip itself.

    Speed is SPEED_MAIN. [Quick-Draw] grants [Reaction] to the card (819.1.b),
    which is about PLAYING it; nothing in 818 or 819 gives the Equip ability
    itself a faster speed, and 151.2 puts a gear's activated abilities in its
    controller's Main Phase outside a Showdown.
    """
    e = int(table.equip_energy[card])
    if e < 0:
        return ()
    # 818.1.c.3's non-resource half. Each kind maps onto a cost the engine
    # already pays; an unrecognised part means the printed cost cannot be
    # charged, so the ability is not offered at all rather than at a discount
    # -- the failure `equip_extra_costs` exists to prevent.
    extra = dict(table.equip_extra[card])
    if "unknown" in extra:
        return ()
    return (Ability(TR_ACTIVATED, speed=SPEED_MAIN,
                    cost_energy=e, cost_power=int(table.equip_power[card]),
                    cost_xp=extra.get("xp", 0),
                    cost_recycle_trash=extra.get("recycle", 0),
                    cost_kill=(TargetSpec(kind=TK_UNIT, who=W_FRIENDLY)
                               if extra.get("kill") else None),
                    targets=(TargetSpec(kind=TK_UNIT, who=W_FRIENDLY),),
                    ops=(Op(OP_ATTACH, target=0),)),)


def weaponmaster_cost(state, table, seat: int, gear: int) -> tuple[int, int, int] | None:
    """(energy, power, xp) [Weaponmaster] pays to attach `gear` (821.1.c), or
    None if it cannot be paid this way.

    821.1.c.2 -- the Equip ability's cost "as modulated by any abilities that
    alter Equip costs", so the Energy goes through `cost.ability_energy` exactly
    as activating it would. 821.1.c.3 -- reduced by [A] only if the cost HAS an
    [A]: most Equip costs print a domain rune, which the discount cannot touch.
    821.1.c.4 -- no Equip cost, no payment. Kill and recycle parts are not
    payable from inside a resolving trigger here, so those Equipment are not
    offered (821.1.c.5 leaves them where they are).
    """
    from rl.engine.cost import ability_energy
    from rl.engine.state import P_CARD as _P_CARD
    card = int(state.perms[gear, _P_CARD])
    abs_ = _equip_abilities(table, card)
    if not abs_:
        return None
    ab = abs_[0]
    if ab.cost_kill is not None or ab.cost_recycle_trash:
        return None
    energy = ability_energy(state, table, seat, card, ab.cost_energy, ab)
    power = ab.cost_power - min(1, _equip_any_runes(table, card))
    return energy, max(0, power), ab.cost_xp


_EQUIP_ANY: dict[tuple[int, int], int] = {}


def _equip_any_runes(table, card: int) -> int:
    """How many {any rune} symbols the printed Equip cost carries."""
    key = (id(table), card)
    if key not in _EQUIP_ANY:
        from rl.engine.cardtable import _EQUIP
        m = _EQUIP.search(table.raw_text[card] or "")
        _EQUIP_ANY[key] = (m.group(1).count("{any rune}") if m else 0)
    return _EQUIP_ANY[key]


def _weaponmaster_abilities(table, card: int) -> tuple[Ability, ...]:
    """[Weaponmaster] (821) -- "When you play me, you may choose a card you
    control with the Equipment tag. Pay the cost of its Equip ability, reduced
    by [A], to attach it to this unit."

    Optional (the "may"), with the Equipment as a real slot. The payment is
    made as the ability RESOLVES, by `OP_WEAPONMASTER`: it is part of the
    effect, and 821.1.c.6 says the Equip ability itself is never activated.
    """
    if not table.has(card, "Weaponmaster"):
        return ()
    return (Ability(TR_PLAY_ME, optional=True,
                    targets=(TargetSpec(kind=TK_UNIT, who=W_FRIENDLY,
                                        card_type=("Gear",), tags=("Equipment",),
                                        locality=LOC_FREE, weaponmaster=True),),
                    ops=(Op(OP_WEAPONMASTER, target=0),)),)


def _quick_draw_abilities(table, card: int) -> tuple[Ability, ...]:
    """[Quick-Draw] (819) -- "When you play this, attach it to a Unit you
    control" (819.1.d).

    The other half of the keyword, [Reaction], is a SPEED and is read where
    speeds are read; only the triggered half is an ability. 819.2 makes
    multiple instances do nothing extra, which synthesising exactly one
    already guarantees.

    Not optional: 819.1.d has no "you may". With no friendly unit on the board
    the trigger simply cannot choose a target, and 355.8 keeps it off the Chain
    -- the gear stays at base, unattached, which is the right outcome.
    """
    if not table.has(card, "Quick-Draw"):
        return ()
    return (Ability(TR_PLAY_ME,
                    targets=(TargetSpec(kind=TK_UNIT, who=W_FRIENDLY),),
                    ops=(Op(OP_ATTACH, target=0),)),)


# 816 -- the ability every [Temporary] permanent has while it carries the
# keyword. It is NOT in `abilities_for`: the keyword can be granted to any
# permanent, so the ability belongs to the ROW, not to the card. `chain.fire`
# synthesizes it under `ABIL_TEMPORARY`, and `chain.item_spec` reads it back
# under the same index -- which is why that index must not collide with a real
# ability slot on any card.
ABIL_TEMPORARY = 250
TEMPORARY_ABILITY = Ability(TR_TEMPORARY, ops=(Op(OP_KILL, target=T_SELF),))


# 383.2.a.1 -- "Any additional conditional statement immediately after the
# Condition ... is part of the Trigger Condition and not the Effect": checked
# when the ability would trigger, and NOT again when it resolves. The rule's
# own example is Sona, Harmonious -- bounce her in response and the runes still
# ready. These were transcribed as op conditions, which `resolve` re-checks, so
# a Gutter Palace whose condition was met could lose the game to a Gust in
# response (RiftJudge #11528) and a Fiora - Peerless met by an Ambush unit lost
# her doubling (#11385, #11396, #11551). Hoisted here onto `Ability.cond`, which
# `chain.fire` asks exactly once, as the trigger is placed. Only abilities whose
# conditional ops all share ONE condition qualify; the name list is the audit of
# printed "When/At ..., if ..." texts where that is so.
TRIGGER_CLAUSE_IFS: frozenset[str] = frozenset({
    "Affectionate Poro", "Blighted Battleaxe", "Dropboarder", "Eclipse Dragon",
    "Gutter Palace", "Hextech Gauntlets", "Mushroom Pouch", "Patched Porobot",
    "Poppy - Paragon", "Poro Herder", "Renekton, Rage Fueled",
    "Shen, Leader of the Kinkou Order", "Shen, Scourge of Shadows",
    "Sona, Harmonious", "Swain, Visionary", "Fiora - Peerless",
})


def _hoist_trigger_ifs() -> None:
    for table in (ABILITIES, EQUIP_ABILITIES, BF_ABILITIES, LEGEND_ABILITIES):
        for name in TRIGGER_CLAUSE_IFS & set(table):
            out = []
            for ab in table[name]:
                # COND_CONTROL_N_GEAR keeps its threshold in `floor`.
                conds = {(o.cond, o.level if o.cond != COND_CONTROL_N_GEAR
                          else int(o.floor or 0), o.cond_tag)
                         for o in ab.ops if o.cond}
                if (ab.trigger == TR_ACTIVATED or ab.cond != COND_NONE
                        or len(conds) != 1):
                    out.append(ab)
                    continue
                cond, level, tag = next(iter(conds))
                out.append(ab._replace(
                    cond=cond, cond_level=level, cond_tag=tag,
                    ops=tuple(o._replace(cond=COND_NONE) if o.cond else o
                              for o in ab.ops)))
            table[name] = tuple(out)


_hoist_trigger_ifs()


def abilities_for(table, card: int) -> tuple[Ability, ...]:
    """Every triggered ability printed on a card id.

    Transcribed entries plus the ones synthesised from keywords, so a card with
    [Hunt] and a written ability gets both without the entry repeating what the
    keyword already says.
    """
    return (ABILITIES.get(table.names[card], ())
            + _hunt_abilities(table, card)
            + _disarm_abilities(table, card)
            + _deploy_abilities(table, card)
            + _vision_abilities(table, card)
            + _equip_abilities(table, card)
            + _quick_draw_abilities(table, card)
            + _weaponmaster_abilities(table, card))


# --- Delayed Abilities (389-390) -------------------------------------------
# Keyed by the card that ARMS the ability, like every other bespoke registry
# here. The entry is what fires later, not what the card does on resolution --
# "Draw 1" is Rally the Troops' own effect and stays in `SPECS`.
# Abilities a spell GIVES a unit for a turn, keyed by the spell (Dominus's
# "{any rune}{any rune}: Ready me.").
GRANTED_ABILITIES: dict[str, tuple[Ability, ...]] = {

    # "Units here have 'Exhaust: Gain 1 XP.'" (Gardens of Becoming). Appended
    # to every unit standing on the ground, so an exhausted garrison turns
    # into XP for a legend that spends it.
    "Gardens of Becoming": (
        Ability(TR_ACTIVATED, cost_exhaust=True, ops=(Op(OP_GAIN_XP, n=1),)),
    ),

    # "While you control this battlefield, friendly legends have 'Exhaust:
    # Attach an Equipment you control to a unit you control.'" (Forge of the
    # Fluft). The champion exhausts, which is the cost it always charges, and
    # the gear moves for free.
    "Forge of the Fluft": (
        Ability(TR_ACTIVATED, cost_exhaust=True,
                targets=(TargetSpec(who=W_FRIENDLY),
                         TargetSpec(who=W_FRIENDLY, card_type=("Gear",),
                                    tags=("Equipment",))),
                ops=(Op(OP_ATTACH, target=0, target_b=1),)),
    ),

    # Jax - Unmatched grants [Quick-Draw]'s "when you play this, attach it to a
    # unit you control" (819.1.d) to Equipment played while he is out. The
    # [Reaction] half is a speed the engine does not read for gear at all yet
    # (printed [Quick-Draw] included).
    "Jax - Unmatched": (
        Ability(TR_PLAY_ME, targets=(TargetSpec(kind=TK_UNIT, who=W_FRIENDLY),),
                ops=(Op(OP_ATTACH, target=0),)),
    ),
    "Dominus": (
        Ability(TR_ACTIVATED, cost_power=2, ops=(Op(OP_READY, target=T_SELF),)),
    ),
}


DELAYED_ABILITIES: dict[str, tuple[Ability, ...]] = {
    # [Action] When a friendly unit is played this turn, buff it. Draw 1.
    #
    # 390.2 makes this a Delayed TRIGGER -- a real Triggered Ability with a
    # window, not a continuous effect -- so each firing becomes its own Chain
    # Item and is finalized like any other (355.5.b). Writing it as an
    # immediate buff inside the play path would be a whole priority window
    # cheaper than the card actually is.
    #
    # `T_SUBJECT` is the unit that was just played; `T_SELF` would be the
    # source, and the source here is a spell that is already in the trash.
    #
    # No `subject_card_type` needed -- "Unit" is the default, and every
    # permanent play reaches `fire_play_unit`, gear included.
    "Rally the Troops": (
        Ability(TR_PLAY_UNIT, ops=(Op(OP_BUFF, target=T_SUBJECT),)),
    ),
    "Siphoning Strike": (
        Ability(TR_MARKED_DIES, ops=(Op(OP_CHANNEL, n=1),)),
    ),
    "Deadly Flourish": (
        Ability(TR_MARKED_DIES,
                ops=(Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                        token=GOLD_TOKEN),)),
    ),
    "Grim Resolve": (
        Ability(TR_MARKED_WINS, ops=(Op(OP_GAIN_XP, n=2),)),
    ),
    "Relentless Pursuit": (
        Ability(TR_MARKED_CONQUERS, optional=True,
                ops=(Op(OP_MOVE_TO, target=T_SUBJECT, target_b=T_OWNER_BASE),)),
    ),
    # Nami - Headstrong: "When I hold, the NEXT time you play a unit this turn,
    # ready it and [Buff] it." Armed by her hold trigger; fires once.
    "Nami - Headstrong": (
        Ability(TR_PLAY_UNIT, delayed_once=True,
                ops=(Op(OP_READY, target=T_SUBJECT),
                     Op(OP_BUFF, target=T_SUBJECT))),
    ),
}


def delayed_abilities_for(table, card: int) -> tuple[Ability, ...]:
    """The Delayed Abilities a card arms. The fourth ability table.

    Separate from `ABILITIES` for the reason `BF_ABILITIES` and
    `LEGEND_ABILITIES` are: every permanent-side loop walks a card's abilities
    expecting them to belong to a permanent on the board, and a delayed
    ability belongs to nothing -- its source card is in the trash by the time
    it fires.
    """
    return DELAYED_ABILITIES.get(table.names[card], ())


def legend_abilities_for(table, card: int) -> tuple[Ability, ...]:
    """Every ability printed on a Champion Legend.

    A third table for the third kind of non-permanent source. A legend is a
    Game Object (174) and not a Permanent (175): it has no row, no location and
    no Might, cannot be killed (174.3) and never leaves its zone (107.4.d). So
    it needs the same separation `BF_ABILITIES` needed, and for the same
    reason -- every permanent-side loop reads `perms[w, P_CARD]`.

    Unlike a permanent, a legend may print SEVERAL activated abilities and the
    player picks between them (Kha'Zix charges 1 XP for one and 2 for another),
    so the action carries the ability INDEX rather than taking the first.
    """
    return LEGEND_ABILITIES.get(table.names[card], ())


def legend_statics_for(table, card: int) -> tuple[Static, ...]:
    return LEGEND_STATICS.get(table.names[card], ())


def bf_abilities_for(table, card: int) -> tuple[Ability, ...]:
    """Every triggered ability printed on a BATTLEFIELD card id.

    A separate table and a separate lookup, for the reason `BF_STATICS` is
    separate: a battlefield is not a permanent. Every loop in the engine that
    walks "this permanent's abilities" would otherwise start finding these, and
    the failure would be silent -- a battlefield has no row for `T_SELF` to
    point at, so an op that referenced its source would read permanent 0.
    """
    return BF_ABILITIES.get(table.names[card], ())


def implemented(table) -> list[int]:
    """Card ids with a spec. The v1 spell pool grows by extending SPECS."""
    return [c for c in range(table.n) if table.names[c] in SPECS]


# --- import-time capacity check -------------------------------------------
# `state.MAX_TARGETS` sizes a numpy column, so it cannot be derived from this
# file without inverting the one-way import. What it CAN do is fail here, at
# import, the moment a card is encoded that does not fit -- rather than in an
# assert a thousand fuzz games deep, or worse, in a silent truncation. Forge of
# the Future's four "up to" slots sit exactly at the limit, so the next card
# with five will trip this on the line that adds it.
_WIDEST = max(
    [(s.n_targets, name) for name, s in SPECS.items()]
    + [(a.n_targets, name) for name, abs_ in ABILITIES.items() for a in abs_])
assert _WIDEST[0] <= MAX_TARGETS, (
    f"{_WIDEST[1]} needs {_WIDEST[0]} target slots but state.MAX_TARGETS is "
    f"{MAX_TARGETS}; raise it there (it sizes GameState.chain_targets)")

# `combat.open_showdown` queues ONE Chain Item per (watcher, subject) and
# resolution then runs every TR_ATTACK_OR_DEFEND ability on that source, so the
# trigger-time conditions are decided once for the card as a whole. That is
# exact while a card's attack/defend abilities all agree on them, which every
# card in the pool does. One that disagrees needs the condition carried on the
# Chain Item instead -- a real change, not a tweak, so it fails here rather
# than resolving an ability whose condition was never met.
# The board-wide ops are scoped by `at`/`who`/`except_target` and go through
# `resolve._sweep`, which never reads `target`. Setting it does nothing at all
# -- Anivia was written `target=T_HERE` and swept every battlefield on the
# board, which looks exactly like a correct card until you count the corpses.
_SWEEP_OPS = {OP_DAMAGE_ALL, OP_MODIFY_MIGHT_ALL, OP_KILL_ALL, OP_EXHAUST_ALL,
              OP_GRANT_KEYWORD_ALL, OP_MOVE_ALL_TO_BASE}
for _name, _entry in list(SPECS.items()) + [
        (n, a) for n, abs_ in ABILITIES.items() for a in abs_] + [
        (n, a) for n, abs_ in EQUIP_ABILITIES.items() for a in abs_]:
    for _op in _entry.ops:
        assert not (_op.op in _SWEEP_OPS and _op.target != -1), (
            f"{_name}: {OP_NAMES[_op.op]} is scoped with `at=`, not `target=`; "
            f"`target={_op.target}` here is silently ignored")

# OP_LOOK_TOP suspends resolution: the cards come off the deck and the player
# is asked to pick through `pend_look`, which happens AFTER `resolve` has
# returned. Any op written after it would therefore run before the pick, in the
# wrong order and with the cards still in limbo. Being last is a real
# constraint, not a style rule, so it fails here rather than silently.
for _name, _entry in list(SPECS.items()) + [
        (n, a) for n, abs_ in ABILITIES.items() for a in abs_] + [
        (n, a) for n, abs_ in EQUIP_ABILITIES.items() for a in abs_]:
    for _i, _op in enumerate(_entry.ops):
        if _op.op in (OP_ASK, OP_PLAY_FROM_HAND, OP_REVEAL_PLAY, OP_SPLIT_DAMAGE,
                      OP_PAY_ANY_AMOUNT, OP_PROMISING_FUTURE,
                      OP_DIVINE_JUDGMENT):
            assert _i == len(_entry.ops) - 1, (
                f"{_name}: OP_ASK suspends resolution and must be the last op")
            continue
        if _op.op != OP_LOOK_TOP:
            continue
        assert _i == len(_entry.ops) - 1, (
            f"{_name}: look_top must be the last op -- resolution suspends "
            f"there, so op {_i + 1} would run before the player picks")
        assert 0 < _op.n <= MAX_LOOK, (
            f"{_name}: looks at {_op.n} cards, but state.MAX_LOOK is "
            f"{MAX_LOOK} (it sizes GameState.look_cards)")
        # A type-restricted pick can find nothing matching among the N, and the
        # player must still have a move -- the action layer adds A_PICK_NONE
        # when the filtered list is empty, so every such card must be one whose
        # text actually says "you MAY". Every printed one does.
        assert not (_op.pick_types and not _op.pick_optional), (
            f"{_name}: a type-restricted pick must be optional -- there may "
            f"be no card of that type among the {_op.n}")

# Zilean's replacement is OFFERED after the resolving card finishes, which is
# only equivalent to offering it at the moment of creation while a token op is
# its card's LAST -- otherwise the extra copy would arrive after effects that
# the printed card puts before it. Every entry satisfies this today; the one
# that does not should fail here rather than reorder a card silently.
for _name, _entry in list(SPECS.items()) + [
        (n, a) for n, abs_ in ABILITIES.items() for a in abs_] + [
        (n, a) for n, abs_ in EQUIP_ABILITIES.items() for a in abs_]:
    for _i, _op in enumerate(_entry.ops):
        assert not (_op.op == OP_CREATE_TOKEN and _i != len(_entry.ops) - 1
                    and _op.token not in NON_UNIT_TOKENS), (
            f"{_name}: create_token must be the last op while the token-doubler "
            f"replacement is deferred (see TOKEN_DOUBLERS)")
# This caught Guards! -- "Play a 2 Might Sand Soldier unit token. You may pay
# {Order rune} to ready it." Both Zilean's doubling and that optional cost
# defer off the same token creation, so they would queue together and
# "ready IT" stops being answerable: one token or both? Two interacting
# deferred decisions is real work, and the card is 2 deck slots, so it is
# left uncovered rather than approximated.

# Costs are read at finalization and ONLY for TR_ACTIVATED (204.1.b -- a base
# cost is what stands before the ':'). A triggered ability that carries one is
# 383.3.b's "cost within instructions" -- Overzealous Fan's "you may kill me to
# move an attacking unit", Ekko's "Recycle me to ready your runes" -- which
# nothing implements yet. Setting a cost field on one is silently ignored: the
# ability would resolve and the cost would never be paid, which reads as a
# strictly better card.
for _name, _abs in ABILITIES.items():
    for _a in _abs:
        if _a.trigger == TR_ACTIVATED:
            continue
        assert not (_a.cost_energy or _a.cost_power or _a.cost_exhaust
                    or _a.cost_kill_self or _a.cost_xp), (
            f"{_name}: a triggered ability carries a cost, which only "
            f"TR_ACTIVATED pays (383.3.b is not implemented)")

# `might` reads every ST_MIGHT static, so a Might static COUNTING Might would
# recurse forever. These counts are for cost discounts only.
for _name, _sts in STATICS.items():
    for _st in _sts:
        assert not (_st.kind == ST_MIGHT and _st.per in (
            CNT_MIGHTY, CNT_HIGHEST_MIGHT)), (
            f"{_name}: a Might static cannot count Might")

# `subject_min_energy` is filtered where TR_PLAY_SPELL is QUEUED (the only
# place the spell is known), so it decides for the whole card at once.
for _name, _abs in ABILITIES.items():
    _ps = [a for a in _abs if a.trigger == TR_PLAY_SPELL]
    assert len({a.subject_min_energy for a in _ps}) <= 1, (
        f"{_name}: play-spell abilities with different cost thresholds")

for _name, _abs in ABILITIES.items():
    _ad = [a for a in _abs if a.trigger == TR_ATTACK_OR_DEFEND]
    assert len({(a.subject_alone, a.subject_role, a.subject_any_friendly)
                for a in _ad}) <= 1, (
        f"{_name} has attack/defend abilities with different trigger-time "
        f"conditions; open_showdown cannot queue them separately")


# --- follow-up op lists (see `Op.then_key`) --------------------------------
# Filled in after the module body so they can use the same Op vocabulary the
# cards do. Index order must match the FU_* constants above.
FOLLOWUPS[FU_DIANA_REVEAL] = (
    Op(OP_LOOK_TOP, reveal=LOOK_REVEAL_ALL, n=1, pick_optional=True, pick_types=("Spell",),
       pick_dest=DEST_HAND, rest_dest=DEST_TOP),
)

# "...then draw 1." The plainest follow-up there is, and it exists because
# ORDER is the whole point: a draw written as a second op runs before the
# player has chosen what to pitch, which lets the card they just drew be the
# card they discard.
FOLLOWUPS[FU_DRAW_1] = (Op(OP_DRAW, n=1),)
# [FU_THEY_DRAW_1] "...they discard that card AND DRAW 1" (Insightful
# Investigator). `who=W_ENEMY` because a follow-up runs for the CHOOSER, and
# the card that was discarded was not theirs -- the compensation goes to the
# player who lost the card, which is what makes this a tempo play rather than
# pure card advantage.
FOLLOWUPS[FU_THEY_DRAW_1] = (Op(OP_DRAW, n=1, who=W_ENEMY),)
# [FU_DRAW_2] Clairvoyance: "[Predict 5]. Draw 2." The draw comes AFTER the
# Predict, off whatever was put back on top.
FOLLOWUPS[FU_DRAW_2] = (Op(OP_DRAW, n=2),)
# [FU_DRAW_1_XP_1] Scryer's Bloom: "[Predict 2], then draw 1. Gain 1 XP."
FOLLOWUPS[FU_DRAW_1_XP_1] = (Op(OP_DRAW, n=1), Op(OP_GAIN_XP, n=1))
# Shakedown: "Deal 6 to it unless its controller has you draw 2."
FOLLOWUPS[FU_DAMAGE_SUBJECT_6] = (Op(OP_DAMAGE, target=T_SUBJECT, n=6),)
# Card Sharp: "you and each opponent may play a Gold gear token exhausted. For
# each opponent who did, you play a Gold gear token exhausted." You answer
# first (FU_CARD_SHARP_*), then the opponent (FU_GOLD_BOTH on yes).
FOLLOWUPS[FU_GOLD_ME] = (Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                            token=GOLD_TOKEN),)
FOLLOWUPS[FU_GOLD_BOTH] = (Op(OP_CREATE_TOKEN, n=1, token=GOLD_TOKEN,
                              who=W_ENEMY),
                           Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1,
                              token=GOLD_TOKEN))
FOLLOWUPS[FU_CARD_SHARP_ASK_OPP] = (Op(OP_ASK, then_key=FU_GOLD_BOTH),)
FOLLOWUPS[FU_CARD_SHARP_MINE_THEN_OPP] = (
    Op(OP_CREATE_TOKEN, target=T_MY_BASE, n=1, token=GOLD_TOKEN),
    Op(OP_ASK, then_key=FU_GOLD_BOTH))
# Party Favors: Cards (yes) -> you and they each draw 1; Runes (no) -> you and
# they each channel 1 rune exhausted.
FOLLOWUPS[FU_BOTH_DRAW_1] = (Op(OP_DRAW, n=1, each_player=True),)
FOLLOWUPS[FU_BOTH_CHANNEL_1] = (Op(OP_CHANNEL, n=1, each_player=True),)
# Keeper's Verdict: its owner places it on the top (yes) or bottom (no).
FOLLOWUPS[FU_SUBJECT_TO_TOP] = (Op(OP_TO_DECK, target=T_SUBJECT,
                                   pick_dest=DEST_TOP),)
FOLLOWUPS[FU_SUBJECT_TO_BOTTOM] = (Op(OP_TO_DECK, target=T_SUBJECT,
                                      pick_dest=DEST_RECYCLE),)
# Ivern - Nurturer: "Then if you revealed a Bird, Cat, Dog, or Poro, do this:
# [Buff] a friendly unit." -- its own Chain Item, for the choice.
FOLLOWUPS[FU_IVERN] = (Op(OP_QUEUE_FOLLOWUP, cond=COND_PICKED_ANIMAL),)
# Guards!: "Then do this: You may pay {Order rune} to ready it." Asked of the
# token's controller only when the rune can be paid.
FOLLOWUPS[FU_GUARDS_READY] = (Op(OP_ASK, target=T_LAST_TOKEN, power=1, domain=5,
                                 then_key=FU_GUARDS_PAY),)
FOLLOWUPS[FU_GUARDS_PAY] = (Op(OP_PAY_POWER, n=1, domain=5),
                            Op(OP_READY, target=T_SUBJECT))
FOLLOWUPS[FU_BECOME_COPY] = (Op(OP_BECOME_COPY),)
FOLLOWUPS[FU_GRENADE_REPLAY] = (Op(OP_REPLAY_CARD, target=T_SUBJECT, power=1),)
FOLLOWUPS[FU_BECOME_COPY_TEMP] = (Op(OP_BECOME_COPY, keyword="Temporary"),)


# --- behaviour features, for the observation encoder ------------------------
# `obs.py` encodes a card as its **attributes, never its id** (PLAN.md §5.2), so
# that a card the net never saw still gets a usable embedding. Stats, type,
# domains and keywords carried that alone -- and they describe the card's BODY,
# not what it DOES. Everything a card's rules text does was therefore invisible:
# 937 cards produced 642 distinct rows, and all 66 battlefields -- whose entire
# content IS rules text, with no energy, power or might to tell them apart --
# collapsed to 3.
#
# This block derives features from the SCRIPTED ABILITY ITSELF: which triggers
# it watches, which ops it runs, what its statics grant. That keeps the rule
# intact -- these are still attributes, just attributes of behaviour rather than
# of the stat line -- and it is self-maintaining, because a card scripted
# tomorrow becomes visible the moment its entry lands, with no table to update.
#
# **The visibility a card gets is exactly the behaviour that is encoded.** An
# unscripted card scores all zeros here and is still aliased against every other
# unscripted card, which is correct: the engine does not run its text either, so
# there is genuinely nothing to see. `has_scripted` is the one bit that says
# which of the two a zero row is -- a vanilla body, or text nothing executes.

# A LEGEND CANNOT HOLD THE EMPOWERED STATUS YET, and the gap is loud here
# rather than silent at the offer site. 174/175 make a legend a Game Object but
# not a Permanent: it has no row, so there is nowhere to put `P_EMPOWER`, and
# `chain.fire_empowered` walks `state.perms` and would never see it.
#
# Two cards in the pool need this and neither is scripted: Ambessa - Matriarch
# of War ("when you empower something else, empower me" -- printed on a LEGEND)
# and Profiteer ("empower a legend, unit, or gear", which also needs a target
# kind that can name one). Both want per-legend status storage, which is a
# state change rather than a card.
#
# `actions._activate`'s legend branch does not check `cost_disempower_self`,
# so an entry using it would be offered while unpayable. This refuses at
# import instead of failing in a game.
for _n, _abs in LEGEND_ABILITIES.items():
    for _a in _abs:
        assert not _a.cost_spend_buff_self, f"{_n}: a legend has no Buff"
        # [Empower] on a legend works now: `state.legend_emp` holds the status
        # (441 applies it to any Game Object), `chain.fire_empowered` asks the
        # champion after the board, and both activation paths pay a
        # "Disempower me" cost. What a legend still cannot do is hold a BUFF,
        # which is a counter on a permanent (702).
        assert not any(_o.op in (OP_EMPOWER, OP_DISEMPOWER) and _o.target >= 0
                       for _o in _a.ops), (
            f"{_n}: a legend may only empower ITSELF -- an op with a target "
            f"slot reads `perms` and a legend has no row.")

# A token UNIT played to a chosen location follows 806.3 like any unit: your
# base or a battlefield you CONTROL (Recruit the Vanguard's reminder text says
# so). Seven token spells chose their slot as a plain friendly location, which
# offered uncontrolled and enemy battlefields too. Normalised here so a new
# token card cannot reintroduce it.
def _token_slots_are_play_destinations(spec):
    tg = list(getattr(spec, "targets", ()) or ())
    changed = False
    for _o in getattr(spec, "ops", ()) or ():
        if (_o.op == OP_CREATE_TOKEN and 0 <= _o.target < len(tg)
                and tg[_o.target].kind == TK_LOCATION
                and not tg[_o.target].play_destination):
            tg[_o.target] = tg[_o.target]._replace(play_destination=True)
            changed = True
    spec = spec._replace(targets=tuple(tg)) if changed else spec
    if getattr(spec, "modes", ()):
        spec = spec._replace(modes=tuple(_token_slots_are_play_destinations(m)
                                         for m in spec.modes))
    return spec


for _n in list(SPECS):
    SPECS[_n] = _token_slots_are_play_destinations(SPECS[_n])
for _d in (ABILITIES, BF_ABILITIES, LEGEND_ABILITIES, EQUIP_ABILITIES):
    for _n in list(_d):
        _d[_n] = tuple(_token_slots_are_play_destinations(_a) for _a in _d[_n])

# `actions._activate` opens `pend_cost_kill` OR `pend_cost_recycle`, and each
# continues straight to targets/finalization when paid -- so an ability owing
# BOTH would pay one and skip the other. The immediate path and the legend path
# pay neither. No card needs any of those combinations; this keeps a future one
# from being offered at a discount instead of failing loudly.
for _n, _abs in list(ABILITIES.items()) + list(LEGEND_ABILITIES.items()):
    for _a in _abs:
        if not _a.cost_recycle_trash:
            continue
        assert _a.cost_kill is None, (
            f"{_n}: a kill cost AND a recycle cost -- `_activate` sequences one")
        assert not _a.immediate, (
            f"{_n}: an immediate ability never stops to pay a recycle cost")
        assert _n not in LEGEND_ABILITIES, (
            f"{_n}: the legend activation path does not pay recycle costs")

_assert_equip_tables_disjoint()

# Every modal entry fits the action row's mode one-hot (obs.MAX_MODES) and the
# Chain's target slots once composed.
for _n, _entry in list(SPECS.items()) + [
        (n, a) for n, abs_ in ABILITIES.items() for a in abs_]:
    if _entry.modes:
        # Curtain Call's modes are its [Repeat] combinations (21); only the
        # first four reach the one-hot, which the card is exempt from.
        assert len(_entry.modes) <= 4 or _entry.mode_costs, f"{_n}: more than 4 modes"
        for _m in range(len(_entry.modes)):
            assert compose_mode(_entry, _m).n_targets <= MAX_TARGETS, (
                f"{_n}: mode {_m} needs more than {MAX_TARGETS} slots")

_N_TRIGGERS = len(TRIGGER_NAMES)
_N_OPS = len(OP_NAMES)
_N_ST = len(ST_NAMES)
_N_SCOPE = 3

# 3 counts + triggers + ops + static kinds + static scopes
# + 2 static magnitudes + 2 static shape bits
# + 5 activation costs + optional + targets + enemy-target + is_bf
ABIL_DIM = 3 + _N_TRIGGERS + _N_OPS + _N_ST + _N_SCOPE + 2 + 2 + 5 + 1 + 1 + 1 + 1


def _clip(x: float, lo: float = -2.0, hi: float = 2.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ability_features(name: str) -> list[float]:
    """[ABIL_DIM] behaviour attributes for one card, by name.

    Every card in the pool goes through here, scripted or not -- an unscripted
    one simply comes back all zeros. Magnitudes are scaled to roughly unit range
    and clipped, since a single outlier column would otherwise dominate the
    embedding's input scale.
    """
    bf_abils = BF_ABILITIES.get(name, ())
    abils = ABILITIES.get(name, ()) + bf_abils
    bf_statics = BF_STATICS.get(name, ())
    all_statics = STATICS.get(name, ()) + bf_statics
    on_bf = bool(bf_abils or bf_statics)

    v = [0.0] * ABIL_DIM
    if not abils and not all_statics:
        return v

    o = 0
    v[o] = 1.0                                    # has_scripted
    v[o + 1] = _clip(len(abils) / 3.0)
    v[o + 2] = _clip(len(all_statics) / 3.0)
    o += 3

    for a in abils:
        v[o + a.trigger] = 1.0
    o += _N_TRIGGERS

    for a in abils:
        # A modal ability's ops live in its modes ("Choose one --").
        for op in a.ops + tuple(o_ for m in a.modes for o_ in m.ops):
            v[o + op.op] = 1.0
    o += _N_OPS

    for s in all_statics:
        v[o + s.kind] = 1.0
    o += _N_ST

    for s in all_statics:
        v[o + s.scope] = 1.0
    o += _N_SCOPE

    # Signed on purpose: a static that SUBTRACTS Might (Vex's aura) is the
    # opposite card from one that adds it, and a magnitude-only column would
    # make the two identical.
    might_n = [s.n for s in all_statics if s.kind == ST_MIGHT]
    disc_n = [s.n for s in all_statics if s.kind == ST_COST_ENERGY]
    v[o] = _clip(max(might_n, key=abs) / 3.0) if might_n else 0.0
    v[o + 1] = _clip(max(disc_n, key=abs) / 3.0) if disc_n else 0.0
    o += 2

    # A scaled static is a different kind of number from a flat one -- it grows
    # with the board or a trash and cannot be read off the card -- and a gated
    # one may contribute nothing at all right now.
    v[o] = float(any(s.per != CNT_NONE or s.per_keyword is not None
                     for s in all_statics))
    v[o + 1] = float(any(s.cond != COND_NONE for s in all_statics))
    o += 2

    act = [a for a in abils if a.trigger == TR_ACTIVATED]
    if act:
        v[o] = _clip(max(a.cost_energy for a in act) / 3.0)
        v[o + 1] = _clip(max(a.cost_power for a in act) / 3.0)
        v[o + 2] = float(any(a.cost_exhaust for a in act))
        v[o + 3] = float(any(a.cost_kill_self for a in act))
        v[o + 4] = _clip(max(a.cost_xp for a in act) / 5.0)
    o += 5

    v[o] = float(any(a.optional for a in abils))
    o += 1
    v[o] = _clip(max((len(a.targets) for a in abils), default=0) / 3.0)
    o += 1
    v[o] = float(any(t.who == W_ENEMY for a in abils for t in a.targets))
    o += 1
    # A battlefield's abilities come from tables of their own: its statics
    # reach BOTH players' units standing there, and its triggers fire once for
    # a player rather than once per permanent. Neither is true of anything
    # printed on a card that goes to the board.
    v[o] = float(on_bf)
    o += 1

    assert o == ABIL_DIM, f"{o} != {ABIL_DIM}"
    return v
