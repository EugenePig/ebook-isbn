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

import os
import sys
import logging
import time
import datetime

sys.path.append("../bookinfo")
from metasearch import BookMeta

logger = logging.getLogger('metasearch')
IGNORE_PREFIX = ['EMANER_', 'DELIAF_', 'NRAW_', 'TSIXE-NUM', 'RORREPTTH_', 'YNAMOOT_']

if __name__ == '__main__':
    # print("argv number = " + str(len(sys.argv)))
    if len(sys.argv) > 1:
        # logging.basicConfig(level=logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        logger.addHandler(console)
        logger.setLevel(logging.DEBUG)
        t = time.time()
        logname = datetime.datetime.fromtimestamp(t).strftime('%Y_%m_%d_%H_%M_%S')
        fh = logging.FileHandler(logname + '.log')
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
        recorder = open(logname + '_Rename.log', 'w')
        logging.debug('filesystemencoding = ' + sys.getfilesystemencoding())
        for root, dirs, files in os.walk(unicode(sys.argv[1], sys.getfilesystemencoding())):
            for f in files:
                if f.endswith(('.pdf', '.epub')) and not f.startswith('EMANER_') and not f.startswith(
                        'DELIAF_') and not f.startswith('NRAW_') and not f.startswith('TSIXE-NUM') and not f.startswith(
                        'RORREPTTH_') and not f.startswith('YNAMOOT_'):
                    filename = os.path.join(root, f)
                    logger.debug('====== ====== ====== ====== ====== ======')
                    logger.debug('Processing ' + filename)
                    bookmata = BookMeta(filename, recorder, 'goob', 'Publisher:Author:Year:Title:Language:ISBN-13')
                    bookmata.rename()
        recorder.close()
