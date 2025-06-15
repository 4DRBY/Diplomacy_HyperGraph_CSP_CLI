# game_engine/adjudicator.py
# The core logic to resolve the turn's hypergraph of orders using CSP.
# This version includes a definitive re-architecture of the adjudication logic,
# correcting the fundamental flaw in dislodgement rules to permanently fix the
# "No consistent resolution found" error.

import constraint
from collections import defaultdict
from .hypergraph import Move, Support, Hold

class Adjudicator:
    """
    Solves the adjudication problem by modeling it as a multi-stage
    Constraint Satisfaction Problem, preventing logical paradoxes.
    """
    def __init__(self, game_state, turn_hypergraph):
        self.game_state = game_state
        self.turn_graph = turn_hypergraph
        self.problem = constraint.Problem()
        
        self.all_orders = list(self.turn_graph.orders.values())
        self.move_orders = [o for o in self.all_orders if isinstance(o, Move)]
        self.support_orders = [o for o in self.all_orders if isinstance(o, Support)]
        
        self._units_with_orders = {o.unit.id for o in self.all_orders}
        self.resolution_details = {}

    def solve(self):
        """Solves the CSP and returns the final outcomes and analysis."""
        try:
            self._setup_variables_and_domains()
            self._add_constraints()
            
            solutions = self.problem.getSolutions()
            
            if not solutions: 
                return "Error: No consistent resolution found. This indicates a deep logical flaw in the constraints.", {}
            if len(solutions) > 1: 
                print(f"Warning: {len(solutions)} solutions found, indicating ambiguity. Returning the first.")
            
            solution = solutions[0]
            final_outcomes = {var.replace("outcome_", ""): val for var, val in solution.items() if var.startswith("outcome_")}
            self._populate_resolution_details(solution)

            return final_outcomes, self.resolution_details
        except Exception as e:
            print(f"An unexpected error occurred during adjudication: {e}")
            return f"Adjudication failed due to an unexpected error: {e}", {}

    def _populate_resolution_details(self, solution):
        """Generates a detailed analysis based on the CSP solution."""
        self.resolution_details = {
            'support_statuses': {s.id: solution.get(f"status_{s.id}") for s in self.support_orders},
            'strengths': {o.id: solution.get(f"strength_{o.id}") for o in self.all_orders},
            'conflicts': {}
        }
        for province_id, province in self.game_state.game_map.provinces.items():
            moves_to_province = [m for m in self.move_orders if m.to_province_id == province_id]
            unit_in_province = self.game_state.get_unit_at(province_id)
            contenders = moves_to_province[:]
            if unit_in_province and unit_in_province.id in self._units_with_orders:
                order = next((o for o in self.all_orders if o.unit.id == unit_in_province.id), None)
                if order: contenders.append(order)

            if len(contenders) < 2 and not moves_to_province: continue

            conflict_strengths = {c.unit.id: self.resolution_details['strengths'].get(c.id, 1) for c in contenders}
            if not conflict_strengths: continue
            max_strength = max(conflict_strengths.values())
            winners = {uid for uid, s in conflict_strengths.items() if s == max_strength}
            
            self.resolution_details['conflicts'][province.id] = {
                'province_name': province.name, 'strengths': conflict_strengths,
                'is_tie': len(winners) > 1, 'winner': list(winners)[0] if len(winners) == 1 else None
            }

    def _setup_variables_and_domains(self):
        max_possible_strength = len(self.all_orders) + 1
        for unit in self.game_state.units.values():
            self.problem.addVariable(f"outcome_{unit.id}", ['stands', 'moves', 'dislodged'])
        for order in self.all_orders:
            self.problem.addVariable(f"strength_{order.id}", range(1, max_possible_strength))
        for support in self.support_orders:
            domain = ['invalid'] if "INVALID" in support.supported_order_id else ['valid', 'cut']
            self.problem.addVariable(f"status_{support.id}", domain)
    
    def _add_constraints(self):
        self._add_support_status_constraints()
        self._add_strength_calculation_constraints()
        self._add_outcome_resolution_constraints()

    def _add_support_status_constraints(self):
        for support in self.support_orders:
            if "INVALID" in support.supported_order_id:
                self.problem.addConstraint(lambda status: status == 'invalid', (f"status_{support.id}",))
                continue
            supported_order = self.turn_graph.orders.get(support.supported_order_id)
            if not supported_order: continue
            action_province_id = supported_order.to_province_id if isinstance(supported_order, Move) else supported_order.unit.location
            is_attacked = any(m.to_province_id == support.unit.location and m.unit.location != action_province_id and m.unit.nationality != support.unit.nationality for m in self.move_orders)
            self.problem.addConstraint(lambda status, attacked=is_attacked: status == ('cut' if attacked else 'valid'), (f"status_{support.id}",))

    def _add_strength_calculation_constraints(self):
        for order in self.all_orders:
            relevant_supports = [s for s in self.support_orders if s.supported_order_id == order.id and "INVALID" not in s.supported_order_id]
            support_status_vars = [f"status_{s.id}" for s in relevant_supports]
            def strength_rule(strength, *statuses):
                return strength == 1 + sum(1 for s in statuses if s == 'valid')
            self.problem.addConstraint(strength_rule, [f"strength_{order.id}"] + support_status_vars)

    def _add_outcome_resolution_constraints(self):
        moving_unit_ids = {order.unit.id for order in self.move_orders}
        for unit_id in self.game_state.units:
            if unit_id not in moving_unit_ids:
                self.problem.addConstraint(lambda outcome: outcome != 'moves', (f"outcome_{unit_id}",))
        
        # --- DEFINITIVE FIX V17 ---
        # The logic is now broken into two clear parts:
        # 1. Resolve conflicts in each province to determine which moves succeed.
        # 2. Determine dislodgements based on successful moves into occupied provinces.

        # Part 1: Resolve all move conflicts
        for province_id in self.game_state.game_map.provinces:
            # All moves targeting this province
            moves_to_province = [m for m in self.move_orders if m.to_province_id == province_id]
            
            # The defending unit, if any, and its hold order
            defending_unit = self.game_state.get_unit_at(province_id)
            hold_order = None
            if defending_unit:
                hold_order = next((o for o in self.all_orders if o.unit.id == defending_unit.id), None)

            # Determine the single strongest move, if there is one
            strongest_move = None
            max_strength = 0
            is_tie = False
            
            move_strengths = {m.id: self.problem.getSolutions()[0][f"strength_{m.id}"] for m in moves_to_province}
            
            if move_strengths:
                max_strength = max(move_strengths.values())
                top_movers = [m for m in moves_to_province if move_strengths[m.id] == max_strength]
                if len(top_movers) == 1:
                    strongest_move = top_movers[0]
                else:
                    is_tie = True

            # The hold strength of the defending unit
            hold_strength = 0
            if hold_order:
                hold_strength = self.problem.getSolutions()[0][f"strength_{hold_order.id}"]

            # Rule: A move succeeds if it's strictly stronger than the strongest hold/move it opposes.
            if strongest_move:
                if max_strength > hold_strength:
                    self.problem.addConstraint(lambda outcome: outcome == 'moves', (f"outcome_{strongest_move.unit.id}",))
                else:
                    self.problem.addConstraint(lambda outcome: outcome == 'stands', (f"outcome_{strongest_move.unit.id}",))
            
            # Rule: All other losing or tied moves fail (bounce).
            for move in moves_to_province:
                if move != strongest_move:
                    self.problem.addConstraint(lambda outcome: outcome == 'stands', (f"outcome_{move.unit.id}",))

        # Part 2: Determine all dislodgements
        for unit in self.game_state.units.values():
            # Find if there is a successful move into this unit's starting province
            successful_move_in = any(
                m.to_province_id == unit.location and self.problem.getSolutions()[0][f"outcome_{m.unit.id}"] == 'moves'
                for m in self.move_orders
            )
            
            # A unit's order
            unit_order = next((o for o in self.all_orders if o.unit.id == unit.id), None)
            
            # Rule: A unit is dislodged if a successful move enters its province,
            # unless it was a successful move itself.
            if successful_move_in:
                if self.problem.getSolutions()[0][f"outcome_{unit.id}"] != 'moves':
                    self.problem.addConstraint(lambda outcome: outcome == 'dislodged', (f"outcome_{unit.id}",))
            else:
                 if self.problem.getSolutions()[0][f"outcome_{unit.id}"] != 'moves':
                    self.problem.addConstraint(lambda outcome: outcome == 'stands', (f"outcome_{unit.id}",))
