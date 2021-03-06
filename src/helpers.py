import sqlite3
from collections import namedtuple

import pandas as pd

from phase_diagram import ureg

DB = 'data/data.db'


def database_dict(database):
    """Generates a dictionary of databases from a given SQLite database"""
    with sqlite3.connect(database) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        d = {}
        for t in tables:
            table_name = t[0]
            d[table_name] = pd.read_sql(f"select * from '{table_name}'", conn)
    return d


d = database_dict(DB)


def compound_index(compound):
    """
    Returns the compound ID in the database
    Parameters
    ----------
    compound : str
        Compound name / CAS / formula

    Returns
    -------
    int
        compound index in the database
    """
    compound_name_idx = d['names'].loc[d['names'].isin([compound]).any(axis=1)].index.tolist()
    compound_formula_cas_idx = d['compounds'].loc[d['compounds'].isin([compound]).any(axis=1)].index.tolist()
    try:
        compound_idx = (compound_formula_cas_idx + compound_name_idx)[0]
    except IndexError as err:
        print(f'{str(err).capitalize()}. Not a valid compound.')
    else:
        return d['compounds'].loc[compound_idx, 'id']


def compound_identification(compound):
    """
    Generates the compound identification

    Parameters
    ----------
    compound : str
        Compound name / CAS / formula

    Returns
    -------
    namedtuple
        compound identification parameters
    """
    compound_idx = compound_index(compound)
    compound_ident_tuple = list(d['compounds'].loc[(d['compounds']['id'] == compound_idx)].itertuples(index=False,
                                                                                                      name=None))[0]
    Identification = namedtuple("comp_id", ["index", "cas", "formula", "molar_mass", "name_ref"])
    return Identification(*compound_ident_tuple)


def compound_names(compound):
    """
    Compound names
    Parameters
    ----------
    compound : str
        Compound name / CAS / formula

    Returns
    -------
    namedtuple
        compound available names
    """
    compound_idx = compound_index(compound)
    compound_names_tuple = list(d['names'].loc[(d['names']['id'] == compound_idx)].itertuples(index=False,
                                                                                              name=None))[0]
    Names = namedtuple("names", ["index", "name", "alt_name1", "alt_name2", "alt_name3"])
    return Names(*compound_names_tuple)


def state_index(state):
    """Return the ID for a given state string"""
    try:
        return d['phys_states'].loc[d['phys_states']['state'] == state, 'id'].item()
    except ValueError:
        print('Invalid state')


def density_table(compound):
    """Generates a density dataframe for a given compound"""
    compound_idx = compound_index(compound)
    try:
        return d['density'].loc[(d['density']['id'] == compound_idx)]
    except IndexError:
        print('Invalid state or compound')


@ureg.wraps('gram/cm**3', [None, None, None])
def density(compound, state, value_index=0):
    """Returns the density for a given compound on a given physical state"""
    table = density_table(compound)
    state_idx = state_index(state)
    try:
        return list(table.loc[(table['state'] == state_idx), 'value'])[value_index]
    except IndexError:
        print('Invalid state or compound')


def antoine_table(compound):
    """Generates a Antoine coefficients dataframe for a given compound"""
    compound_idx = compound_index(compound)
    try:
        return d['antoine'].loc[(d['antoine']['id'] == compound_idx)]
    except IndexError:
        print('Invalid state or compound')


def antoine(compound, value_index=0):
    """Generates Antoine data for a given compound"""
    table = antoine_table(compound)
    try:
        antoine_tuple = list(table.loc[:, ['t_min', 't_max', 'A', 'B', 'C']].itertuples(index=False,
                                                                                        name=None))[value_index]
        Antoine = namedtuple("antoine", ["Tmin", "Tmax", "A", "B", "C"])
        return Antoine(*antoine_tuple)
    except IndexError:
        print('Invalid compound')


def point_table(compound, point_name):
    """Generates dataframe with data for given point for a given compound"""
    compound_idx = compound_index(compound)
    try:
        return d[point_name].loc[d[point_name]['id'] == compound_idx]
    except KeyError:
        print('Invalid point name')


@ureg.wraps(('kelvin', 'pascal'), [None, None, None])
def _point(compound, point_name, value_index=0):
    table = point_table(compound, point_name)
    return list(table.loc[:, ['temperature', 'pressure']].itertuples(index=False, name=None))[value_index]


def point(compound, point_name, value_index=0):
    """Returns a point with units"""
    point_with_units = _point(compound, point_name, value_index)
    Point = namedtuple("point", ["temperature", "pressure"])
    return Point(*point_with_units)


def enthalpy_table(compound, enthalpy_name):
    """Generates a enthalpy dataframe for a given compound"""
    compound_idx = compound_index(compound)
    name_dict = {'fusion': 'h_melt',
                 'sublimation': 'h_sub',
                 'vaporization': 'h_vap_boil'}
    try:
        return d[name_dict[enthalpy_name]].loc[d[name_dict[enthalpy_name]]['id'] == compound_idx]
    except KeyError:
        print('Invalid enthalpy name')


@ureg.wraps('kJ/mole', [None, None, None])
def enthalpy(compound, enthalpy_name, value_index=0):
    """Returns the value of an enthalpy for a given compound"""
    table = enthalpy_table(compound, enthalpy_name)
    return list(table.loc[:, 'value'])[value_index]


@ureg.wraps(None, ['gram/(cm**3)', 'gram/(cm**3)', 'gram/mol'])
def volume_change_fusion_calc(density_liquid, density_solid, molar_mass):
    """Calculates the molar volume change during fusion based on density values"""
    return (1/density_liquid - 1/density_solid) * molar_mass


@ureg.wraps('(cm**3)/mole', [None, None, None, None])
def volume_change_fusion(compound, value_index=0, calc=True, calc_values_index=(0, 0)):
    """Returns the molar volume change during fusion for a given compound"""
    compound_idx = compound_index(compound)
    if calc:
        d_sol = density(compound, 'solid', calc_values_index[0])
        d_liq = density(compound, 'liquid', calc_values_index[1])
        molar_mass = compound_identification(compound)[3] * ureg('gram/mole')
        return volume_change_fusion_calc(d_liq, d_sol, molar_mass)
    try:
        return list(d['v_melt'].loc[(d['v_melt']['id'] == compound_idx), 'value'])[value_index]
    except IndexError:
        print('Not valid. Try calculated value.')
