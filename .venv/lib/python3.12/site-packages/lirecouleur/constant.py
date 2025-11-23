#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from __future__ import unicode_literals

###################################################################################
# LireCouleur - tools to help with reading French
#
# http://lirecouleur.arkaline.fr
#
# @author Marie-Pierre Brungard
# @version 0.0.4
#
# GNU General Public Licence (GPL) version 3
# https://www.gnu.org/licenses/gpl-3.0.en.html
###################################################################################
import json

'''
Constantes LireCouleur
'''

# différentes configurations de marquage des syllabes
SYLLABES_LC = 0
SYLLABES_STD = 1
SYLLABES_ORALES = 1
SYLLABES_ECRITES = 0

# prononciation différente entre l'Europe et le Canada
MESTESSESLESDESCES = {'':'e_comp', 'fr':'e_comp', 'fr_CA':'e^_comp'}        

# Les phonèmes sont codés en voyelles (v), consonnes (c) et semi-voyelles (s)
syllaphon = json.loads("""
{
"v":["a","q","q_caduc","i","o","o_comp","o_ouvert","u","y","e","e_comp","e^","e^_comp","a~","e~","x~","o~","x","x^","wa","w5"],
"c":["p","t","k","b","d","g","f","f_ph","s","s^","v","z","z^","l","r","m","n","k_qu","z^_g","g_u","s_c","s_t","z_s","ks","gz"],
"s":["j","g~","n~","w"],"#":["#","verb_3p"]
}
""")
