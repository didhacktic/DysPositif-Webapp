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
import re
import codecs
import logging
import os
import inspect

class Parser:
    _autom = None
    _adb = None
    _dico = None
    
    def __init__(self):
        '''
        load the automate and some other stuff for decoding words
        '''
        __CURRENT_FILENAME = inspect.getframeinfo(inspect.currentframe()).filename
        __CURRENT_PATH = os.path.dirname(os.path.abspath(__CURRENT_FILENAME))
        
        if self._autom is None:
            f = codecs.open(__CURRENT_PATH+"/appdata/automaton.json", "r", "utf_8_sig", errors="replace")
            self._autom = json.load(f)
            f.close()

        # load exception database and other tools
        
        ###################################################################################
        # verbes_ier : ensemble de verbes qui se terminent par -ier // attention : pas d'accents !!
        # verbes_mer : ensemble de verbes qui se terminent par -mer
        # mots_ent : ensemble de mots qui se terminent par -ent
        # exceptions_final_er : exceptions dans lesquelles -ier se prononce [ièR]
        # possibles_nc_ai_final : le ai final se prononce è et non pas é
        # possibles_avoir : conjugaison du verbe avoir : eu = [u]
        # mots_s_final : ensemble de mots pour lesquels le s final est prononcé
        # mots_t_final : ensemble de mots pour lesquels le t final est prononcé
        # exceptions_final_tien : ensemble de mots pour lesquels le ien final se prononce [in]
        # mots en 'osse' qui se prononcent avec un o ouvert
        ###################################################################################
        if self._adb is None:
            f = codecs.open(__CURRENT_PATH+"/appdata/database.json", "r", "utf_8_sig", errors="replace")
            self._adb = json.load(f)
            f.close()

        if self._dico is None:
            f = codecs.open(__CURRENT_PATH+"/appdata/dictionary.json", "r", "utf_8_sig", errors="replace")
            self._dico = json.load(f)
            f.close()
            
    def get_mots_osse(self):
        '''
        utilisé dans le post traitement des phonèmes pour identifier les o ouverts/fermés
        '''
        return self._adb["mots_osse"]
    mots_osse = property(get_mots_osse)

    def no_accent(self, texte):
        '''
        Élimine les caractères accentués et les remplace par des non accentués
        '''
        ultexte = texte.lower()  # tout mettre en minuscules
        ultexte = re.sub('[àäâ]', 'a', ultexte)
        ultexte = re.sub('[éèêë]', 'e', ultexte)
        ultexte = re.sub('[îï]', 'i', ultexte)
        ultexte = re.sub('[ôö]', 'o', ultexte)
        ultexte = re.sub('[ûù]', 'u', ultexte)
        ultexte = re.sub('ç', 'c', ultexte)
        ultexte = re.sub('œ', 'e', ultexte)
    
        return ultexte

    def regle_ient(self, mot, pos_mot):
        '''
        Règle spécifique de traitement des successions de lettres finales 'ient'
        sert à savoir si la séquence 'ient' se prononce [i][#] ou [j][e~]
        '''
        m = re.match('[bcçdfghjklnmpqrstvwxz]ient', mot[-5:])
        if m == None or (pos_mot < len(mot[:-4])):
            # le mot ne se termine pas par 'ient' (précédé d'une consonne)
            # ou alors on est en train d'étudier une lettre avant la terminaison en 'ient'
            return False
    
        # il faut savoir si le mot est un verbe dont l'infinitif se termine par 'ier' ou non
        pseudo_infinitif = mot[:-2] + 'r'
        if pseudo_infinitif in self._adb['verbes_ier']:
            logging.info("func regle_ient : " + mot + " (" + pseudo_infinitif + ")")
            return True
        pseudo_infinitif = self.no_accent(pseudo_infinitif)
        if len(pseudo_infinitif) > 1 and pseudo_infinitif[1] == '@':
            # mot précédé d'un déterminant élidé - codage de l'apostrophe : voir pretraitement_texte
            pseudo_infinitif = pseudo_infinitif[2:]
        if pseudo_infinitif in self._adb['verbes_ier']:
            logging.info("func regle_ient : " + mot + " (" + pseudo_infinitif + ")")
            return True
        return False
    
    
    def regle_mots_ent(self, mot, pos_mot):
        '''
        Règle spécifique de traitement des successions de lettres '*ent'
        sert à savoir si le mot figure dans les mots qui se prononcent a~ à la fin
        '''
        m = re.match('^[bcdfghjklmnpqrstvwxz]ent(s?)$', mot)
        if m != None:
            logging.info("func regle_mots_ent : " + mot + " -- mot commencant par une consonne et terminé par 'ent'")
            return True
    
        # il faut savoir si le mot figure dans la liste des adverbes ou des noms répertoriés
        comparateur = mot
        if mot[-1] == 's':
            comparateur = mot[:-1]
        if pos_mot + 2 < len(comparateur):
            return False
    
        if len(comparateur) > 1 and comparateur[1] == '@':
            # mot précédé d'un déterminant élidé - codage de l'apostrophe : voir pretraitement_texte
            comparateur = comparateur[2:]
    
        # comparaison directe avec la liste de mots où le 'ent' final se prononce [a~]
        if comparateur in self._adb['mots_ent']:
            logging.info("func regle_mots_ent : " + mot + " -- mot répertorié")
            return True
    
        # comparaison avec la liste de verbes qui se terminent par 'enter'
        pseudo_verbe = comparateur + 'er'
        if pseudo_verbe in self._adb['verbes_enter']:
            logging.info("func regle_mots_ent : " + mot + " -- verbe 'enter'")
            return True
    
        return False
    
    
    def regle_ment(self, mot, pos_mot):
        '''
        Règle spécifique de traitement des successions de lettres 'ment'
        sert à savoir si le mot figure dans les mots qui se prononcent a~ à la fin
        '''
        m = re.match('ment', mot[-4:])
        if m == None or (pos_mot < len(mot[:-3])):
            # le mot ne se termine pas par 'ment'
            # ou alors on est en train d'étudier une lettre avant la terminaison en 'ment'
            return False
    
        # il faut savoir si le mot figure dans la liste des verbes terminés par -mer
        pseudo_infinitif = self.no_accent(mot[:-2] + 'r')
        if len(pseudo_infinitif) > 1 and pseudo_infinitif[1] == '@':
            # mot précédé d'un déterminant élidé - codage de l'apostrophe : voir pretraitement_texte
            pseudo_infinitif = pseudo_infinitif[2:]
        if pseudo_infinitif in self._adb['verbes_mer']:
            return False
    
        # dernier test : le verbe dormir (ils/elles dorment)
        if len(mot) > 6:
            if re.match('dorment', mot[-7:]) != None:
                return False
        logging.info("func regle_ment : " + mot + " (" + pseudo_infinitif + ")")
        return True
    
    
    def regle_verbe_mer(self, mot, pos_mot):
        '''
        L'inverse de la règle "regle_ment" ou presque
        '''
        m = re.match('ment', mot[-4:])
        if m == None or (pos_mot < len(mot[:-3])):
            # le mot ne se termine pas par 'ment'
            # ou alors on est en train d'étudier une lettre avant la terminaison en 'ment'
            return False
    
        return not self.regle_ment(mot, pos_mot)
    
    
    def regle_er(self, mot, pos_mot):
        '''
        Règle spécifique de traitement des successions de lettres finales 'er'
        sert à savoir si le mot figure dans la liste des exceptions
        '''
        # prendre le mot au singulier uniquement
        m_sing = mot
        if mot[-1] == 's':
            m_sing = mot[:-1]
    
        if len(m_sing) > 1 and m_sing[1] == '@':
            # mot précédé d'un déterminant élidé - codage de l'apostrophe : voir pretraitement_texte
            m_sing = m_sing[2:]
    
        # tester la terminaison
        m = re.match('er', m_sing[-2:])
        if m == None or (pos_mot < len(m_sing[:-2])):
            # le mot ne se termine pas par 'er'
            # ou alors on est en train d'étudier une lettre avant la terminaison en 'er'
            return False
    
        # il faut savoir si le mot figure dans la liste des exceptions
        if m_sing in self._adb['exceptions_final_er']:
            logging.info("func regle_er : " + mot + " -- le mot n'est pas une exception comme 'amer' ou 'cher'")
            return True
        return False
    
    
    def regle_nc_ai_final(self, mot, pos_mot):
        '''
        Règle spécifique de traitement des noms communs qui se terminent par 'ai'
        - dans les verbes terminés par 'ai', le phonème est 'é'
        - dans les noms communs terminés par 'ai', le phonème est 'ê'
        '''
        m_seul = mot
        if len(m_seul) > 1 and m_seul[1] == '@':
            # mot précédé d'un déterminant élidé - codage de l'apostrophe : voir pretraitement_texte
            m_seul = m_seul[2:]
    
        if m_seul in self._adb['possibles_nc_ai_final']:
            res = (pos_mot == len(mot) - 1)
            logging.info("func regle_nc_ai_final : " + mot + " -- " + str(res))
            return res
        return False
    
    
    def regle_avoir(self, mot, pos_mot):
        '''
        Règle spécifique de traitement des successions de lettres 'eu('
        sert à savoir si le mot est le verbe avoir conjugué (passé simple, participe
        passé ou subjonctif imparfait
        '''
        if mot in self._adb['possibles_avoir']:
            res = (pos_mot < 2)
            logging.info("func regle_avoir : " + mot + " -- " + str(res))
            return res
        return False
    
    
    def regle_s_final(self, mot, __pos_mot):
        '''
        Règle spécifique de traitement des mots qui se terminent par "us".
        pour un certain nombre de ces mots, le 's' final se prononce.
        '''
        m_seul = mot
        if len(m_seul) > 1 and m_seul[1] == '@':
            # mot précédé d'un déterminant élidé - codage de l'apostrophe : voir pretraitement_texte
            m_seul = m_seul[2:]
    
        if m_seul in self._adb['mots_s_final']:
            logging.info("func regle_s_final : " + m_seul + " -- mot avec un 's' final qui se prononce")
            return True
        return False
    
    
    def regle_t_final(self, mot, __pos_mot):
        '''
        Règle spécifique de traitement des mots qui se terminent par la lettre "t" prononcée.
        '''
        # prendre le mot au singulier uniquement
        m_sing = mot
        if mot[-1] == 's':
            m_sing = mot[:-1]
    
        if len(m_sing) > 1 and m_sing[1] == '@':
            # mot précédé d'un déterminant élidé - codage de l'apostrophe : voir pretraitement_texte
            m_sing = m_sing[2:]
    
        if m_sing in self._adb['mots_t_final']:
            logging.info("func regle_t_final : " + mot + " -- mot avec un 't' final qui se prononce")
            return True
        return False
    
    
    def regle_tien(self, mot, pos_mot):
        '''
        Règle spécifique de traitement de quelques mots qui se terminent par 'tien' et
        dans lesquels le 't' se prononce [t]
        '''
        # prendre le mot au singulier uniquement
        m_sing = mot
        if m_sing[-1] == 's':
            m_sing = mot[:-1]
    
        # tester la terminaison
        m = re.match('tien', m_sing[-4:])
        if m == None or (pos_mot < len(m_sing[:-4])):
            # le mot ne se termine pas par 'tien'
            # ou alors on est en train d'étudier une lettre avant la terminaison en 'tien'
            return False
    
        # il faut savoir si le mot figure dans la liste des exceptions
        if m_sing in self._adb['exceptions_final_tien']:
            logging.info("func regle_tien : " + mot + " -- mot où le 't' de 'tien' se prononce 't'")
            return True
        return False

    def check(self, nom_regle, cle, mot, pos_mot):
        '''
        Teste l'application d'une règle
        '''
    
        logging.debug ('mot : ' + mot + '[' + str(pos_mot - 1) + '] lettre : ' + mot[pos_mot - 1] + ' regle : ' + nom_regle)
        if not isinstance(cle, dict):
            # la regle est une fonction spécifique
            # logging.debug(nom_regle, ' fonction');
            return getattr(self, cle)(mot, pos_mot)
    
        # exemples : '+':'n|m' ou '-':'[aeiou]'
        trouve_s = True
        trouve_p = True
    
        if '+' in cle.keys():
            logging.debug(nom_regle + ' cle + testee : ' + cle['+'])
            logging.debug (mot, pos_mot)
            # il faut lire les lettres qui suivent
            # recherche le modèle demandé au début de la suite du mot
            pattern = re.compile(cle['+'])
            res = pattern.match(mot, pos_mot)
            trouve_s = ((res != None) and (res.start() == pos_mot))
        
        if '-' in cle.keys():
            logging.debug(nom_regle + ' cle - testee : ' + cle['-']);
            trouve_p = False
            pattern = re.compile(cle['-'])
            # teste si la condition inclut le début du mot ou seulement les lettres qui précèdent
            if (cle['-'][0] == '^'):
                # le ^ signifie 'début de chaîne' et non 'tout sauf'
                if (len(cle['-']) == 1):
                    # on vérifie que le début de mot est vide
                    trouve_p = (pos_mot == 1)
                else:
                    # le début du mot doit correspondre au pattern
                    res = pattern.match(mot, 0, pos_mot)
                    if (res != None):
                        trouve_p = (res.end() - res.start() + 1 == pos_mot)
            else :
                k = pos_mot - 2
                while ((k > -1) and (not trouve_p)):
                    logging.debug (mot, k, pos_mot)
                    # il faut lire les lettres qui précèdent
                    # recherche le modèle demandé à la fin du début du mot
                    res = pattern.match(mot, k, pos_mot)
                    if (res != None):
                        # print (res.end(), res.start())
                        trouve_p = (res.end() - res.start() + 1 == pos_mot - k)
                    k -= 1
    
        return (trouve_p and trouve_s)

    def one_step(self, word, pos=0):
        '''
        Fait avancer le décodage d'un pas - 1 pas = 1 phonème ou 1 caractère non décodable
        '''
        letter = word[pos]
        logging.debug ('lettre : ' + letter)

        phoneme = ''
        step = 1
        if not letter in self._autom:
            logging.info('non phoneme ; caractere lu:' + letter)
            return (phoneme, step)
        aut = self._autom[letter][1]
        
        # recherche si une règle est applicable dans la liste des règles associées à la lettre
        lrules = self._autom[letter][0]
        logging.debug ('liste des règles : ' + str(lrules))
        for k in lrules:
            if self.check(k, aut[k][0], word, pos + 1):
                phoneme = aut[k][1]
                step = aut[k][2]
                logging.debug ('trouve:', phoneme, step)
                return (phoneme, step)
        
        if pos == len(word) - 1:
            # c'est la dernière lettre du mot, il faut vérifier que ce n'est pas une lettre muette
            if '@' in aut:
                phoneme = aut['@'][1]
                step = 1
                logging.info('phoneme fin de mot:' + phoneme + ' ; lettre lue:' + letter)
                return (phoneme, step)

        # rien trouvé donc on prend le phonème de base ('*')
        try:
            phoneme = aut['*'][1]
            step = aut['*'][2]
            logging.info('phoneme par defaut:' + phoneme + ' ; lettre lue:' + letter)
        except:
            logging.info('non phoneme ; caractere lu:' + letter)

        return (phoneme, step)
    
    def parse(self, word):
        '''
        Décodage d'un mot sous la forme d'une suite de phonèmes
        '''
        
        pos = 0
        lword = len(word)
        code = []

        # cas particulier : le mot ou au moins son début est inclus dans le dictionnaire
        for w in self._dico:
            if word.startswith(w):
                # récupération de la segmentation en phonème du (début du) mot
                code = [(l[0], l[1]) for l in self._dico[w]['phon']]
                # calcul de la position à partir de laquelle prendre le décodage
                pos = len(w)
                break
        
        # cas général : décodage des phonèmes du mot
        while pos < lword:
            phon, step = self.one_step(word, pos)
            code.append((phon, step))
            pos += step

        return code

# un seul parser est utilisé dans toute l'application
lcparser = Parser()

if __name__ == "__main__":
    # Liste des mots non correctement traités :
    # agenda, consensus, référendum
    print(lcparser.parse(u"éléphant"))