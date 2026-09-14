"""deterministic game transitions; callers persist only successful transitions."""

from copy import deepcopy
from dataclasses import asdict
from random import SystemRandom

from ofc.rules import DECK, ROWS, RuleError, Rules, next_fantasy, settle


def new_game(owner, name, rules):
    if not name.strip():
        raise RuleError("game name cannot be empty")
    return {
        "name": name,
        "owner": owner,
        "rules": asdict(rules),
        "members": [owner],
        "version": 0,
        "hand_number": 0,
        "button": 0,
        "fantasy": {},
        "hand": None,
    }


def start_hand(game, actor, players, deck=None):
    if actor != game["owner"]:
        raise RuleError("only the owner may start a hand")
    if game["hand"] and game["hand"]["status"] != "complete":
        raise RuleError("a hand is already running")
    rules = Rules(**game["rules"])
    if not 2 <= len(players) <= rules.capacity or len(set(players)) != len(players):
        raise RuleError("invalid active player count")
    if any(p not in game["members"] for p in players):
        raise RuleError("active players must be game members")
    # membership order fixes the seat order across hands and sit-outs.
    players = [p for p in game["members"] if p in players]
    available = list(DECK if deck is None else deck)
    if len(available) != 52 or set(available) != set(DECK):
        raise RuleError("deck must be a permutation of 52 cards")
    if deck is None:
        SystemRandom().shuffle(available)
    fantasies = {p: game["fantasy"].get(p, 0) for p in players}
    required = sum(
        fantasies[p] or (17 if rules.variant == "pineapple" else 13) for p in players
    )
    if required > 52:
        raise RuleError("rules and fantasyland awards exceed deck capacity")
    hand = {
        "number": game["hand_number"] + 1,
        "status": "playing",
        "players": players,
        "deck": available,
        "boards": {p: {r: [] for r in ROWS} for p in players},
        "draws": {},
        "discards": {p: [] for p in players},
        "fantasy": fantasies,
        "queue": [],
        "result": None,
    }
    # fantasy boards are committed before normal play but stay hidden until showdown.
    normal = [p for p in players if not fantasies[p]]
    button = game["button"] % len(game["members"])
    ordered = game["members"][button + 1 :] + game["members"][: button + 1]
    normal = [p for p in ordered if p in normal]
    for p in players:
        if fantasies[p]:
            hand["queue"].append({"player": p, "draw": fantasies[p], "keep": 13})
    for street in range(5 if rules.variant == "pineapple" else 9):
        for p in normal:
            draw, keep = (
                (5, 5)
                if street == 0
                else ((3, 2) if rules.variant == "pineapple" else (1, 1))
            )
            hand["queue"].append({"player": p, "draw": draw, "keep": keep})
    game["hand"] = hand
    game["hand_number"] += 1
    _deal_turn(hand)


def _deal_turn(hand):
    turn = hand["queue"][0]
    n = turn["draw"]
    if len(hand["deck"]) < n:
        raise RuleError("deck exhausted")
    hand["draws"][turn["player"]] = hand["deck"][:n]
    del hand["deck"][:n]


def place(game, actor, placements, discards):
    hand = game["hand"]
    if not hand or hand["status"] != "playing":
        raise RuleError("no active hand")
    turn = hand["queue"][0]
    if actor != turn["player"]:
        raise RuleError("not your turn")
    if set(placements) - set(ROWS):
        raise RuleError("unknown row")
    played = [c for cards in placements.values() for c in cards]
    submitted = played + discards
    if (
        len(played) != turn["keep"]
        or len(submitted) != len(set(submitted))
        or set(submitted) != set(hand["draws"][actor])
    ):
        raise RuleError("place the required cards and discard the rest of your draw")
    for row, cards in placements.items():
        if len(hand["boards"][actor][row]) + len(cards) > ROWS[row]:
            raise RuleError("row capacity exceeded")
    for row, cards in placements.items():
        hand["boards"][actor][row].extend(cards)
    hand["discards"][actor].extend(discards)
    hand["draws"][actor] = []
    hand["queue"].pop(0)
    if hand["queue"]:
        _deal_turn(hand)
    else:
        rules = Rules(**game["rules"])
        result = settle(hand["boards"], rules)
        hand["result"] = result
        hand["status"] = "complete"
        for p, evaluation in result["evaluations"].items():
            game["fantasy"][p] = next_fantasy(
                evaluation, rules, bool(hand["fantasy"][p])
            )
        # hold the button while an active player has earned another fantasy hand.
        if not any(game["fantasy"].get(p) for p in hand["players"]):
            game["button"] = (game["button"] + 1) % len(game["members"])


def transition(game, actor, command):
    """return a new state, leaving the original untouched on any error."""
    state = deepcopy(game)
    kind = command.get("type")
    if kind == "join":
        if actor in state["members"]:
            raise RuleError("already a member")
        state["members"].append(actor)
    else:
        if actor not in state["members"]:
            raise RuleError("not a member")
        if kind == "start":
            start_hand(state, actor, command["players"])
        elif kind == "place":
            place(state, actor, command["placements"], command["discards"])
        else:
            raise RuleError("unknown command")
    state["version"] += 1
    return state


def public_view(game, actor):
    if actor not in game["members"]:
        raise RuleError("not a member")
    view = deepcopy(game)
    hand = view["hand"]
    if hand:
        hand.pop("deck")
        hand["draws"] = {actor: hand["draws"].get(actor, [])}
        hand["discards"] = {actor: hand["discards"].get(actor, [])}
        hand["turn"] = hand["queue"][0] if hand["queue"] else None
        hand.pop("queue")
        if hand["status"] != "complete":
            for p in hand["players"]:
                if p != actor and hand["fantasy"][p]:
                    hand["boards"][p] = {r: [] for r in ROWS}
    return view
