# -*- coding: utf-8 -*-
'''Chemical Engineering Design Library (ChEDL). Utilities for process modeling.
Copyright (C) 2016, 2017, 2018, 2019 Caleb Bell <Caleb.Andrew.Bell@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''

from __future__ import division
from pprint import pprint
from thermo.utils import property_mass_to_molar, property_molar_to_mass
from fluids.numerics import normalize

__all__ = ['Hcombustion', 'combustion_products', 'combustion_products_mixture',
           'air_fuel_ratio_solver', 'fuel_air_spec_solver', 
           'fuel_air_third_spec_solver', 'combustion_spec_solver']


combustion_atoms = set(['C', 'H', 'N', 'O', 'S', 'Br', 'I', 'Cl', 'F', 'P'])


unreactive_CASs = {
    '124-38-9': 'CO2',
    '16752-60-6': 'P4O10',
    '7446-09-5': 'SO2',
    '7553-56-2': 'I2',
    '7647-01-0': 'HCl',
    '7664-39-3': 'HF',
    '7726-95-6': 'Br2',
    '7727-37-9': 'N2',
    '7732-18-5': 'H2O'}

O2_CAS = '7782-44-7'
H2O_CAS = '7732-18-5'


def combustion_products(atoms):
    '''Calculates the combustion products of a molecule, given a dictionary of
    its constituent atoms and their counts.
    Products for non-hydrocarbons may not be correct, but are still 
    calculated.

    Parameters
    ----------
    atoms : dict
        Dictionary of atoms and their counts, [-]

    Returns
    -------
    combustion_producucts : dict
        Dictionary of combustion products and their counts, [-]

    Notes
    -----
    Also included in the results is the moles of O2 required per mole of
    the mixture of the molecule.
    
    HF and HCl are gaseous products in their standard state. P4O10 is a solid
    in its standard state. Bromine is a liquid as is iodine. Water depends on
    the chosen definition of heating value. The other products are gases.
    
    Atoms not in ['C', 'H', 'N', 'O', 'S', 'Br', 'I', 'Cl', 'F', 'P'] are 
    returned as pure species; i.e. sodium hydroxide produces water and pure
    Na.
    
    

    Examples
    --------
    Methanol:

    >>> pprint(combustion_products({'H': 4, 'C': 1, 'O': 1}))
    {'Br2': 0.0,
     'CO2': 1,
     'H2O': 2.0,
     'HCl': 0,
     'HF': 0,
     'I2': 0.0,
     'N2': 0.0,
     'O2_required': 1.5,
     'P4O10': 0.0,
     'SO2': 0}
    '''
    nC, nH, nN, nO, nS, nBr, nI, nCl, nF, nP = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

    if 'C' in atoms and atoms['C'] != 0:
        nC = atoms['C']
    if 'H' in atoms:
        nH = atoms['H']
    if 'N' in atoms:
        nN = atoms['N']
    if 'O' in atoms:
        nO = atoms['O']
    if 'S' in atoms:
        nS = atoms['S']
    if 'Br' in atoms:
        nBr = atoms['Br']
    if 'I' in atoms:
        nI = atoms['I']
    if 'Cl' in atoms:
        nCl = atoms['Cl']
    if 'F' in atoms:
        nF = atoms['F']
    if 'P' in atoms:
        nP = atoms['P']

    nO2_req = nC + nS + .25*nH + 1.25*nP - .25*(nCl + nF) - .5*nO
    nCO2 = nC
    nBr2 = .5*nBr
    nI2 = .5*nI

    nHCl = nCl
    nHF = nF

    nSO2 = nS

    nN2 = .5*nN
    nP4O10 = .25*nP
    nH2O = (nH - nCl - nF)/2.
    products = {'CO2': nCO2, 'Br2': nBr2, 'I2': nI2, 'HCl': nCl, 'HF': nHF, 
                'SO2': nSO2, 'N2': nN2, 'P4O10': nP4O10, 'H2O': nH2O,
                'O2_required': nO2_req}
    
    for atom, value in atoms.items():
        if atom not in combustion_atoms:
            products[atom] = value
    return products


# mixture - mole fractions and atoms

def combustion_products_mixture(atoms_list, zs, reactivities=None, CASs=None):
    '''Calculates the combustion products of a mixture of molecules and their,
    mole fractions; requires a list of dictionaries of each molecule's 
    constituent atoms and their counts.
    Products for non-hydrocarbons may not be correct, but are still 
    calculated.

    Parameters
    ----------
    atoms_list : list[dict]
        List of dictionaries of atoms and their counts, [-]
    zs : list[float]
        Mole fractions of each molecule in the mixture, [-]
    reactivities : list[bool]
        Indicators as to whether to combust each molecule, [-]
    CASs : list[str]
        CAS numbers of all compounds; non-reacted products will appear
        in the products indexed by their CAS number, [-]

    Returns
    -------
    combustion_producucts : dict
        Dictionary of combustion products and their counts, [-]

    Notes
    -----
    Also included in the results is the moles of O2 required per mole of
    the mixture to be burnt.
    
    Note that if O2 is in the feed, this will be subtracted from the required
    O2 amount.

    HF and HCl are gaseous products in their standard state. P4O10 is a solid
    in its standard state. Bromine is a liquid as is iodine. Water depends on
    the chosen definition of heating value. The other products are gases.
    
    Note that if instead of mole fractions, mole flows are given - the results
    are in terms of mole flows as well!

    Examples
    --------
    Mixture of methane and ethane.

    >>> combustion_products_mixture([{'H': 4, 'C': 1}, {'H': 6, 'C': 2}, {'Ar': 1}, {'C': 15, 'H': 32}],
    ... [.9, .05, .04, .01], reactivities=[True, True, True, False], 
    ... CASs=['74-82-8', '74-84-0', '7440-37-1', '629-62-9'])
    {'629-62-9': 0.01,
     'Ar': 0.04,
     'Br2': 0.0,
     'CO2': 1.0,
     'H2O': 1.9500000000000002,
     'HCl': 0.0,
     'HF': 0.0,
     'I2': 0.0,
     'N2': 0.0,
     'O2_required': 1.975,
     'P4O10': 0.0,
     'SO2': 0.0}
    '''
    # Attempted to use a .copy() on a base dict but that was slower
    products = {'CO2': 0.0, 'Br2': 0.0, 'I2': 0.0, 'HCl': 0.0, 'HF': 0.0, 
                'SO2': 0.0, 'N2': 0.0, 'P4O10': 0.0, 'H2O': 0.0,
                'O2_required': 0.0}
    has_reactivities = reactivities is not None
    for i, (atoms, zs_i) in enumerate(zip(atoms_list, zs)):
        if has_reactivities and not reactivities[i]:
            products[CASs[i]] = zs_i
        else:
            ans = combustion_products(atoms)
            if ans is not None:
                for key, val in ans.items():
                    if key in products:
                        products[key] += val*zs_i
                    else:
                        products[key] = val*zs_i
    return products


def Hcombustion(atoms, Hf=None, HfH2O=-285825, HfCO2=-393474,
                HfSO2=-296800, HfBr2=30880, HfI2=62417, HfHCl=-92173,
                HfHF=-272711, HfP4O10=-3009940, HfO2=0, HfN2=0, 
                CASRN=None, higher=True):
    '''Calculates the heat of combustion, in J/mol.
    Value non-hydrocarbons is not correct, but still calculable.a
    
    Can calculate the higher heating value (HHV)/heat of combusion or the
    lower heating value (LHV), according to the value of `higher`.
    
    Other names for the higher value are **Gross Calorific Value (GCV)** ,
    **Higher Calorific Value (HCV)**, **Upper Heating Value (UHV)**,
    **Greater Heating Value (GHV)**, and **Gross Energy**.
    
    Other names for the lower value are **Net Caloric Value (NCV)**,
    **Lower Caloric Value (LCV)**, and **Net Heating Value (NHV)**.

    Parameters
    ----------
    atoms : dict
        Dictionary of atoms and their counts, []
    Hf : float
        Standard heat of formation of given chemical, [J/mol]
    HfH2O : float, optional
        Heat of formation of water, [J/mol]
    HfCO2 : float, optional
        Standard heat of formation of carbon dioxide, [J/mol]
    HfSO2 : float, optional
        Standard heat of formation of sulfur dioxide, [J/mol]
    HfBr2 : float, optional
        Standard heat of formation of bromine, [J/mol]
    HfI2 : float, optional
        Standard heat of formation of iodine, [J/mol]
    HfHCl : float, optional
        Standard heat of formation of chlorine, [J/mol]
    HfHF : float, optional
        Standard heat of formation of hydrogen fluoride, [J/mol]
    HfP4O10 : float, optional
        Standard heat of formation of phosphorus pentoxide, [J/mol]
    HfO2 : float, optional
        Standard heat of formation of oxygen, [J/mol]
    HfN2 : float, optional
        Standard heat of formation of nitrogen, [J/mol]
    CASRN : str, optional
        CAS number, [-]
    higher : bool, optional
        Whether or not to return the higher heat of combustion or the lower,
        [-]

    Returns
    -------
    Hc : float
        Heat of combustion of chemical, in the selected basis, [J/mol]

    Notes
    -----
    Default heats of formation for chemicals are at 298 K, 1 atm.
    HF and HCl are gaseous products in their standard state. P4O10 is a solid
    in its standard state. Bromine is a liquid as is iodine. Water depends on
    the chosen definition of heating value. The other products are gases.

    Examples
    --------
    Liquid methanol burning

    >>> Hcombustion({'H': 4, 'C': 1, 'O': 1}, Hf=-239100)
    -726024.0
    
    >>> Hcombustion({'H': 4, 'C': 1, 'O': 1}, Hf=-239100, higher=False)
    -638049.1
    '''
    if Hf is None or atoms is None:
        return None
    if not higher:
         HfH2O += 43987.45 # CoolProp, Q=0/1 (not ideal gas)
    if CASRN is not None and CASRN in incombustible_materials:
        return 0.0
    
    nC, nH, nN, nO, nS, nBr, nI, nCl, nF, nP = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

    if 'C' in atoms and atoms['C'] != 0:
        nC = atoms['C']
    else:
        return None  # C is necessary for this formula
    if 'H' in atoms:
        nH = atoms['H']
    if 'N' in atoms:
        nN = atoms['N']
    if 'O' in atoms:
        nO = atoms['O']
    if 'S' in atoms:
        nS = atoms['S']
    if 'Br' in atoms:
        nBr = atoms['Br']
    if 'I' in atoms:
        nI = atoms['I']
    if 'Cl' in atoms:
        nCl = atoms['Cl']
    if 'F' in atoms:
        nF = atoms['F']
    if 'P' in atoms:
        nP = atoms['P']

    nO2_req = nC + nS + nH/4. + 5*nP/4. - (nCl + nF)/4. - nO/2.
    nCO2 = nC
    nBr2 = nBr/2.
    nI2 = nI/2.

    nHCl = nCl
    nHF = nF

    nSO2 = nS

    nN2 = nN/2.
    nP4O10 = nP/4.
    nH2O = (nH - nCl - nF)/2.

    Hc = (nBr2*HfBr2 + nI2*HfI2) + (nHCl*HfHCl + nHF*HfHF) + nSO2*HfSO2 + \
        nN2*HfN2 + nP4O10*HfP4O10 + nH2O*HfH2O - nO2_req*HfO2 + nCO2*HfCO2 - Hf
    return Hc

incombustible_materials = {
'7440-37-1': 'Ar',
'7782-44-7': 'O2',
'7440-01-9': 'Ne',
'7439-90-9': 'Kr',
'7440-63-3': 'Xe',
'7727-37-9': 'N2',
'124-38-9': 'CO2',
'1314-13-2': 'ZnO2',
'7732-18-5': 'water',
'7789-20-0': 'water(D2)',
'13463-67-7': 'TiO2',
'14762-55-1': 'He3',
'7440-59-7': 'He',
'7782-50-5': 'Cl',
'7446-09-5': 'SO2',
'7726-95-6': 'Br'}

combustion_products_to_CASs = {
'Br2': '7726-95-6',
'CO2': '124-38-9',
'H2O': '7732-18-5',
'HCl': '7647-01-0',
'HF': '7664-39-3',
'I2': '7553-56-2',
'N2': '7727-37-9',
'O2': '7782-44-7',
'P4O10': '16752-60-6',
'SO2': '7446-09-5'}


def combustion_products_to_list(products, CASs):
    zs = [0.0 for i in CASs]
    for product, zi in products.items():
        if product == 'O2_required':
            product = 'O2'
            zi = -zi
            
        if product in CASs:
            zs[CASs.index(product)] = zi
        elif combustion_products_to_CASs[product] in CASs:
            zs[CASs.index(combustion_products_to_CASs[product])] = zi
        else:
            if abs(zi) > 0:
                raise ValueError("Combustion product not in package")
        
    return zs



def is_combustible(CAS, atoms, reactive=True):
    if not reactive:
        return False
    if CAS in unreactive_CASs:
        return False
    elif 'C' in atoms and atoms['C'] > 0:
        return True
    elif 'H' in atoms and atoms['H'] > 0:
        return True
    else:
        return False


def air_fuel_ratio_solver(ratio, Vm_air, Vm_fuel, MW_air, MW_fuel,
                          n_air=None, n_fuel=None,
                          basis='mass', full_info=False):
    '''Calculates molar flow rate of air or fuel from the other,
    using a specified air-fuel ratio. Supports 'mole', 'mass', and 'volume'
    bases for the ratio variable. The ratio must be of the same units - 
    i.e. kg/kg instead of lb/kg.
    
    If `full_info` is True, the mole, mass, and volume air-fuel ratios will
    all be calculated and returned as well.

    Parameters
    ----------
    ratio : float
        Air-fuel ratio, in the specified `basis`, [-]
    Vm_air : float
        Molar volume of air, [m^3/mol]
    Vm_fuel : float
        Molar volume of fuel, [m^3/mol]
    MW_air : float
        Molecular weight of air, [g/mol]
    MW_fuel : float
        Molecular weight of fuel, [g/mol]
    n_air : float, optional
        Molar flow rate of air, [mol/s]
    n_fuel : float, optional
        Molar flow rate of fuel, [mol/s]
    basis : str, optional
        One of 'mass', 'mole', or 'volume', [-]
    full_info : bool, optional
        Whether to calculate and return all the mole, mass, and volume 
        ratios as well, [-]
        
    Returns
    -------
    n_air : float
        Molar flow rate of air, [mol/s]
    n_fuel : float
        Molar flow rate of fuel, [mol/s]
    mole_ratio : float, only returned if full_info == True
        Air-fuel mole ratio, [-]
    mass_ratio : float, only returned if full_info == True
        Air-fuel mass ratio, [-]
    volume_ratio : float, only returned if full_info == True
        Air-fuel volume ratio, [-]

    Notes
    -----
    The function works so long as the flow rates, molar volumes, and molecular
    weights are in a consistent basis.
    
    The function may also be used to obtain the other ratios, even if both 
    flow rates are known.
    
    Be careful to use standard volumes if the ratio known is at standard
    conditions! 
    
    This function has no provision for mixed units like mass/mole or 
    volume/mass.
    
    Examples
    --------
    >>> Vm_air = 0.024936627188566596
    >>> Vm_fuel = 0.024880983160354486
    >>> MW_air = 28.850334
    >>> MW_fuel = 17.86651
    >>> n_fuel = 5.0
    >>> n_air = 25.0
    >>> air_fuel_ratio_solver(ratio=5, Vm_air=Vm_air, Vm_fuel=Vm_fuel,
    ... MW_air=MW_air, MW_fuel=MW_fuel, n_air=n_air,
    ... n_fuel=n_fuel, basis='mole', full_info=True)
    (25.0, 5.0, 5.0, 8.073858296891782, 5.011182039683378)
    
    '''
    if basis == 'mole':
        if n_air is not None and n_fuel is None:
            n_fuel = n_air/ratio
        elif n_fuel is not None and n_air is None:
            n_air = n_fuel*ratio
    elif basis == 'mass':
        if n_air is not None and n_fuel is None:
            m_air = property_mass_to_molar(n_air, MW_air)
            m_fuel = m_air/ratio
            n_fuel = property_molar_to_mass(m_fuel, MW_fuel)
        elif n_fuel is not None and n_air is None:
            m_fuel = property_mass_to_molar(n_fuel, MW_fuel)
            m_air = m_fuel*ratio
            n_air = property_molar_to_mass(m_air, MW_air)
    elif basis == 'volume':
        if n_air is not None and n_fuel is None:
            V_air = n_air*Vm_air
            V_fuel = V_air/ratio
            n_fuel = V_fuel/Vm_fuel
        elif n_fuel is not None and n_air is None:
            V_fuel = n_fuel*Vm_fuel
            V_air = V_fuel*ratio
            n_air = V_air/Vm_air
    if n_air is None or n_fuel is None:
        raise ValueError("Could not convert")
    if full_info:
        mole_ratio = n_air/n_fuel
        mass_ratio, volume_ratio = MW_air/MW_fuel*mole_ratio, Vm_air/Vm_fuel*mole_ratio
        return n_air, n_fuel, mole_ratio, mass_ratio, volume_ratio
        
    return n_air, n_fuel


def fuel_air_spec_solver(zs_air, zs_fuel, CASs, atomss, n_fuel=None, 
                         n_air=None, n_out=None,
                         O2_excess=None, frac_out_O2=None,
                         frac_out_O2_dry=None, ratio=None,
                         Vm_air=None, Vm_fuel=None, MW_air=None, MW_fuel=None,
                         ratio_basis='mass', reactivities=None):
    '''Solves the system of equations describing a flow of air, with a flow of
    combustibles, burning completely. All calculated variables are returned as
    a dictionary.
    
    Supports solving with any 2 of the extensive variables, or one extensive
    and one intensive variable:
    
    Extensive variables:
        
    * `n_air`
    * `n_fuel`
    * `n_out`
    
    Intensive variables:
        
    * `O2_excess`
    * `frac_out_O2`
    * `frac_out_O2_dry`
    * `ratio`
    
    The variables `Vm_air`, `Vm_fuel`, `MW_air`, and `MW_fuel` are only
    required when an air-fuel ratio is given. Howver, the ratios cannot be
    calculated for the other solve options without them.
    
    Parameters
    ----------
    zs_air : list[float]
        Mole fractions of the air; most not contain any combustibles, [-]
    zs_fuel : list[float]
        Mole fractions of the fuel; can contain inerts and/or oxygen as well,
        [-]
    CASs : list[str]
        CAS numbers of all compounds, [-]
    atomss : list[dict[float]]
        List of dictionaries of elements and their counts for all molecules in
        the mixtures, [-]
    n_fuel : float, optional
        Flow rate of fuel, [mol/s]
    n_air : float, optional
        Flow rate of air, [mol/s]
    n_out : float, optional
        Flow rate of combustion products, remaining oxygen, and inerts, [mol/s]
    O2_excess : float, optional
        The excess oxygen coming out; (O2 in)/(O2 required) - 1, [-]
    frac_out_O2 : float, optional
        The mole fraction of oxygen out, [-]
    frac_out_O2_dry : float, optional
        The mole fraction of oxygen out on a dry basis, [-]
    ratio : float, optional
        Air-fuel ratio, in the specified `basis`, [-]
    Vm_air : float, optional
        Molar volume of air, [m^3/mol]
    Vm_fuel : float, optional
        Molar volume of fuel, [m^3/mol]
    MW_air : float, optional
        Molecular weight of air, [g/mol]
    MW_fuel : float, optional
        Molecular weight of fuel, [g/mol]
    ratio_basis : str, optional
        One of 'mass', 'mole', or 'volume', [-]
    reactivities : list[bool], optional
        Optional list which can be used to mark otherwise combustible 
        compounds as incombustible and which will leave unreacted, [-]
        
    Returns
    -------
    results : dict
        * n_fuel : Flow rate of fuel, [mol/s]
        * n_air : Flow rate of air, [mol/s]
        * n_out : Flow rate of combustion products, remaining oxygen, and 
          inerts, [mol/s]
        * O2_excess : The excess oxygen coming out; (O2 in)/(O2 required) - 1,
          [-]
        * frac_out_O2 : The mole fraction of oxygen out, [-]
        * frac_out_O2_dry : The mole fraction of oxygen out on a dry basis, [-]
        * mole_ratio : Air-fuel mole ratio, [-]
        * mass_ratio : Air-fuel mass ratio, [-]
        * volume_ratio : Air-fuel volume ratio, [-]
        * ns_out : Mole flow rates out, [mol/s] 
        * zs_out : Mole fractions out, [-]

    Notes
    -----
    Combustion products themselves cannot be set as unreactive.
    
    The function works so long as the flow rates, molar volumes, and molecular
    weights are in a consistent basis.
    
    The function may also be used to obtain the other ratios, even if both 
    flow rates are known.
    
    Be careful to use standard volumes if the ratio known is at standard
    conditions! 
    
    Examples
    --------
    '''
    TRACE_FRACTION_IN_AIR = 1e-10
    # what burns and what does not
#                          T_flame, efficiency, efficiency_basis, combustion_duty,
#                          T_air, T_fuel, P_air, P_fuel, T_out, P_out,
    # Goal is only to solve for air or fuel flow rate without rigorous combustion
    
    # Only one path to get n_air, n_fuel should ever be followed. Calculate all the
    # extra information redundantly at the end!

    # Handle combustibles in the air by burning them right away,
    # and working with that n_air.
    
    # To include a fixed fuel flow rate, a similar process should be able to be done.
    
    N = len(CASs)
    cmps = range(N)
    
    if reactivities is None:
        reactivities = [True for i in zs_air]
    combustibilities = [is_combustible(CASs[i], atomss[i], reactivities[i]) for i in cmps]
    
    for i in combustibilities:
        if zs_air[i] > TRACE_FRACTION_IN_AIR:
            pass
        
        
    O2_index = CASs.index(O2_CAS)
    H2O_index = CASs.index(H2O_CAS)
    
    z_air_O2 = zs_air[O2_index]
    z_air_H20 = zs_air[H2O_index]
    z_fuel_O2 = zs_fuel[O2_index]
    
    if ratio is not None and (n_air is None or n_fuel is None):
        n_air, n_fuel = air_fuel_ratio_solver(ratio, Vm_air, Vm_fuel, MW_air, MW_fuel, n_air=n_air,
                                              n_fuel=n_fuel, basis=ratio_basis)
    
    # Given O2 excess and either air or fuel flow rate, can solve directly for the other
    if O2_excess is not None and (n_fuel is None or n_air is None):
        if n_fuel is not None:
            comb_ans = combustion_products_mixture(atomss, zs_fuel, reactivities=reactivities, CASs=CASs)
            n_O2_required = comb_ans['O2_required']*n_fuel + z_fuel_O2*n_fuel
            N_O2_required_air = n_O2_required*(1.0 + O2_excess)- z_fuel_O2*n_fuel
            n_air = N_O2_required_air/zs_air[O2_index]
        elif n_air is not None:
            '''from sympy import *
            O2, n_fuel, O2_per_mole_fuel, n_O2_air, z_fuel_O2 = symbols('O2, n_fuel, O2_per_mole_fuel, n_O2_air, z_fuel_O2')
            Eq1 = Eq(O2/n_fuel, O2_per_mole_fuel)
            Eq2 = Eq(O2, n_O2_air + z_fuel_O2*n_fuel)
            solve([Eq1, Eq2], [n_fuel, O2])'''
            comb_ans = combustion_products_mixture(atomss, zs_fuel, reactivities=reactivities, CASs=CASs)
            O2_per_mole_fuel = (comb_ans['O2_required'] + zs_fuel[O2_index])*(1.0 + O2_excess)
            n_O2_air = zs_air[O2_index]*n_air
            n_fuel = n_O2_air/(O2_per_mole_fuel - z_fuel_O2)
        elif n_out is not None:
            '''from sympy import *
            n_air, n_fuel, n_out, n_delta, O2_coeff, O2_excess, z_air_O2, z_fuel_O2 = symbols('n_air, n_fuel, n_out, n_delta, O2_coeff, O2_excess, z_air_O2, z_fuel_O2')
            n_O2_in = n_air*z_air_O2 + z_fuel_O2*n_fuel
            Eq1 = Eq(O2_excess, n_O2_in/(n_fuel*O2_coeff) - 1)
            Eq2 = Eq(n_out, n_air + (n_delta)*n_fuel + n_fuel)
            solve([Eq1, Eq2], [n_fuel, n_air])'''
            comb_ans = combustion_products_mixture(atomss, zs_fuel, reactivities=reactivities, CASs=CASs)
            stoic_comb_products = combustion_products_to_list(comb_ans, CASs)
            O2_coeff = O2_burnt_n_fuel = comb_ans['O2_required'] + z_fuel_O2
            n_delta = 1
            for z_new, z_old, CAS in zip(stoic_comb_products, zs_fuel, CASs):
                if CAS != O2_CAS:
                    n_delta += z_new - z_old
            n_delta -= comb_ans['O2_required'] + z_fuel_O2

            n_fuel = n_out*z_air_O2/(O2_coeff*O2_excess + O2_coeff + n_delta*z_air_O2 - z_fuel_O2)
            n_air = n_out*(O2_coeff*O2_excess + O2_coeff - z_fuel_O2)/(O2_coeff*O2_excess + O2_coeff + n_delta*z_air_O2 - z_fuel_O2)
            
#            n_fuel = n_out*z_air_O2/(O2_burnt_n_fuel*O2_excess + O2_burnt_n_fuel + n_delta*z_air_O2)
#            n_air = O2_burnt_n_fuel*n_out*(O2_excess + 1)/(O2_burnt_n_fuel*O2_excess + O2_burnt_n_fuel + n_delta*z_air_O2)          
            
            
            
    # Solvers for frac_out_O2 and dry basis
    if (frac_out_O2 is not None or frac_out_O2_dry is not None) and (n_fuel is None or n_air is None):
        if n_fuel is not None:
            ns_fuel = [zi*n_fuel for zi in zs_fuel]
            comb_ans = combustion_products_mixture(atomss, ns_fuel, reactivities=reactivities, CASs=CASs)
            n_O2_stoic = comb_ans['O2_required']
            if n_O2_stoic < 0:
                raise ValueError("Cannot meet air spec - insufficient air for full combustion")
            # when burning stoichiometrically, how many moles out?
            stoic_comb_products = combustion_products_to_list(comb_ans, CASs)
            stoic_comb_products[O2_index] = 0 # Set the O2 to zero as it is negative
            n_fixed_products = sum(stoic_comb_products)

            # Following two equations solved using SymPy
            if frac_out_O2 is not None:
                '''from sympy import *
                from sympy.abc import *
                frac_goal, n_air, n_fixed, z_O2, O2_burnt = symbols('frac_goal, n_air, n_fixed, z_O2, O2_burnt')
                solve(Eq(frac_goal, (z_O2*n_air-O2_burnt)/((n_fixed+n_air)-O2_burnt)), n_air)
                '''
                n_air = (n_O2_stoic*frac_out_O2 - n_O2_stoic - frac_out_O2*n_fixed_products)/(frac_out_O2 - z_air_O2)
            elif frac_out_O2_dry is not None:
                '''from sympy import *
                from sympy.abc import *
                frac_goal, n_air, n_fixed, z_O2, n_O2_stoic, z_H20 = symbols('frac_goal, n_air, n_fixed, z_O2, n_O2_stoic, z_H20')
                solve(Eq(frac_goal, (z_O2*n_air-n_O2_stoic)/((n_fixed+n_air)-n_O2_stoic -n_air*z_H20)), n_air)
                '''
                n_fixed_products -= stoic_comb_products[H2O_index]
                n_air = ((-frac_out_O2_dry*n_O2_stoic + frac_out_O2_dry*n_fixed_products + n_O2_stoic)
                         /(frac_out_O2_dry*z_air_H20 - frac_out_O2_dry + z_air_O2))
        elif n_air is not None or n_out is not None:
            comb_ans = combustion_products_mixture(atomss, zs_fuel, reactivities=reactivities, CASs=CASs)
            O2_burnt_n_fuel = comb_ans['O2_required']
            H2O_from_fuel_n = comb_ans['H2O']
            n_delta = 0
            for k, v in comb_ans.items():
                if k != 'O2_required':
                    n_delta += v
                else:
                    n_delta -= v
            
            if frac_out_O2 is not None and n_air is not None:
                '''from sympy import *
                from sympy.abc import *
                frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff = symbols('frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff')
                n_unburnt_O2 = n_air*z_O2 - n_fuel*O2_coeff
                n_out = n_air + coeff*n_fuel
                solve(Eq(frac_goal, n_unburnt_O2/n_out), n_fuel)
                '''
                n_fuel = n_air*(-frac_out_O2 + z_air_O2)/(O2_burnt_n_fuel + n_delta*frac_out_O2)
            elif frac_out_O2_dry is not None and n_air is not None:
                '''from sympy import *
                from sympy.abc import *
                frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, H2O_coeff, z_H2O = symbols('frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, H2O_coeff, z_H2O')
                n_unburnt_O2 = n_air*z_O2 - n_fuel*O2_coeff
                n_out = n_air + coeff*n_fuel
                n_H2O = n_air*z_H2O + H2O_coeff*n_fuel
                solve(Eq(frac_goal, n_unburnt_O2/(n_out-n_H2O)), n_fuel)'''
                n_fuel = n_air*(frac_out_O2_dry*z_air_H20 - frac_out_O2_dry + z_air_O2)/(-H2O_from_fuel_n*frac_out_O2_dry + O2_burnt_n_fuel + n_delta*frac_out_O2_dry)
            elif frac_out_O2 is not None and n_out is not None:
                '''from sympy import *
                frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, n_out = symbols('frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, n_out')
                n_unburnt_O2 = n_air*z_O2 - n_fuel*O2_coeff
                Eq1 = Eq(frac_goal, n_unburnt_O2/n_out)
                Eq2 = Eq(n_out, n_air + coeff*n_fuel)
                solve([Eq1, Eq2], [n_fuel, n_air])'''
                n_fuel = -n_out*(frac_out_O2 - z_air_O2)/(O2_burnt_n_fuel + n_delta*z_air_O2)
                n_air = n_out*(O2_burnt_n_fuel + n_delta*frac_out_O2)/(O2_burnt_n_fuel + n_delta*z_air_O2)
            elif frac_out_O2_dry is not None and n_out is not None:
                '''from sympy import *
                frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, n_out, z_H2O, H2O_coeff = symbols('frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, n_out, z_H2O, H2O_coeff')
                n_unburnt_O2 = n_air*z_O2 - n_fuel*O2_coeff
                n_H2O = n_air*z_H2O + H2O_coeff*n_fuel
                Eq1 = Eq(frac_goal, n_unburnt_O2/(n_out-n_H2O))
                Eq2 = Eq(n_out, n_air + coeff*n_fuel)
                solve([Eq1, Eq2], [n_fuel, n_air])'''
                n_fuel = n_out*(frac_out_O2_dry*z_air_H20 - frac_out_O2_dry + z_air_O2)/(-H2O_from_fuel_n*frac_out_O2_dry + O2_burnt_n_fuel + n_delta*frac_out_O2_dry*z_air_H20 + n_delta*z_air_O2)
                n_air = n_out*(-H2O_from_fuel_n*frac_out_O2_dry + O2_burnt_n_fuel + n_delta*frac_out_O2_dry)/(-H2O_from_fuel_n*frac_out_O2_dry + O2_burnt_n_fuel + n_delta*(frac_out_O2_dry*z_air_H20 + z_air_O2))

    # Case of two fuels known - one n out
    if n_out is not None and (n_fuel is None or n_air is None):
        '''from sympy import *
        from sympy.abc import *
        frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, n_out = symbols('frac_goal, n_air, z_O2, n_fuel, coeff, O2_coeff, n_out')
        solve(Eq(n_out, n_air + coeff*n_fuel), n_fuel)
        solve(Eq(n_out, n_air + coeff*n_fuel), n_air)'''
        comb_ans = combustion_products_mixture(atomss, zs_fuel, reactivities=reactivities, CASs=CASs)
        n_delta = 0
        for k, v in comb_ans.items():
            if k != 'O2_required':
                n_delta += v
            else:
                n_delta -= v
                
        if n_fuel is not None:
            n_air = -n_delta*n_fuel + n_out
        elif n_air is not None:
            n_fuel = (-n_air + n_out)/n_delta
            
        
    
    
    # Compute all other properties from the air and fuel flow rate
    results = {'n_fuel': n_fuel, 'n_air': n_air}
    if n_fuel is not None and n_air is not None:
        ns_to_combust = []
        for zi_air, zi_fuel in zip(zs_air, zs_fuel):
            ns_to_combust.append(zi_air*n_air + zi_fuel*n_fuel)
        
        comb_ans = combustion_products_mixture(atomss, ns_to_combust, reactivities=reactivities, CASs=CASs)
        ns_out = combustion_products_to_list(comb_ans, CASs)

        comb_fuel_only = combustion_products_mixture(atomss, [n_fuel*zi for zi in zs_fuel], reactivities=reactivities, CASs=CASs)
        
        n_out = sum(ns_out)
        zs_out = normalize(ns_out)
        frac_out_O2 = zs_out[CASs.index(O2_CAS)]
        frac_out_O2_dry = frac_out_O2/(1.0 - zs_out[CASs.index(H2O_CAS)])
        
        results['ns_out'] = ns_out
        results['zs_out'] = zs_out
        results['n_out'] = n_out
        results['frac_out_O2'] = frac_out_O2
        results['frac_out_O2_dry'] = frac_out_O2_dry
        
        
        O2_in = n_air*zs_air[O2_index] + n_fuel*zs_fuel[O2_index]
        O2_demand = O2_in - results['ns_out'][O2_index]
        results['O2_excess'] = O2_in/O2_demand - 1
#        results['O2_excess'] = n_air*z_air_O2/(comb_fuel_only['O2_required']) - 1
        
        ratios = (None, None, None)
        if Vm_air is not None and Vm_fuel is not None and MW_air is not None and MW_fuel is not None:
            ratios = air_fuel_ratio_solver(None, Vm_air, Vm_fuel, MW_air, MW_fuel, 
                                           n_air=n_air, n_fuel=n_fuel, full_info=True)[2:]
        results['mole_ratio'], results['mass_ratio'], results['volume_ratio'] = ratios
        
    return results


def fuel_air_third_spec_solver(zs_air, zs_fuel, zs_third, CASs, atomss, n_third,
                           n_fuel=None, n_air=None, n_out=None,
                           O2_excess=None, frac_out_O2=None,
                           frac_out_O2_dry=None, ratio=None,
                           Vm_air=None, Vm_fuel=None, Vm_third=None, 
                           MW_air=None, MW_fuel=None, MW_third=None,
                           ratio_basis='mass', reactivities=None):
    # I believe will always require 1 intensive spec (or flow of )
    # To begin - exclude n_out spec? Should be possible to solve for it/with it though.
    
    common_specs = {'zs_air': zs_air, 'CASs': CASs, 'atomss': atomss,
                    'n_air': n_air, 'O2_excess': O2_excess, 'frac_out_O2': frac_out_O2,
                    'frac_out_O2_dry': frac_out_O2_dry, 'Vm_air': Vm_air, 'MW_air': MW_air,
                    'ratio': ratio, 'ratio_basis': ratio_basis,
                    'reactivities': reactivities}
    
    O2_index = CASs.index(O2_CAS)
    H2O_index = CASs.index(H2O_CAS)
    z_air_O2 = zs_air[O2_index]
    z_fuel_O2 = zs_fuel[O2_index]

    Vm_mix, MW_mix = None, None

    def fix_ratios(results):
        if n_fuel is not None:
            if Vm_fuel is not None and Vm_third is not None:
                Vm_mix = (Vm_fuel*n_fuel + Vm_third*n_third)/(n_fuel+n_third)
            if MW_fuel is not None and MW_third is not None:
                MW_mix = (MW_fuel*n_fuel + MW_third*n_third)/(n_fuel+n_third)
        # Needs n_fuel and n_air to be in outer namespace
        ratios = (None, None, None)
        if Vm_air is not None and Vm_mix is not None and MW_air is not None and MW_mix is not None:
            ratios = air_fuel_ratio_solver(None, Vm_air, Vm_mix, MW_air, MW_mix, 
                                           n_air=n_air, n_fuel=n_fuel+n_third, full_info=True)[2:]
        results['mole_ratio'], results['mass_ratio'], results['volume_ratio'] = ratios
            
    if n_fuel is not None :
        if Vm_fuel is not None and Vm_third is not None:
            Vm_mix = (Vm_fuel*n_fuel + Vm_third*n_third)/(n_fuel + n_third)
        if MW_fuel is not None and MW_third is not None:
            MW_mix = (MW_fuel*n_fuel + MW_third*n_third)/(n_fuel + n_third)

        # Combine the two fuels for one burn
        n_fuel_mix = n_fuel + n_third
        ns_fuel_mix = [zi*n_fuel + zj*n_third for zi, zj in zip(zs_fuel, zs_third)]
        zs_fuel_mix = normalize(ns_fuel_mix)
        
        mix_burn = fuel_air_spec_solver(zs_fuel=zs_fuel_mix, n_fuel=n_fuel_mix, 
                                        Vm_fuel=Vm_mix, MW_fuel=MW_mix,
                                        n_out=n_out,
                                       **common_specs)
        mix_burn['n_fuel'] -= n_third
        return mix_burn
    if n_air is not None and n_fuel is None:
        O2_in_third = n_third*zs_third[O2_index]
        O2_in_orig = n_air*z_air_O2 + O2_in_third
        
        third_burn = fuel_air_spec_solver(zs_fuel=zs_third, n_fuel=n_third,
                                          Vm_fuel=Vm_third, MW_fuel=MW_third,
                                          **common_specs)
        n_air2 = third_burn['n_out']
        zs_air2 = third_burn['zs_out']

        O2_demand_third = O2_in_orig - third_burn['ns_out'][O2_index]
        
        extra_specs = common_specs.copy()
        extra_specs['n_air'] = n_air2
        extra_specs['zs_air'] = zs_air2
        if O2_excess is not None:
            '''from sympy import *
            O2_excess, excess_sub, O2_air, O2_in_third, O2_fixed, z_fuel_O2, n_fuel, O2_coeff, O2_demand_third = symbols('O2_excess, excess_sub, O2_air, O2_in_third, O2_fixed, z_fuel_O2, n_fuel, O2_coeff, O2_demand_third')
            Eq1 = Eq(O2_excess, (O2_air + O2_in_third + z_fuel_O2*n_fuel)/(O2_demand_third + n_fuel*O2_coeff) - 1)
            Eq2 = Eq(excess_sub, (O2_fixed +z_fuel_O2*n_fuel)/(n_fuel*O2_coeff) - 1)
            solve([Eq1, Eq2], [excess_sub, n_fuel])'''
            comb_ans = combustion_products_mixture(atomss, zs_fuel, reactivities=reactivities, CASs=CASs)
            O2_burnt_n_fuel = O2_coeff = comb_ans['O2_required'] + z_fuel_O2
            O2_air = z_air_O2*n_air
            # Simpler expression for n_fuel than fake O2 excess
            n_fuel = (O2_air - O2_demand_third*O2_excess - O2_demand_third + O2_in_third)/(O2_coeff*O2_excess + O2_coeff - z_fuel_O2)

        elif ratio is not None:
            if ratio_basis == 'mole':
                n_fuel = n_air/ratio - n_third
            elif ratio_basis == 'mass':
                m_air, m_third = n_air*MW_air*1e-3, n_third*MW_third*1e-3
                m_fuel = m_air/ratio - m_third
                n_fuel = m_fuel/(MW_fuel*1e-3)
            elif ratio_basis == 'volume':
                Q_air, Q_third = n_air*Vm_air, n_third*Vm_third
                Q_fuel = Q_air/ratio - Q_third
                n_fuel = Q_fuel/Vm_fuel
        
        
        fuel_burn = fuel_air_spec_solver(zs_fuel=zs_fuel, n_fuel=n_fuel,
                                         Vm_fuel=Vm_fuel, MW_fuel=MW_fuel,
                                         n_out=n_out,
                                         **extra_specs)
        
        O2_in_fuel = fuel_burn['n_fuel']*zs_fuel[O2_index]
        O2_demand_fuel = (n_air2*zs_air2[O2_index] + O2_in_fuel)/(fuel_burn['O2_excess'] + 1)
        

        
        # denominator and numerator are correct now, do not change vars used..
        fuel_burn['O2_excess'] = (O2_in_orig + O2_in_fuel)/(O2_demand_fuel + O2_demand_third) - 1

        fuel_burn['n_air'] = n_air
        n_fuel = fuel_burn['n_fuel']
        fix_ratios(fuel_burn)
        
        # O2 excess should be wrong, same for ratios
        return fuel_burn
    if n_out is not None:
        # missing fuel and air, but know outlet and another spec
        
        # Burn all the third stream at O2 excess=0
        # Call the solver with the first
        # Add the two air inlets and the combustion products
        third_burn = fuel_air_spec_solver(zs_fuel=zs_third, n_fuel=n_third,
                                          Vm_fuel=Vm_third, MW_fuel=MW_third,
                                          **common_specs)
        n_out_remaining = n_out - third_burn['n_out']
        
        fuel_burn = fuel_air_spec_solver(zs_fuel=zs_fuel, n_out=n_out_remaining,
                                             Vm_fuel=Vm_fuel, MW_fuel=MW_fuel,
                                             **common_specs)
        
        ans = {'n_out': n_out}
        ans['n_air'] = n_air = third_burn['n_air'] + fuel_burn['n_air']
        ans['n_fuel'] = n_fuel = fuel_burn['n_fuel']
        ans['ns_out'] = [ni+nj for ni, nj in zip(third_burn['ns_out'], fuel_burn['ns_out'])]
        ans['zs_out'] = normalize(ans['ns_out'])
        ans['frac_out_O2'] = ans['ns_out'][O2_index]/n_out
        ans['frac_out_O2_dry'] = ans['ns_out'][O2_index]/(n_out - ans['ns_out'][H2O_index])
        
        
        # O2 excess definition needs to include O2 from elsewhere!
        O2_in = n_air*zs_air[O2_index] + n_fuel*zs_fuel[O2_index] + n_third*zs_third[O2_index]
        O2_demand = O2_in - ans['ns_out'][O2_index]
        ans['O2_excess'] = O2_in/O2_demand - 1
        fix_ratios(ans)
        
        return ans
        

def combustion_spec_solver(zs_air, zs_fuel, zs_third, CASs, atomss, n_third,
                           n_fuel=None, n_air=None, n_out=None,
                           O2_excess=None, frac_out_O2=None,
                           frac_out_O2_dry=None, ratio=None,
                           Vm_air=None, Vm_fuel=None, Vm_third=None, 
                           MW_air=None, MW_fuel=None, MW_third=None,
                           ratio_basis='mass', reactivities=None):
    TRACE_FRACTION_IN_AIR = 1e-12
    if reactivities is None:
        reactivities = [True for i in zs_air]
    combustibilities = [is_combustible(CASs[i], atomss[i], reactivities[i]) for i in range(len(CASs))]

    zs_air_comb = []
    zs_air_pure = []
    n_air_comb = 0.0
    n_air_pure = 0.0

    air_has_combustibles = False
    for combustible, zi in zip(combustibilities, zs_air):
        if combustible and zi > TRACE_FRACTION_IN_AIR:
            air_has_combustibles = True
            zs_air_comb.append(zi)
            zs_air_pure.append(0.0)
            if n_air is not None:
                n_air_comb += zi*n_air
        else:
            zs_air_pure.append(zi)
            zs_air_comb.append(0.0)
            if n_air is not None:
                n_air_pure += zi*n_air
    
    if air_has_combustibles:
        try:
            zs_air_comb = normalize(zs_air_comb)
        except ZeroDivisionError:
            pass
        zs_air_pure = normalize(zs_air_pure)
        
    if not air_has_combustibles:
        return fuel_air_third_spec_solver(zs_air=zs_air, zs_fuel=zs_fuel, 
                                          zs_third=zs_third, CASs=CASs, 
                                          atomss=atomss, n_third=n_third,
                           n_fuel=n_fuel, n_air=n_air, n_out=n_out,
                           O2_excess=O2_excess, frac_out_O2=frac_out_O2,
                           frac_out_O2_dry=frac_out_O2_dry, ratio=ratio,
                           Vm_air=Vm_air, Vm_fuel=Vm_fuel, Vm_third=Vm_third, 
                           MW_air=MW_air, MW_fuel=MW_fuel, MW_third=MW_third,
                           ratio_basis=ratio_basis, reactivities=reactivities)
    else:
        # Can handle air flow specs easily - burn the air, and then pass in the 
        # burnt air composition. This includes n_air and n_out spec.
        
        # Can handle fuel and air/fuel ratio easily as is equivalent spec to air flow.
        # Can 
        raise ValueError("Composition of air includes combustibles")