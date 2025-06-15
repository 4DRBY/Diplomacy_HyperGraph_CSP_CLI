# game_engine/gamestate.py
# Defines the GameState, Player, and Unit classes.

import json
from .hypergraph import Move

class Unit:
    """Represents a single army or fleet unit."""
    def __init__(self, u_id, nationality, unit_type, location):
        self.id = u_id
        self.nationality = nationality
        self.type = unit_type
        self.location = location # Province ID
        
        # Dynamic attributes calculated by the adjudicator
        self.nearest_friendly_force = (None, float('inf'))
        self.nearest_opposing_force = (None, float('inf'))
        self.nearest_sc = (None, float('inf'))

    def __repr__(self):
        return f"Unit({self.id} in {self.location})"

class GameState:
    """Holds the complete state of the game at a specific moment."""
    def __init__(self, game_map, save_file_path=None):
        self.game_map = game_map
        self.year = 0
        self.season = ""
        self.units = {} # Maps unit_id to Unit object
        self.turn_hypergraph = None # Store the turn's orders for state updates
        
        if save_file_path:
            self._load_state(save_file_path)

    def _load_state(self, file_path):
        """Loads the game state from a JSON save file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        self.year = data['year']
        self.season = data['season']
        
        for unit_data in data['units']:
            unit = Unit(
                u_id=unit_data['id'],
                nationality=unit_data['nationality'],
                unit_type=unit_data['unit_type'],
                location=unit_data['location']
            )
            self.units[unit.id] = unit

    def get_unit_at(self, province_id):
        """Returns the unit in a given province, if any."""
        for unit in self.units.values():
            if unit.location == province_id:
                return unit
        return None

    def update_state_after_turn(self, results):
        """
        Updates the locations of all units based on the adjudication results.
        This prepares the state for the next turn.
        """
        if isinstance(results, str):
            print("Cannot update state due to adjudication error.")
            return

        dislodged_units = set()
        
        # First pass: identify dislodged units
        for unit_id, outcome in results.items():
            if outcome == 'dislodged':
                dislodged_units.add(unit_id)

        # Second pass: update locations for successful moves
        for unit_id, outcome in results.items():
            if outcome == 'moves':
                unit = self.units.get(unit_id)
                if not unit: continue
                # Find the move order to get the destination
                order = self.turn_hypergraph.orders.get(f"Order_{unit_id}")
                if unit and isinstance(order, Move):
                    unit.location = order.to_province_id
        
        # Third pass: remove dislodged units from the board
        # In a full game, they would go to a retreat phase. Here we just remove them.
        for unit_id in dislodged_units:
            if unit_id in self.units:
                del self.units[unit_id]

    def advance_turn(self):
        """Advances the game year and season."""
        if self.season == "Spring":
            self.season = "Fall"
        else:
            self.season = "Spring"
            self.year += 1

