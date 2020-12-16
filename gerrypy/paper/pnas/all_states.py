from gerrypy import constants
from gerrypy.data.load import *
from gerrypy.data.precinct_state_wrappers import *
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from gerrypy.analyze.viz import *
from gerrypy.analyze.plan import *
from gerrypy.analyze.districts import *
from gerrypy.analyze.historical_districts import *
from gerrypy.analyze.tree import *
from gerrypy.analyze.states import *
from scipy.stats import t, spearmanr


def load_all_state_results(all_states_dir):
    ensemble_results = {}
    for f in os.listdir(all_states_dir):
        print(f)
        ensemble_results[f[:2]] = pickle.load(open(os.path.join(all_states_dir, f), 'rb'))
    return ensemble_results


def load_historical_house_winner_df(house_results_path, starting_year):
    house_df = pd.read_csv(house_results_path, encoding='unicode_escape')
    house_df = house_df[house_df.year > starting_year]
    winner_df = house_df.groupby(['state_po', 'year', 'district']).apply(
        lambda x: x.iloc[x['candidatevotes'].argmax()].party)

    return winner_df


def cm2inch(*tupl):
    inch = 2.54
    if isinstance(tupl[0], tuple):
        return tuple(i / inch for i in tupl[0])
    else:
        return tuple(i / inch for i in tupl)


def make_affiliation_df():
    """Create DataFrame to recording partisan affiliation for each state."""
    election_results = get_state_election_results()
    affiliation_dict = {}
    for state, er in election_results.items():
        election_arr = np.array(list(er.values()))
        mean = election_arr.mean()
        std = election_arr.std(ddof=1)
        std_multiple = [-2, -1, 0, 1, 2]
        affiliation_dict[state] = [mean + i * std for i in std_multiple]
    return pd.DataFrame(affiliation_dict)


def plot_state_affiliation(affiliation_df, fig_dir, min_seats=3):
    """Saves figure of partisan distribution for each state."""
    plt.figure(figsize=(20, 5))
    affiliation_df = affiliation_df.drop(columns=[c for c in affiliation_df.columns
                                                  if constants.seats[c]["house"] < min_seats])
    affiliation_df.T.sort_values(2).T.boxplot(whis=(0, 100))
    plt.ylabel('Republican vote-share')
    plt.gca().set_ylim([0, 1])
    plt.yticks(ticks=np.arange(0, 1.1, .1))
    plt.axhline(y=.5, color='red', linewidth=1, linestyle=':')
    plt.savefig(os.path.join(fig_dir, 'state_affiliation.eps'), format='eps', bbox='tight')


def make_state_election_table():
    """Creates a table of all the elections in our dataset for each state."""
    election_results = get_state_election_results()
    state_elections_dict = {}
    for state in constants.seats:
        if constants.seats[state]['house'] < 2:
            continue
        try:
            results_array = np.array(list(election_results[state].values()))
            wrapper = wrappers[state]()
            election_strings = sorted(
                [election for ix, election in enumerate(wrapper.election_columns(include_party=False))],
                key=lambda x: x[-4:])
            try:
                county_elections = set(['_'.join([office, str(year)]) for office, year in wrapper.county_inference])
            except:
                county_elections = {}
            election_strings = [election + '*' if election in county_elections else election for election in
                                election_strings]
            state_elections_dict[state] = {
                'sample mean': round(results_array.mean(), 3),
                'sample std': round(results_array.std(ddof=1), 3),
                'elections': ', '.join(election_strings)
            }
        except NotImplementedError:
            state_elections_dict[state] = {
                'sample mean': round(results_array.mean(), 3),
                'sample std': round(results_array.std(ddof=1), 3),
                'elections': 'pres_2008*, pres_2012*, pres_2016*'
            }
    return pd.DataFrame(state_elections_dict).T


def make_state_graph_table():
    """Create table of selected statistics of state adjacency graph."""
    G_stat_dict = {}
    for state in constants.seats:
        if constants.seats[state]['house'] < 2:
            continue
        state_df, G, _, _ = load_opt_data(state)
        G_stat_dict[state] = {
            'k': constants.seats[state]['house'],
            'nodes': len(G.nodes),
            'edges': len(G.edges),
            'population': state_df.population.sum()
        }
    return pd.DataFrame(G_stat_dict).T.rename(columns={'k': 'districts'})


