'''
stackpy is a command line program for working with Stack Overflow.
It allows you to search for questions (and later post and answer them!)

Copyright (c) 2015 Victor Kindhart GPL3.
'''
# !/usr/bin/env python

# coding: utf-8
from __future__ import print_function  # Python 3 compatibility
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from urllib import quote
import argparse
import urllib2
import gzip
import json
import sys
import os
import re

# Misc information
__version__ = "0.1"
__author__ = "Victor Kindhart"

search_link = ("https://api.stackexchange.com/2.2/search/advanced"
                "?pagesize=100"
                "&order=desc"
                "&sort=%s"
                "&q=\"%s\""
                "&tagged=%s"
                "&site=stackoverflow"
                "&filter=withbody")
answer_link = ("https://api.stackexchange.com/2.2/questions/%d/answers"
                "?pagesize=100"
                "&order=desc"
                "&sort=%s"
                "&site=stackoverflow"
                "&filter=withbody")

sort = "votes"


elements_remove = [
    "a",
    "blockquote",
    "del",
    "dd",
    "dl",
    "dt",
    "img",
    "kbd",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "sup",
    "sub",
    "strike",
    "ul",
]
elements_all = elements_remove + [
    "b",
    "code",
    "em",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "i",
    "strong"
]

elements_bold = [
    "b",
    "strong",
    "h1", "h2", "h3", "h4", "h5", "h6"
]


def stackpy_getch_nix():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    ch = None
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    if ch == '\x03': # Ctrl + C
        return None
    return ch


if os.name == "nt":
    import msvcrt
    stackpy_getch = msvcrt.getwch
else:
    import tty, termios
    stackpy_getch = stackpy_getch_nix


def stackpy_urlopen(*args, **kwargs):
    try:
        return urllib2.urlopen(*args, **kwargs)
    except Exception as err:
        print("stackpy: %s" % err, file=sys.stderr)
        sys.exit(1)


def stackpy_get_answer(question_id):
    link = answer_link % (question_id, sort)

    page = stackpy_urlopen(link)

    with gzip.GzipFile(fileobj=StringIO(page.read())) as gz:
        data = json.loads(gz.read())
    
    page.close()

    if not data.items: return None
    answer = data["items"][0]
    for _answer in data["items"]:
        if _answer["is_accepted"]:
            answer = _answer
            break

    return answer


def stackpy_parse_body_bw(body):
    for element in elements_all:
        body = re.sub("<%s.[\S\s]?>(.[\S\s]?)</%s>" % (body, body), "\\1", body)

    body = body.replace("<hr.[\S\s]?>", "---").replace("<br>", "\n")

    return body


def stackpy_parse_body_color(body):
    for element in elements_remove:
        body = re.sub("<%s>([\S\s]*?)</%s>" % (element, element),
                      "\\1", body)

    body = body.replace("<hr>", "---").replace("<br>", "\n")

    for element in elements_bold:
        body = re.sub("<%s>([\S\s]*?)</%s>" % (element, element),
                      colorama.Style.BRIGHT + "\\1" + colorama.Style.RESET_ALL,
                      body)

    body = re.sub("<i>([\S\s]*?)</i>",
                  colorama.Style.BRIGHT + "\\1" + colorama.Style.RESET_ALL,
                  body)

    body = re.sub("<code>([\S\s]*?)</code>",
                  colorama.Back.WHITE + colorama.Fore.BLACK + \
                  "\\1" + colorama.Back.RESET + colorama.Fore.RESET,
                  body)

    return body


def stackpy_print_question_color(question, answer):
    question["title"] = question["title"].encode("utf-8")
    question["body"] = stackpy_parse_body_color(question["body"]).encode("utf-8")

    print(("\n\n" + colorama.Fore.BLUE + "{question_id}" + \
           colorama.Fore.RESET + \
           " --- " + \
           colorama.Fore.GREEN + "{title}" + colorama.Fore.RESET + \
           "\n{body}\n").format(**question))

    if answer:
        answer["body"] = stackpy_parse_body_color(answer["body"]).encode("utf-8")
        print(("Answer: " +\
              colorama.Fore.BLUE + "{answer_id}" + colorama.Fore.RESET \
              + "\n{body}").format(**answer))
    else:
        print(colorama.Fore.RED + "No answers" + colorama.Fore.RESET)


def stackpy_print_question_bw(question, answer):
    question["title"] = question["title"].encode("utf-8")
    question["body"] = stackpy_parse_body_bw(question["body"]).encode("utf-8")

    print("\n\n{question_id} --- {title}\n{body}\n".format(**question))
    if answer:
        answer["body"] = stackpy_parse_body_bw(answer["body"]).encode("utf-8")
        print("Answer: {answer_id}\n{body}".format(answer))
    else:
        print("No answers")


try:
    import colorama
    colorama.init() # Colors available
    stackpy_print_question = stackpy_print_question_color
except ImportError:
    # No colors
    stackpy_print_question = stackpy_print_question_bw


def stackpy_search(query, tags):
    # Build query link
    if tags:
        parsed_tags = [quote(tag) for tag in tags]
    else:
        parsed_tags = []

    if query is not None:
        parsed_query = quote(query)
    else:
        parsed_query = ""

    # Search only questions
    link = search_link % (sort,
                          parsed_query,
                          ' '.join(parsed_tags))

    page = stackpy_urlopen(link)

    with gzip.GzipFile(fileobj=StringIO(page.read())) as gz:
        data = json.loads(gz.read())
    
    page.close()

    if not data["items"]:
        print("No questions found")
        return

    n = False
    for question in data["items"]:
        answer = stackpy_get_answer(question["question_id"])
        stackpy_print_question(question, answer)

        n = False
        while True:
            print("Press `n' for next or `q' to quit: ", end="")
            key = stackpy_getch()
            if not key:
                print()
                sys.exit()

            print(key)
            if key == 'n':
                n = True
                break
            elif key == 'q':
                return
            else:
                continue

        if n:
            continue

    if n:
        print("End of page")

def main():
    parser = argparse.ArgumentParser(prog="stackpy")
    parser.add_argument("-v", "--version", action="store_true",
                        help="print stackpy version")
    parser.add_argument("-s", "--search", metavar="QUERY",
                        help="search Stack Overflow for specified query")
    parser.add_argument("-t", "--tags", nargs="+", metavar="TAG",
                        help="search only specified tags")
    parser.add_argument("-i", "--info", action="store_true",
                        help="print information")

    args = parser.parse_args()

    if args.version:
        print("stackpy version %s" % __version__)
        return

    if args.info:
        print(__doc__)
        return

    if args.search or args.tags:
        stackpy_search(args.search, args.tags)
    else:
        parser.print_usage()

if __name__ == "__main__":
    main()
