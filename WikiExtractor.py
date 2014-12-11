#!/usr/bin/python
# -*- coding: utf-8 -*-


import sys
import gzip
import gc
import getopt
import urllib
import requests
import re
import bz2
import os.path
from htmlentitydefs import name2codepoint
import json
from urlparse import urlparse

### PARAMS ####################################################################

# This is obtained from the dump itself
prefix = None

##
# Whether to preseve links in output
#
keepLinks = False

##
# Whether to transform sections into HTML
#
keepSections = False

##
# Recognize only these namespaces
# w: Internal links to the Wikipedia
# wiktionary: Wiki dictionry
# wikt: shortcut for Wikctionry
#
acceptedNamespaces = set(['w', 'wiktionary', 'wikt'])

##
# Drop these elements from article text
#
discardElements = set([
		'gallery', 'timeline', 'noinclude', 'pre',
		'table', 'tr', 'td', 'th', 'caption',
		'form', 'input', 'select', 'option', 'textarea',
		'ul', 'li', 'ol', 'dl', 'dt', 'dd', 'menu', 'dir',
		'ref', 'references', 'img', 'imagemap', 'source'
		])

#=========================================================================
#
# MediaWiki Markup Grammar

# Template = "{{" [ "msg:" | "msgnw:" ] PageName { "|" [ ParameterName "=" AnyText | AnyText ] } "}}" ;
# Extension = "<" ? extension ? ">" AnyText "</" ? extension ? ">" ;
# NoWiki = "<nowiki />" | "<nowiki>" ( InlineText | BlockText ) "</nowiki>" ;
# Parameter = "{{{" ParameterName { Parameter } [ "|" { AnyText | Parameter } ] "}}}" ;
# Comment = "<!--" InlineText "-->" | "<!--" BlockText "//-->" ;
#
# ParameterName = ? uppercase, lowercase, numbers, no spaces, some special chars ? ;
#
#===========================================================================

# Program version
version = '2.5'

##### Main function ###########################################################

def WikiDocument(out, id, title, text,config):
	#print text
	#print "hello"
	url = get_url(id, prefix)
	#header = '<doc id="%s" url="%s" title="%s">\n' % (id, url, title)
	# Separate header from text with a newline.
	#header += title + '\n'
	#header = header.encode('utf-8')
	text,categories = dropNested(text, r'\[\[Category\:', r'\]\]')
	text,matches = dropNested(text, r'{{', r'}}')
	obj=processmatches(matches)
	obj["category"]=categories
	obj["ref"]=id
	obj["url"]=url
	obj["title"]=title
	#print obj
	text = clean(text)
	obj["content"]=text
	#print config
	if config:
		newobj={}
		for rule in config.get('rules',[]):
			if rule["source"] in obj:
				try:
					ruleout=re.sub(rule["pattern"],rule["output"],obj[rule["source"]])
					obj[rule["destination"]]=ruleout
				except:
					print "there was a problem applying your rule"
		obj.update(newobj)
	#footer = "\n</doc>"
	#print obj
	jsonstr=json.dumps(obj)
	out.reserve(len(jsonstr))
	#out.reserve(len(header) + len(text) + len(footer))
	print >> out, json.dumps(obj)
	#print >> out, header
	#for line in compact(text):
	#	print >> out, line.encode('utf-8')
	#print >> out, footer

def get_url(id, prefix):
	return "%s?curid=%s" % (prefix, id)

#------------------------------------------------------------------------------

selfClosingTags = [ 'br', 'hr', 'nobr', 'ref', 'references' ]

# handle 'a' separetely, depending on keepLinks
ignoredTags = [
		'b', 'big', 'blockquote', 'center', 'cite', 'div', 'em',
		'font', 'h1', 'h2', 'h3', 'h4', 'hiero', 'i', 'kbd', 'nowiki',
		'p', 'plaintext', 's', 'small', 'span', 'strike', 'strong',
		'sub', 'sup', 'tt', 'u', 'var',
]

