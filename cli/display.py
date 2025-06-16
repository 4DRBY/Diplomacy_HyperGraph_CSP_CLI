# cli/display.py
# Functions for printing the board state, orders, and a detailed analysis of results
# to the command line interface.

from collections import defaultdict
from game_engine.hypergraph import Move, Hold, Support # Used for type checking and accessing order details
from game_engine.gamestate import GameState # Used for type hinting

def display_welcome():
    """Prints a welcome message to the console."""
    print("--- Diplomacy Adjudicator (Interactive Modular Version) ---")

def display_turn_info(game_state: GameState):
    """
    Prints the current turn information (season and year).

    Args:
        game_state: The current GameState object.
    """
    print("\n" + "="*50)
    # Display current season (e.g., SPRING, FALL, WINTER) and year.
    # Phase information is also available in game_state.phase if needed for more detail.
    print(f"--- {game_state.season.upper()} {game_state.year} ({game_state.phase} PHASE) ---")
    print("="*50)

def display_board_state(game_state: GameState):
    """
    Prints the current state of all units on the board, grouped by nationality.

    Args:
        game_state: The current GameState object.
    """
    print("\n--- Current Board State ---")
    # Sort units by nationality for grouped display, then by unit ID for consistent order.
    units = sorted(game_state.units.values(), key=lambda u: (u.nationality, u.id))
    for unit in units:
        print(f"  - {unit.nationality}: {unit.type} in {unit.location} ({unit.id})")
    if not units:
        print("  - No units on the board.")

def display_orders(orders):
    """
    Prints the list of submitted orders for the current turn.

    Args:
        orders (Iterable[Order]): An iterable of Order objects from the TurnHypergraph.
    """
    print("\n--- Submitted Orders ---")
    # Convert to list for multiple potential iterations if needed, and sort for consistent display.
    all_orders_list = sorted(list(orders), key=lambda o: o.unit.id)

    if not all_orders_list:
        print("  - No orders submitted for this turn.")
        return

    for order in all_orders_list:
        unit_id, unit_loc = order.unit.id, order.unit.location

        if isinstance(order, Move):
            print(f"  - Unit {unit_id} in {unit_loc}: Move to {order.to_province_id}")
        elif isinstance(order, Support):
            # Displaying support orders, including outcome if already validated (e.g., by TurnHypergraph)
            action_desc = ""
            target_info = f"unit at {order.supported_unit_loc}"
            if order.is_move:
                action_desc = f"move from {order.supported_unit_loc} to {order.move_destination}"
            else:
                action_desc = f"hold in {order.supported_unit_loc}"

            # Check if support validation has marked this order
            if hasattr(order, 'supported_order_id') and order.supported_order_id and "INVALID" in order.supported_order_id:
                # Extract a human-readable reason from codes like "INVALID_UNIT_NOT_FOUND"
                reason = order.supported_order_id.split('_', 1)[-1].replace('_', ' ').lower()
                print(f"  - Unit {unit_id} in {unit_loc}: Support {target_info} to {action_desc} (FAILED: {reason})")
            elif hasattr(order, 'supported_order_id') and order.supported_order_id:
                # Try to find the actual order object that is being supported, for more descriptive text.
                # This assumes `orders` contains all orders.
                supported_order_object = next((o for o in all_orders_list if o.id == order.supported_order_id), None)
                if supported_order_object:
                    target_info = f"Unit {supported_order_object.unit.id}" # Use actual unit ID
                print(f"  - Unit {unit_id} in {unit_loc}: Support {target_info} to {action_desc}")
            else:
                # Fallback if supported_order_id is not set or None (should ideally be set by validation)
                print(f"  - Unit {unit_id} in {unit_loc}: Support {target_info} to {action_desc} (Status pending adjudication)")

        elif isinstance(order, Hold):
            print(f"  - Unit {unit_id} in {unit_loc}: Hold")
        else: # Catch-all for other order types, if any
            print(f"  - Unit {unit_id} in {unit_loc}: {order.type} (Details: {order.__dict__})")