def create_seat_share_box_df(ensemble_results, sort_by):
    """Create table of seat share ensemble distribution metrics"""
    series_dict = {s: pd.Series(
        r['seat_share_distribution'] + [r['r_advantage']['objective_value'],
                                        constants.seats[s]['house'] -
                                        r['d_advantage']['objective_value']]
    ).describe() / constants.seats[s]['house']
                   for s, r in ensemble_results.items()}

    box_df = pd.DataFrame(series_dict).drop(['count', 'mean', 'std'])
    box_df.loc['sort_column'] = sort_by
    return box_df.T.sort_values(by='sort_column').T.drop('sort_column')


def plot_seat_share_distribution(fig_dir, box_df, state_partisanship, seat_fractions, min_seats=3):
    """Plot distribution of expected seat shares"""
    plt.rcParams.update({'font.size': 14})
    box_df = box_df.drop(columns=[s for s in box_df.columns if constants.seats[s]['house'] < min_seats])
    box_df.boxplot(figsize=(20, 5), whis=(0, 100), positions=range(0, len(box_df.columns)))
    plt.scatter(box_df.columns,
                [(state_partisanship[state] - .5) * 2 + .5 for state in box_df.columns],
                c='green', marker='P', vmin=0, vmax=1, label='Estimated 0 efficiency gap', s=65)
    plt.scatter(box_df.columns,
                [seat_fractions[state] for state in box_df.columns],
                c='red', marker='x', vmin=0, vmax=1, label='Average seat-share 2012-2018', s=55)
    plt.ylabel('Republican seat-share')
    plt.legend()
    plt.margins(x=.01)
    plt.gca().set_ylim([-0.025, 1.025])
    plt.yticks(ticks=np.arange(0, 1.1, .1))
    plt.grid(linewidth=.5, alpha=.5)
    plt.axhline(y=.5, color='black', linewidth=.5, alpha=.25, linestyle=":")
    plt.savefig(os.path.join(fig_dir, 'state_seat_shares.eps'), format='eps', bbox='tight')


def responsiveness_to_feasibility(ensemble_results, state_partisanship, r_min, r_max, r_interval=.01):
    """Calculate feasibility of different levels of responsiveness based on whether the value
    exists between the max and min estimated seat shares."""
    states = sorted(list(ensemble_results.keys()))
    state_maxs = np.array([(ensemble_results[state]['r_advantage']['objective_value']) / constants.seats[state]['house']
                           for state in states])
    state_mins = np.array([(constants.seats[state]['house'] -
                            ensemble_results[state]['d_advantage']['objective_value'])
                           / constants.seats[state]['house']
                           for state in states])
    partisanship = np.array([state_partisanship[state] for state in states])
    domain = np.arange(r_min, r_max + r_interval, r_interval)
    n_feasible = []
    seats_feasible = []
    for resp in domain:
        optimal_seat_share = (partisanship - .5) * resp + .5
        feasible_at_r = ((state_mins < optimal_seat_share) & (optimal_seat_share < state_maxs))
        seats_feasible_at_r = sum([constants.seats[state]['house']
                                   for state, feasible in zip(states, feasible_at_r)
                                   if feasible])
        n_feasible.append(feasible_at_r.sum())
        seats_feasible.append(seats_feasible_at_r)
    return domain, np.array(n_feasible), np.array(seats_feasible)


def plot_feasibility_by_responsiveness(fig_dir, ensemble_results, state_partisanship):
    """Plot seat and state level feasibility as a function of responsiveness."""
    plt.rcParams.update({'font.size': 14})
    domain, n_feasible, n_seats_feasible = responsiveness_to_feasibility(ensemble_results,
                                                                         state_partisanship,
                                                                         0, 5, .1)
    fig, ax1 = plt.subplots()
    plt.grid()
    ax2 = ax1.twinx()
    ax1.plot(domain, n_feasible, label='states')
    ax2.plot(domain, n_seats_feasible, label='seats', color='red')
    ax1.set_xlabel('responsiveness')
    ax1.set_ylabel('feasible states')
    ax2.set_ylabel('feasible seats')
    plt.margins(x=.01)
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc="upper left")
    plt.savefig(os.path.join(fig_dir, 'responsiveness_feasibility.eps'),
                format='eps', bbox='tight')


def create_competitiveness_box_df(ensemble_results, sort_by):
    """Calculate competitiveness distributional quantities"""
    series_dict = {s: pd.Series(
        r['competitiveness_distribution']).describe()
                   for s, r in ensemble_results.items()}

    box_df = pd.DataFrame(series_dict).drop(['count', 'mean', 'std'])
    box_df.loc['sort_column'] = sort_by
    return box_df.T.sort_values(by='sort_column').T.drop('sort_column')


