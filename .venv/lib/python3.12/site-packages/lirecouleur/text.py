#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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
from .constant import (SYLLABES_ECRITES, SYLLABES_ORALES, SYLLABES_LC, SYLLABES_STD)
from .decoder import lcdecoder

def phonemes(w, novice_reader=0, mode=SYLLABES_ECRITES):
    return lcdecoder.extract_phonemes(w, novice_reader, mode)

def syllables(w, novice_reader=0, mode=(SYLLABES_LC, SYLLABES_ECRITES)):
    return lcdecoder.extract_syllables(w, novice_reader, mode)

if __name__ == "__main__":
    # Liste des mots non correctement traités : agenda, consensus, référendum
    print(phonemes('éléphant'))
    print(syllables('éléphant'))