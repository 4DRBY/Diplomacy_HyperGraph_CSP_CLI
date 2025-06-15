# main.py
# Main application entry point and game loop.
# This version is refactored into a Game class to correctly handle state
# for clients that connect or reload mid-game.

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

def sanitize_for_json(data):
    """
    Recursively traverses a data structure and replaces non-JSON-compliant
    values like float('inf') with None (which becomes 'null' in JSON).
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

class Game:
    """Encapsulates the entire game logic, state, and WebSocket communication."""
    def __init__(self):
        self.game_map = GameMap('data/classic_map.json')
        self.game_state = GameState(self.game_map, 'data/game_save.json')
        self.connected_clients = set()

    async def register(self, websocket):
        """Registers a new client, sends the current state, and handles disconnection."""
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
        """Broadcasts a message to all connected clients."""
        if self.connected_clients:
            sanitized_message = sanitize_for_json(message)
            tasks = [asyncio.create_task(client.send(json.dumps(sanitized_message))) for client in self.connected_clients]
            if tasks:
                await asyncio.wait(tasks)

    async def run_turn(self):
        """Runs a single, complete game turn."""
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
                
                # *** FIX: Restore the helper text for adjacent territories ***
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

        for order in raw_orders:
            if isinstance(order, Support):
                supported_unit = next((u for u in self.game_state.units.values() if u.location == order.supported_unit_loc), None)
                if not supported_unit: order.supported_order_id = "INVALID_UNIT"; continue
                target_order = next((o for o in raw_orders if o.unit.id == supported_unit.id), None)
                if not target_order: order.supported_order_id = "INVALID_NO_ORDER"; continue
                action_province = order.move_destination if order.is_move else supported_unit.location
                supporter_adjacencies = self.game_state.game_map.adjacencies.get(order.unit.location, [])
                if action_province not in supporter_adjacencies: order.supported_order_id = "INVALID_NOT_ADJACENT"; continue
                is_match = (order.is_move and isinstance(target_order, Move) and target_order.to_province_id == order.move_destination) or \
                           (not order.is_move and isinstance(target_order, Hold))
                order.supported_order_id = target_order.id if is_match else "INVALID_ACTION_MISMATCH"

        turn_hypergraph = TurnHypergraph()
        for order in raw_orders:
            turn_hypergraph.add_order(order)
        self.game_state.turn_hypergraph = turn_hypergraph
        
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
    print(f"WebSocket server started on ws://localhost:{port}")
    print("Please open 'Visualiser/diplomacy_visualiser.html' in your browser to see the game board.")
    
    game = Game()
    async with websockets.serve(game.register, "localhost", port):
        await game.game_loop()

if __name__ == "__main__":
    asyncio.run(main())