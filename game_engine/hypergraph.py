# game_engine/hypergraph.py
# Defines Order classes as hyperedges and the turn's Hypergraph.

class Order:
    """Base class for all orders, representing a hyperedge."""
    # To add a new order type (e.g., Build, Convoy):
    # 1. Subclass Order.
    # 2. Define __init__ with necessary parameters (unit, target provinces, etc.).
    # 3. Ensure self.type is set (usually defaults correctly via self.__class__.__name__).
    # 4. Consider if the new order type needs special handling in Adjudicator.py
    #    for variable setup, constraint definition, or result interpretation.
    def __init__(self, order_id, unit):
        self.id = order_id
        self.unit = unit
        self.type = self.__class__.__name__

    def __repr__(self):
        return f"{self.type}({self.unit.id})"

class Move(Order):
    def __init__(self, order_id, unit, to_province_id):
        super().__init__(order_id, unit)
        self.to_province_id = to_province_id

class Support(Order):
    """Represents a support order, either supporting a move or a hold."""
    def __init__(self, order_id, unit, supported_unit_loc, is_move=False, move_destination=None):
        super().__init__(order_id, unit)
        self.supported_unit_loc = supported_unit_loc
        self.is_move = is_move
        self.move_destination = move_destination
        self.supported_order_id = None  # Will be set during order linking
        self.type = 'Support'
    
    def __repr__(self):
        if self.is_move:
            return f"Support({self.unit.id} supports move from {self.supported_unit_loc} to {self.move_destination})"
        return f"Support({self.unit.id} supports hold in {self.supported_unit_loc})"

class Convoy(Order):
    def __init__(self, order_id, unit, convoyed_army_order_id):
        super().__init__(order_id, unit)
        self.convoyed_army_order_id = convoyed_army_order_id

class Hold(Order):
    def __init__(self, order_id, unit):
        super().__init__(order_id, unit)

class TurnHypergraph:
    """Manages the collection of all orders for a single game turn."""
    def __init__(self):
        self.orders = {} # Maps order_id to Order object
    
    def add_order(self, order):
        if any(o.unit.id == order.unit.id for o in self.orders.values()):
            raise ValueError(f"Unit '{order.unit.id}' has already been issued an order.")
        self.orders[order.id] = order

    def finalize_and_validate_supports(self, game_state):
        """
        Validates all Support orders within the hypergraph.
        This method should be called after all orders for a turn are added.
        It checks:
        1. If the supported unit exists at the specified location.
        2. If the supported unit has an order.
        3. If the supporting unit is adjacent to the province of action.
        4. If the support action matches the supported unit's actual order.
        Sets `supported_order_id` to the ID of the actual supported order
        or an 'INVALID_...' string if validation fails.
        """
        all_orders_in_turn = list(self.orders.values()) # List of all orders in this hypergraph

        for order in self.orders.values():
            if not isinstance(order, Support):
                continue

            # 1. Check if the unit being supported exists at the specified location
            supported_unit = next((u for u in game_state.units.values() if u.location == order.supported_unit_loc), None)
            if not supported_unit:
                order.supported_order_id = "INVALID_UNIT_NOT_FOUND"
                continue

            # 2. Check if the supported unit has an order this turn
            target_order_for_supported_unit = next((o for o in all_orders_in_turn if o.unit.id == supported_unit.id), None)
            if not target_order_for_supported_unit:
                order.supported_order_id = "INVALID_TARGET_HAS_NO_ORDER"
                continue

            # 3. Check adjacency for the supporting unit to the action province
            # The "action province" is where the supported unit is performing its action
            # For a supported move, it's the destination of the move.
            # For a supported hold, it's the location of the unit holding.
            action_province = order.move_destination if order.is_move else supported_unit.location

            # Get adjacencies for the supporting unit's current location
            supporter_adjacencies = game_state.game_map.adjacencies.get(order.unit.location, [])
            if action_province not in supporter_adjacencies:
                order.supported_order_id = "INVALID_SUPPORT_NOT_ADJACENT_TO_ACTION"
                continue

            # 4. Check if the type of support (move or hold) matches the actual order of the supported unit
            is_action_match = False
            if order.is_move: # Supporting a move
                if isinstance(target_order_for_supported_unit, Move) and \
                   target_order_for_supported_unit.to_province_id == order.move_destination:
                    is_action_match = True
            else: # Supporting a hold
                # A unit holds if its order is Hold, or if its Move order fails (bounces).
                # For initial validation, we check against an explicit Hold order.
                # The adjudicator will handle cases where a failed Move becomes a hold.
                if isinstance(target_order_for_supported_unit, Hold) and \
                   target_order_for_supported_unit.unit.location == order.supported_unit_loc: # Ensure hold is in the correct location
                    is_action_match = True
                # Note: Simple support validation doesn't usually predict if a Move will become a Hold.
                # It primarily checks if the declared support matches a declared Hold or a declared Move.

            if is_action_match:
                order.supported_order_id = target_order_for_supported_unit.id
            else:
                order.supported_order_id = "INVALID_ACTION_MISMATCH"