placeholder_tags = {'math':'formula', 'code':'codice'}

##
# Normalize title
def normalizeTitle(title):
  # remove leading whitespace and underscores
  title = title.strip(' _')
  # replace sequences of whitespace and underscore chars with a single space
  title = re.compile(r'[\s_]+').sub(' ', title)

  m = re.compile(r'([^:]*):(\s*)(\S(?:.*))').match(title)
  if m:
		prefix = m.group(1)
		if m.group(2):
			optionalWhitespace = ' '
		else:
			optionalWhitespace = ''
		rest = m.group(3)

		ns = prefix.capitalize()
		if ns in acceptedNamespaces:
		# If the prefix designates a known namespace, then it might be
		# followed by optional whitespace that should be removed to get
		# the canonical page name
		# (e.g., "Category:  Births" should become "Category:Births").
			title = ns + ":" + rest.capitalize()
		else:
		# No namespace, just capitalize first letter.
	 # If the part before the colon is not a known namespace, then we must
		# not remove the space after the colon (if any), e.g.,
		# "3001: The_Final_Odyssey" != "3001:The_Final_Odyssey".
		# However, to get the canonical page name we must contract multiple
		# spaces into one, because
		# "3001:	The_Final_Odyssey" != "3001: The_Final_Odyssey".
			title = prefix.capitalize() + ":" + optionalWhitespace + rest
  else:
		# no namespace, just capitalize first letter
		title = title.capitalize();
  return title

##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text):
	def fixup(m):
		text = m.group(0)
		code = m.group(1)
		try:
			if text[1] == "#":  # character reference
				if text[2] == "x":
					return unichr(int(code[1:], 16))
				else:
					return unichr(int(code))
			else:				# named entity
				return unichr(name2codepoint[code])
		except:
			return text # leave as is

	return re.sub("&#?(\w+);", fixup, text)

# Match HTML comments
comment = re.compile(r'<!--.*?-->', re.DOTALL)

# Match elements to ignore
discard_element_patterns = []
for tag in discardElements:
	pattern = re.compile(r'<\s*%s\b[^>]*>.*?<\s*/\s*%s>' % (tag, tag), re.DOTALL | re.IGNORECASE)
	discard_element_patterns.append(pattern)

# Match ignored tags
ignored_tag_patterns = []
def ignoreTag(tag):
	left = re.compile(r'<\s*%s\b[^>]*>' % tag, re.IGNORECASE)
	right = re.compile(r'<\s*/\s*%s>' % tag, re.IGNORECASE)
	ignored_tag_patterns.append((left, right))

for tag in ignoredTags:
	ignoreTag(tag)

# Match selfClosing HTML tags
selfClosing_tag_patterns = []
for tag in selfClosingTags:
	pattern = re.compile(r'<\s*%s\b[^/]*/\s*>' % tag, re.DOTALL | re.IGNORECASE)
	selfClosing_tag_patterns.append(pattern)

# Match HTML placeholder tags
placeholder_tag_patterns = []
for tag, repl in placeholder_tags.items():
	pattern = re.compile(r'<\s*%s(\s*| [^>]+?)>.*?<\s*/\s*%s\s*>' % (tag, tag), re.DOTALL | re.IGNORECASE)
	placeholder_tag_patterns.append((pattern, repl))

# Match preformatted lines
preformatted = re.compile(r'^ .*?$', re.MULTILINE)

# Match external links (space separates second optional parameter)
externalLink = re.compile(r'\[\w+.*? (.*?)\]')
externalLinkNoAnchor = re.compile(r'\[\w+[&\]]*\]')

# Matches bold/italic
bold_italic = re.compile(r"'''''([^']*?)'''''")
bold = re.compile(r"'''(.*?)'''")
italic_quote = re.compile(r"''\"(.*?)\"''")
italic = re.compile(r"''([^']*)''")
quote_quote = re.compile(r'""(.*?)""')

