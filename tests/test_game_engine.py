import unittest
from pathlib import Path

from game_engine.map import GameMap
from game_engine.gamestate import GameState, Unit
from game_engine.hypergraph import TurnHypergraph, Move, Hold, Support
from game_engine.adjudicator import Adjudicator

# Path to the classic map file, assuming script is run from project root or tests/
# Adjust if necessary depending on execution context of tests
TEST_MAP_PATH = Path(__file__).parent.parent / 'data' / 'classic_map.json'

class TestAdjudicator(unittest.TestCase):
    def setUp(self):
        """Set up a basic game map, game state, and turn hypergraph for each test."""
        self.map = GameMap(TEST_MAP_PATH)
        self.game_state = GameState(self.map)
        self.turn_hypergraph = TurnHypergraph()

        # Clear units for a clean slate, then add specific units for tests
        self.game_state.units = {}

    def _add_unit(self, unit_id, nationality, province_id, unit_type="Army"):
        unit = Unit(unit_id, nationality, unit_type, province_id)
        self.game_state.units[unit_id] = unit
        return unit

    def test_simple_move_success(self):
        # Unit moves to an empty adjacent province
        u1 = self._add_unit("U1", "England", "LON", "Army")
        move_order = Move("Order_U1", u1, "WAL")
        self.turn_hypergraph.add_order(move_order)

        self.turn_hypergraph.finalize_and_validate_supports(self.game_state)
        adjudicator = Adjudicator(self.game_state, self.turn_hypergraph)
        results, details = adjudicator.solve()

        self.assertEqual(results.get("U1"), "moves")
        # After move, U1 should be in WAL
        # This check should be in GameState tests, Adjudicator only returns outcome.

    def test_simple_hold(self):
        u1 = self._add_unit("U1", "France", "PAR", "Army")
        hold_order = Hold("Order_U1", u1)
        self.turn_hypergraph.add_order(hold_order)

        self.turn_hypergraph.finalize_and_validate_supports(self.game_state)
        adjudicator = Adjudicator(self.game_state, self.turn_hypergraph)
        results, details = adjudicator.solve()

        self.assertEqual(results.get("U1"), "stands")

    def test_move_conflict_bounce(self):
        # U1 (LON -> BEL) vs U2 (HOL -> BEL), both strength 1
        u1 = self._add_unit("U1", "England", "LON", "Army")
        u2 = self._add_unit("U2", "Germany", "HOL", "Army")

        move1 = Move("Order_U1", u1, "BEL")
        move2 = Move("Order_U2", u2, "BEL")
        self.turn_hypergraph.add_order(move1)
        self.turn_hypergraph.add_order(move2)

        self.turn_hypergraph.finalize_and_validate_supports(self.game_state)
        adjudicator = Adjudicator(self.game_state, self.turn_hypergraph)
        results, details = adjudicator.solve()

        self.assertEqual(results.get("U1"), "stands") # Bounce
        self.assertEqual(results.get("U2"), "stands") # Bounce

        # Check conflict details
        self.assertIn("BEL", details['conflicts'])
        self.assertTrue(details['conflicts']["BEL"]['is_tie'])


class TestGameState(unittest.TestCase):
    def setUp(self):
        self.map = GameMap(TEST_MAP_PATH)
        self.game_state = GameState(self.map)
        self.game_state.units = {} # Start with no units

    def _add_unit(self, unit_id, nationality, province_id, unit_type="Army"):
        unit = Unit(unit_id, nationality, unit_type, province_id)
        self.game_state.units[unit_id] = unit
        return unit

    def test_update_state_after_turn_moves(self):
        u1 = self._add_unit("U1", "England", "LON", "Army")
        # Mock results where U1 moves to WAL
        results = {"U1": "moves"}
        # Mock turn_hypergraph with the move order
        self.game_state.turn_hypergraph = TurnHypergraph()
        move_order = Move("Order_U1", u1, "WAL")
        self.game_state.turn_hypergraph.add_order(move_order)

        self.game_state.update_state_after_turn(results)
        self.assertEqual(self.game_state.units["U1"].location, "WAL")

    def test_update_state_after_turn_dislodged(self):
        u1 = self._add_unit("U1", "France", "PAR", "Army")
        results = {"U1": "dislodged"}
        # turn_hypergraph can be minimal as it's not strictly needed for dislodgement outcome
        self.game_state.turn_hypergraph = TurnHypergraph()
        # Hold order for U1 (or any order, outcome is what matters)
        hold_order = Hold("Order_U1", u1)
        self.game_state.turn_hypergraph.add_order(hold_order)


        self.game_state.update_state_after_turn(results)
        self.assertNotIn("U1", self.game_state.units)

    def test_advance_phase(self):
        initial_year = self.game_state.year
        initial_season = self.game_state.season
        initial_phase = self.game_state.phase

        # Test a full cycle of phases
        phases_in_cycle = len(self.game_state._phase_sequence)

        for i in range(phases_in_cycle):
            self.game_state.advance_phase()
            current_season, current_phase = self.game_state._phase_sequence[self.game_state._current_phase_index]
            self.assertEqual(self.game_state.season, current_season)
            self.assertEqual(self.game_state.phase, current_phase)
            if i < phases_in_cycle -1 : # Year should not advance until cycle completes
                 self.assertEqual(self.game_state.year, initial_year)

        # After a full cycle, year should advance by 1, and phase should reset
        self.assertEqual(self.game_state.year, initial_year + 1)
        self.assertEqual(self.game_state.season, self.game_state._phase_sequence[0][0])
        self.assertEqual(self.game_state.phase, self.game_state._phase_sequence[0][1])


