# main.py
# Main application entry point and game loop.
# This version orchestrates a fully dynamic turn from input to analysis.

from collections import defaultdict
from game_engine.map import GameMap
from game_engine.gamestate import GameState
from game_engine.hypergraph import TurnHypergraph
from game_engine.adjudicator import Adjudicator
from cli.parser import get_orders_for_turn
from cli.display import (display_welcome, display_board_state, 
                         display_orders, display_results, display_turn_info)

def run_turn(game_state):
    """Runs a single, complete game turn with dynamic interaction and analysis."""
    display_turn_info(game_state)
    display_board_state(game_state)

    # 1. Dynamically get orders from the user
    raw_orders = get_orders_for_turn(game_state)
    
    # 2. Build the Turn Hypergraph from the dynamic orders
    turn_hypergraph = TurnHypergraph()
    for order in raw_orders:
        try:
            turn_hypergraph.add_order(order)
        except ValueError as e:
            print(f"Input Error: {e}") # Handle case where a unit gets two orders
            # In a real app, you might re-prompt the user
            return False # Skip turn processing
            
    game_state.turn_hypergraph = turn_hypergraph
    
    # This will now use the updated parser which shows adjacent territories
    display_orders(turn_hypergraph.orders.values())
    
    # 3. Adjudicate the turn
    print("\n--- Adjudicating Turn... ---")
    adjudicator = Adjudicator(game_state, turn_hypergraph)
    results, details = adjudicator.solve()
    
    # 4. Display dynamic results and analysis
    # This will use the display module that shows success/fail and final positions
    display_results(results, details, game_state)
    
    # 5. Update game state for the next turn
    game_state.update_state_after_turn(results)
    game_state.advance_turn()
    return True # Indicate success

def main():
    """Main game loop for interactive play."""
    
    display_welcome()
    
    # Load initial game data from modules
    game_map = GameMap('data/classic_map.json')
    game_state = GameState(game_map, 'data/game_save.json')
    
    # Main game loop
    while True:
        # If run_turn returns False, it means there was an error, so we stop.
        if not run_turn(game_state):
            break
        
        if not game_state.units:
            print("\n--- No units remaining on the board. Game Over. ---")
            break
            
        cont = input("Proceed to next turn? (Y/n): ").strip().lower()
        if cont == 'n':
            print("Exiting game.")
            break

if __name__ == "__main__":
    # To run the application:
    # 1. Ensure you have the 'python-constraint2' library installed:
    #    pip install python-constraint2
    # 2. Run this file from the root 'diplomacy_hypergraph' directory:
    #    python main.py
    main()