def plot_competitiveness_distribution(fig_dir, ensemble_results, seat_change_dict, min_seats=3):
    """Plot distribution of expected seat swaps of ensemble."""
    average_seat_flips = pd.DataFrame(seat_change_dict).mean(axis=1)
    average_seat_flips.loc['MN'] = 6 / 3
    competitive_box_df = create_competitiveness_box_df(ensemble_results,
                                                       pd.Series({state: seat_dict['house']
                                                                  for state, seat_dict
                                                                  in constants.seats.items()}))
    competitive_box_df = competitive_box_df.drop(
        columns=[s for s in competitive_box_df.columns if constants.seats[s]['house'] < min_seats])
    competitive_box_df.boxplot(figsize=(20, 5), whis=(0, 100), positions=range(0, len(competitive_box_df.columns)))

    plt.scatter(competitive_box_df.columns,
                [average_seat_flips[state] for state in competitive_box_df.columns],
                c='red', marker='x', label='Average seat flips 2012-2018')
    plt.ylabel('Expected seats swapped per election')
    plt.legend()
    plt.margins(x=.01)

    plt.savefig(os.path.join(fig_dir, 'seat_swap_distribution.eps'), format='eps', bbox='tight')


def compute_fairness_compactness_correlations(ensemble_results, state_partisanship):
    """Compute spearman correlation coefficients between the magnitude of the
     expected efficiency gap and three different measures of compactness."""
    spearman_dict = {}
    for state in ensemble_results:
        # https://www.brennancenter.org/sites/default/files/legal-work/How_the_Efficiency_Gap_Standard_Works.pdf
        # Efficiency Gap = (Seat Margin – 50%) – 2 (Vote Margin – 50%)
        seat_share = np.array(ensemble_results[state]['seat_share_distribution']) / constants.seats[state]['house']
        vote_share = state_partisanship[state]
        gap_magnitude = np.abs((seat_share - .5) - 2 * (vote_share - .5))
        spearman_dict[state] = {
            'centralization': spearmanr(gap_magnitude, ensemble_results[state]['dispersion_distribution'])[0],
            'roeck': spearmanr(gap_magnitude, ensemble_results[state]['roeck_distribution'])[0],
            'cut_edges': spearmanr(gap_magnitude, ensemble_results[state]['cut_edges_distribution'])[0],
        }
    return pd.DataFrame(spearman_dict)


def plot_fairness_correlation(fig_dir, spearman_df, state_partisanship, min_seats=3):
    """Plot the spearman correlation coefficient between compactness and three
    different measures of compactness."""

    marker_dict = {
        'centralization': '*',
        'roeck': 'o',
        'cut_edges': '4'
    }
    spearman_df.loc['affiliation'] = {state: state_partisanship[state]
                                      for state in spearman_df.columns}
    spearman_df = spearman_df.T.sort_values(by='affiliation').T.drop('affiliation')
    spearman_df = spearman_df.drop(columns=[c for c in spearman_df.columns
                                            if constants.seats[c]['house'] < min_seats])
    plt.figure(figsize=(20, 5))
    for ix, row in spearman_df.iterrows():
        if ix == 'roeck':
            plt.scatter(list(row.index), row.values, label=ix, marker=marker_dict[ix],
                        facecolor='none', edgecolors='r', s=80)
        elif ix == 'cut_edges':
            plt.scatter(list(row.index), row.values,
                        label="cut edges", marker=marker_dict[ix], color='green', s=170)
        else:
            plt.scatter(list(row.index), row.values,
                        label=ix, marker=marker_dict[ix], s=95)
    plt.legend(loc='upper left')
    plt.grid(linewidth=.5, alpha=.5)
    plt.axhline(y=0, color='black', linewidth=.5, alpha=.25, linestyle=":")
    plt.ylabel('Spearman correlation')
    plt.gca().set_ylim([-1, 1])
    plt.margins(x=.005)
    plt.savefig(os.path.join(fig_dir, 'compactness_correlation.eps'),
                format='eps', bbox='tight')


def correlation_table(spearman_df):
    """Table of average spearman correlation coefficient."""
    unweighted_correlation_mean = spearman_df.mean(axis=1)
    seat_weights = [constants.seats[state]['house']
                    for state in spearman_df.columns]
    weighted_correlation_mean = pd.Series(np.average(spearman_df.values,
                                                     weights=seat_weights, axis=1),
                                          index=spearman_df.index)
    return pd.DataFrame({
        '$\rho$ mean': unweighted_correlation_mean,
        '$\rho$ weighted mean': weighted_correlation_mean,
    })


