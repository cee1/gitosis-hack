"""
	A gitolite style config Parser&writer
"""

import re
from cStringIO import StringIO

class GitoliteConfigException(Exception):
	pass

def _line_to_words(line):
	line = line.strip()

	if not ("'" in line or '"' in line):
		return line.split()

	words = []

	open_quot = None
	escape_on = False # escape take effect only when a quote opened!
	word_closed = False
	word = ''

	for x in line:
		if word_closed:
			if x.isspace():
				words.append(word)
				word = ''

				word_closed = False
			else:
				raise GitoliteConfigException, \
				      "Word is closed, but extra chars follow in '%s'" % line
		elif escape_on:
			if x in '\'"\\':
				word += x
			else:
				word += '\\' # Not consumed
				word += x

			escape_on = False
		elif open_quot:
			if x == open_quot:
				open_quot = None
				word_closed = True
			elif x == '\\':
				escape_on = True
			else:
				word += x
		else:
			if x.isspace():
				if word:
					words.append(word)
					word = ''
			else:
				if x in '\'"' and not word:
					# Only open quote at the beginning of a word!
					open_quot = x
				else:
					word += x

	if open_quot:
		raise GitoliteConfigException, \
		      "Open quotation mark not closed! In '%s'." % line

	if escape_on:
		raise GitoliteConfigException, \
		      "Tailing '\\' is not allowed! In '%s'." % line

	if word:
		words.append(word)
		word = ''

	return words

def _words_to_line(words):
	line = ''
	_words = []
	space_pattern = re.compile('\s')

	for word in words:
		if space_pattern.search(word):
			tmp = word.split(r'\\')
			for i in xrange(len(tmp)):
				seg = tmp[i]
				seg = seg.replace(r"\'", r"\\'")
				seg = seg.replace(r'\"', r'\\"')
				seg = seg.replace("'", r"\'")
				tmp[i] = seg
			word = r'\\\\'.join(tmp)
			assert not word.endswith('\\')

			word = "'%s'" % word
		_words.append(word)
	return ' '.join(_words)

def _write_section(cfg, name, section):
	print >>cfg, "%s" % name

	for k in section:
		v = section[k]
		if type(v) == list:
			v = _words_to_line(v)

		print >>cfg, "\t%s\t = %s" % (k, v)

class GitoliteConfig(object):
	def __init__(self):
		self.__global = {
			"gitosis" : {
				'loglevel' 	: 'INFO',
				'decodeID' 	: 'no'
			},
		}
		self.__groups = {}
		self.__repos = {}

	def load(self, lines):
		section_open_pattern = re.compile("(gitosis|repo)(\s|$)")

		line_cnt = 0
		section_open = None
		for line in lines:
			line = line.strip()
			line_cnt += 1

			if not line or line.startswith('#'):
				continue
			elif line.startswith('@'):
				try:
					grpname, members = line.split('=', 1)
					grpname, members = map(str.strip, (grpname, members))
				except ValueError:
					raise GitoliteConfigException, \
					      "[Syntax Error][%d] '@' keywork should follows " \
					      "group_name = member1 member2 ..., but got '%s'" \
					      % (line_cnt, line)
				
				self.__groups[grpname] = members
			elif section_open_pattern.match(line):
				if section_open:
					_type, name, section = section_open
					_type[name] = section
					section_open = None
				
				if line.startswith('gitosis'):
					_type = self.__global
					name = 'gitosis'
				elif line.startswith('repo'):
					_type = self.__repos
					try:
						name = line.split(None, 1)[1]
						name = name.strip()
					except IndexError:
						raise GitoliteConfigException, \
						      "[Syntax Error][%d] 'repo' keyword requires a name" \
						      " in '%s' " \
						      % (line_cnt, line)
				else:
					assert 0, "Internal Error!"

				section_open = (_type, name, {})
			elif section_open:
				try:
					key, val = line.split('=', 1)
					key, val = map(str.strip, (key, val))
				except ValueError:
					raise GitoliteConfigException, \
					      "[Syntax Error][%d] expect form like 'key = value', " \
					      "but got '%s'" % (line_cnt, line)

				section_open[2][key] = val
			else:
				raise GitoliteConfigException, \
				      "[Syntax Error][%d] invalid syntax in '%s'" \
				      % (line_cnt, line)

		if section_open:
			_type, name, section = section_open
			_type[name] = section
			section_open = None

	def serialize(self):
		cfg = StringIO()

		for name in self.__global:
			section = self.__global[name]
			_write_section(cfg, name, section)
		print >>cfg

		for name in self.__groups:
			members = self.__groups[name]
			if type(members) == list:
				members = _words_to_line(members)
			print >>cfg, "%s\t = %s" % (name, members)
		print >>cfg

		for name in self.__repos:
			section = self.__repos[name]
			_write_section(cfg, 'repo %s' % name, section)

		return cfg

	def get_gitosis(self, option):
		section = self.__global['gitosis']
		return section.get(option, None)

	def set_group_members(self, grpname, members):
		assert type(members) == list
		assert grpname.startswith('@')
		self.__groups[grpname] = members

	def set_repo(self, reponame, option, val):
		if option in ('RW+', 'R'):
			assert type(val) == list

		section = self.__repos.get(reponame, {})
		section[option] = val

		self.__repos[reponame] = section

	def get_group_members(self, grpname):
		try:
			members = self.__groups[grpname]
		except KeyError:
			return

		if type(members) != list:
			members = _line_to_words(members)
			self.__groups[grpname] = members

		return members

	def get_repo(self, reponame, option):
		try:
			section = self.__repos[reponame]
		except KeyError:
			return

		try:
			val = section[option]
		except KeyError:
			return

		if option in ('RW+', 'R'):
			if type(val) != list:
				val = _line_to_words(val)
				section[option] = val

		return val

	def lookup_repo(self, path):
		if self.__repos.has_key(path):
			return path

		try:
			repo_patterns = self.__repo_patterns
		except AttributeError:
			repo_patterns = {}
			for repo in self.__repos:
				path_regex = self.__repos[repo].get('path_regex', None)
				if path_regex:
					try:
						r = re.compile(path_regex)
						repo_patterns[r] = repo
					except re.error:
						raise GitoliteConfigException, \
						      "Bad regex \'%s\' for repo \'%s\'" \
						      % (path_regex, repo)
			self.__repo_patterns = repo_patterns

		for p in repo_patterns:
			if p.match(path):
				return repo_patterns[p]

	def groups(self):
		return [grp for grp in self.__groups]

	def repos(self):
		return [repo for repo in self.__repos]
