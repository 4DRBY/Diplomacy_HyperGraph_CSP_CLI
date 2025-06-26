# Diplomacy Hypergraph

This project is a command-line implementation of the classic strategy game Diplomacy, with a real-time web-based visualizer. It uses a unique architecture that models the game's complex, simultaneous turn resolutions as a Constraint Satisfaction Problem (CSP), providing a robust and provably correct adjudication engine.

The system represents the game's orders as a hypergraph, which naturally captures the multi-unit relationships inherent in supports and convoys. This data model is then translated into a formal logical problem that is solved by a dedicated constraint solver, ensuring that even the most complex paradoxes are resolved according to the official rules.

The architecture is split into two main components:

  * **Python Backend**: A command-line application that runs the core game logic. It handles order parsing, adjudication using a CSP solver, and state management. It also acts as a WebSocket server to send updates to the visualizer.
  * **HTML/JavaScript Frontend**: A single HTML file that acts as a pure visualizer. It connects to the Python backend as a WebSocket client and uses the D3.js library to dynamically render the game board, units, and orders as they happen.

This client-server model ensures a clean separation of concerns, with the robust Python engine handling all the game's complex logic.

## Core Concepts Explained

### Hypergraph for Turn Representation

In a standard graph, an edge connects two vertices. However, in Diplomacy, some actions involve more than two entities. For example, a support order involves the supporting unit, the supported unit, and the province where the action takes place. A hypergraph is a generalization of a graph where an edge, called a hyperedge, can connect any number of vertices.

In this project, each order (Move, Hold, Support, Convoy) is modeled as a hyperedge. This provides a much richer and more accurate representation of the game state than a simple graph.

  * **Vertices**: The vertices in our hypergraph are the units and provinces on the map.
  * **Hyperedges**: The orders given by the players are the hyperedges.
      * A **Hold** order is a hyperedge that connects a single unit to its province.
    <!-- end list -->
      - A **Move** order is a hyperedge connecting the moving unit, its origin province, and its destination province.
    <!-- end list -->
      * A **Support** order is a hyperedge connecting the supporting unit, the supported unit, and the provinces involved in the supported action (either a hold or a move).

This hypergraph model, defined in `game_engine/hypergraph.py`, provides a structured and semantically rich representation of all the actions and dependencies in a single turn.

### Constraint Satisfaction Problem (CSP) for Adjudication

The most complex part of any Diplomacy implementation is the adjudication of turns, which is the process of determining the outcome of all the orders simultaneously. The rules of Diplomacy can lead to complex paradoxes and circular dependencies that are difficult to resolve with traditional procedural code.

This project's `Adjudicator` takes a novel approach by modeling the adjudication process as a Constraint Satisfaction Problem (CSP). A CSP is a type of problem in which you have a set of variables, a domain of possible values for each variable, and a set of constraints that the variables must satisfy.

Here's how the Diplomacy turn is modeled as a CSP in this project:

  * **Variables**:
      * For each unit, there is a variable representing its **outcome** (e.g., 'moves', 'stands', 'dislodged').
      * For each order, there is a variable representing its **strength**.
      * For each support order, there is a variable representing its **status** ('valid', 'cut', 'invalid').
  * **Domains**:
      * The domain for the outcome variables is the set of possible outcomes.
      * The domain for the strength variables is a range of integers.
      * The domain for the support status variables is the set of possible statuses.
  * **Constraints**: The rules of Diplomacy are translated into a set of logical constraints that the variables must satisfy. For example:
      * A support order's status is 'cut' if the supporting unit is attacked.
      * The strength of an order is 1 plus the number of valid supports it receives.
      * A move to a province succeeds only if its strength is greater than the strength of any other unit trying to move to or hold that same province.
      * A unit is dislodged if a stronger unit successfully moves into its province.

The `Adjudicator` uses the `python-constraint2` library to define all these variables, domains, and constraints. It then asks the library to find a solution to the CSP. A solution is an assignment of values to all the variables that satisfies all the constraints. This solution represents the one and only valid outcome of the turn, according to the rules of Diplomacy.

