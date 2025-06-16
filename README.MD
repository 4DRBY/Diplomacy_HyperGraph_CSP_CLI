Diplomacy Engine with Hypergraph, CSP Adjudicator and Real-Time Web Visualiser

This project is a fully functional, command-line implementation of the classic strategy game Diplomacy. It is engineered around an advanced architecture that models the game's complex, simultaneous turn resolutions as a Constraint Satisfaction Problem (CSP), providing a robust and provably correct adjudication engine.

The system moves beyond simple procedural logic by representing the game's orders as a hypergraph, a structure that natively understands the multi-unit relationships inherent in supports and convoys. This clean, semantic data model is then translated into a formal logical problem that is solved by a dedicated constraint solver, ensuring that even the most complex paradoxes are resolved according to the official rules.

The architecture is split into two distinct components:

    Python Backend: A powerful command-line application that runs the core game logic. It handles order parsing, adjudication using a CSP solver, and state management. It also acts as a WebSocket server.

    HTML/JavaScript Frontend: A single HTML file that acts as a pure visualizer. It connects to the Python backend as a WebSocket client, receives real-time updates, and uses the D3.js library to dynamically render the game board, units, and orders as they happen.

This client-server model ensures a clean separation of concerns, with the robust Python engine handling all the game's complex logic.

Core Concepts

    Hypergraph State Model: Instead of a flat list, all orders for a turn are constructed into a hypergraph. Units and provinces are vertices, and orders (Move, Support, Hold) are hyperedges that link them. This provides a rich, relational model of the turn's dependencies.

    CSP Adjudication: The heart of the engine is the Adjudicator. It translates the hypergraph of orders into a Constraint Satisfaction Problem. The game's rules are defined as logical constraints, and a powerful CSP solver finds the single, consistent outcome for all units simultaneously. This declarative approach is more robust and maintainable than traditional procedural algorithms.

    Phase-Based Turn System: The game progresses through a defined sequence of phases for each year: Spring Movement, Spring Retreats, Fall Movement, Fall Retreats, and Winter Builds/Disbands. This structured progression allows for distinct types of orders and actions appropriate to each phase of a Diplomacy turn.

    Unit Testing: Core components of the game engine, including the adjudicator, game state logic, and order parsing, are now covered by a suite of unit tests, enhancing the robustness and reliability of the system.

Project Structure

diplomacy_hypergraph/
├── main.py               # Main application entry point, game loop
│
├── game_engine/
│   ├── __init__.py
│   ├── map.py              # Defines the Map, Province classes and adjacencies
│   ├── gamestate.py        # Defines the GameState and Unit classes
│   ├── hypergraph.py       # Defines Order classes (as hyperedges)
│   └── adjudicator.py      # The core CSP-based adjudication logic
│
├── cli/
│   ├── __init__.py
│   ├── display.py          # Functions for printing the board, orders, and results
│   └── parser.py           # Functions for parsing user commands
│
├── tests/                  # Unit tests for the project
│   ├── __init__.py
│   ├── test_cli.py         # Tests for command-line interface components
│   └── test_game_engine.py # Tests for core game engine logic
│
├── Web/
│    ├──Diplomacy_visualiser.html          # Renders the gameboard in the browser via Websockets
│
└── data/
    ├── classic_map.json    # Data defining provinces, supply centers, and adjacencies
    └── game_save.json      # Starting positions for the units

    Python: Python 3.7 or higher is recommended.

    Dependencies: The project requires `python-constraint` for adjudication and `websockets` for real-time communication. Testing uses `pytest`. A `requirements.txt` file is provided.

To set up the project, clone the repository and install the dependencies using pip:

# Navigate to the project's root directory
pip install -r requirements.txt

How to Run

You must run the Python backend first, and then open the HTML visualizer.

Step 1: Start the Python Backend Server

In your terminal, from the project's root directory, run main.py:

python main.py

You will see a message confirming that the WebSocket server has started (e.g., WebSocket server started on ws://localhost:8765). The game will wait for you to open the visualizer.

Step 2: Open the Visualizer

Open the diplomacy_visualizer.html file in your web browser. It will automatically connect to the Python backend.

Step 3: Play the Game

All game interaction (entering orders for Move, Support, Hold, etc.) happens in your terminal. As you enter orders and as each turn is adjudicated, the web browser visualization will update instantly and automatically to reflect the changes.

The game will load the initial state and prompt you to enter orders for each unit, nation by nation.
How to Play: Order Notation

When prompted, enter orders for each unit using standard Diplomacy notation. You can omit the unit type (A or F) if you wish.

    Hold: To order a unit to hold, simply type H or press Enter.

        RUH H

    Move: To order a unit to move, specify the destination province.

        BEL - RUH

    Support Hold: To support a unit that is holding, specify your unit, the S command, the location of the unit you are supporting, and H.

        MUN S RUH H (The unit in Munich supports the unit in Ruhr to hold)

    Support Move: To support a unit that is moving, specify your unit, the S command, the starting location of the moving unit, and its destination.

        BEL S RUH - MUN (The unit in Belgium supports the unit that started in Ruhr in its move to Munich)

After all orders are entered, the adjudicator will resolve the turn and display a detailed report, including which orders succeeded or failed, a breakdown of all conflicts, and the final board positions.