class TestTurnHypergraph(unittest.TestCase):
    def setUp(self):
        self.map = GameMap(TEST_MAP_PATH)
        self.game_state = GameState(self.map)
        self.game_state.units = {} # Clear units initially

        # Corrected Unit instantiation: type then location
        self.u1 = Unit("U1", "England", "Army", "LON")
        self.u2 = Unit("U2", "France", "Army", "PAR")
        self.game_state.units = {"U1": self.u1, "U2": self.u2}

        self.turn_hypergraph = TurnHypergraph()

    def test_add_order_duplicate_unit_id_raises_error(self):
        order1 = Hold("Order1_U1", self.u1)
        self.turn_hypergraph.add_order(order1)
        order2 = Move("Order2_U1", self.u1, "WAL") # Second order for U1
        with self.assertRaises(ValueError):
            self.turn_hypergraph.add_order(order2)

    def test_finalize_and_validate_supports_valid_hold_support(self):
        # U1 LON supports U2 PAR H
        support_order = Support("Support_U1", self.u1, "PAR", is_move=False)
        hold_order_u2 = Hold("Hold_U2", self.u2)

        self.turn_hypergraph.add_order(support_order)
        self.turn_hypergraph.add_order(hold_order_u2)
        self.turn_hypergraph.finalize_and_validate_supports(self.game_state)

        self.assertEqual(support_order.supported_order_id, hold_order_u2.id)

    def test_finalize_and_validate_supports_invalid_unit_not_found(self):
        # U1 LON supports non-existent unit in MAR
        support_order = Support("Support_U1", self.u1, "MAR", is_move=False)
        self.turn_hypergraph.add_order(support_order)
        self.turn_hypergraph.finalize_and_validate_supports(self.game_state)
        self.assertEqual(support_order.supported_order_id, "INVALID_UNIT_NOT_FOUND")

    def test_finalize_and_validate_supports_invalid_target_has_no_order(self):
        # U1 LON supports U2 PAR (but U2 has no order)
        support_order = Support("Support_U1", self.u1, "PAR", is_move=False)
        # U2 has no order added to hypergraph
        self.turn_hypergraph.add_order(support_order)
        self.turn_hypergraph.finalize_and_validate_supports(self.game_state)
        self.assertEqual(support_order.supported_order_id, "INVALID_TARGET_HAS_NO_ORDER")

    def test_finalize_and_validate_supports_invalid_support_not_adjacent_to_action(self):
        # U1 (LON) supports U2 (PAR) move to BUR. LON is not adjacent to BUR.
        # Need to ensure U2 is in PAR, and its order is PAR-BUR
        self.u2.location = "PAR" # ensure U2 is in PAR
        support_order = Support("Support_U1", self.u1, "PAR", is_move=True, move_destination="BUR")
        move_order_u2 = Move("Move_U2", self.u2, "BUR")

        self.turn_hypergraph.add_order(support_order)
        self.turn_hypergraph.add_order(move_order_u2)
        self.turn_hypergraph.finalize_and_validate_supports(self.game_state)
        # LON is not adjacent to BUR (action province)
        self.assertEqual(support_order.supported_order_id, "INVALID_SUPPORT_NOT_ADJACENT_TO_ACTION")


if __name__ == '__main__':
    unittest.main()
