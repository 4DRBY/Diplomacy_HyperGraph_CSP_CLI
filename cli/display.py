# cli/display.py
# Functions for printing the board state, orders, and a detailed analysis of results.
# This version includes a full logical review and optimization for clarity and correctness.

from collections import defaultdict
from game_engine.hypergraph import Move, Hold, Support

def display_welcome():
    print("--- Diplomacy Adjudicator (Interactive Modular Version) ---")

def display_turn_info(game_state):
    print("\n" + "="*50)
    print(f"--- {game_state.season.upper()} {game_state.year} ---")
    print("="*50)

def display_board_state(game_state):
    print("\n--- Current Board State ---")
    units = sorted(game_state.units.values(), key=lambda u: u.nationality)
    for unit in units:
        print(f"  - {unit.nationality}: {unit.type} in {unit.location} ({unit.id})")
    if not units:
        print("  - No units on the board.")

def display_orders(orders):
    print("\n--- Submitted Orders ---")
    all_orders = list(orders)
    for order in sorted(all_orders, key=lambda o: o.id):
        unit_id, unit_loc = order.unit.id, order.unit.location
        if order.type == 'Move':
            print(f"  - {unit_id} ({unit_loc}): Move to {order.to_province_id}")
        elif order.type == 'Support':
            reason = "Invalid"
            if hasattr(order, 'supported_order_id') and "INVALID" in order.supported_order_id:
                 reason = order.supported_order_id.split('_', 1)[1].replace('_', ' ')
                 print(f"  - {unit_id} ({unit_loc}): Support (FAILED: {reason})")
            else:
                 supp_order = next((o for o in all_orders if hasattr(order, 'supported_order_id') and o.id == order.supported_order_id), None)
                 if supp_order:
                     action_str = f"move to {supp_order.to_province_id}" if isinstance(supp_order, Move) else "hold"
                     print(f"  - {unit_id} ({unit_loc}): Support {supp_order.unit.id}'s {action_str}")
                 else:
                     print(f"  - {unit_id} ({unit_loc}): Support (FAILED: Target order not found)")
        else: # Hold
            print(f"  - {unit_id} ({unit_loc}): {order.type}")

def display_results(results, details, game_state):
    """Displays explicit success/fail status, conflict analysis, and final positions."""
    
        # --- NEW CONFLICT ANALYSIS SECTION ---
    print("\n--- Conflict Analysis ---")
    if not details.get('conflicts'):
        print("  - No contested provinces this turn.")
    else:
        for province_id, conflict in details['conflicts'].items():
            print(f"\n  Conflict in {conflict['province_name']}:")
            
            participants_str = []
            for unit_id, strength in conflict['strengths'].items():
                unit = game_state.units[unit_id]
                order = next((o for o in game_state.turn_hypergraph.orders.values() if o.unit.id == unit_id), None)
                action = f"move by {unit_id}" if isinstance(order, Move) else f"hold by {unit_id}"
                participants_str.append(f"The {action} (Strength {strength})")
            print(f"    - Battle: {' vs '.join(participants_str)}")
            
            if conflict['is_tie']:
                print("    - Outcome: BOUNCE. The forces were of equal strength. All units fail to enter or are held in place.")
            else:
                winner_id = conflict['winner']
                print(f"    - Outcome: {winner_id} wins with superior strength.")
    
    print("\n--- Order Resolution ---")
    if isinstance(results, str):
        print(f"  Error: {results}")
        return

    for order in sorted(game_state.turn_hypergraph.orders.values(), key=lambda o: o.unit.nationality):
        unit_id = order.unit.id
        outcome = results.get(unit_id)
        
        if isinstance(order, Move):
            if outcome == 'moves':
                print(f"  - [SUCCESS] Move: {unit_id} ({order.unit.location} -> {order.to_province_id}).")
            else:
                reason = "BOUNCE" if outcome == 'stands' else "DISLODGED"
                print(f"  - [FAILED]  Move: {unit_id} ({order.unit.location} -> {order.to_province_id}) failed due to {reason}.")
        
        elif isinstance(order, Support):
            status = details.get('support_statuses', {}).get(order.id)
            if status == 'cut':
                print(f"  - [FAILED]  Support from {unit_id} was CUT.")
            elif status == 'invalid':
                print(f"  - [FAILED]  Support from {unit_id} was INVALID from the start.")
            elif status == 'valid':
                supported_order = game_state.turn_hypergraph.orders.get(order.supported_order_id)
                if not supported_order:
                     print(f"  - [FAILED]  Support from {unit_id} was valid but its target was not found.")
                     continue
                
                supported_outcome = results.get(supported_order.unit.id)
                
                # Check if the supported action was actually successful
                action_succeeded = (isinstance(supported_order, Move) and supported_outcome == 'moves') or \
                                   (isinstance(supported_order, Hold) and supported_outcome == 'stands')

                if action_succeeded:
                    print(f"  - [SUCCESS] Support from {unit_id} successfully contributed to a successful action.")
                else:
                    print(f"  - [FAILED]  Support from {unit_id} was valid, but the supported action failed anyway.")
        
        elif isinstance(order, Hold):
            if outcome == 'stands':
                print(f"  - [SUCCESS] Hold: {unit_id} successfully held its position.")
            else:
                print(f"  - [FAILED]  Hold: {unit_id} failed; the unit was DISLODGED.")


    # --- REFORMATTED FINAL POSITIONS ---
    print("\n--- Final Board Positions for Next Turn ---")
    final_positions = defaultdict(list)
    
    # CRITICAL FIX: Determine final locations from the results, not the old gamestate
    for unit_id, outcome in results.items():
        if outcome == 'dislodged':
            continue # Dislodged units are removed
        
        unit = game_state.units.get(unit_id)
        if not unit: continue

        final_loc = ""
        if outcome == 'moves':
            order = game_state.turn_hypergraph.orders.get(f"Order_{unit_id}")
            if order:
                final_loc = order.to_province_id
        else: # stands
            final_loc = unit.location
        
        if final_loc:
             final_positions[unit.nationality].append(f"{unit.type} in {final_loc}")

    if not final_positions:
        print("  - All units were dislodged from the board.")
    else:
        for nation in sorted(final_positions.keys()):
            print(f"\n  {nation}:")
            for pos in sorted(final_positions[nation]):
                print(f"    - {pos}")

    print("\n" + "="*50)