def create_compactness_box_df(ensemble_results, metric, sort_by):
    """Create table of compactness distribution values."""
    series_dict = {s: pd.Series(
        r[metric + '_distribution']
    ).describe() / constants.seats[s]['house']
                   for s, r in ensemble_results.items()}

    box_df = pd.DataFrame(series_dict).drop(['count', 'mean', 'std'])
    box_df.loc['sort_column'] = sort_by
    return box_df.T.sort_values(by='sort_column').T.drop('sort_column')


def compute_historical_compactness(ensemble_results):
    """Plot the distribution of ensemble compactness versus enacted plan compactness."""
    all_district_gdf = load_district_shapes()
    districts_to_tracts_by_state = {}
    for state in ensemble_results:
        print(state)
        state_geoid = str(constants.ABBREV_DICT[state][constants.FIPS_IX])
        district_gdf = all_district_gdf[all_district_gdf.STATEFP == state_geoid]
        tract_gdf = load_tract_shapes(state)
        dtot, ttod = district_tract_map(tract_gdf, district_gdf)
        districts_to_tracts_by_state[state] = dtot

    historical_dispersion = {}
    historical_roeck = {}
    historical_cut_edges = {}
    for state in districts_to_tracts_by_state:
        state_df, G, lengths, _ = load_opt_data(state)
        plan = list(districts_to_tracts_by_state[state].values())
        historical_dispersion[state] = np.array(dispersion_compactness(plan, state_df)).mean()
        historical_roeck[state] = np.array(roeck_compactness(plan, state_df, lengths)).mean()
        historical_cut_edges[state] = np.array(list(
            map(lambda x: sum(1 for _ in nx.edge_boundary(G, x)), plan))).mean()
    return historical_dispersion, historical_roeck, historical_cut_edges


def plot_centralization_distribution(fig_dir, ensemble_results, historical_dispersion, min_seats=3):
    """Plot ensemble distribution of centralization compactness."""
    dispersion_box_df = create_compactness_box_df(ensemble_results, 'dispersion', historical_dispersion)
    plt.rcParams.update({'font.size': 14})
    dispersion_box_df = dispersion_box_df.drop(
        columns=[s for s in dispersion_box_df.columns
                 if constants.seats[s]['house'] < min_seats])
    dispersion_box_df.boxplot(figsize=(20, 5), whis=(0, 100),
                              positions=range(0, len(dispersion_box_df.columns)))
    plt.scatter(dispersion_box_df.columns,
                [historical_dispersion[state] for state in dispersion_box_df.columns],
                c='red', marker='x', vmin=0, vmax=1, label='enacted plan (2018)')
    plt.ylabel('centralization')
    plt.legend()
    plt.axhline(.5, color='black', linewidth=.1)
    plt.margins(x=.01)
    plt.savefig(os.path.join(fig_dir, 'ensemble_centralization_distribution.eps'),
                format='eps', bbox='tight')


def plot_roeck_distribution(fig_dir, ensemble_results, historical_roeck, min_seats=3):
    """Plot ensemble distribution of Roeck compactness."""
    roeck_box_df = create_compactness_box_df(ensemble_results, 'roeck', historical_roeck)
    plt.rcParams.update({'font.size': 14})
    roeck_box_df = roeck_box_df.drop(columns=[s for s in roeck_box_df.columns
                                              if constants.seats[s]['house'] < min_seats])
    roeck_box_df.boxplot(figsize=(20, 5), whis=(0, 100),
                         positions=range(0, len(roeck_box_df.columns)))
    plt.scatter(roeck_box_df.columns,
                [historical_roeck[state] * 1000 ** 2 for state in roeck_box_df.columns],
                c='red', marker='x', vmin=0, vmax=1, label='enacted plan (2018)')
    plt.ylabel('Roeck compactness')
    plt.legend()
    plt.margins(x=.01)
    plt.savefig(os.path.join(fig_dir, 'ensemble_roeck_distribution.eps'),
                format='eps', bbox='tight')


def plot_cut_edges_distributions(fig_dir, ensemble_results, historical_cut_edges, min_seats=3):
    """Plot ensemble distribution of cut edges compactness."""
    cut_edges_box_df = create_compactness_box_df(ensemble_results, 'cut_edges', historical_cut_edges)
    plt.rcParams.update({'font.size': 14})
    cut_edges_box_df = cut_edges_box_df.drop(
        columns=[s for s in cut_edges_box_df.columns
                 if constants.seats[s]['house'] < min_seats])
    cut_edges_box_df.boxplot(figsize=(20, 5), whis=(0, 100),
                             positions=range(0, len(cut_edges_box_df.columns)))
    plt.scatter(cut_edges_box_df.columns,
                [historical_cut_edges[state] for state in cut_edges_box_df.columns],
                c='red', marker='x', vmin=0, vmax=1, label='enacted plan (2018)', s=55)
    plt.ylabel('average edge cuts')
    plt.legend()
    plt.margins(x=.01)
    plt.savefig(os.path.join(fig_dir, 'ensemble_cut_distribution.eps'),
                format='eps', bbox='tight')


