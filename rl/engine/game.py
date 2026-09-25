"""Game setup and the driver loop.

`play_game` is the only thing that advances a game, so the fuzz gate, the
baselines, and the gym wrapper all share one control flow. An agent is any
callable `(state, table, cfg, seat, actions) -> Action`.

The loop asks whichever seat `acting_seat` names. A seat with an empty action
list is not being asked; an empty list for the seat that *is* to act is a
deadlock, and `invariants.check_actions` fails loudly on it rather than letting
the game spin to the turn cap.
"""

from __future__ import annotations

import numpy as np

from rl.config import DOMAINS, Config
from rl.engine import actions as A
from rl.engine import invariants, phases
# Setup constants and the Mulligan live in `phases`: `actions` needs them
# and `game` imports `actions`, so keeping them here made a real import
# cycle that only worked by luck of import order. Re-exported so the
# existing call sites keep working.
from rl.engine.phases import (MULLIGAN_MAX, STARTING_HAND,  # noqa: F401
                              mulligan)
from rl.engine.cardtable import CardTable
from rl.engine.state import MAX_DECK, N_DOMAINS, N_SEATS, RUNE_RING, GameState



def deck_knowledge(cfg: Config, seed: int) -> list[int]:
    """Which seats' registered decklists are known to the opponent, per episode.

    Derived from the episode seed rather than dealt, so every existing
    `deal_fn` keeps its signature and a replay reproduces the match context
    along with the shuffle.

    **Shared with the engine-side paths on purpose.** `deck_known` is inert to
    the rules -- nothing in `actions`, `resolve` or `combat` reads it -- but it
    is in `state_hash` because it is part of the position the *policy* sees.
    So the env and `fuzz.make_game` have to derive it identically or test_env's
    equivalence check fails on a difference that is not a wrapper bug.
    """
    rng = np.random.default_rng((int(seed), 0x9E3779B9))
    return [int(rng.random() < cfg.deck_known_prob) for _ in range(N_SEATS)]