def display_results(results: dict, details: dict, game_state: GameState):
    """
    Displays a comprehensive summary of the turn's resolution, including:
    - Conflict analysis: Details of battles, strengths, and winners.
    - Order resolution: Success or failure status for each submitted order.
    - Final board positions: The state of units leading into the next turn/phase.

    Args:
        results: A dictionary mapping unit IDs to their adjudicated outcomes (e.g., 'moves', 'stands', 'dislodged').
                 Can also be a string in case of a top-level adjudication error.
        details: A dictionary containing detailed adjudication information, such as
                 support statuses ('support_statuses') and conflict details ('conflicts').
        game_state: The GameState object, used to access unit information and the turn hypergraph.
    """
    
    # --- CONFLICT ANALYSIS SECTION ---
    print("\n--- Conflict Analysis ---")
    # Check if the 'conflicts' key exists and has content.
    if not details or not details.get('conflicts'):
        print("  - No contested provinces this turn.")
    else:
        for province_id, conflict in details['conflicts'].items():
            print(f"\n  Conflict in {conflict['province_name']}:")
            
            participants_str = []
            for unit_id_in_conflict, strength in conflict['strengths'].items():
                # Attempt to find the unit in the current game state's units.
                # It's possible a unit involved in a conflict was dislodged elsewhere
                # and might not be in game_state.units if that's updated prematurely.
                # However, for displaying conflict details, we refer to units as they were.
                # Adjudicator's 'details' should ideally use unit objects or full unit data if needed beyond ID.
                # For now, assume unit_id_in_conflict is sufficient if direct unit object access fails.
                unit_obj = game_state.units.get(unit_id_in_conflict)
                unit_display_name = f"Unit {unit_id_in_conflict}"
                if unit_obj:
                    unit_display_name = f"Unit {unit_obj.id} ({unit_obj.nationality} {unit_obj.type} in {unit_obj.location})"

                # Find the order associated with this unit in the conflict
                order_for_unit_in_conflict = None
                if game_state.turn_hypergraph and game_state.turn_hypergraph.orders:
                    order_for_unit_in_conflict = next((o for o in game_state.turn_hypergraph.orders.values() if o.unit.id == unit_id_in_conflict), None)

                action_desc = "action" # Default action description
                if order_for_unit_in_conflict:
                    if isinstance(order_for_unit_in_conflict, Move):
                        action_desc = f"move to {order_for_unit_in_conflict.to_province_id}"
                    elif isinstance(order_for_unit_in_conflict, Hold):
                        action_desc = "hold"
                    # Add more descriptions for other order types if they can be part of conflicts

                participants_str.append(f"{unit_display_name} performing {action_desc} (Strength {strength})")
            
            if participants_str:
                print(f"    - Participants: {'; '.join(participants_str)}")
            else:
                print(f"    - No specific participant strength details available.")

            if conflict['is_tie']:
                print("    - Outcome: BOUNCE. The forces were of equal strength. All units fail to enter or are held in place.")
            else:
                winner_id = conflict['winner']
                print(f"    - Outcome: {winner_id} wins with superior strength.")
    
    print("\n--- Order Resolution ---")
    if isinstance(results, str): # Indicates a global adjudication error
        print(f"  Adjudication Error: {results}")
        return

    # Ensure there's a hypergraph to iterate orders from; otherwise, can't display order-specific results.
    if not game_state.turn_hypergraph or not game_state.turn_hypergraph.orders:
        print("  - No orders were processed in the turn hypergraph.")
        # Still print unit outcomes if available
        if results:
            print("\n  --- Unit Outcomes ---")
            for unit_id_res, outcome_res in results.items():
                 unit_obj_res = game_state.units.get(unit_id_res)
                 unit_loc_res = unit_obj_res.location if unit_obj_res else "Unknown Location"
                 print(f"    - Unit {unit_id_res} (at {unit_loc_res}): {outcome_res.upper()}")
        return

    # Iterate through orders for detailed resolution display
    for order in sorted(game_state.turn_hypergraph.orders.values(), key=lambda o: (o.unit.nationality, o.unit.id)):
        unit_id = order.unit.id
        outcome = results.get(unit_id) # Get the adjudicated outcome for the unit that issued this order
        
        order_type_str = order.__class__.__name__.upper() # e.g., "MOVE", "SUPPORT", "HOLD"

        if isinstance(order, Move):
            move_details = f"{order.unit.location} -> {order.to_province_id}"
            if outcome == 'moves':
                print(f"  - [SUCCESS] {order_type_str}: Unit {unit_id} ({move_details}). Unit is now in {order.to_province_id}.")
            elif outcome == 'stands': # Bounced
                print(f"  - [FAILED]  {order_type_str}: Unit {unit_id} ({move_details}). Move failed (BOUNCE). Unit remains in {order.unit.location}.")
            elif outcome == 'dislodged': # Should not happen for a move order itself, but unit might be dislodged by another action.
                 print(f"  - [INFO]    {order_type_str}: Unit {unit_id} ({move_details}). Move failed. Unit was DISLODGED from {order.unit.location}.")
            else: # Other outcomes or None
                print(f"  - [INFO]    {order_type_str}: Unit {unit_id} ({move_details}). Outcome: {str(outcome).upper() if outcome else 'UNKNOWN'}.")
        
        elif isinstance(order, Support):
            support_status = details.get('support_statuses', {}).get(order.id, 'UNKNOWN') # e.g., 'valid', 'cut', 'invalid'

            action_desc = f"move of unit at {order.supported_unit_loc} to {order.move_destination}" if order.is_move else f"hold of unit at {order.supported_unit_loc}"
            base_text = f"Support by Unit {unit_id} (from {order.unit.location}) for {action_desc}"

            if support_status == 'cut':
                print(f"  - [FAILED]  {base_text}. Support was CUT.")
            elif support_status == 'invalid' or "INVALID" in str(order.supported_order_id): # Check pre-validation status too
                invalid_reason = order.supported_order_id.replace("INVALID_", "").replace("_", " ").lower() if order.supported_order_id and "INVALID" in order.supported_order_id else "invalid"
                print(f"  - [FAILED]  {base_text}. Support was {invalid_reason.upper()}.")
            elif support_status == 'valid':
                # Find the order that was supported
                supported_order_obj = game_state.turn_hypergraph.orders.get(order.supported_order_id)
                if not supported_order_obj:
                     print(f"  - [INFO]    {base_text}. Support was valid, but target order data not found post-adjudication.")
                else:
                    supported_unit_actual_outcome = results.get(supported_order_obj.unit.id)
                    # Determine if the action the support was for actually succeeded
                    action_succeeded = (isinstance(supported_order_obj, Move) and supported_unit_actual_outcome == 'moves') or \
                                       (isinstance(supported_order_obj, Hold) and supported_unit_actual_outcome == 'stands')
                    if action_succeeded:
                        print(f"  - [SUCCESS] {base_text}. Support contributed to a successful action.")
                    else:
                        print(f"  - [INFO]    {base_text}. Support was valid, but the supported action ({supported_order_obj.type} by {supported_order_obj.unit.id}) ultimately failed (Outcome: {str(supported_unit_actual_outcome).upper()}).")
            else: # Unknown status
                 print(f"  - [INFO]    {base_text}. Support status: {support_status.upper()}.")
        
        elif isinstance(order, Hold):
            hold_details = f"Unit {unit_id} in {order.unit.location}"
            if outcome == 'stands':
                print(f"  - [SUCCESS] {order_type_str}: {hold_details} successfully held position.")
            elif outcome == 'dislodged':
                print(f"  - [FAILED]  {order_type_str}: {hold_details} failed; unit was DISLODGED.")
            elif outcome == 'moves': # Should not happen for a hold order
                print(f"  - [ERROR]   {order_type_str}: {hold_details} has outcome 'moves', which is inconsistent for a Hold.")
            else:
                print(f"  - [INFO]    {order_type_str}: {hold_details}. Outcome: {str(outcome).upper() if outcome else 'UNKNOWN'}.")

        # Placeholder for other order types (e.g., Convoy - not fully implemented in adjudication yet)
        elif order.type not in ["Move", "Support", "Hold"]:
             print(f"  - [INFO]    {order_type_str}: Unit {unit_id} in {order.unit.location}. Outcome: {str(outcome).upper() if outcome else 'PENDING IMPLEMENTATION'}.")


    # --- FINAL POSITIONS SECTION ---
    # This section calculates and displays the board state *after* the turn's resolution.
    print("\n--- Final Board Positions for Next Turn ---")
    final_positions_by_nation = defaultdict(list)
    
    # Iterate through the results to determine final unit locations.
    # `results` dict is {unit_id: outcome_string}.
    for unit_id_result, outcome_result in results.items():
        if outcome_result == 'dislodged':
            # Dislodged units are removed from the board (or handled by retreat phase in a full game)
            continue
        
        # Get the unit object from the original game state (before this turn's moves were applied)
        # This is important because unit.location might be outdated if we look at game_state.units directly
        # if it has been partially updated. Best to rely on the original state + results.
        original_unit = game_state.units.get(unit_id_result) # This uses the GameState *before* update_state_after_turn
        if not original_unit:
            print(f"Warning: Unit {unit_id_result} found in results, but not in initial GameState for displaying final position.")
            continue

        final_location_of_unit = ""
        if outcome_result == 'moves':
            # Find the Move order to know the destination
            move_order_for_unit = None
            if game_state.turn_hypergraph and game_state.turn_hypergraph.orders:
                for o in game_state.turn_hypergraph.orders.values():
                    if o.unit.id == unit_id_result and isinstance(o, Move):
                        move_order_for_unit = o
                        break
            if move_order_for_unit:
                final_location_of_unit = move_order_for_unit.to_province_id
            else:
                # This implies an inconsistency: outcome is 'moves' but no corresponding Move order found.
                print(f"Warning: Could not find Move order for unit {unit_id_result} listed with 'moves' outcome. Using original location as fallback.")
                final_location_of_unit = original_unit.location
        else: # Unit 'stands' (either held, or a move failed and resulted in standing)
            final_location_of_unit = original_unit.location
        
        if final_location_of_unit: # Should always be true unless there's a major issue
             final_positions_by_nation[original_unit.nationality].append(f"{original_unit.type} in {final_location_of_unit} (Unit {original_unit.id})")

    if not final_positions_by_nation:
        print("  - All units were dislodged or no units remained.")
    else:
        for nation in sorted(final_positions_by_nation.keys()):
            print(f"\n  {nation}:")
            for pos_string in sorted(final_positions_by_nation[nation]):
                print(f"    - {pos_string}")

    print("\n" + "="*50)
