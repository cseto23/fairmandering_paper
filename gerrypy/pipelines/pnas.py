import os
import glob
import time
import ntpath
import json
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from gerrypy import constants
from gerrypy.analyze import tree
from gerrypy.analyze import subsample
from gerrypy.analyze import districts
from gerrypy.data.load import *
from gerrypy.optimize import master


def run_all_states_result_pipeline(result_path, test=False):
    try:
        os.mkdir(os.path.join(result_path, 'pnas_results'))
    except FileExistsError:
        pass

    if test:
        states = ['CO', 'WV']
    else:
        states = [state for state in constants.seats
                  if constants.seats[state]['house'] > 1]

    for state in states:
        state_start_t = time.time()
        tree_path = glob.glob(os.path.join(result_path, '%s_[0-9]*.p' % state))[0]
        tree_data = pickle.load(open(tree_path, 'rb'))
        district_df = pd.read_csv(os.path.join(result_path, 'district_dfs',
                                               ntpath.basename(tree_path)[:-2] + '_district_df.csv'))

        leaf_nodes = tree_data['leaf_nodes']
        internal_nodes = tree_data['internal_nodes']

        extreme_electoral_data = extreme_electoral_solutions(leaf_nodes, internal_nodes, district_df)
        extreme_compactness_data = extreme_electoral_solutions(leaf_nodes, internal_nodes, district_df)
        distributions = subsampled_distributions(leaf_nodes, internal_nodes, district_df, state)
        solutions = master_solutions(leaf_nodes, internal_nodes, district_df, state)

        pipeline_result = {**extreme_electoral_data,
                           **extreme_compactness_data,
                           **distributions,
                           **solutions}
        elapsed_time = round((time.time() - state_start_t) / 60, 2)
        save_file = os.path.join(result_path, 'pnas_results', '%s.p' % state)
        pickle.dump(pipeline_result, open(save_file, 'wb'))
        print('Pipeline finished for %s taking %f mins' % (state, elapsed_time))


def extreme_electoral_solutions(leaf_nodes, internal_nodes, district_df):
    extreme_data = {}
    r_advantage_query_vals = tree.party_advantage_query_fn(district_df)
    d_advantage_query_vals = 1 - r_advantage_query_vals
    r_val, r_sol = tree.query_tree(leaf_nodes, internal_nodes, r_advantage_query_vals)
    d_val, d_sol = tree.query_tree(leaf_nodes, internal_nodes, d_advantage_query_vals)
    extreme_data['r_advantage'] = {
        'objective_value': r_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(r_sol)}
    }
    extreme_data['d_advantage'] = {
        'objective_value': d_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(d_sol)}
    }

    competitive_query_vals = tree.competitive_query_fn(district_df)
    uncompetitive_query_vals = -competitive_query_vals
    uncompetitive_val, uncompetitive_sol = tree.query_tree(leaf_nodes, internal_nodes, competitive_query_vals)
    competitive_val, competitive_sol = tree.query_tree(leaf_nodes, internal_nodes, uncompetitive_query_vals)
    extreme_data['uncompetitive'] = {
        'objective_value': -uncompetitive_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(uncompetitive_sol)}
    }
    extreme_data['competitive'] = {
        'objective_value': competitive_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(competitive_sol)}
    }
    return extreme_data


