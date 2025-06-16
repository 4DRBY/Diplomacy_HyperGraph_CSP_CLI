import unittest
from unittest.mock import Mock

from cli.parser import parse_order_string
from game_engine.gamestate import GameState, Unit
from game_engine.map import GameMap # Required for GameState
from game_engine.hypergraph import Move, Hold, Support # Expected output types
from pathlib import Path

# Path to the classic map file, assuming script is run from project root or tests/
TEST_MAP_PATH = Path(__file__).parent.parent / 'data' / 'classic_map.json'

class TestParser(unittest.TestCase):
    def setUp(self):
        # Mock GameState and Unit for parsing tests
        # A real GameMap is needed by GameState, so we load it.
        self.map = GameMap(TEST_MAP_PATH)
        self.game_state = GameState(self.map)

        # Mock a unit; its location and type are important for parsing
        self.mock_unit_army_london = Unit("U1", "England", "Army", "LON") # Corrected: type then location
        self.mock_unit_fleet_north_sea = Unit("U2", "Germany", "Fleet", "NTH") # Corrected: type then location

        # Add adjacencies for LON to game_state's map for move validation
        # This setup is a bit simplified; ideally, the mock GameState's map
        # would be fully configured or we'd use a specific test map.
        # For now, directly setting adjacencies for the mock unit's location.
        if not self.game_state.game_map.adjacencies:
             self.game_state.game_map.adjacencies = {} # Ensure it's initialized
        self.game_state.game_map.adjacencies["LON"] = ["WAL", "ENG", "PIC", "BEL", "NTH"]


    def test_parse_move_valid_army(self):
        order_str = "LON - WAL" # Implicitly uses self.mock_unit_army_london
        order = parse_order_string(order_str, self.mock_unit_army_london, self.game_state)
        self.assertIsInstance(order, Move)
        self.assertEqual(order.unit, self.mock_unit_army_london)
        self.assertEqual(order.to_province_id, "WAL")

    def test_parse_move_valid_with_unit_prefix(self):
        # Parser should ignore "A LON" if unit is already provided
        order_str = "A LON - WAL"
        order = parse_order_string(order_str, self.mock_unit_army_london, self.game_state)
        self.assertIsInstance(order, Move)
        self.assertEqual(order.to_province_id, "WAL")

    def test_parse_move_invalid_non_adjacent(self):
        order_str = "LON - PAR" # LON is not adjacent to PAR in classic_map
        with self.assertRaisesRegex(ValueError, "not adjacent to PAR"):
            parse_order_string(order_str, self.mock_unit_army_london, self.game_state)

    def test_parse_hold_simple(self):
        order_str = "H"
        order = parse_order_string(order_str, self.mock_unit_army_london, self.game_state)
        self.assertIsInstance(order, Hold)
        self.assertEqual(order.unit, self.mock_unit_army_london)

    def test_parse_hold_with_location(self):
        order_str = "LON H" # Parser should ignore location if unit is provided
        order = parse_order_string(order_str, self.mock_unit_army_london, self.game_state)
        self.assertIsInstance(order, Hold)

    def test_parse_support_hold_valid(self):
        # Assuming self.mock_unit_fleet_north_sea is supporting self.mock_unit_army_london holding
        # NTH is adjacent to LON.
        self.game_state.game_map.adjacencies["NTH"] = ["LON", "SKA", "EDI", "YOR", "HOL", "BEL", "ENG"]
        order_str = "NTH S LON H" # Support Hold
        order = parse_order_string(order_str, self.mock_unit_fleet_north_sea, self.game_state)
        self.assertIsInstance(order, Support)
        self.assertEqual(order.unit, self.mock_unit_fleet_north_sea)
        self.assertEqual(order.supported_unit_loc, "LON")
        self.assertFalse(order.is_move)
        self.assertIsNone(order.move_destination)

    def test_parse_support_hold_valid_short_form(self):
        # NTH S LON (implies support hold)
        self.game_state.game_map.adjacencies["NTH"] = ["LON", "SKA", "EDI", "YOR", "HOL", "BEL", "ENG"]
        order_str = "NTH S LON"
        order = parse_order_string(order_str, self.mock_unit_fleet_north_sea, self.game_state)
        self.assertIsInstance(order, Support)
        self.assertEqual(order.supported_unit_loc, "LON")
        self.assertFalse(order.is_move)

    def test_parse_support_move_valid(self):
        # Assuming self.mock_unit_fleet_north_sea is supporting self.mock_unit_army_london moving LON-WAL
        # NTH is adjacent to WAL (the destination of the move being supported)
        self.game_state.game_map.adjacencies["NTH"] = ["WAL", "SKA", "EDI", "YOR", "HOL", "BEL", "ENG"]
        order_str = "NTH S LON - WAL"
        order = parse_order_string(order_str, self.mock_unit_fleet_north_sea, self.game_state)
        self.assertIsInstance(order, Support)
        self.assertEqual(order.unit, self.mock_unit_fleet_north_sea)
        self.assertEqual(order.supported_unit_loc, "LON") # Location of the unit whose move is supported
        self.assertTrue(order.is_move)
        self.assertEqual(order.move_destination, "WAL") # Destination of the move being supported

    def test_parse_support_move_valid_with_unit_prefix_in_supported_action(self):
        self.game_state.game_map.adjacencies["NTH"] = ["WAL", "SKA", "EDI", "YOR", "HOL", "BEL", "ENG"]
        order_str = "NTH S A LON - WAL" # Support Army LON move to WAL
        order = parse_order_string(order_str, self.mock_unit_fleet_north_sea, self.game_state)
        self.assertIsInstance(order, Support)
        self.assertEqual(order.supported_unit_loc, "LON")
        self.assertTrue(order.is_move)
        self.assertEqual(order.move_destination, "WAL")

if __name__ == '__main__':
    unittest.main()
