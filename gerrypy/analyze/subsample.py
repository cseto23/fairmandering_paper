import os
import pickle
import random
import copy
from gerrypy import constants
from gerrypy.analyze.districts import *


def get_node_info(leaf_nodes, interior_nodes):
    solution_count = {}
    parent_nodes = {}
    nodes = leaf_nodes + interior_nodes
    id_to_node = {node.id: node for node in nodes}
    root = interior_nodes[0] if interior_nodes[0].is_root \
        else [n for n in interior_nodes if n.is_root][0]

    def recursive_compute(current_node, all_nodes):
        if not current_node.children_ids:
            return 1

        total_districtings = 0
        for sample in current_node.children_ids:
            sample_districtings = 1
            for child_id in sample:
                child_node = id_to_node[child_id]
                parent_nodes[child_node.id] = current_node.id
                sample_districtings *= recursive_compute(child_node, all_nodes)

            total_districtings += sample_districtings
        solution_count[current_node.id] = total_districtings
        return total_districtings

    recursive_compute(root, nodes)

    return solution_count, parent_nodes


def prune_sample_space(internal_nodes,
                       solution_count,
                       parent_nodes,
                       target_size=1000):
    def recompute_node_size(node):
        new_node_size = 0
        for sample in node.children_ids:
            sample_districtings = 1
            for child_id in sample:
                sample_districtings *= solution_count.get(child_id, 1)
            new_node_size += sample_districtings
        return new_node_size

    root = internal_nodes[0]
    assert root.is_root
    assert target_size > 0

    id_to_node = {node.id: node for node in internal_nodes}

    nodes_by_size = {}
    for node in internal_nodes:
        try:
            nodes_by_size[int(node.n_districts)].append(node)
        except KeyError:
            nodes_by_size[int(node.n_districts)] = [node]

    current_node_prune_size = 2
    for size, node_list in nodes_by_size.items():
        random.shuffle(node_list)
    while solution_count[root.id] > target_size:
        n_skinny_nodes = 0
        node_list = nodes_by_size.get(current_node_prune_size, [])
        for node in node_list:
            if solution_count[root.id] <= target_size:
                break
            if len(node.children_ids) > 1:
                node.children_ids = node.children_ids[:-1]
                solution_count[node.id] = recompute_node_size(node)
                parent_id = parent_nodes.get(node.id, None)
                while parent_id is not None:
                    solution_count[parent_id] = recompute_node_size(id_to_node[parent_id])
                    parent_id = parent_nodes.get(parent_id, None)
            else:
                n_skinny_nodes += 1
        if n_skinny_nodes == len(nodes_by_size.get(current_node_prune_size, [])):
            current_node_prune_size += 1
    return internal_nodes

