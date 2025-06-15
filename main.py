# main.py
# Main application entry point and game loop.
# This version includes a definitive fix for the Infinity JSON serialization error.

import asyncio
import websockets
import json
import math
from collections import defaultdict
from game_engine.map import GameMap
from game_engine.gamestate import GameState
from game_engine.hypergraph import TurnHypergraph, Move, Hold, Support
from game_engine.adjudicator import Adjudicator
from cli.parser import parse_order_string
from cli.display import (display_welcome, display_board_state, 
                         display_orders, display_results, display_turn_info)

# --- WebSocket Server Setup ---
CONNECTED_CLIENTS = set()

def sanitize_for_json(data):
    """
    Recursively traverses a data structure and replaces non-JSON-compliant
    values like float('inf') with None (which becomes 'null' in JSON).
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(i) for i in data]
    elif isinstance(data, float) and math.isinf(data):
        return None # JSON standard for null
    return data

async def register(websocket):
    """Registers a new client connection."""
    CONNECTED_CLIENTS.add(websocket)
    print(f"Visualizer connected. Total connections: {len(CONNECTED_CLIENTS)}")
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Visualizer disconnected. Total connections: {len(CONNECTED_CLIENTS)}")

async def broadcast(message):
    """Broadcasts a message to all connected clients after sanitizing it."""
    if CONNECTED_CLIENTS:
        sanitized_message = sanitize_for_json(message)
        tasks = [asyncio.create_task(client.send(json.dumps(sanitized_message))) for client in CONNECTED_CLIENTS]
        if tasks:
            await asyncio.wait(tasks)

# --- Game Logic ---

async def run_turn(game_state):
    """Runs a single, complete game turn, broadcasting state to the visualizer."""
    display_turn_info(game_state)
    display_board_state(game_state)
    await broadcast({
        "type": "turn_update",
        "season": game_state.season,
        "year": game_state.year,
        "units": [u.__dict__ for u in game_state.units.values()]
    })

    raw_orders = []
    units_by_nationality = defaultdict(list)
    for unit in game_state.units.values():
        units_by_nationality[unit.nationality].append(unit)

    print("\n--- Please Enter Orders ---")
    print("Use standard notation (e.g., '- BUR', 'S RUH H').")
    
    for nation in sorted(units_by_nationality.keys()):
        print(f"\n--- Orders for {nation} ---")
        for unit in sorted(units_by_nationality[nation], key=lambda u: u.id):
            available_moves = game_state.game_map.adjacencies.get(unit.location, [])
            if available_moves:
                print(f"    (Unit {unit.id} in {unit.location} can move to: {', '.join(available_moves)})")
            
            while True:
                try:
                    prompt = f"  Order for {unit.type} at {unit.location}: "
                    order_string = await asyncio.to_thread(input, prompt)
                    if not order_string: order_string = "H"
                    
                    parsed_order = parse_order_string(order_string, unit, game_state)
                    raw_orders.append(parsed_order)
                    
                    order_dict = parsed_order.__dict__.copy()
                    order_dict['unit'] = parsed_order.unit.__dict__
                    await broadcast({ "type": "add_order", "order": order_dict })
                    break
                except ValueError as e:
                    print(f"    ERROR: {e} Please enter a valid order.")
                except Exception as e:
                    print(f"    Invalid order format. Please try again. Error: {e}")

    for order in raw_orders:
        if isinstance(order, Support):
            supported_unit = next((u for u in game_state.units.values() if u.location == order.supported_unit_loc), None)
            if not supported_unit: order.supported_order_id = "INVALID_UNIT"; continue
            target_order = next((o for o in raw_orders if o.unit.id == supported_unit.id), None)
            if not target_order: order.supported_order_id = "INVALID_NO_ORDER"; continue
            action_province = order.move_destination if order.is_move else supported_unit.location
            supporter_adjacencies = game_state.game_map.adjacencies.get(order.unit.location, [])
            if action_province not in supporter_adjacencies: order.supported_order_id = "INVALID_NOT_ADJACENT"; continue
            is_match = (order.is_move and isinstance(target_order, Move) and target_order.to_province_id == order.move_destination) or \
                       (not order.is_move and isinstance(target_order, Hold))
            order.supported_order_id = target_order.id if is_match else "INVALID_ACTION_MISMATCH"

    turn_hypergraph = TurnHypergraph()
    for order in raw_orders:
        turn_hypergraph.add_order(order)
    game_state.turn_hypergraph = turn_hypergraph
    
    display_orders(turn_hypergraph.orders.values())
    
    print("\n--- Adjudicating Turn... ---")
    adjudicator = Adjudicator(game_state, turn_hypergraph)
    results, details = adjudicator.solve()
    
    display_results(results, details, game_state)
    
    await broadcast({ "type": "adjudication_result", "results": results, "details": details })
    
    game_state.update_state_after_turn(results)
    game_state.advance_turn()
    return True

async def game_loop():
    """Main game loop for interactive play."""
    display_welcome()
    
    game_map = GameMap('data/classic_map.json')
    game_state = GameState(game_map, 'data/game_save.json')

    await broadcast({
        "type": "initial_state",
        "provinces": {pid: p.__dict__ for pid, p in game_map.provinces.items()},
        "adjacencies": [{"source": s, "target": t} for s, t_list in game_map.adjacencies.items() for t in t_list],
        "units": [u.__dict__ for u in game_state.units.values()]
    })
    
    print("\nVisualizer connected. Starting game in 3 seconds...")
    await asyncio.sleep(3)
    
    while True:
        if not await run_turn(game_state):
            break
        if not game_state.units:
            print("\n--- No units remaining on the board. Game Over. ---")
            await broadcast({"type": "game_over"})
            break
        cont = await asyncio.to_thread(input, "Proceed to next turn? (Y/n): ")
        if cont.strip().lower() == 'n':
            print("Exiting game.")
            await broadcast({"type": "game_over"})
            break

async def main():
    port = 8765
    print(f"--- Starting Diplomacy Engine ---")
    print(f"WebSocket server started on ws://localhost:{port}")
    print("Please open 'diplomacy_visualizer.html' in your browser to see the game board.")

    async with websockets.serve(register, "localhost", port):
        while not CONNECTED_CLIENTS:
            await asyncio.sleep(1)
        await game_loop()

if __name__ == "__main__":
    asyncio.run(main())
