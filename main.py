# main.py
# Main application entry point and game loop.
# This version is refactored to allow map selection at startup.

import asyncio
import websockets
import json
import math
import os
from pathlib import Path
from collections import defaultdict
from game_engine.map import GameMap
from game_engine.gamestate import GameState
from game_engine.hypergraph import TurnHypergraph, Move, Hold, Support
from game_engine.adjudicator import Adjudicator
from cli.parser import parse_order_string
from cli.display import (display_welcome, display_board_state, 
                         display_orders, display_results, display_turn_info)

def sanitize_for_json(data):
    """
    Recursively traverses a data structure (dicts, lists, tuples) and converts
    non-JSON-serializable values to JSON-compliant equivalents.
    Currently handles:
    - float('inf') and float('-inf'): Replaces with None (becomes 'null' in JSON).
    - Tuples: Converts to lists.
    Custom objects (like Unit, Province, Order) should ideally be converted to dicts
    (e.g., using obj.__dict__) before being included in the data structure passed here,
    though this function will not fail on them, they might not serialize as expected
    by the client unless they are simple data containers.
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(i) for i in data]
    elif isinstance(data, tuple):
        return [sanitize_for_json(i) for i in data]
    elif isinstance(data, float) and math.isinf(data):
        return None
    return data

def select_map():
    """Scans the data directory for map files and prompts the user to select one."""
    data_dir = Path(__file__).parent / 'data'
    # Find all .json files, excluding game_save.json
    map_files = sorted([f for f in os.listdir(data_dir) if f.endswith('.json') and f != 'game_save.json'])

    if not map_files:
        print("Error: No map files found in the 'data' directory.")
        return None

    print("\n--- Please Select a Map ---")
    for i, map_file in enumerate(map_files):
        # Create a user-friendly name from the filename
        display_name = map_file.replace('.json', '').replace('_', ' ').title()
        print(f"  [{i + 1}] {display_name}")

    while True:
        try:
            choice = input(f"\nEnter the number of the map you want to play (1-{len(map_files)}): ")
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(map_files):
                selected_map_path = data_dir / map_files[choice_index]
                print(f"Loading map: {map_files[choice_index]}...")
                return str(selected_map_path)
            else:
                print(f"Invalid number. Please enter a number between 1 and {len(map_files)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nExiting.")
            return None


class Game:
    """
    Encapsulates the entire game logic, state, and WebSocket communication.

    MULTI-PLAYER SCALABILITY NOTES:
    - Instance Management: Currently, this class represents a single global game. For multiple
      concurrent games, a manager would be needed to map client connections or game IDs
      to distinct Game instances.
    - Player Identification: WebSocket handlers would need to identify which player a
      connection belongs to, likely via an authentication token or session ID established
      on connection.
    - State Scoping: Game state (self.game_state, self.game_map) is per-instance. If Game
      instances are managed, this is fine.
    """
    def __init__(self, map_path: str):
        if not map_path or not Path(map_path).exists():
            raise FileNotFoundError(f"The selected map file could not be found at: {map_path}")
            
        self.game_map = GameMap(map_path)
        # Note: You might want to create different game_save.json files for each map
        self.game_state = GameState(self.game_map, 'data/game_save.json')
        self.connected_clients = set()

    async def register(self, websocket):
        """
        Registers a new client, sends the current state, and handles disconnection.

        MULTI-PLAYER SCALABILITY NOTES:
        - Authentication: For actual multi-player, an authentication step would be needed here
          to associate the websocket connection with a specific player/nation in the game.
        - Player-Specific State: The initial state sent might need to be tailored if players
          should only see certain parts of the game state (e.g., their own orders).
        """
        self.connected_clients.add(websocket)
        print(f"Visualizer connected. Total connections: {len(self.connected_clients)}")
        
        try:
            central_province_id = None
            if self.game_map.adjacencies:
                central_province_id = max(self.game_map.adjacencies, key=lambda p: len(self.game_map.adjacencies[p]))

            initial_state_message = {
                "type": "initial_state",
                "provinces": {pid: p.__dict__ for pid, p in self.game_map.provinces.items()},
                "adjacencies": [{"source": s, "target": t} for s, t_list in self.game_map.adjacencies.items() for t in t_list],
                "units": [u.__dict__ for u in self.game_state.units.values()],
                "season": self.game_state.season,
                "year": self.game_state.year,
                "centralProvinceId": central_province_id
            }
            await websocket.send(json.dumps(sanitize_for_json(initial_state_message)))
            await websocket.wait_closed()
        finally:
            self.connected_clients.remove(websocket)
            print(f"Visualizer disconnected. Total connections: {len(self.connected_clients)}")

    async def broadcast(self, message):
        """
        Broadcasts a message to all connected clients.

        MULTI-PLAYER SCALABILITY NOTES:
        - Targeted Messaging: In a multi-player game, many messages should be targeted to
          specific players or groups (e.g., orders for one nation, private messages)
          rather than broadcast to everyone. This would require managing connections
          per player.
        - Selective Broadcasting: Some messages (like general game state updates) might still
          be broadcast, but potentially with player-specific views filtered.
        """
        if self.connected_clients:
            sanitized_message = sanitize_for_json(message)
            tasks = [asyncio.create_task(client.send(json.dumps(sanitized_message))) for client in self.connected_clients]
            if tasks:
                await asyncio.wait(tasks)

    async def run_turn(self):
        """
        Runs a single, complete game turn.

        MULTI-PLAYER SCALABILITY NOTES:
        - Order Submission: Instead of iterating through all units locally, the server would
          wait for orders from each player's client via WebSocket messages. This would involve
          deadlines, handling partial submissions, and potentially private order confirmation.
        - Turn Progression: Logic to advance turns/phases might depend on all players
          confirming readiness or a timeout, rather than synchronous input.
        - Order Privacy: Raw orders (`raw_orders`) should not be broadcast if submitted
          privately until the adjudication/results phase. The current broadcasting of
          `add_order` is for visualization and assumes a single local player.
        """
        display_turn_info(self.game_state)
        
        await self.broadcast({
            "type": "turn_update",
            "season": self.game_state.season,
            "year": self.game_state.year,
            "units": [u.__dict__ for u in self.game_state.units.values()]
        })

        display_board_state(self.game_state)
        raw_orders = []
        units_by_nationality = defaultdict(list)
        for unit in self.game_state.units.values():
            units_by_nationality[unit.nationality].append(unit)

        print("\n--- Please Enter Orders ---")
        for nation in sorted(units_by_nationality.keys()):
            print(f"\n--- Orders for {nation} ---")
            for unit in sorted(units_by_nationality[nation], key=lambda u: u.id):
                
                available_moves = self.game_state.game_map.adjacencies.get(unit.location, [])
                if available_moves:
                    print(f"    (Unit {unit.id} in {unit.location} can move to: {', '.join(available_moves)})")

                while True:
                    try:
                        prompt = f"  Order for {unit.type} at {unit.location}: "
                        order_string = await asyncio.to_thread(input, prompt)
                        if not order_string: order_string = "H"
                        
                        parsed_order = parse_order_string(order_string, unit, self.game_state)
                        raw_orders.append(parsed_order)
                        
                        order_dict = parsed_order.__dict__.copy()
                        order_dict['unit'] = parsed_order.unit.__dict__
                        
                        if isinstance(parsed_order, Support):
                            supported_unit = next((u for u in self.game_state.units.values() if u.location == parsed_order.supported_unit_loc), None)
                            order_dict['is_valid_support'] = bool(supported_unit)
                            if supported_unit:
                                order_dict['supported_action_start_loc'] = parsed_order.supported_unit_loc
                                order_dict['supported_action_end_loc'] = parsed_order.move_destination if parsed_order.is_move else parsed_order.supported_unit_loc

                        await self.broadcast({ "type": "add_order", "order": order_dict })
                        break
                    except Exception as e:
                        print(f"    Invalid order format. Please try again. Error: {e}")

        turn_hypergraph = TurnHypergraph()
        for order in raw_orders: # Add all parsed (raw) orders to the hypergraph first
            turn_hypergraph.add_order(order)

        # After all orders are in the hypergraph, perform validation and linking for supports.
        # This requires game_state for unit locations and map adjacencies.
        turn_hypergraph.finalize_and_validate_supports(self.game_state)

        self.game_state.turn_hypergraph = turn_hypergraph # Assign the processed hypergraph to game_state
        
        display_orders(turn_hypergraph.orders.values())
        
        print("\n--- Adjudicating Turn... ---")
        adjudicator = Adjudicator(self.game_state, turn_hypergraph)
        results, details = adjudicator.solve()
        
        display_results(results, details, self.game_state)
        await self.broadcast({ "type": "adjudication_result", "results": results, "details": details })
        
        self.game_state.update_state_after_turn(results)
        self.game_state.advance_turn()

    async def game_loop(self):
        """Main game loop for interactive play."""
        display_welcome()
        print("\nWaiting for visualizer to connect...")
        while not self.connected_clients:
            await asyncio.sleep(1)
        
        print("Visualizer connected. Starting game.")
        
        while True:
            await self.run_turn()
            if not self.game_state.units:
                print("\n--- No units remaining on the board. Game Over. ---")
                await self.broadcast({"type": "game_over"})
                break
            cont = await asyncio.to_thread(input, "Proceed to next turn? (Y/n): ")
            if cont.strip().lower() == 'n':
                print("Exiting game.")
                await self.broadcast({"type": "game_over"})
                break

async def main():
    port = 8765
    print(f"--- Starting Diplomacy Engine ---")
    
    # Let the user select the map before starting the server
    selected_map_path = select_map()
    if not selected_map_path:
        return # Exit if no map was chosen or an error occurred

    print(f"WebSocket server started on ws://localhost:{port}")
    print("Please open 'Visualiser/diplomacy_visualiser.html' in your browser to see the game board.")
    
    try:
        game = Game(selected_map_path)
        async with websockets.serve(game.register, "localhost", port):
            await game.game_loop()
    except FileNotFoundError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())