# Matches space
spaces = re.compile(r' {2,}')

# Matches dots
dots = re.compile(r'\.{4,}')


def dropNested(text, openDelim, closeDelim):
	openRE = re.compile(openDelim)
	closeRE = re.compile(closeDelim)
	# partition text in separate blocks { } { }

	matches = []				# pairs (s, e) for each partition
	nest = 0					# nesting level
	start = openRE.search(text, 0)
	if not start:

		return text,[]

	end = closeRE.search(text, start.end())

	next = start
	while end:
		next = openRE.search(text, next.end())

		if not next:			# termination
			while nest:		# close all pending
				nest -=1
				end0 = closeRE.search(text, end.end())
				if end0:
					end = end0
				else:
					break
			matches.append((start.start(), end.end()))
			break
		while end.end() < next.start():
			# { } {
			if nest:
				nest -= 1
				# try closing more
				last = end.end()
				end = closeRE.search(text, end.end())
				if not end:	 # unbalanced
					if matches:
						span = (matches[0][0], last)
					else:
						span = (start.start(), last)
					matches = [span]
					break
			else:
				matches.append((start.start(), end.end()))
				# advance start, find next close
				start = next
				end = closeRE.search(text, next.end())
				break			# { }
		if next != start:
			# { { }
			nest += 1
	# collect text outside partitions
	res = ''
	start = 0
	returnmatches=[]

	openlength=len(openDelim.replace("\\",""))
	closelength=len(closeDelim.replace("\\",""))
	for s, e in  matches:
		returnmatches.append(text[s+openlength:e-closelength])
		res += text[start:s]
		start = e
	res += text[start:]
	return res,returnmatches

def cleanvals(val):
	#print val
	val=map(lambda x: re.sub(r'\[\[(.*?)\]\]',r'\1',x),val)
	val=map(lambda x: re.sub(r'\[(.*?)\]',r'\1',x),val)
	val=[ " ".join(x.split("&&")[1:]).strip() if "&&" in x else x.strip() for x in val]
	val=filter(lambda x: x,val)
	return val


def processmatches(matches):
	detailobj={}
	tags=[]
	for match in matches:

		#print re.sub(match,'[[(.*)|(.*?)?]]','[[$1&&$2]]')
		match=re.sub(r'\[\[(.*?)\|([^\[]*?)\]\]',r'[[\1&&\2]]',match)
		match,drop= dropNested(match,r'{{', r'}}')
		match,drop= dropNested(match,r'&lt;', r'&gt;')
		match,drop= dropNested(match,r'\'\'\[\[',r'\]\]\'\'')
		#print match
		splits=match.split("|")
		tag=splits[0]
		tag=tag.replace('\n','')
		tag=tag.strip()
		#tags.append(tag)
		if len(splits)>1:
			attrs=splits[1:]
			if len(attrs)== len(filter(lambda x: "=" in x,attrs)):
				tags.append(tag)
				for attr in attrs:
					key,val=attr.split('=',1)
					val=val.replace('\n','')
					key=key.replace("\n","")
					key=key.strip()
					val=val.split("*")
					val=cleanvals(val)
					#print val
					detailobj[tag+"_"+key]=val

			else:
				attrs=filter(lambda x: not "=" in x,attrs)
				attrs=cleanvals(attrs)
				vals=detailobj.get(tag,[])
				vals=vals+attrs

		#match.split("|")
	detailobj["tags"]=tags
	#print detailobj
	return detailobj