This CSP-based approach has several advantages:

  * **Correctness**: Because the rules are declared as logical constraints, the adjudicator is provably correct, as long as the constraints accurately reflect the rules of the game.
  * **Maintainability**: If a rule needs to be changed, you only need to update the corresponding constraint, rather than untangling complex procedural code.
  * **Robustness**: The CSP solver can handle even the most convoluted and paradoxical situations, such as circular support chains or convoys, without any special-case logic.

## Philosophy: Using AI to Learn

This project was built with the philosophy of using AI as a tool for learning and development. The developer used an AI assistant throughout the entire process, from initial conception to the final code. This approach demonstrates a modern workflow where human creativity and AI-powered tools collaborate to build complex systems.

By offloading some of the more tedious aspects of coding, the developer was able to focus on the high-level architecture and the core logical problems, such as how to model the game's rules as a CSP. The AI assistant helped with:

  * **Boilerplate Code**: Generating repetitive code for classes, functions, and file I/O.
  * **Debugging**: Identifying and fixing bugs in the code.
  * **Learning New Concepts**: The AI assistant provided explanations and examples of new concepts, such as hypergraphs and CSPs, which were crucial for the project's design.
  * **Exploring Alternative Solutions**: The AI assistant could quickly suggest and prototype different approaches to a problem, allowing the developer to make more informed decisions about the project's direction.

This project is a testament to the power of using AI as a partner in the creative process of software development. It shows that AI can not only help us to be more productive but can also help us to learn and to tackle more ambitious and complex projects.

## Project Structure

```
diplomacy_hypergraph/
├── main.py               # Main application entry point, game loop, and WebSocket server
│
├── game_engine/
│   ├── __init__.py
│   ├── map.py              # Defines the Map and Province classes and manages adjacencies
│   ├── gamestate.py        # Defines the GameState and Unit classes
│   ├── hypergraph.py       # Defines the Order classes as hyperedges
│   └── adjudicator.py      # The core CSP-based adjudication logic
│
├── cli/
│   ├── __init__.py
│   ├── display.py          # Functions for printing the board, orders, and results to the console
│   └── parser.py           # Functions for parsing user commands from the console
│
├── Visualiser/
│    └── diplomacy_visualiser.html  # Renders the game board in the browser via WebSockets
│
└── data/
    ├── classic_map.json    # Data defining provinces, supply centers, and adjacencies
    └── game_save.json      # Starting positions for the units
```

## How to Run

You must run the Python backend first, and then open the HTML visualizer.

### Step 1: Install Dependencies

This project requires Python 3.7 or higher. You will also need to install the dependencies listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Step 2: Start the Python Backend Server

In your terminal, from the project's root directory, run `main.py`:

```bash
python main.py
```

You will see a message confirming that the WebSocket server has started on `ws://localhost:8765`. The game will then wait for the visualizer to connect.

### Step 3: Open the Visualizer

Open the `Visualiser/diplomacy_visualiser.html` file in your web browser. It will automatically connect to the Python backend. The visualizer uses D3.js to render the map and the units.

### Step 4: Play the Game

All game interaction (entering orders for Move, Support, Hold, etc.) happens in your terminal. As you enter orders and as each turn is adjudicated, the web browser visualization will update instantly and automatically to reflect the changes.

#### Order Notation

When prompted in the terminal, enter orders for each unit using standard Diplomacy notation.

  * **Hold**: To order a unit to hold, simply type `H` or press Enter.
  * **Move**: To order a unit to move, specify the destination province. For example: `BEL - RUH`
  * **Support Hold**: To support a unit that is holding, specify the location of the unit you are supporting. For example: `MUN S RUH`
  * **Support Move**: To support a unit that is moving, specify the starting location of the moving unit and its destination. For example: `BEL S RUH - MUN`

After all orders are entered, the adjudicator will resolve the turn and display a detailed report in the terminal, including which orders succeeded or failed, a breakdown of all conflicts, and the final board positions. The visualizer will also be updated with the results.
