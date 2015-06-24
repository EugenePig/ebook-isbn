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
import re
import os
import subprocess
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

    def __init__(self, filename, recorder, isbndb='goob', pattern='default'):
        self.filename = filename
        self.recorder = recorder
        self.isbndb = isbndb
        self.pattern = self.check_pattern(pattern)

    def check_pattern(self, patt):
        fields = []
        vaild = False
        if ':' in patt:
            patt = re.sub(r"\s+", '', patt)
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

    def get_isbns(self, texts):
        lines = texts.splitlines()
        countdown = 100 # for finding other ISBNs
        found = False
        isbns = []
        for line in lines:
            isbn = ''
            try:
                isbn = isbnlib.get_canonical_isbn(line)
            except:
                logger.error('Error in isbnlib while calling get_canonical_isbn')
            # '0000000000' is a special valid ISBN
            if isbn and isbn != '0000000000':
                if not any(isbn in s for s in isbns):
                    isbns.append(isbn)
                found = True

            if found:
                countdown -= 1

            if countdown < 1:
                break

        if len(isbns) < 1:
            logger.debug('Not Found ISBN in ' + self.filename)
        else:
            logger.debug(self.filename + ' has ' + str(len(isbns)) + ' ISBN')
            logger.debug(isbns)
        logger.debug('')
        return isbns

    def extract_texts(self, args):
        cmd = 'java -jar tika-app-1.8.jar -eUTF-8 ' + args + ' "' + self.filename + '"'
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (output, err) = process.communicate()
        print(err)
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
        try:
            logger.debug('Searching ' + isbn)
            meta = isbnlib.meta(isbn,  self.isbndb)
        except:
            logger.debug('Metadata of ISBN ' + isbn + ' Not Found')
            logger.debug('')
        else:
            self.print_metadata(meta)
        return meta

    def get_meta_from_isbnlin(self, isbns):
        meta_array = []

        for isbn in isbns:
            meta = self.call_isbnlin_meta(isbn)
            if len(meta) > 0:
                meta_array.append(meta)
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
        if self.filename.endswith('.epub'):
            meta_epub = self.get_epub_meata()
            texts = self.extract_epub_texts()
        elif self.filename.endswith('.pdf'):
            texts = self.extract_texts('-T')
            if len(texts) == 0:
                logger.error('Can not open "' + self.filename + '"')
        isbns = self.get_isbns(texts)
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
            log = 'Rename "' + self.filename + '" to "' + new_filename.encode('utf8') + '"'
            logger.debug(log)
            logger.debug('')
            try:
                os.rename(self.filename, new_filename)
                self.recorder.write(log + '\r\n')
            except:
                logger.error('!!!!!! [Renaming Fail]: ' + log + ' !!!!!!')
        else:
            new_filename = 'DELIAF_' + os.path.basename(self.filename)
            new_filename = os.path.join(dirname, new_filename)
            log = 'Rename "' + self.filename + '" to "' + new_filename.encode('utf8') + '"'
            try:
                os.rename(self.filename, new_filename)
            except:
                logger.error('!!!!!! [Renaming Fail]: ' + log + ' !!!!!!')