def new_game(table: CardTable, cfg: Config, decks: list[list[int]],
             rune_decks: list[list[int]], battlefields: list[int],
             seed: int = 0, mulligan_choices=None,
             legends: list[int] | None = None,
             champions: list[int] | None = None,
             deck_known: list[int] | None = None) -> GameState:
    """Deal a game. `decks` are card ids, `rune_decks` are domain ids.

    Battlefields start **uncontrolled**: each player picked one (486.5) but
    neither has units there, and 190.4.c is unambiguous that Control requires
    Units. The opening position therefore has two free points on the table,
    which is most of why the first few turns are a race rather than a setup.

    `legends` is each seat's Champion Legend (111), placed in the Legend Zone
    before the first turn and never leaving it. Optional, and -1 per seat when
    omitted: a caller dealing a random pool has no decklist to take one from,
    and a game with no legend is a legal game with one fewer ability.

    `champions` is each seat's Chosen Champion (103.2.a), the 40th registered
    card, which 133.4 starts in the Champion Zone rather than the Main Deck --
    which is why `decks` is 39 cards and not 40. Optional for the same reason
    as `legends`: a random pool has no decklist, so no Chosen Champion.

    `deck_known[seat]` says whether THIS seat's registered decklist is known to
    its opponent -- the Bo3 game-2 case. Defaults to nobody knowing anything
    beyond what the rules make public.
    """
    s = GameState()
    s.rng = np.random.default_rng(seed)
    # 194.3, and the curriculum's annealed value rather than the rulebook's --
    # cards that read the Victory Score must read the game being played.
    s.victory_score = int(cfg.victory_score)

    for seat in range(N_SEATS):
        deck = list(decks[seat])
        # Registered before the shuffle, because that is what a decklist is.
        # Kept because `deck` stops being one the moment cards are drawn --
        # see `GameState.decklist`.
        assert len(deck) <= MAX_DECK, "deck larger than MAX_DECK"
        s.n_decklist[seat] = len(deck)
        s.decklist[seat, :len(deck)] = deck
        s.rng.shuffle(deck)
        s.n_deck[seat] = len(deck)
        s.deck[seat, :len(deck)] = deck

        runes = list(rune_decks[seat])
        s.rng.shuffle(runes)
        assert len(runes) <= RUNE_RING, "rune deck larger than the ring buffer"
        s.rune_deck[seat, :len(runes)] = runes
        s.rune_head[seat] = 0
        s.rune_left[seat] = len(runes)

    for i, bf in enumerate(battlefields):
        s.bf_card[i] = bf
        # "Increase the points needed to win the game by 1" (Aspirant's
        # Climb) -- read as the battlefields are laid out, because it changes
        # the game's Victory Score rather than anything on the board.
        from rl.engine.effects import BF_SCORE_RULES
        _rule = BF_SCORE_RULES.get(table.names[bf], {})
        s.victory_bonus += int(_rule.get("victory_plus", 0))

    # 111 -- each player separates their Champion Legend into the Legend Zone.
    # Ready to begin with: 174.2.b establishes it at the start of the game, and
    # nothing has exhausted it yet.
    for seat in range(N_SEATS):
        if legends is not None and seat < len(legends):
            s.legend[seat] = int(legends[seat])
    s.legend_ready[:] = 1

    # 112 -- and each player separates their Chosen Champion into the Champion
    # Zone. 103.2 counts it in the 40-card Main Deck but 133.4 starts it here,
    # so `decks` holding 39 and this holding the 40th is one deck, not a card
    # short of one. Public to BOTH players (108.3.e), which together with the
    # Legend is the whole pre-game archetype: you know what your opponent is
    # playing before a single card is drawn.
    #
    # **108.3.d -- "can be played from here as normal" -- is NOT implemented.**
    # Every play path takes a hand index, so a second source zone is a real
    # feature and not a line of wiring. Until it lands the Chosen Champion is
    # public information the policy conditions on and a card neither player can
    # cast, which understates every deck by one guaranteed threat. Recorded as
    # an engine gap in `rl/docs/PLAN.md`, not in `PARTIAL_TRANSCRIPTIONS` -- that set
    # withholds cards whose own TEXT is unscripted, and there is nothing wrong
    # with these cards' text. What is missing is a zone.
    for seat in range(N_SEATS):
        if champions is not None and seat < len(champions):
            # Zone occupancy and registered identity start equal; 108.3.d lets
            # the first be spent while the second is a fact about the deck.
            s.champion[seat] = int(champions[seat])
            s.champion_reg[seat] = int(champions[seat])

    # 103.1.b.2 -- a Legend fixes the deck's Domain Identity, and the Legend
    # Zone is Public (355.10.a.1), so *some* knowledge of the opponent's deck
    # is unconditional. `deck_known` is the stronger claim on top of that: the
    # full 40-card list, as in a match after game 1.
    if deck_known is not None:
        for seat in range(N_SEATS):
            s.deck_known[seat] = int(bool(deck_known[seat]))

    s.active = 0
    s.turn = 1
    for seat in range(N_SEATS):
        s.active = seat
        phases.draw(s, STARTING_HAND)
    s.active = 0

    # 117 -- the Mulligan happens in turn order, before the first turn begins,
    # and it is a real DECISION: "up to two" is a choice about a quarter of the
    # opening hand. So `new_game` stops here and hands the first decision to
    # the First Player; `actions._finish_mulligan` starts the turn once both
    # players are done (118).
    #
    # `mulligan_choices` short-circuits that for tests and for any caller that
    # wants a ready-to-play state.
    if mulligan_choices is None:
        s.pend_mull = 0
        return s
    for seat in range(N_SEATS):
        keep = mulligan_choices[seat]
        if keep:
            mulligan(s, seat, keep)
    phases.start_turn(s, table, cfg)
    # `start_turn` SUSPENDS if anything triggered in the Beginning Step (315.2),
    # and it is `_settle` that puts those triggers on the Chain and hands out
    # priority. Every other caller reaches it through `actions.apply`; this one
    # does not, and without this the state came back mid-Beginning-Phase with a
    # queued trigger and NO legal actions -- a deadlock rather than a game.
    # The Arena's Greatest fires on turn 1, so it is reachable from a plain
    # deal, not just a contrived one.
    A._settle(s, table, cfg)
    return s




def random_agent(rng: np.random.Generator):
    def choose(state, table, cfg, seat, actions):
        return actions[int(rng.integers(len(actions)))]
    return choose


def play_game(table: CardTable, cfg: Config, state: GameState, agents,
              check: bool = False, max_steps: int = 20000) -> dict:
    """Run to termination. Returns a summary dict.

    `check` turns on the invariant suite -- a few array ops per step, so it is
    off for training and on for the fuzz gate.
    """
    steps = 0
    while not A.is_terminal(state):
        seat = A.acting_seat(state)
        if seat < 0:
            break
        legal = A.legal_actions(state, table, cfg, seat)
        if check:
            invariants.check(state)
            invariants.check_actions(state, table, cfg, seat, legal)
        if not legal:
            # The seat to act has nothing to do; the position is stuck. Only
            # reachable if the enumerator regressed, and `check_actions` above
            # would already have fired when checking is on.
            raise invariants.InvariantError(
                f"seat {seat} to act with no legal actions on turn {state.turn}")
        A.apply(state, table, cfg,
                agents[seat](state, table, cfg, seat, legal))
        steps += 1
        if steps > max_steps:
            raise RuntimeError(f"game exceeded {max_steps} steps")

    return {
        "winner": int(state.winner),
        "truncated": bool(state.truncated),
        "turns": int(state.turn),
        "steps": steps,
        "points": state.points.tolist(),
        "hash": state.state_hash(),
    }