# A matching function for nested expressions, e.g. namespaces and tables.
def dropNested2(text, openDelim, closeDelim):
	openRE = re.compile(openDelim)
	closeRE = re.compile(closeDelim)
	# partition text in separate blocks { } { }
	matches = []				# pairs (s, e) for each partition
	nest = 0					# nesting level
	start = openRE.search(text, 0)
	if not start:
		return text
	end = closeRE.search(text, start.end())
	next = start
	while end:
		next = openRE.search(text, next.end())
		if not next:			# termination
			while nest:		# close all pending
				nest -=1
				end0 = closeRE.search(text, end.end())
				if end0:
					end = end0
				else:
					break
			matches.append((start.start(), end.end()))
			break
		while end.end() < next.start():
			# { } {
			if nest:
				nest -= 1
				# try closing more
				last = end.end()
				end = closeRE.search(text, end.end())
				if not end:	 # unbalanced
					if matches:
						span = (matches[0][0], last)
					else:
						span = (start.start(), last)
					matches = [span]
					break
			else:
				matches.append((start.start(), end.end()))
				# advance start, find next close
				start = next
				end = closeRE.search(text, next.end())
				break			# { }
		if next != start:
			# { { }
			nest += 1
	# collect text outside partitions
	res = ''
	start = 0
	for s, e in  matches:
		res += text[start:s]
		start = e
	res += text[start:]
	return res

def dropSpans(matches, text):
	"""Drop from text the blocks identified in matches"""
	matches.sort()
	res = ''
	start = 0
	for s, e in  matches:
		res += text[start:s]
		start = e
	res += text[start:]
	return res

# Match interwiki links, | separates parameters.
# First parameter is displayed, also trailing concatenated text included
# in display, e.g. s for plural).
#
# Can be nested [[File:..|..[[..]]..|..]], [[Category:...]], etc.
# We first expand inner ones, than remove enclosing ones.
#
wikiLink = re.compile(r'\[\[([^[]*?)(?:\|([^[]*?))?\]\](\w*)')

parametrizedLink = re.compile(r'\[\[.*?\]\]')

# Function applied to wikiLinks
def make_anchor_tag(match):
	global keepLinks
	link = match.group(1)
	colon = link.find(':')
	if colon > 0 and link[:colon] not in acceptedNamespaces:
		return ''
	trail = match.group(3)
	anchor = match.group(2)
	if not anchor:
		anchor = link
	anchor += trail
	if keepLinks:
		return '<a href="%s">%s</a>' % (link, anchor)
	else:
		return anchor

def clean(text):

	# FIXME: templates should be expanded
	# Drop transclusions (template, parser functions)
	# See: http://www.mediawiki.org/wiki/Help:Templates
	text = dropNested2(text, r'{{', r'}}')
	# Drop tables
	text = dropNested2(text, r'{\|', r'\|}')

	# Expand links
	text = wikiLink.sub(make_anchor_tag, text)
	# Drop all remaining ones
	text = parametrizedLink.sub('', text)

	# Handle external links
	text = externalLink.sub(r'\1', text)
	text = externalLinkNoAnchor.sub('', text)

	# Handle bold/italic/quote
	text = bold_italic.sub(r'\1', text)
	text = bold.sub(r'\1', text)
	text = italic_quote.sub(r'&quot;\1&quot;', text)
	text = italic.sub(r'&quot;\1&quot;', text)
	text = quote_quote.sub(r'\1', text)
	text = text.replace("'''", '').replace("''", '&quot;')

	################ Process HTML ###############

	# turn into HTML
	text = unescape(text)
	# do it again (&amp;nbsp;)
	text = unescape(text)

	# Collect spans

	matches = []
	# Drop HTML comments
	for m in comment.finditer(text):
			matches.append((m.start(), m.end()))

	# Drop self-closing tags
	for pattern in selfClosing_tag_patterns:
		for m in pattern.finditer(text):
			matches.append((m.start(), m.end()))

	# Drop ignored tags
	for left, right in ignored_tag_patterns:
		for m in left.finditer(text):
			matches.append((m.start(), m.end()))
		for m in right.finditer(text):
			matches.append((m.start(), m.end()))

	# Bulk remove all spans
	text = dropSpans(matches, text)

	# Cannot use dropSpan on these since they may be nested
	# Drop discarded elements
	for pattern in discard_element_patterns:
		text = pattern.sub('', text)

	# Expand placeholders
	for pattern, placeholder in placeholder_tag_patterns:
		index = 1
		for match in pattern.finditer(text):
			text = text.replace(match.group(), '%s_%d' % (placeholder, index))
			index += 1


	text = text.replace('<<', u'Â«').replace('>>', u'Â»')

	#############################################

	# Drop preformatted
	# This can't be done before since it may remove tags
	text = preformatted.sub('', text)

	# Cleanup text
	text = text.replace('\t', ' ')
	text = spaces.sub(' ', text)
	text = dots.sub('...', text)
	text = re.sub(u' (,:\.\)\]Â»)', r'\1', text)
	text = re.sub(u'(\[\(Â«) ', r'\1', text)
	text = re.sub(r'\n\W+?\n', '\n', text) # lines with only punctuations
	text = text.replace(',,', ',').replace(',.', '.')
	return text

