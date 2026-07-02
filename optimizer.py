# optimizer.py
"""
TSP Solver menggunakan Google OR-Tools
PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH
+ Open Path TSP (tanpa kembali ke depot)
"""
import numpy as np

try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("⚠️  OR-Tools tidak terinstall. Jalankan: pip install ortools==9.10.4067")

def _route_cost(route, matrix):
    """Hitung total biaya rute"""
    return sum(matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))

def _solve_ortools(time_matrix_int, num_nodes):
    """
    Solve TSP dengan OR-Tools
    Tahap 1: PATH_CHEAPEST_ARC - konstruksi solusi awal
    Tahap 2: GUIDED_LOCAL_SEARCH - penyempurnaan (dibatasi 300ms)
    """
    manager = pywrapcp.RoutingIndexManager(num_nodes, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return time_matrix_int[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    # Max 7 nodes → PATH_CHEAPEST_ARC sudah optimal dalam milidetik
    search_params.time_limit.FromMilliseconds(300)

    solution = routing.SolveWithParameters(search_params)

    if not solution:
        return None

    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))
    return route

def solve_tsp(time_matrix):
    """
    Main TSP solver (CLOSED PATH - kembali ke depot)
    """
    if not ORTOOLS_AVAILABLE:
        raise ImportError(
            "\n" + "="*60 + "\n"
            "ERROR: Google OR-Tools tidak terinstall!\n"
            "Jalankan: pip install ortools==9.10.4067\n"
            "="*60
        )

    mat = np.array(time_matrix, dtype=float)
    n = len(mat)
    int_mat = [[int(v * 100 + 0.5) for v in row] for row in mat.tolist()]
    route = _solve_ortools(int_mat, n)

    if route is None:
        raise RuntimeError("OR-Tools gagal menemukan solusi")

    total_time = _route_cost(route, mat)
    return {
        "route": route,
        "total_time": round(total_time, 2),
        "solver_used": "OR-Tools (PATH_CHEAPEST_ARC + GLS)",
        "num_nodes": n
    }


def solve_tsp_open(time_matrix):
    """
    Open path TSP solver — TIDAK kembali ke titik awal.
    Rute: 0 → 1 → 2 → ... → n-1 (berhenti)
    Untuk max 7+1 node, waktu solve < 300ms.
    """
    if not ORTOOLS_AVAILABLE:
        raise ImportError(
            "\n" + "="*60 + "\n"
            "ERROR: Google OR-Tools tidak terinstall!\n"
            "Jalankan: pip install ortools==9.10.4067\n"
            "="*60
        )

    mat = np.array(time_matrix, dtype=float)
    n = len(mat)

    n_with_dummy = n + 1
    dummy_idx = n

    extended_mat = np.zeros((n_with_dummy, n_with_dummy))
    extended_mat[:n, :n] = mat
    extended_mat[:, dummy_idx] = 0
    extended_mat[dummy_idx, :] = 999999
    extended_mat[dummy_idx, dummy_idx] = 0

    int_mat = [[int(v * 100 + 0.5) for v in row] for row in extended_mat.tolist()]

    manager = pywrapcp.RoutingIndexManager(n_with_dummy, 1, 0, dummy_idx)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int_mat[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.FromMilliseconds(300)

    solution = routing.SolveWithParameters(search_params)

    if not solution:
        # Fallback: nearest-neighbor
        route = [0]
        unvisited = set(range(1, n))
        current = 0
        while unvisited:
            next_node = min(unvisited, key=lambda x: mat[current][x])
            route.append(next_node)
            unvisited.remove(next_node)
            current = next_node
    else:
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node < n:
                route.append(node)
            index = solution.Value(routing.NextVar(index))

    total_time = sum(mat[route[i]][route[i+1]] for i in range(len(route)-1))

    return {
        "route": route,
        "total_time": round(total_time, 2),
        "solver_used": "OR-Tools Open Path",
        "num_nodes": n
    }