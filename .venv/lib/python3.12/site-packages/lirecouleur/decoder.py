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
import re
import logging
from .constant import (SYLLABES_LC, SYLLABES_STD, SYLLABES_ORALES, SYLLABES_ECRITES, syllaphon)
from .parser import lcparser 

class Decoder:
	
	def __init__(self):
		pass
	
	def __text_cleaner(self, text, substitut=' '):
		'''
		Élimine des caractères de la chaîne de caractères à traiter
		'''
		# suppression des \r qui engendrent des décalages de codage sous W*
		ultext = text.replace('\r', '')
		ultext = ultext.lower()  # tout mettre en minuscules
		ultext = re.sub('[\'´’]', '@', ultext)  # remplace les apostrophes par des @
		ultext = re.sub('[^a-zA-Z@àäâéèêëîïôöûùçœ]', substitut, ultext)  # ne garde que les caractères significatifs
		
		return ultext

	
	def __indices(self, value, qlist):
		indices = []
		if isinstance(value, list):
			for v in value:
				idx = -1
				while True:
					try:
						idx = qlist.index(v, idx + 1)
						indices.append(idx)
					except ValueError:
						break
	
		else:
			idx = -1
			while True:
				try:
					idx = qlist.index(value, idx + 1)
					indices.append(idx)
				except ValueError:
					break
		return indices

	
	def __post_process_e(self, pp):
		'''
		Post traitement pour déterminer si le son [q] est ouvert "e" ou fermé "eu"
		'''
		if not isinstance(pp, list) or len(pp) == 1:
			return pp
	
		phonemes = [x[0] for x in pp]
		if not 'x' in phonemes:
			# pas de 'eu' dans le mot
			return pp
	
		# indice du dernier phonème prononcé
		nb_ph = len(phonemes) - 1
		while nb_ph >= 1 and phonemes[nb_ph] == "#":
			nb_ph -= 1
	
		# recherche de tous les indices de phonèmes avec 'x' qui précèdent le dernier phonème prononcé
		i_x = self.__indices('x', phonemes[:nb_ph + 1])
	
		# on ne s'intéresse qu'au dernier phonème (pour les autres, on ne peut rien décider)
		i_ph = i_x[-1]
	
		if i_ph < nb_ph - 2:
			# le phonème n'est pas l'un des 3 derniers du mot : on ne peut rien décider
			return pp
	
		if i_ph == nb_ph:
			# le dernier phonème prononcé dans le mot est le 'eu' donc 'eu' fermé
			pp[i_ph] = ('x^', pp[i_ph][1])
			return pp
	
		# le phonème est l'avant dernier du mot (syllabe fermée)
		consonnes_son_eu_ferme = ['z', 'z_s', 't']
		if phonemes[i_ph + 1] in consonnes_son_eu_ferme and phonemes[nb_ph] == 'q_caduc':
			pp[i_ph] = ('x^', pp[i_ph][1])
	
		return pp

	
	def __post_process_o(self, pp):
		'''
		Post traitement pour déterminer si le son [o] est ouvert ou fermé
		'''
		if not isinstance(pp, list) or len(pp) == 1:
			return pp
		
		phonemes = [x[0] for x in pp]
		if not 'o' in phonemes:
			# pas de 'o' dans le mot
			return pp

		# consonnes qui rendent possible un o ouvert en fin de mot
		consonnes_syllabe_fermee = ['p', 'k', 'b', 'd', 'g', 'f', 'f_ph', 's^', 'l', 'r', 'm', 'n']

		# mots en 'osse' qui se prononcent avec un o ouvert
		#mots_osse = json.loads("""
		#["cabosse", "carabosse", "carrosse", "colosse", "molosse", "cosse", "crosse", "bosse", "brosse", "rhinocéros", "désosse", "fosse", "gosse", "molosse", "écosse", "rosse", "panosse"]
		#""")
	
		# indice du dernier phonème prononcé
		nb_ph = len(phonemes) - 1
		while nb_ph > 0 and phonemes[nb_ph] == "#":
			nb_ph -= 1
	
		# recherche de tous les indices de phonèmes avec 'o'
		i_o = self.__indices('o', phonemes[:nb_ph + 1])
	
		# reconstitution du mot sans les phonèmes muets à la fin
		mot = ''.join([x[1] for x in pp[:nb_ph + 1]])
	
		if mot in lcparser.mots_osse:
			# certains mots en 'osse' on un o ouvert
			i_ph_o = i_o[-1:][0]
			pp[i_ph_o] = ('o_ouvert', pp[i_ph_o][1])
			return pp
	
		for i_ph in i_o:
			if i_ph == nb_ph:
				# syllabe tonique ouverte (rien après ou phonème muet) en fin de mot : o fermé
				return pp
	
			if pp[i_ph][1] != 'ô':
				if i_ph == nb_ph - 2 and phonemes[i_ph + 1] in consonnes_syllabe_fermee and phonemes[i_ph + 2] == 'q_caduc':
					# syllabe tonique fermée (présence de consonne après) en fin de mot : o ouvert
					pp[i_ph] = ('o_ouvert', pp[i_ph][1])
				elif phonemes[i_ph + 1] in ['r', 'z^_g', 'v']:
					# o ouvert lorsqu’il est suivi d’un [r] : or, cor, encore, dort, accord
					# o ouvert lorsqu’il est suivi d’un [z^_g] : loge, éloge, horloge
					# o ouvert lorsqu’il est suivi d’un [v] : ove, innove.
					pp[i_ph] = ('o_ouvert', pp[i_ph][1])
				elif (i_ph < nb_ph - 2) and (phonemes[i_ph + 1] in syllaphon['c']) and (phonemes[i_ph + 2] in syllaphon['c']):
					# un o suivi de 2 consonnes est un o ouvert
					pp[i_ph] = ('o_ouvert', pp[i_ph][1])

		return pp

	def __post_process_w(self, pp):
		'''
		Post traitement la constitution d'allophones des phonèmes avec w
		référence : voir http://andre.thibault.pagesperso-orange.fr/PhonologieSemaine10.pdf (cours du 3 février 2016)
		'''
		if not isinstance(pp, list) or len(pp) == 1:
			return pp
	
		phonemes = [x[0] for x in pp]

		# transformation des [wa] en [w_a]
		i_j = self.__indices('wa', phonemes)
		for i_ph in i_j:
			pp[i_ph] = ('w_a', pp[i_ph][1])

		# recherche de tous les indices de phonèmes avec 'u'
		i_j = self.__indices('u', phonemes[:-1])
		i_j.reverse() # commencer par la fin puisqu'on risque de compacter la chaîne de phonèmes
		for i_ph in i_j:
			# phonème suivant
			phon_suivant = ['a', 'a~', 'e', 'e^', 'e_comp', 'e^_comp', 'o', 'o_comp', 'o~', 'e~', 'x', 'x^', 'i']
			if phonemes[i_ph + 1] in phon_suivant:
				pp[i_ph] = ('w_' + phonemes[i_ph + 1], pp[i_ph][1] + pp[i_ph + 1][1])
				if len(pp[i_ph + 2:]) > 0:
					pp[i_ph + 1:] = pp[i_ph + 2:]  # compactage de la chaîne de phonèmes
				else:
					del pp[-1]
	
		return pp

	def __post_process_yod(self, pp, mode=SYLLABES_ECRITES):
		'''
		Post traitement la constitution d'allophones des phonèmes avec yod
		référence : voir http://andre.thibault.pagesperso-orange.fr/PhonologieSemaine10.pdf (cours du 3 février 2016)
		'''
		if not isinstance(pp, list) or len(pp) == 1:
			return pp
	
		phon_suivant = ['a', 'a~', 'e', 'e^', 'e_comp', 'e^_comp', 'o', 'o_comp', 'o~', 'e~', 'q', 'x', 'x^', 'u']
		if mode == SYLLABES_ECRITES:
			phon_suivant.append('q_caduc')
	
		phonemes = [x[0] for x in pp]
	
		# recherche de tous les indices de phonèmes avec 'i' ou 'j'
		i_j = self.__indices(['i', 'j'], phonemes[:-1])
		i_j.reverse() # commencer par la fin puisqu'on risque de compacter la chaîne de phonèmes
		for i_ph in i_j:
			# phonème suivant
			if phonemes[i_ph + 1] in phon_suivant:
				pp[i_ph] = ('j_' + phonemes[i_ph + 1], pp[i_ph][1] + pp[i_ph + 1][1])
				if len(pp[i_ph + 2:]) > 0:
					pp[i_ph + 1:] = pp[i_ph + 2:]  # compactage de la chaîne de phonèmes
				else:
					del pp[-1]
	
		return pp
	
	def __assemble_syllables(self, phonemes, mode=(SYLLABES_LC, SYLLABES_ECRITES)):
		'''
		Recomposition des phonèmes en une suite de syllabes (utilitaire)
		'''
		nb_phon = len(phonemes)
		if nb_phon < 2:
			return [range(nb_phon)], phonemes
	
		# décodage standard
		nphonemes = []
		if mode[0] == SYLLABES_STD:
			# dupliquer les phonèmes qui comportent des consonnes doubles
			for i in range(nb_phon):
				phon = phonemes[i]
				if isinstance(phon, tuple):
					if (phon[0] in syllaphon['c'] or phon[0] in syllaphon['s']) and (len(phon[1]) > 1):
						if phon[1][-1] == phon[1][-2]:
							# consonne redoublée ou plus
							nphonemes.append((phon[0], phon[1][:-1]))
							nphonemes.append((phon[0], phon[1][-1]))
						else:
							nphonemes.append(phon)
					else:
						nphonemes.append(phon)
				else:
					nphonemes.append(phon)
		else:
			nphonemes = [ph for ph in phonemes]
		nb_phon = len(nphonemes)
	
		logging.info('--------------------' + str(nphonemes) + '--------------------')
		# préparer la liste de syllabes
		sylph = []
		for i in range(nb_phon):
			phon = nphonemes[i]
			if isinstance(phon, tuple):
				if phon[0] in syllaphon['v']:
					sylph.append(('v', [i]))
				elif phon[0].startswith('j_') or phon[0].startswith('w_') or phon[0].startswith('y_'):  # yod+voyelle, 'w'+voyelle, 'y'+voyelle sans diérèse
					sylph.append(('v', [i]))
				elif phon[0] in syllaphon['c']:
					sylph.append(('c', [i]))
				elif phon[0] in syllaphon['s']:
					sylph.append(('s', [i]))
				else:
					# c'est un phonème muet : '#'
					sylph.append(('#', [i]))
	
		# mixer les doubles phonèmes de consonnes qui incluent [l] et [r] ; ex. : bl, tr, cr, chr, pl
		i = 0
		while i < len(sylph) - 1:
			if ((sylph[i][0] == 'c') and (sylph[i + 1][0] == 'c')):
				# deux phonèmes consonnes se suivent
				phon0 = nphonemes[sylph[i][1][0]]
				phon1 = nphonemes[sylph[i + 1][1][0]]
				if ((phon1[0] == 'l') or (phon1[0] == 'r')) and (phon0[0] in ['b', 'k', 'p', 't', 'g', 'd', 'f', 'v']):
					# mixer les deux phonèmes puis raccourcir la chaîne
					sylph[i][1].extend(sylph[i + 1][1])
					for j in range(i + 1, len(sylph) - 1):
						sylph[j] = sylph[j + 1]
					sylph.pop()
			i += 1
		logging.info("mixer doubles phonèmes consonnes (bl, tr, cr, etc.) :" + str(sylph))
	
		# mixer les doubles phonèmes [y] et [i], [u] et [i,e~,o~]
		i = 0
		while i < len(sylph) - 1:
			if ((sylph[i][0] == 'v') and (sylph[i + 1][0] == 'v')):
				# deux phonèmes voyelles se suivent
				phon1 = nphonemes[sylph[i][1][0]][0]
				phon2 = nphonemes[sylph[i + 1][1][0]][0]
				if (phon1 == 'y' and phon2 == 'i') or (phon1 == 'u' and phon2 in ['i', 'e~', 'o~']):
					# mixer les deux phonèmes puis raccourcir la chaîne
					sylph[i][1].extend(sylph[i + 1][1])
					for j in range(i + 1, len(sylph) - 1):
						sylph[j] = sylph[j + 1]
					sylph.pop()
			i += 1
		logging.info("mixer doubles phonèmes voyelles ([y] et [i], [u] et [i,e~,o~]) :" + str(sylph))
	
		# accrocher les lettres muettes aux lettres qui précèdent
		i = 0
		while i < len(sylph) - 1:
			if sylph[i + 1][0] == '#':
				# mixer les deux phonèmes puis raccourcir la chaîne
				sylph[i][1].extend(sylph[i + 1][1])
				for j in range(i + 1, len(sylph) - 1):
					sylph[j] = sylph[j + 1]
				sylph.pop()
			i += 1
	
		# construire les syllabes par association de phonèmes consonnes et voyelles
		sylls = []
		nb_sylph = len(sylph)
		i = j = 0
		while i < nb_sylph:
			# début de syllabe = tout ce qui n'est pas voyelle
			j = i
			while (i < nb_sylph) and (sylph[i][0] != 'v'):
				i += 1
	
			# inclure les voyelles
			if (i < nb_sylph) and (sylph[i][0] == 'v'):
				i += 1
				cur_syl = []
				for k in range(j, i):
					cur_syl.extend(sylph[k][1])
				j = i
	
				# ajouter la syllabe à la liste
				sylls.append(cur_syl)
	
			# la lettre qui suit est une consonne
			if i + 1 < nb_sylph:
				lettre1 = nphonemes[sylph[i][1][-1]][1][-1]
				lettre2 = nphonemes[sylph[i + 1][1][0]][1][0]
				if 'bcdfghjklmnpqrstvwxzç'.find(lettre1) > -1 and 'bcdfghjklmnpqrstvwxzç'.find(lettre2) > -1:
					# inclure cette consonne si elle est suivie d'une autre consonne
					cur_syl.extend(sylph[i][1])
					i += 1
					j = i
	
		# précaution de base : si pas de syllabes reconnues, on concatène simplement les phonèmes
		if len(sylls) == 0:
			return [range(nb_phon)], phonemes
	
		# il ne doit rester à la fin que les lettres muettes ou des consonnes qu'on ajoute à la dernière syllabe
		for k in range(j, nb_sylph):
			sylls[-1].extend(sylph[k][1])
	
		if mode[1] == SYLLABES_ORALES and len(sylls) > 1:
			# syllabes orales : si la dernière syllabe est finalisée par des lettres muettes ou un e caduc,
			# il faut la concaténer avec la syllabe précédente
			k = len(sylls[-1]) - 1
			while k > 0 and nphonemes[sylls[-1][k]][0] in ['#', 'verb_3p']:
				k -= 1
			if nphonemes[sylls[-1][k]][0] .endswith('q_caduc'):
				# concaténer la dernière syllabe à l'avant-dernière
				sylls[-2].extend(sylls[-1])
				del sylls[-1]
	
		# ménage
		del sylph
	
		return sylls, nphonemes

	def extract_syllables(self, text, novice_reader=0, mode=(SYLLABES_LC, SYLLABES_ECRITES)):
		'''
		Décomposition d'un mot en une suite de syllabes
		'''
		# extraction des phonèmes
		pp = self.extract_phonemes(text, novice_reader, mode[1])
		
		ps = []
		for word in pp:
			if isinstance(word, list):
				# assemblage des syllabes : syllabe = liste de phonème
				sylls, nphonemes = self.__assemble_syllables(word, mode)
			
				# recomposition des syllabes avec les lettres à partir des listes de phonèmes
				try:
					lsylls = [''.join([nphonemes[i][1] for i in sylls[j]]) for j in range(len(sylls))]
				except:
					lsylls = [''.join([pp[i][1] for i in range(len(pp))])]
				logging.info('--------------------' + str(lsylls) + '--------------------')
					
				ps.append(lsylls)
				
			else:
				ps.append(word)
				
		return ps

	def extract_phonemes(self, text, novice_reader=0, mode=SYLLABES_ECRITES):
		'''
		Décodage d'un texte sous la forme d'une suite de phonèmes
		'''

		# nettoyage du texte
		ultext = self.__text_cleaner(text)
		
		# extraire les mots
		lwords = ultext.split()
		
		# #
		# Traitement
		# #
		pp = []
		p_text = 0
		for word in lwords:
			# recherche de l'emplacement du mot à traiter dans le texte d'origine
			pp_text = ultext.find(word, p_text)
			
			# ajoute au paragraphe la portion de texte non traitée (ponctuation, espaces...)
			if pp_text > p_text:
				pp.append(text[p_text:pp_text])
			p_text = pp_text
	
			# première extraction d'une suite de phonèmes
			phons = lcparser.parse(word)

			# reconstruction de la liste avec les lettres qui composent les phonèmes
			ii = [ph[1] for ph in phons]
			iii = [(sum(ii[:i]),ii[i]+sum(ii[:i])) for i in range(len(ii))]
			phonemes = [(phons[i][0], text[p_text+iii[i][0]:p_text+iii[i][1]]) for i in range(len(phons))]

			# post-traitements les eu ouverts et les eu fermés
			phonemes = self.__post_process_e(phonemes)
		
			if not novice_reader:
				# post traitement pour associer u + [an, in, en, on, a, é, etc.]
				phonemes = self.__post_process_w(phonemes)
		
				# post traitement pour associer yod + [an, in, en, on, a, é, etc.]
				phonemes = self.__post_process_yod(phonemes, mode)
		
				# post traitement pour différencier les o ouverts et les o fermés
				phonemes = self.__post_process_o(phonemes)
	

			pp.append(phonemes)
			p_text += len(word)
	
		# ajouter le texte qui suit le dernier mot
		if p_text < len(text)-1:
			pp.append(text[p_text:])
	
		return pp

# un seul dédodeur est utilisé dans toute l'application
lcdecoder = Decoder()

if __name__ == "__main__":
	# Liste des mots non correctement traités : agenda, consensus, référendum
	print(lcdecoder.extract_phonemes("éléphant"))
	print(lcdecoder.extract_syllables("227 poivrons et --4 )= champignons épais"))