section = re.compile(r'(==+)\s*(.*?)\s*\1')

def compact(text):
	"""Deal with headers, lists, empty sections, residuals of tables"""
	page = []				# list of paragraph
	headers = {}				# Headers for unfilled sections
	emptySection = False		# empty sections are discarded
	inList = False				# whether opened <UL>

	for line in text.split('\n'):

		if not line:
			continue
		# Handle section titles
		m = section.match(line)
		if m:
			title = m.group(2)
			lev = len(m.group(1))
			if keepSections:
				page.append("<h%d>%s</h%d>" % (lev, title, lev))
			if title and title[-1] not in '!?':
				title += '.'
			headers[lev] = title
			# drop previous headers
			for i in headers.keys():
				if i > lev:
					del headers[i]
			emptySection = True
			continue
		# Handle page title
		if line.startswith('++'):
			title = line[2:-2]
			if title:
				if title[-1] not in '!?':
					title += '.'
				page.append(title)
		# handle lists
		elif line[0] in '*#:;':
			if keepSections:
				page.append("<li>%s</li>" % line[1:])
			else:
				continue
		# Drop residuals of lists
		elif line[0] in '{|' or line[-1] in '}':
			continue
		# Drop irrelevant lines
		elif (line[0] == '(' and line[-1] == ')') or line.strip('.-') == '':
			continue
		elif len(headers):
			items = headers.items()
			items.sort()
			for (i, v) in items:
				page.append(v)
			headers.clear()
			page.append(line)	# first line
			emptySection = False
		elif not emptySection:
			page.append(line)

	return page

def handle_unicode(entity):
	numeric_code = int(entity[2:-1])
	if numeric_code >= 0x10000: return ''
	return unichr(numeric_code)

#------------------------------------------------------------------------------

class OutputSplitter:
	def __init__(self, compress, max_file_size, path_name,config):
		self.dir_index = 0
		self.file_index = -1
		self.compress = compress
		self.max_file_size = max_file_size
		self.path_name = path_name
		self.config=config
		self.out_file = self.open_next_file()

	def reserve(self, size):
		cur_file_size = self.out_file.tell()
		if cur_file_size + size > self.max_file_size:
			self.close()
			self.out_file = self.open_next_file()

	def write(self, text):
		self.out_file.write(text)
	def index(self):
		if self.config:
			dir_name = self.dir_name()
			if not os.path.isdir(dir_name):
				os.makedirs(dir_name)
			file_name = os.path.join(dir_name, self.file_name())
			idoldata={'document':[]}
			idoldocs=[];
			docs=open(file_name,'r').readlines()
			for doc in docs:
				try:
					idoldocs.append(json.loads(doc))
				except:
					pass
			idoldata['document']=idoldocs
			idolindex=self.config["idolindex"]
			idolkey=self.config["idolkey"]
			res=requests.post('https://api.idolondemand.com/1/api/async/addtotextindex/v1',{'json':json.dumps(idoldata),'index':idolindex,'apikey':idolkey})
			print res.json()

	def close(self):
		self.index()
		self.out_file.close()

	def open_next_file(self):
		self.file_index += 1
		if self.file_index == 100:
			self.dir_index += 1
			self.file_index = 0
		dir_name = self.dir_name()
		if not os.path.isdir(dir_name):
			os.makedirs(dir_name)
		file_name = os.path.join(dir_name, self.file_name())
		#self.index()
		if self.compress:
			return bz2.BZ2File(file_name + '.bz2', 'w')
		else:
			return open(file_name, 'w')

	def dir_name(self):
		char1 = self.dir_index % 26
		char2 = self.dir_index / 26 % 26
		return os.path.join(self.path_name, '%c%c' % (ord('A') + char2, ord('A') + char1))

	def file_name(self):
		return 'wiki_%02d' % self.file_index

