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
        "normal_hands": 0,
        "orbit_size": None,
        "status": "active",
        "button": 0,
        "fantasy": {},
        "hand": None,
    }


def start_hand(game, actor, players, deck=None):
    if actor != game["owner"]:
        raise RuleError("only the owner may start a hand")
    if game.get("status") == "complete":
        raise RuleError("orbit limit reached; this game is complete")
    if game["hand"] and game["hand"]["status"] != "complete":
        raise RuleError("a hand is already running")
    rules = Rules(**game["rules"])
    if not 2 <= len(players) <= rules.capacity or len(set(players)) != len(players):
        raise RuleError("invalid active player count")
    if any(p not in game["members"] for p in players):
        raise RuleError("active players must be game members")
    if rules.orbits and any(
        game["fantasy"].get(p) and p not in players for p in game["members"]
    ):
        raise RuleError("include players with pending fantasyland before continuing")
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
    if game.get("orbit_size") is None:
        game["orbit_size"] = len(players)
    # the dealer must occupy an active seat, even when members are sitting out.
    button = game["button"] % len(game["members"])
    seats = game["members"][button:] + game["members"][:button]
    dealer = next(p for p in seats if p in players)
    button = game["members"].index(dealer)
    game["button"] = button
    hand = {
        "number": game["hand_number"] + 1,
        "dealer": dealer,
        "status": "playing",
        "players": players,
        "deck": available,
        "boards": {p: {r: [] for r in ROWS} for p in players},
        "draws": {},
        "discards": {p: [] for p in players},
        "fantasy": fantasies,
        "queue": [],
        "fantasy_pending": [p for p in players if fantasies[p]],
        "result": None,
    }
    # fantasy submissions run independently of the normal turn queue.
    normal = [p for p in players if not fantasies[p]]
    ordered = game["members"][button + 1 :] + game["members"][: button + 1]
    normal = [p for p in ordered if p in normal]
    for p in players:
        if fantasies[p]:
            _deal_draw(hand, {"player": p, "draw": fantasies[p]})
    for street in range(5 if rules.variant == "pineapple" else 9):
        for p in normal:
            draw, keep = (
                (5, 5)
                if street == 0
                else ((3, 2) if rules.variant == "pineapple" else (1, 1))
            )
            hand["queue"].append(
                {"player": p, "draw": draw, "keep": keep, "street": street}
            )
    game["hand"] = hand
    game["hand_number"] += 1
    if hand["queue"]:
        _deal_turn(hand)


def _deal_turn(hand):
    first = hand["queue"][0]
    # reserve the current street in seat order, before anyone confirms.
    # older saved hands lack street markers and retain their original dealing.
    turns = hand["queue"] if "street" in first else [first]
    for turn in turns:
        if turn.get("street") != first.get("street"):
            break
        if not hand["draws"].get(turn["player"]):
            _deal_draw(hand, turn)


def _deal_draw(hand, turn):
    n = turn["draw"]
    if len(hand["deck"]) < n:
        raise RuleError("deck exhausted")
    hand["draws"][turn["player"]] = hand["deck"][:n]
    del hand["deck"][:n]


def place(game, actor, placements, discards):
    hand = game["hand"]
    if not hand or hand["status"] != "playing":
        raise RuleError("no active hand")
    independent = actor in hand.get("fantasy_pending", [])
    turn = (
        {"player": actor, "keep": 13}
        if independent
        else (hand["queue"][0] if hand["queue"] else None)
    )
    if turn is None or actor != turn["player"]:
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
    if independent:
        hand["fantasy_pending"].remove(actor)
    else:
        hand["queue"].pop(0)
        if hand["queue"]:
            _deal_turn(hand)
    if not hand["queue"] and not hand.get("fantasy_pending"):
        _finish_hand(game)


def _finish_hand(game):
    hand = game["hand"]
    rules = Rules(**game["rules"])
    result = settle(hand["boards"], rules)
    hand["result"] = result
    hand["status"] = "complete"
    for p, evaluation in result["evaluations"].items():
        game["fantasy"][p] = next_fantasy(evaluation, rules, bool(hand["fantasy"][p]))
    if not any(hand["fantasy"].values()):
        game["normal_hands"] = game.get("normal_hands", 0) + 1
    update_completion(game)
    # hold the button while an active player has earned another fantasy hand.
    if not any(game["fantasy"].get(p) for p in hand["players"]):
        dealer = hand.get("dealer", game["members"][game["button"]])
        active = hand["players"]
        if dealer not in active:
            dealer = active[0]
        next_dealer = active[(active.index(dealer) + 1) % len(active)]
        game["button"] = game["members"].index(next_dealer)


def update_completion(game):
    limit = game["rules"].get("orbits")
    size = game.get("orbit_size")
    if limit and size and game.get("normal_hands", 0) >= limit * size:
        game["status"] = (
            "active"
            if any(game["fantasy"].get(p) for p in game["members"])
            else "complete"
        )


def transition(game, actor, command):
    """return a new state, leaving the original untouched on any error."""
    state = deepcopy(game)
    kind = command.get("type")
    if kind == "join":
        if actor in state["members"]:
            raise RuleError("already a member")
        state["members"].append(actor)
        if state["owner"] is None:
            state["owner"] = actor
    else:
        if actor not in state["members"]:
            raise RuleError("not a member")
        if kind == "update_settings":
            if actor != state["owner"]:
                raise RuleError("only the owner may edit table settings")
            if state["hand"] and state["hand"]["status"] == "playing":
                raise RuleError("edit table settings between hands")
            rules = Rules(
                **{
                    **state["rules"],
                    "turn_seconds": command["turn_seconds"],
                    "orbits": command["orbits"],
                }
            )
            state["rules"] = asdict(rules)
            # older unlimited games did not record their starting seat count.
            if state.get("orbit_size") is None and state["hand"]:
                state["orbit_size"] = len(state["hand"]["players"])
            state["status"] = "active"
            update_completion(state)
        elif kind == "start":
            start_hand(state, actor, command["players"])
        elif kind == "leave":
            if state["hand"] and state["hand"]["status"] == "playing":
                raise RuleError("leave the table between hands")
            state["members"].remove(actor)
            if state["owner"] == actor:
                state["owner"] = next(
                    (
                        p
                        for p in state["members"]
                        if p not in state.get("cpu_players", [])
                    ),
                    None,
                )
            state["button"] %= max(1, len(state["members"]))
            update_completion(state)
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
        own_turn = next((t for t in hand["queue"] if t["player"] == actor), None)
        hand["draw_keep"] = (
            13
            if actor in hand.get("fantasy_pending", [])
            else own_turn["keep"]
            if own_turn
            else None
        )
        hand.pop("queue")
        if hand["status"] != "complete":
            for p in hand["players"]:
                if p != actor and (hand["fantasy"][p] or hand["fantasy"].get(actor)):
                    hand["boards"][p] = {r: [] for r in ROWS}
    return view
