#!/usr/bin/python
# coding=utf-8

# Copyright 2015 Eugene Su

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import HTMLParser
import logging
from random import randint
import re
import os
import subprocess
import time
import zipfile

import isbnlib

logger = logging.getLogger(__name__)

class EpubParser(HTMLParser.HTMLParser):
    def __init__(self, filename):
        HTMLParser.HTMLParser.__init__(self)
        self.filename = filename
        self.content = ""

    def handle_data(self, data):
        self.content += data

    def get_htmls(self, zf):
        htmls = []
        for info in zf.filelist:
            if info.filename.endswith("html"):
                htmls.append(info)
        return htmls

    def get_numbers(self, s):
        pieces = re.compile(r'(\d+)').split(s)
        pieces[1::2] = map(int, pieces[1::2])
        return pieces

    def sort_numbers(self, infos):
        aux = [(self.get_numbers(info.filename), info) for info in infos]
        aux.sort()
        return [info for _, info in aux]

    def run(self):
        try:
            zf = zipfile.ZipFile(self.filename, 'r')
            htmls = self.get_htmls(zf)
            htmls = self.sort_numbers(htmls)
            for html in htmls:
                try:
                    self.feed(zf.read(html))
                except:
                    logging.debug('Exception in EpubParser')
                    pass
        except:
            logging.debug('Exception in ZipFile')
            pass


