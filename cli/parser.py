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


def get_orders_for_turn(game_state):
    """Interactively prompts the user for orders for each unit."""
    print("\n--- Please Enter Orders ---")
    print("Use standard notation (e.g., 'A PAR - BUR', 'F RUH S A MUN - BUR', 'A BEL H').")
    
    orders = []
    units_by_nationality = defaultdict(list)
    for unit in game_state.units.values():
        units_by_nationality[unit.nationality].append(unit)

    for nation in sorted(units_by_nationality.keys()):
        print(f"\n--- Orders for {nation} ---")
        for unit in sorted(units_by_nationality[nation], key=lambda u: u.id):
            
            available_moves = game_state.game_map.adjacencies.get(unit.location, [])
            if available_moves:
                print(f"    (Unit {unit.id} in {unit.location} can move to: {', '.join(available_moves)})")
            
            while True:
                try:
                    prompt = f"  Order: "
                    order_string = input(prompt)
                    if not order_string:
                        order_string = f"H"
                    parsed_order = parse_order_string(order_string, unit, game_state)
                    orders.append(parsed_order)
                    break
                except ValueError as e:
                    print(f"    ERROR: {e} Please enter a valid order.")
                except Exception as e:
                    print(f"    Invalid order format. Please try again. Error: {e}")
    
    # Validate supports AFTER all orders are parsed
    for order in orders:
        if isinstance(order, Support):
            supported_unit = next((u for u in game_state.units.values() if u.location == order.supported_unit_loc), None)
            
            if not supported_unit:
                order.supported_order_id = "INVALID_UNIT"
                continue
            
            target_order = next((o for o in orders if o.unit.id == supported_unit.id), None)
            if not target_order:
                order.supported_order_id = "INVALID_NO_ORDER"
                continue

            action_province = order.move_destination if order.is_move else supported_unit.location
            
            supporter_adjacencies = game_state.game_map.adjacencies.get(order.unit.location, [])
            if action_province not in supporter_adjacencies:
                order.supported_order_id = "INVALID_NOT_ADJACENT"
                continue

            is_match = (order.is_move and isinstance(target_order, Move) and target_order.to_province_id == order.move_destination) or \
                       (not order.is_move and isinstance(target_order, Hold))

            order.supported_order_id = target_order.id if is_match else "INVALID_ACTION_MISMATCH"

    return orders
