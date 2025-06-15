# game_engine/hypergraph.py
# Defines Order classes as hyperedges and the turn's Hypergraph.

class Order:
    """Base class for all orders, representing a hyperedge."""
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