class BookMeta:
    PATTERN_FIELD = ['Publisher', 'Year', 'Title', 'Author', 'Language', 'ISBN-13']
    DEFAULT_PATTERN = ['Publisher', 'Year', 'Author', 'Title', 'Language' 'ISBN-13']
    SPECIAL_ISBN = ['0000000000']
    ISBN10_PATTERN_1 = re.compile(r'(?:\s|^)[- 0-9X]{10,16}(?:\s|$)')
    ISBN10_PATTERN_2 = re.compile(r'ISBN[\x20\w\t\(\)]{0,40}[0-9xX]{10}(?:\s|$)')
    ISBN13_PATTERN_1 = re.compile(r'97[89][-0-9 ]{14}(?:\s|$)')
    ISBN13_PATTERN_2 = re.compile(r'ISBN[\x20\w\t\(\)]{0,40}97[89]\d{10}(?:\s|$)')
    ISBN_PATTERN = [ISBN13_PATTERN_1, ISBN10_PATTERN_1, ISBN13_PATTERN_2, ISBN10_PATTERN_2]
    MAX_HTTP_RETRY = 2
    MAX_ISBN_COUNT = 5
    LONG_SLEEP = 300
    SHORT_SLEEP = 5
    STATUS_OK = 0
    STATUS_HTTPERROR = 1
    STATUS_NOTFOUND = 2
    STATUS_TOOMANYISBN = 3

    def __init__(self, filename, recorder, isbndb='goob', pattern='default'):
        self.filename = filename
        self.recorder = recorder
        self.isbndb = isbndb
        self.pattern = self.check_pattern(pattern)
        self.isbnfound = False
        self.status = self.STATUS_OK

    def check_pattern(self, patt):
        fields = []
        vaild = False
        if ':' in patt:
            patt = re.sub(r'\s+', '', patt)
            fields = patt.split(':')
            for field in fields:
                if field in self.PATTERN_FIELD:
                    vaild = True
                else:
                    vaild = False
                    break
        if not vaild:
            fields = self.DEFAULT_PATTERN
        return fields

    def get_canonical_isbn(self, line):
        # logger.debug('[ ' + line + ' ]')
        isbns = []
        for regex in self.ISBN_PATTERN:
            matches = regex.findall(line)
            if len(matches) > 0:
                logger.debug('Unchecked [' + ' '.join(matches) + ']')
                for match in matches:
                    match = match.strip()
                    match = match.replace('i', 'I')
                    match = match.replace('s', 'S')
                    match = match.replace('b', 'B')
                    match = match.replace('n', 'N')
                    match = re.sub(r'\x20', '', match)
                    match = re.sub(r'ISBN', 'ISBN\x20', match)
                    # logger.debug('match= ' + match)
                    if match not in self.SPECIAL_ISBN:
                        try:
                            # logger.debug('isbn= ' + isbn)
                            isbn = isbnlib.get_canonical_isbn(match)
                        except:
                            logger.error('Error in isbnlib while calling get_canonical_isbn')
                        else:
                            if isbn:
                                isbns.append(isbn)
        return isbns

    def get_canonical_isbn2(self, line):
        # logger.debug('[ ' + line + ' ]')
        isbns = []
        matches = isbnlib.get_isbnlike(line)
        if len(matches) > 0:
            logger.debug('Unchecked [' + ' '.join(matches) + ']')
        for match in matches:
            if match not in self.SPECIAL_ISBN and not any(match in s for s in isbns):
                try:
                    # logger.debug('isbn= ' + isbn)
                    isbn = isbnlib.get_canonical_isbn(match)
                except:
                    logger.error('Error in isbnlib while calling get_canonical_isbn')
                else:
                    if isbn:
                        isbns.append(isbn)
        return isbns

    def get_isbns(self, texts):
        # logger.debug('[ ' + texts + ' ]')
        lines = texts.splitlines()
        countdown = 100  # for finding other ISBNs
        found = False
        isbns = []
        for line in lines:
            candidates = self.get_canonical_isbn(line)
            # candidates = self.get_canonical_isbn2(line)
            for isbn in candidates:
                if isbn not in self.SPECIAL_ISBN and not any(isbn in s for s in isbns):
                    isbns.append(isbn)
                    found = True
            if found:
                countdown -= 1
            if countdown < 1:
                break
        self.isbnfound = found
        if len(isbns) < 1:
            logger.debug('Not Found ISBN in ' + self.filename)
        else:
            logger.debug(self.filename + ' has ' + str(len(isbns)) + ' ISBN')
            logger.debug(isbns)
        logger.debug('')
        return isbns

    def extract_texts(self, args):
        cmd = 'java -jar tika-app-1.8.jar -t -eUTF-8 ' + args + ' "' + self.filename + '"'
        # cmd = 'java -jar pdfbox-app-1.8.9.jar ExtractText -sort -console "' + self.filename + '"'
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (output, err) = process.communicate()
        # logger.debug(err)
        return output

    def extract_epub_texts(self):
        parser = EpubParser(self.filename)
        parser.run()
        return parser.content

    def print_metadata(self, meta):
        for matadata in meta.items():
            logger.debug(matadata[0] + ' : ' + ' '.join(matadata[1]))
        logger.debug('')

    def get_epub_meata(self):
        texts = self.extract_texts('-m')
        if len(texts) == 0:
            logger.error('Can not open "' + self.filename + '"')
        lines = texts.splitlines()
        meta = {}
        for line in lines:
            line = line.strip()
            if ': ' in line:
                (key, value) = line.split(': ', 1)
                if len(key) > 1 and len(value) > 1:
                    meta[key] = value
        if ('meta:author' in meta or 'Author' in meta) and ('dc:title' in meta or 'title' in meta):
            logger.debug('HAVE METADATA in epub')
        else:
            logger.debug('HAVE NOT METADATA in epub')
            meta = {}
        return meta

    def call_isbnlin_meta(self, isbn):

        meta = {}
        logger.debug('Searching ' + isbn + ' on ' + self.isbndb)
        count = 0
        while count <= self.MAX_HTTP_RETRY:
            try:
                meta = isbnlib.meta(isbn,  self.isbndb)
            except Exception as ex:
                if ex.message.startswith('an HTTP error has ocurred'):
                    logger.debug('HTTP error ... ...')
                    logger.debug('Sleep Start : %s' % time.ctime())
                    count += 1
                    time.sleep(self.LONG_SLEEP * count)
                    logger.debug('Sleep End : %s' % time.ctime())
                    logger.debug('End of Try ' + str(count))
                elif ex.message.startswith('an URL error has ocurred'):
                    logger.debug('URL error ... ...')
                    count += 1
                else:
                    logger.debug('Exception: ' + ex.message)
                    logger.debug('Metadata of ISBN ' + isbn + ' Not Found')
                    logger.debug('')
                    if self.status != self.STATUS_HTTPERROR:
                        self.status = self.STATUS_NOTFOUND
                    break
            else:
                self.print_metadata(meta)
                break
        if count > self.MAX_HTTP_RETRY:
            self.status = self.STATUS_HTTPERROR
        return meta

    def get_meta_from_isbnlin(self, isbns):
        meta_array = []
        for isbn in isbns:
            meta = self.call_isbnlin_meta(isbn)
            if self.status == self.STATUS_HTTPERROR:
                break
            if len(meta) > 0:
                meta_array.append(meta)
            time.sleep(self.SHORT_SLEEP)  # avoid http 403 error
        result = {}
        if len(meta_array) > 0:
            if len(meta_array) == 1:
                result = meta_array[0]
            else:
                title_count = {}
                for meta in meta_array:
                    if meta['Title'] in title_count:
                        count = int(title_count[meta['Title']]) + 1
                        title_count[meta['Title']] = count
                    else:
                        title_count[meta['Title']] = 1
                sorted_title = list(sorted(title_count, key=title_count.__getitem__, reverse=True))
                if (len(sorted_title) > 1 and int(title_count[sorted_title[0]]) > int(
                        title_count[sorted_title[1]])) or len(sorted_title) == 1:
                    for meta in meta_array:
                        if meta['Title'] == sorted_title[0]:
                            result = meta
                            break
        # just need the first Author
        if 'Authors' in result:
            authors = result['Authors']
            result.pop('Authors')
            result['Author'] = authors[0]
        return result

    def merge_meta(self, meta_isbnlin, meta_epub):
        meta_merged = {}
        if len(meta_isbnlin) == 0:
            if 'Author' in meta_epub and len(meta_epub['Author']) > 1:
                meta_merged['Author'] = meta_epub['Author']
            elif 'meta:author' in meta_epub and len(meta_epub['meta:author']) > 1:
                meta_merged['Author'] = meta_epub['meta:author']
            if 'language' in meta_epub and len(meta_epub['language']) > 1:
                meta_merged['Language'] = meta_epub['language']
            elif 'dc:language' in meta_epub and len(meta_epub['dc:language']) > 1:
                meta_merged['Language'] = meta_epub['dc:language']
            if 'title' in meta_epub and len(meta_epub['title']) > 1:
                meta_merged['Title'] = meta_epub['title']
            elif 'dc:title' in meta_epub and len(meta_epub['dc:title']) > 1:
                meta_merged['Title'] = meta_epub['dc:title']
            if 'publisher' in meta_epub and len(meta_epub['publisher']) > 1:
                meta_merged['Publisher'] = meta_epub['publisher']
            elif 'dc:publisher' in meta_epub and len(meta_epub['dc:publisher']) > 1:
                meta_merged['Publisher'] = meta_epub['dc:publisher']
        elif len(meta_epub) == 0:
            meta_merged = meta_isbnlin
            if 'Author' in meta_merged and len(meta_merged['Author']) < 2:
                meta_merged.pop('Author')
            if 'Language' in meta_merged and len(meta_merged['Language']) < 2:
                meta_merged.pop('Language')
            if 'Title' in meta_merged and len(meta_merged['Title']) < 2:
                meta_merged.pop('Title')
            if 'Publisher' in meta_merged and len(meta_merged['Publisher']) < 2:
                meta_merged.pop('Publisher')
        else:
            meta_merged = meta_isbnlin
            if 'Author' in meta_merged and len(meta_merged['Author']) < 2:
                if 'Author' in meta_epub and len(meta_epub['Author']) > 1:
                    meta_merged['Author'] = meta_epub['Author']
                elif 'meta:author' in meta_epub and len(meta_epub['meta:author']) > 1:
                    meta_merged['Author'] = meta_epub['meta:author']
                else:
                    meta_merged.pop('Author')
            if 'Language' in meta_merged and len(meta_merged['Language']) < 2:
                if 'language' in meta_epub and len(meta_epub['language']) > 1:
                    meta_merged['Language'] = meta_epub['language']
                elif 'dc:language' in meta_epub and len(meta_epub['dc:language']) > 1:
                    meta_merged['Language'] = meta_epub['dc:language']
                else:
                    meta_merged.pop('Language')
            if 'Title' in meta_merged and len(meta_merged['Title']) < 2:
                if 'title' in meta_epub and len(meta_epub['title']) > 1:
                    meta_merged['Title'] = meta_epub['title']
                elif 'dc:title' in meta_epub and len(meta_epub['dc:title']) > 1:
                    meta_merged['Title'] = meta_epub['dc:title']
                else:
                    meta_merged.pop('Title')
            if 'Publisher' in meta_merged and len(meta_merged['Publisher']) < 2:
                if 'publisher' in meta_epub and len(meta_epub['publisher']) > 1:
                    meta_merged['Publisher'] = meta_epub['publisher']
                elif 'dc:publisher' in meta_epub and len(meta_epub['dc:publisher']) > 1:
                    meta_merged['Publisher'] = meta_epub['dc:publisher']
                else:
                    meta_merged.pop('Publisher')
        return meta_merged

    def get_mata(self):
        texts = ''
        meta_epub = {}
        meta_isbnlin = []
        if self.filename.endswith('.epub'):
            meta_epub = self.get_epub_meata()
            texts = self.extract_epub_texts()
        elif self.filename.endswith('.pdf'):
            texts = self.extract_texts('-T -t')
            if len(texts) == 0:
                logger.error('Can not open "' + self.filename + '"')
        isbns = self.get_isbns(texts)
        if len(isbns) > self.MAX_ISBN_COUNT:
            self.status = self.STATUS_TOOMANYISBN
        else:
            meta_isbnlin = self.get_meta_from_isbnlin(isbns)
        meta_merged = self.merge_meta(meta_isbnlin, meta_epub)
        if len(meta_merged) > 0:
            logger.debug('Merged Metadata')
            self.print_metadata(meta_merged)
        return meta_merged

    def replace_illegal_char(self, str):
        str = re.sub(r'\W+', ' ', str)
        str = re.sub(r'\s+', '.', str)
        return str

    def rename(self):
        meta = self.get_mata()
        dirname = os.path.dirname(self.filename)
        if len(meta) > 0:
            new_filename = 'EMANER'
            for field in self.pattern:
                if field in meta:
                    if field == 'Year' or field == 'ISBN-13':
                        s = re.sub(r"\s+", '', meta[field])
                        new_filename += ('_' + s)
                    else:
                        s = self.replace_illegal_char(meta[field])
                        new_filename += ('_' + s)
                else:
                    new_filename += '_NONE'
            (name, extension) = os.path.splitext(self.filename)
            new_filename += extension
            new_filename = os.path.join(dirname, new_filename)
            log = 'Rename "' + self.filename + '" to "' + new_filename + '"'
            try:
                os.rename(self.filename, new_filename)
                logger.debug(log)
                logger.debug('')
                self.recorder.write(log + '\r\n')
            except:
                exfilename = 'TSIXE-NUM' + str(randint(1, 65535)) + '_' + os.path.basename(self.filename)
                exfilename = os.path.join(dirname, exfilename)
                exlog = 'Rename "' + self.filename + '" to "' + exfilename + '"'
                try:
                    os.rename(self.filename, exfilename)
                    logger.error('!!!!!! [Existed File]: ' + new_filename + ' !!!!!!')
                except:
                    logger.error('!!!!!! [Renaming Fail]: ' + exlog + ' !!!!!!')
        else:
            if self.isbnfound:
                if self.status == self.STATUS_HTTPERROR:
                    new_filename = 'RORREPTTH_' + os.path.basename(self.filename)
                elif self.status == self.STATUS_TOOMANYISBN:
                    new_filename = 'YNAMOOT_' + os.path.basename(self.filename)
                else:
                    new_filename = 'NRAW_' + os.path.basename(self.filename)
            else:
                new_filename = 'DELIAF_' + os.path.basename(self.filename)
            new_filename = os.path.join(dirname, new_filename)
            log = 'Rename "' + self.filename + '" to "' + new_filename + '"'
            try:
                os.rename(self.filename, new_filename)
            except:
                logger.error('!!!!!! [Renaming Fail]: ' + log + ' !!!!!!')