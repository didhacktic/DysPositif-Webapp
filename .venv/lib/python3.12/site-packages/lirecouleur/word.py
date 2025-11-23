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
    pp = lcdecoder.extract_phonemes(w, novice_reader, mode)
    return pp[-1]

def syllables(w, novice_reader=0, mode=(SYLLABES_LC, SYLLABES_ECRITES)):
    pp = lcdecoder.extract_syllables(w, novice_reader, mode)
    return pp[-1]