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
            Defaults to the classic map in the data directory.
    """
    def __init__(self, map_file_path=None):
        self.provinces = {}
        self.adjacencies = {}
        self.distances = {}
        map_path = Path(map_file_path) if map_file_path else DEFAULT_MAP_PATH
        self._load_map(map_path)
        self._calculate_all_distances()

    def _load_map(self, file_path):
        """Loads province and adjacency data from a JSON file.
        
        Args:
            file_path (Path): Path to the map JSON file.
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        for p_id, attrs in data['provinces'].items():
            self.provinces[p_id] = Province(
                p_id=p_id,
                name=attrs['name'],
                is_supply_center=attrs['is_supply_center'],
                province_type=attrs['type']
            )
        self.adjacencies = data['adjacencies']

    def _bfs(self, start_node_id):
        """Performs a Breadth-First Search to find shortest paths."""
        q = deque([(start_node_id, 0)])
        visited = {start_node_id: 0}
        
        while q:
            current_node, dist = q.popleft()
            for neighbor in self.adjacencies.get(current_node, []):
                if neighbor not in visited:
                    visited[neighbor] = dist + 1
                    q.append((neighbor, dist + 1))
        return visited

    def _calculate_all_distances(self):
        """Calculates and stores all-pairs shortest paths for all provinces."""
        for province_id in self.provinces:
            self.distances[province_id] = self._bfs(province_id)