### READER ###################################################################

tagRE = re.compile(r'(.*?)<(/?\w+)[^>]*>(?:([^<]*)(<.*?>)?)?')

def process_data(input, output,config):
	global prefix

	page = []
	id = None
	inText = False
	redirect = False
	for line in input:
		line = line.decode('utf-8')
		#print line
		tag = ''
		if '<' in line:
			m = tagRE.search(line)
			if m:
				tag = m.group(2)
		if tag == 'page':
			page = []
			redirect = False
		elif tag == 'id' and not id:
			id = m.group(3)
		elif tag == 'title':
			title = m.group(3)
		elif tag == 'redirect':
			redirect = True
		elif tag == 'text':
			inText = True
			line = line[m.start(3):m.end(3)] + '\n'
			page.append(line)
			if m.lastindex == 4: # open-close
				inText = False
		elif tag == '/text':
			if m.group(1):
				page.append(m.group(1) + '\n')
			inText = False
		elif inText:
			page.append(line)
		elif tag == '/page':
			colon = title.find(':')
			if (colon < 0 or title[:colon] in acceptedNamespaces) and \
					not redirect:
				print id, title.encode('utf-8')
				sys.stdout.flush()
				WikiDocument(output, id, title, ''.join(page),config)
				#sys.exit()
			id = None
			page = []
		elif tag == 'base':
			# discover prefix from the xml dump file
			# /mediawiki/siteinfo/base
			base = m.group(3)
			prefix = base[:base.rfind("/")]

### CL INTERFACE ############################################################

def show_help():
	print >> sys.stdout, __doc__,

def show_usage(script_name):
	print >> sys.stderr, 'Usage: %s [options]' % script_name

##
# Minimum size of output files
minFileSize = 500 * 1024


def download_file(url):
	local_filename = url.split('/')[-1]
	# NOTE the stream=True parameter
	r = requests.get(url, stream=True)
	with open(local_filename, 'wb') as f:
		for chunk in r.iter_content(chunk_size=1024):
			if chunk: # filter out keep-alive new chunks
				f.write(chunk)
				f.flush()
	return local_filename

def process_api(url,output,config):
	print "api",config
	mediawikiurl=url
	mediawikiurl = urlparse( mediawikiurl )
	mediawikiurl = '{uri.scheme}://{uri.netloc}/'.format(uri=mediawikiurl)
	if "shoutwiki" in mediawikiurl:
		mediawikiurl=mediawikiurl+"w/"

	url="%s/api.php?action=query&generator=allpages&gaplimit=1000&gapfilterredir=nonredirects&prop=revisions&%s&rvprop=content&format=json"
	pageurl=url % (mediawikiurl,"nothing=")
	print pageurl
	gapcontinue=True
	compress = False
	file_size = 500 * 1024
	output_dir = '.'

	while gapcontinue:
		page=requests.get(pageurl).json()
		gapcontinue=False
		if "query-continue" in page:
			qc=page["query-continue"]
			gapcontinue=qc["allpages"]
			if "gapcontinue" in gapcontinue:
				gapcontinue="gapcontinue="+gapcontinue["gapcontinue"]
			elif "gapfrom" in gapcontinue:
				gapcontinue="gapfrom="+gapcontinue["gapfrom"]
			print gapcontinue
			pageurl=url % (mediawikiurl,gapcontinue)
		results=page["query"]["pages"]
		for res in results.values():
			id=res["pageid"]
			title=res["title"]
			try:
				text=res["revisions"][0]["*"]
			except:
				text=""
			WikiDocument(output, id, title,text,config)


