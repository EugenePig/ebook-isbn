# ebook-isbn
An eBook tool to extract ISBN or Metadata form eBook and rename them by using ISBN database and Metadata

# Requrement
1. Python 2.7
2. isbnlib 3.5.5 [https://pypi.python.org/pypi/isbnlib/3.5.5](https://pypi.python.org/pypi/isbnlib/3.5.5)
3. Apache Tika 1.8 [https://tika.apache.org/download.html](https://tika.apache.org/download.html)

# Command
python rename.py [the PATH of eBook]

# Pattern
There are six kinds of fields for the filename pattern. You can set it in rename.py. For example, if you set it as 'Publisher:Author:Year:Title:Language:ISBN-13', The book, "And the Mountains Echoed", will be renamed to "EMANER_A.C.Black_Khaled.Hosseini_2013_And.The.Mountains.Echoed_en_9781408842447.pdf". 

# Result
1. If some filenames start with "EMANER_", it means the metadata were found and the files were renamed successfully.
2. if some filenames start with "DELIAF_", it means the metadata weren't found and the files failed to be renamed.
3. The program will skip processing for any files taht start with "EMANER_" or "DELIAF_".

# Q&A
**Q: If you meet some errors like "python 'ascii' codec can't decode byte 0xa1" or "UnicodeDecodeError: 'big5' codec can't decode bytes in position 8-9: illegal mul
tibyte sequence"?**

A: 

1. Create sitecustomize.py in the same folder as site.py and set the default encoding. In my case, I use traditional chinese operating system, so I edited sitecustomize.py as follows.

    import sys
    sys.setdefaultencoding('cp950')

2. Check if the encoding of the original filename of the eBook is not the default coding that you set it in sitecustomize.py or is not unicode.

**Q: Why does the program fail to rename eBooks?**

A:

1. The program may not find any valid ISBN in the book.
2. There are more than one valid ISBN in the book. The program could not determine which one is the ISBN of the book. 
3. You exceed the daily max of requests of ISDN database. 

# Resources
1. [http://blog.univle.com/blog/2015/06/21/extract-isbn-from-pdf-and-epub-and-query-matadata-from-isbn-database/](http://blog.univle.com/blog/2015/06/21/extract-isbn-from-pdf-and-epub-and-query-matadata-from-isbn-database/)


 