# game_engine/map.py
# Defines the Map, Province classes and manages adjacencies.

import json
from collections import deque
from pathlib import Path

# Default path to the classic map file
DEFAULT_MAP_PATH = Path(__file__).parent.parent / 'data' / 'classic_map.json'

class Province:
    """Represents a single province on the game map."""
    def __init__(self, p_id, name, is_supply_center, province_type):
        self.id = p_id
        self.name = name
        self.is_supply_center = is_supply_center
        # is_coastal removed as it's no longer in the data file
        self.type = province_type
    
    def __repr__(self):
        return f"Province({self.name})"

class GameMap:
    """Loads and manages the game map, including provinces and adjacencies.
    
    Args:
        map_file_path (str or Path, optional): Path to the map JSON file. 
            If not provided, will use the classic map from the data directory.
    """
    def __init__(self, map_file_path=DEFAULT_MAP_PATH):
        self.provinces = {}
        self.adjacencies = {}
        self.distances = {}
        # Ensure we're using a Path object and the default map if no path provided
        map_path = Path(map_file_path) if map_file_path else DEFAULT_MAP_PATH
        if not map_path.exists():
            raise FileNotFoundError(f"Map file not found at: {map_path}")
        self._load_map(map_path)
        self._calculate_all_distances()

    def _load_map(self, file_path):
        """
        Loads province and adjacency data from a specified JSON file.

        The JSON file is expected to have two main keys:
        - "provinces": A dictionary where each key is a province ID and the value
                       is an object containing details like 'name', 'is_supply_center',
                       and 'type'.
        - "adjacencies": A dictionary where each key is a province ID and the value
                         is a list of province IDs adjacent to it.
        
        Args:
            file_path (Path): The path object pointing to the map JSON file.

        Raises:
            json.JSONDecodeError: If the file is not valid JSON.
            KeyError: If the JSON structure does not contain expected keys
                      (e.g., 'provinces', 'adjacencies', or attributes within a province).
        """
        with open(file_path, 'r') as f:
            data = json.load(f) # Load the entire map data from JSON
        
        # Populate self.provinces
        # Expects data['provinces'] to be a dict like: {"PROV_ID": {"name": "Name", ...}}
        for p_id, attrs in data['provinces'].items():
            self.provinces[p_id] = Province(
                p_id=p_id,
                name=attrs['name'],
                is_supply_center=attrs['is_supply_center'],
                province_type=attrs['type']
            )
        # Populate self.adjacencies
        # Expects data['adjacencies'] to be a dict like: {"PROV_ID": ["ADJ_PROV1", "ADJ_PROV2"]}
        self.adjacencies = data['adjacencies']

    def _bfs(self, start_node_id):
        """
        Performs a Breadth-First Search (BFS) starting from a given node
        to find the shortest path (in terms of number of edges) to all
        reachable nodes in the graph defined by `self.adjacencies`.

        Args:
            start_node_id (str): The ID of the province to start the BFS from.

        Returns:
            dict: A dictionary where keys are reachable province IDs and values
                  are their shortest distance (number of edges) from `start_node_id`.
                  The `start_node_id` itself is included with distance 0.
        """
        # q is a deque (double-ended queue) to manage nodes to visit, storing tuples of (node_id, distance)
        q = deque([(start_node_id, 0)])
        # visited is a dictionary storing {node_id: distance_from_start_node}
        # It also serves to keep track of visited nodes to avoid cycles and redundant processing.
        visited = {start_node_id: 0}
        
        while q: # Loop as long as there are nodes to process
            current_node, dist = q.popleft() # Get the next node and its distance from start

            # Iterate over neighbors of the current_node.
            # self.adjacencies.get(current_node, []) robustly handles cases where a node
            # might not have an entry in adjacencies (e.g., an isolated province not listed as a key).
            for neighbor in self.adjacencies.get(current_node, []):
                if neighbor not in visited: # Process only if the neighbor hasn't been visited yet
                    visited[neighbor] = dist + 1 # Mark neighbor as visited and record its distance
                    q.append((neighbor, dist + 1)) # Add neighbor to the queue for processing its own neighbors
        return visited # Return the map of reachable nodes and their distances

    def _calculate_all_distances(self):
        """
        Calculates and stores all-pairs shortest paths (distances) for all provinces
        on the map. It populates `self.distances`.

        `self.distances` will be a dictionary where each key is a province ID (from_province),
        and its value is another dictionary. This inner dictionary maps other province IDs
        (to_province) to the shortest distance (number of edges) from from_province to to_province.
        Example: self.distances["PAR"]["MAR"] would give the distance from Paris to Marseilles.
        """
        for province_id in self.provinces:
            # For each province, perform a BFS starting from it to find distances to all other provinces.
            # The result of _bfs (a dict of {to_province: distance}) is stored.
            self.distances[province_id] = self._bfs(province_id)