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
        self.year = 1901 # Standard starting year
        # self.season is now set by phase logic
        # self.phase is now set by phase logic
        self.units = {} # Maps unit_id to Unit object
        self.turn_hypergraph = None # Store the turn's orders for state updates

        # Define the sequence of phases and seasons
        # Each tuple is (Season_Name, Phase_Name)
        self._phase_sequence = [
            ("Spring", "MOVEMENT"),
            ("Spring", "RETREATS"),
            ("Fall", "MOVEMENT"),
            ("Fall", "RETREATS"),
            ("Winter", "BUILDS") # Winter is typically for builds/disbands
        ]
        self._current_phase_index = 0 # Start with the first phase in the sequence
        self.season, self.phase = self._phase_sequence[self._current_phase_index]
        
        if save_file_path:
            self._load_state(save_file_path) # year, season, phase might be overwritten

    def _load_state(self, file_path):
        """Loads the game state from a JSON save file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        self.year = data['year']
        loaded_season = data['season']
        loaded_phase = data.get('phase', self._determine_initial_phase(loaded_season))
        
        # Try to sync _current_phase_index with loaded data
        try:
            self._current_phase_index = self._phase_sequence.index((loaded_season, loaded_phase))
            self.season = loaded_season
            self.phase = loaded_phase
        except ValueError:
            print(f"Warning: Loaded season/phase ({loaded_season}/{loaded_phase}) not found in sequence. Defaulting to start of sequence.")
            # Default to start of sequence if loaded combination is invalid
            self._current_phase_index = 0
            self.season, self.phase = self._phase_sequence[self._current_phase_index]

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
        Updates unit locations and removes dislodged units based on adjudication results.

        This method processes the outcomes of a turn (e.g., 'moves', 'stands', 'dislodged')
        for each unit involved in the turn's orders. It ensures that the game state
        accurately reflects these outcomes.

        The process is streamlined into two main stages:
        1. A single pass through the adjudication results to:
            a. Update the location of units that successfully moved. This requires
               looking up their original 'Move' order from the turn's hypergraph
               to find the destination province.
            b. Identify and collect the IDs of units that were dislodged.
        2. A final pass to remove all dislodged units from the game state.
           In a more complex game, this might lead to a retreat phase instead.

        Pre-conditions:
        - `results`: A dictionary mapping unit_id (str) to outcome (str).
        - `self.turn_hypergraph`: Must be populated with the hypergraph of orders
                                   for the turn that was just adjudicated. This is crucial
                                   for finding the destination of 'Move' orders.
        """
        if isinstance(results, str):
            # This typically indicates an error message from the adjudicator.
            print(f"Cannot update state due to adjudication error: {results}")
            return

        units_to_be_removed_ids = set()

        # Stage 1: Process moves and identify dislodgements.
        for unit_id, outcome in results.items():
            unit = self.units.get(unit_id)
            if not unit:
                print(f"Warning: Unit ID {unit_id} from results not found in game state. Skipping.")
                continue

            if outcome == 'moves':
                # Unit successfully moved. Update its location.
                # We need to find the original 'Move' order from the turn's hypergraph
                # to determine the destination province.
                if not self.turn_hypergraph or not self.turn_hypergraph.orders:
                    print(f"Warning: Turn hypergraph not available or empty. Cannot process move for unit {unit_id}.")
                    continue

                found_order = None
                for order_obj in self.turn_hypergraph.orders.values():
                    if order_obj.unit.id == unit_id:
                        found_order = order_obj
                        break

                if isinstance(found_order, Move):
                    unit.location = found_order.to_province_id
                elif found_order: # Order found but it's not a Move order.
                    print(f"Warning: Unit {unit_id} outcome is 'moves', but its resolved order "
                          f"(ID: {found_order.id}, Type: {type(found_order).__name__}) is not a Move order. Location not updated.")
                else: # No order found for this unit_id in the hypergraph.
                    print(f"Warning: No order found in turn_hypergraph for unit {unit_id} whose outcome was 'moves'. Location not updated.")

            elif outcome == 'dislodged':
                # Unit was dislodged. Add its ID to the set for removal.
                units_to_be_removed_ids.add(unit_id)

            # If outcome == 'stands', the unit's location does not change,
            # and it's not dislodged. No specific action needed here.

        # Stage 2: Remove all dislodged units from the game state.
        for unit_id_to_remove in units_to_be_removed_ids:
            if unit_id_to_remove in self.units:
                del self.units[unit_id_to_remove]
            else:
                # This might happen if a unit was already removed or if there's an inconsistency.
                print(f"Warning: Attempted to remove unit ID {unit_id_to_remove} (marked as dislodged), but it was not found in game state units.")
        # EXTENSIBILITY: For orders like 'Build', this method would need to handle new unit creation
        # based on results, or a separate method in GameState would manage it during a 'Builds' phase.
        # The 'results' structure might also need to be enhanced to convey information about newly built units.


    def _determine_initial_phase(self, season_name):
        """Helper to determine a default phase for a given season, typically for loading."""
        for s, p in self._phase_sequence:
            if s == season_name:
                return p
        return self._phase_sequence[0][1] # Default to first phase's type if season not found

    def advance_phase(self):
        """
        Advances the game to the next phase in its defined sequence (e.g., Spring Movement -> Spring Retreats).
        If the current phase is the last in a year's sequence (e.g., Winter Builds),
        it advances to the next year and resets to the first phase (e.g., Spring Movement).
        This method also updates `self.season` and `self.phase` attributes.
        """
        self._current_phase_index += 1
        if self._current_phase_index >= len(self._phase_sequence):
            # End of the year cycle, loop back to the first phase and advance year
            self._current_phase_index = 0
            self.year += 1

        self.season, self.phase = self._phase_sequence[self._current_phase_index]

        # Log the new phase
        print(f"Advanced to: {self.year} {self.season} {self.phase}")

        # Important: Clear the hypergraph for the new phase, as old orders are no longer valid.
        self.turn_hypergraph = None

        # TODO for future development:
        # - Add logic here for phase-specific actions when a new phase begins. Examples:
        #   - If self.phase == "RETREATS": Initiate retreat order collection for dislodged units.
        #   - If self.phase == "BUILDS": Initiate build/disband order collection based on supply centers.
        #   - Check for game end conditions (e.g., solo victory).
        #   - Save game state automatically at certain phase transitions if desired.