def extreme_compactness_solutions(leaf_nodes, internal_nodes, district_df):
    extreme_compact_data = {}
    dispersion = district_df.dispersion.values
    # Negative since lower dispersion is better
    dispersion_val, dispersion_sol = tree.query_tree(leaf_nodes, internal_nodes, -dispersion)
    anti_dispersion_val, anti_dispersion_sol = tree.query_tree(leaf_nodes, internal_nodes, dispersion)
    extreme_compact_data['dispersion'] = {
        'objective_value': -dispersion_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(dispersion_sol)}
    }
    extreme_compact_data['anti_dispersion'] = {
        'objective_value': anti_dispersion_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(anti_dispersion_sol)}
    }

    roeck = district_df.roeck.values
    roeck_val, roeck_sol = tree.query_tree(leaf_nodes, internal_nodes, roeck)
    anti_roeck_val, anti_roeck_sol = tree.query_tree(leaf_nodes, internal_nodes, -roeck)
    extreme_compact_data['roeck'] = {
        'objective_value': roeck_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(roeck_sol)}
    }
    extreme_compact_data['anti_roeck'] = {
        'objective_value': -anti_roeck_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(anti_roeck_sol)}
    }

    roeck_squared = district_df.roeck.values ** 2
    roeck_squared_val, roeck_squared_sol = tree.query_tree(leaf_nodes, internal_nodes, roeck_squared)
    anti_roeck_squared_val, anti_roeck_squared_sol = tree.query_tree(leaf_nodes, internal_nodes, -roeck_squared)
    extreme_compact_data['roeck_squared'] = {
        'objective_value': roeck_squared_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(roeck_squared_sol)}
    }
    extreme_compact_data['anti_roeck_squared'] = {
        'objective_value': -anti_roeck_squared_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(anti_roeck_squared_sol)}
    }

    edge_ratio = district_df.edge_ratio.values
    edge_ratio_val, edge_ratio_sol = tree.query_tree(leaf_nodes, internal_nodes, edge_ratio)
    anti_edge_ratio_val, anti_edge_ratio_sol = tree.query_tree(leaf_nodes, internal_nodes, -edge_ratio)
    extreme_compact_data['edge_ratio'] = {
        'objective_value': edge_ratio_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(edge_ratio_sol)}
    }
    extreme_compact_data['anti_edge_ratio'] = {
        'objective_value': -anti_edge_ratio_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(anti_edge_ratio_sol)}
    }

    edge_ratio_squared = district_df.edge_ratio.values ** 2
    edge_ratio_squared_val, edge_ratio_squared_sol = tree.query_tree(leaf_nodes, internal_nodes, edge_ratio_squared)
    anti_edge_ratio_squared_val, anti_edge_ratio_squared_sol = tree.query_tree(leaf_nodes,
                                                                               internal_nodes, -edge_ratio_squared)
    extreme_compact_data['edge_ratio_squared'] = {
        'objective_value': edge_ratio_squared_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(edge_ratio_squared_sol)}
    }
    extreme_compact_data['anti_edge_ratio_squared'] = {
        'objective_value': -anti_edge_ratio_squared_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(anti_edge_ratio_squared_sol)}
    }

    cut_edges = district_df.cut_edges.values
    cut_edges_val, cut_edges_sol = tree.query_tree(leaf_nodes, internal_nodes, -cut_edges)
    anti_cut_edges_val, anti_cut_edges_sol = tree.query_tree(leaf_nodes, internal_nodes, cut_edges)
    extreme_compact_data['cut_edges'] = {
        'objective_value': -cut_edges_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(cut_edges_sol)}
    }
    extreme_compact_data['anti_cut_edges'] = {
        'objective_value': anti_cut_edges_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(anti_cut_edges_sol)}
    }

    cut_edges_squared = district_df.cut_edges.values ** 2
    cut_edges_squared_val, cut_edges_squared_sol = tree.query_tree(leaf_nodes, internal_nodes, -cut_edges_squared)
    anti_cut_edges_squared_val, anti_cut_edges_squared_sol = tree.query_tree(leaf_nodes,
                                                                             internal_nodes, cut_edges_squared)
    extreme_compact_data['cut_edges_squared'] = {
        'objective_value': -cut_edges_squared_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(cut_edges_squared_sol)}
    }
    extreme_compact_data['anti_cut_edges_squared'] = {
        'objective_value': anti_cut_edges_squared_val,
        'solution': {n.id: n.area for n in leaf_nodes if n.id in set(anti_cut_edges_squared_sol)}
    }


def subsampled_distributions(leaf_nodes, internal_nodes, district_df, state):
    subsample_constant = 1000 * constants.seats[state]['house'] ** 2

    solution_count, parent_nodes = subsample.get_node_info(leaf_nodes, internal_nodes)
    pruned_internal_nodes = subsample.prune_sample_space(internal_nodes,
                                                         solution_count,
                                                         parent_nodes,
                                                         subsample_constant)

    r_advantage_vals = tree.party_advantage_query_fn(district_df)
    dispersion_vals = district_df.dispersion.values
    roeck_vals = district_df.roeck.values
    roeck_squared_vals = district_df.roeck.values ** 2
    edge_ratio_vals = district_df.edge_ratio.values
    edge_ratio_squared_vals = district_df.edge_ratio.values ** 2
    cut_edges_vals = district_df.cut_edges.values
    cut_edges_squared_vals = district_df.cut_edges.values ** 2
    competitive_vals = tree.competitive_query_fn(district_df)

    return {
        'seat_share_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                                    r_advantage_vals),
        'dispersion_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes, dispersion_vals),
        'roeck_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                               roeck_vals),
        'roeck_squared_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                                       roeck_squared_vals),
        'edge_ratio_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                                    edge_ratio_vals),
        'edge_ratio_squared_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                                            edge_ratio_squared_vals),
        'cut_edges_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                                   cut_edges_vals),
        'cut_edges_squared_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                                           cut_edges_squared_vals),
        'competitiveness_distribution': districts.enumerate_distribution(leaf_nodes, pruned_internal_nodes,
                                                                         competitive_vals),
    }


def master_solutions(leaf_nodes, internal_nodes, district_df, state):
    bdm = districts.make_bdm(leaf_nodes)
    cost_coeffs = master.efficiency_gap_coefficients(district_df)
    root_map = master.make_root_partition_to_leaf_map(leaf_nodes, internal_nodes)
    sol_dict = {}
    for partition_ix, leaf_slice in root_map.items():
        start_t = time.time()
        model, dvars = master.make_master(constants.seats[state]['house'],
                                          bdm[:, leaf_slice],
                                          cost_coeffs[leaf_slice])
        construction_t = time.time()

        model.Params.LogToConsole = 0
        model.Params.MIPGapAbs = 1e-4
        model.Params.TimeLimit = len(leaf_nodes) / 10
        model.optimize()
        opt_cols = [j for j, v in dvars.items() if v.X > .5]
        solve_t = time.time()

        sol_dict[partition_ix] = {
            'construction_time': construction_t - start_t,
            'solve_time': solve_t - construction_t,
            'n_leaves': len(leaf_slice),
            'solution_ixs': root_map[partition_ix][opt_cols],
            'optimal_objective': cost_coeffs[leaf_slice][opt_cols]
        }
    return {'master_solutions': sol_dict}


if __name__ == '__main__':
    for dir in [
        os.path.join(constants.RESULTS_PATH, 'allstates', 'aaai_columns1595813019'),
        os.path.join(constants.RESULTS_PATH, 'allstates', 'aaai_columns1595891125')
    ]:
        run_all_states_result_pipeline(dir)
