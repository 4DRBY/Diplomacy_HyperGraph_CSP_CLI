# cli/parser.py
# Functions for parsing user commands and orders interactively.
# This version corrects the logic for parsing support-hold orders.

import re
from collections import defaultdict
from game_engine.hypergraph import Move, Support, Hold, Convoy

def parse_order_string(order_string, unit, game_state):
    """
    Parses a single line of text into an Order object, validating legality.
    Raises ValueError for illegal moves.
    """
    order_string = order_string.strip().upper()
    
    # Check for Support first
    if ' S ' in order_string:
        parts = re.split(r'\s+S\s+', order_string)
        supported_action_str = parts[1]
        
        # Supporting a move (e.g., A MUN - BUR)
        if '-' in supported_action_str:
            move_parts = re.split(r'\s+-\s+', supported_action_str)
            supported_unit_loc = move_parts[0].split()[-1] # Takes last part, e.g., MUN from "A MUN"
            target_loc = move_parts[1]
            return Support(f"Order_{unit.id}", unit, 
                           supported_unit_loc=supported_unit_loc,
                           is_move=True,
                           move_destination=target_loc)
        # Supporting a hold (e.g., A MUN or A MUN H)
        else:
            # --- LOGIC CORRECTION ---
            # Correctly identify the province in a support-hold order,
            # accounting for an optional unit type (A or F).
            action_parts = supported_action_str.split()
            if action_parts[0] in ['A', 'F'] and len(action_parts) > 1:
                supported_unit_loc = action_parts[1]
            else:
                supported_unit_loc = action_parts[0]
            
            return Support(f"Order_{unit.id}", unit, 
                           supported_unit_loc=supported_unit_loc,
                           is_move=False)

    # Check for Move second
    if '-' in order_string:
        parts = re.split(r'\s+-\s+', order_string)
        to_province_id = parts[1]
        
        available_moves = game_state.game_map.adjacencies.get(unit.location, [])
        if to_province_id not in available_moves:
            raise ValueError(f"Illegal move: {unit.location} is not adjacent to {to_province_id}.")
            
        return Move(f"Order_{unit.id}", unit, to_province_id)

    # Fallback to Hold last
    return Hold(f"Order_{unit.id}", unit)

# The function get_orders_for_turn has been removed as its functionality
# (iterating units, prompting for input, and initial support validation)
# is now handled directly within the Game.run_turn method in main.py.
# The parse_order_string function above is still used by main.py for parsing individual order strings.