def make_ensemble_parameter_table(exp_path):
    """Make table of the ensemble generation parameters and selected statistics
    of the ensemble."""
    ensemble_table_dict = {}
    for file in os.listdir(exp_path):
        if file[-2:] != '.p':
            continue
        state = file[:2]
        subsample_constant = 1000 * constants.seats[state]['house'] ** 2
        tree = pickle.load(open(os.path.join(exp_path, file), 'rb'))
        ensemble_table_dict[state] = {
            'w(root)': int(tree['trial_config']['n_root_samples']),
            'w': int(tree['trial_config']['n_samples']),
            'generated districts': int(len(tree['leaf_nodes'])),
            'plans': tree['n_plans'],
            'leverage': round(math.log(tree['n_plans'] / len(tree['leaf_nodes'])) / math.log(10), 2),
            'runtime': round(tree['generation_time'] / 60, 2),
            'subsampled plans': min(int(subsample_constant), tree['n_plans'])
        }
    ensemble_table = pd.DataFrame(ensemble_table_dict).T
    ensemble_table.index.name = 'state'
    int_cols = ['w(root)', 'w', 'generated districts', 'subsampled plans']
    ensemble_table[int_cols] = ensemble_table[int_cols].astype(np.int32)
    return ensemble_table


def plot_seat_share_ensemble_comparison(new_df, old_df, fig_dir, historical=None):
    """Plot seat-share ensemble comparison."""
    plt.rcParams.update({'font.size': 14})
    new_df = new_df[[s for s in new_df.columns if constants.seats[s]['house'] > 2]]
    new_df.boxplot(figsize=(20, 5), whis=(0, 100), positions=range(0, len(new_df.columns)))
    old_df = old_df[new_df.columns]
    plt.scatter(old_df.loc['max'].index, old_df.loc['max'].values,
               marker="_", color='red', s=100, label="FC+1-P max")
    plt.scatter(old_df.loc['min'].index, old_df.loc['min'].values,
                marker='_', color='red', s=100, label="FC+1-P min")
    if historical is not None:
        plt.scatter(new_df.columns,
                [historical[state] for state in new_df.columns],
                c='purple', marker='x', vmin=0, vmax=1,
                    label='Average seat-share 2012-2018', s=55)
    plt.legend()
    plt.ylabel('Republican seat-share')
    plt.legend()
    plt.margins(x=.01)
    plt.gca().set_ylim([-0.025, 1.025])
    plt.yticks(ticks=np.arange(0, 1.1, .1))
    plt.grid(linewidth=.5, alpha=.5)
    plt.axhline(y=.5, color='black', linewidth=.5, alpha=.25, linestyle=":")
    plt.savefig(os.path.join(fig_dir, 'ensemble_seat_share_comparison.eps'),
                format='eps', bbox='tight')


def plot_compactness_ensemble_comparison(new_df, old_df, fig_dir, historical=None):
    """Plot compactness ensemble comparison."""
    plt.rcParams.update({'font.size': 14})
    new_df = new_df[[s for s in new_df.columns if constants.seats[s]['house'] > 2]]
    new_df.boxplot(figsize=(20, 5), whis=(0, 100), positions=range(0, len(new_df.columns)))
    old_df = old_df[new_df.columns]
    plt.scatter(old_df.loc['max'].index, old_df.loc['max'].values,
               marker="_", color='red', s=100, label="FC+1-P max")
    plt.scatter(old_df.loc['min'].index, old_df.loc['min'].values,
                marker='_', color='red', s=100, label="FC+1-P min")
    if historical is not None:
        plt.scatter(new_df.columns,
                [historical[state] for state in new_df.columns],
                c='purple', marker='x', vmin=0, vmax=1, label='enacted plan (2018)', s=55)
    plt.legend(loc='upper left', prop={'size': 12})
    plt.ylabel('Average cut edges')
    plt.margins(x=.01)
    plt.savefig(os.path.join(fig_dir, 'ensemble_compactness_comparison.eps'),
                format='eps', bbox='tight')