statsurl="%s/Special:Statistics"

def main():
	global keepLinks, keepSections, prefix, acceptedNamespaces
	script_name = os.path.basename(sys.argv[0])

	try:
		long_opts = ['help', 'config=','compress','input=', 'bytes=','wikia=', 'basename=', 'links', 'ns=', 'sections', 'output=', 'version']
		opts, args = getopt.gnu_getopt(sys.argv[1:], 'cb:hln:o:i:w:B:sv', long_opts)
	except getopt.GetoptError:
		show_usage(script_name)
		sys.exit(1)

	compress = False
	file_size = 500 * 1024
	output_dir = '.'
	inputfile=sys.stdin
	config=None
	configpath=False
	mediawikiurl=False

	for opt, arg in opts:
		if opt in ('-h', '--help'):
			show_help()
			sys.exit()
		elif opt in ('-c', '--compress'):
			compress = True
		elif opt in ('-l', '--links'):
			keepLinks = True
		elif opt in ('-s', '--sections'):
			keepSections = True
		elif opt in ('-B', '--base'):
			prefix = arg
		elif opt in ('-b', '--bytes'):
			try:
				if arg[-1] in 'kK':
					file_size = int(arg[:-1]) * 1024
				elif arg[-1] in 'mM':
					file_size = int(arg[:-1]) * 1024 * 1024
				else:
					file_size = int(arg)
				if file_size < minFileSize: raise ValueError()
			except ValueError:
				print >> sys.stderr, \
				'%s: %s: Insufficient or invalid size' % (script_name, arg)
				sys.exit(2)
		elif opt in ('-n', '--ns'):
				acceptedNamespaces = set(arg.split(','))
		elif opt in ('-o', '--output'):
				output_dir = arg
		elif opt in ('-v', '--version'):
				print 'WikiExtractor.py version:', version
				sys.exit(0)
		elif opt in ('-i', '--input'):
				if arg.endswith("gz"):
					inputfile=gzip.open(arg,'r')
				else:
					inputfile=open(arg)
		elif opt in ('-w', '--wikia'):
				mediawikiurl=arg
		elif opt in ('--config'):
				configpath=arg


	if configpath:
		config=json.loads(open(configpath,'r').read())
		mediawikiurl=config["mediawikiurl"]
		idol=True
		idolkey=config["idolkey"]
		idolindex=config["idolindex"]

	if len(args) > 0:
		show_usage(script_name)
		sys.exit(4)

	if not os.path.isdir(output_dir):
		try:
			os.makedirs(output_dir)
		except:
			print >> sys.stderr, 'Could not create: ', output_dir
			return

	if not keepLinks:
		ignoreTag('a')



	output_splitter = OutputSplitter(compress, file_size, output_dir,config)
	processdatabool=True
	if mediawikiurl:
		text= requests.get (statsurl % (mediawikiurl)).text
		print statsurl % (mediawikiurl)
		dump=re.search('http://.*?\.xml\.gz',text)
		if dump:
			dump=dump.group(0)
			print "downloading wikia dump"
			dumpfile=download_file(dump)
			print "extracting wikia dump"
			inputfile=gzip.open(dumpfile,'r')
			print "done"
		else:
			print "dump was not found"
			processdatabool=False
	print "hello",config
	if processdatabool:
		process_data(inputfile, output_splitter,config)
	else:
		process_api(mediawikiurl,output_splitter,config)
	output_splitter.close()



if __name__ == '__main__':
	main()
