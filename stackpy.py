"""
stackpy is a command line program for working with Stack Overflow.
It allows you to search questions and view answers

Copyright (c) 2015 Victor Kindhart GPL3.
"""
# !/usr/bin/env python
# coding: utf-8
from __future__ import print_function # because it's better
import cmd, sys, json
import webbrowser

try:
    from bs4 import BeautifulSoup as bsoup
except ImportError:
    print("[!!!] BeautifulSoup4 is not available, aborting")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[!!!] Requests is not available, aborting")
    sys.exit(1)

try:
    from colorama import init as colorama_init, Fore, Back, Style
    # initialize colorama
    colorama_init()
except ImportError:
    print("[!] colorama not found, no colors available")

    class Fake(object):
        def __getattr__(self, attr):
            return ""
    Fore = Back = Style = Fake()

try:
    # try importing faster version of StringIO, if available
    from cStringIO import StringIO
except ImportError:
    # nope, fall back to default one
    from io import StringIO

TERMSIZE = (80, 24)

# detect OS
try:
    # Windows
    import msvcrt
    OS = "Windows"
except ImportError:
    # *nix or other
    try:
        import tty, termios
        OS = "*nix"
    except ImportError:
        # other
        OS = "other"


class appdata(object):
    """Class for storing some data.
    """
    search_link = "https://api.stackexchange.com/2.2/search/advanced"
    answers_link = "https://api.stackexchange.com/2.2/questions/%d/answers"

    pagesize = 100 # Number of items to fetch at once
    sort = "votes" # Sorting type

    # tags to replace
    _headings = ["h1", "h2", "h3", "h4", "h5", "h6"]
    replace = {
        "code": ["code", "blockquote"] + _headings,
        "bold": ["strong", "b"] + _headings,
        "underline": ["em", "strike"],
        "blink": ["sup", "sub"]
    }

    question_link = "https://stackoverflow.com/questions/{}/"

class StackPy(object):
    """Main application class.
    """
    def __init__(self):
        self.buffer = StringIO()

        if OS == "Windows":
            self.getch = msvcrt.getwch
        elif OS == "*nix":
            self.getch = self.getch_nix
        else:
            self.getch = self.getch_other


    def getline(self, prompt=""):
        try:
            return raw_input(prompt)
        except EOFError:
            return None
        except KeyboardInterrupt:
            return None


    def search(self, query, tags):
        data = {"pagesize": appdata.pagesize,
                "order": "desc",
                "sort": appdata.sort,
                "q": query,
                "site": "stackoverflow",
                "filter": "withbody"}
        if tags:
            data["tagged"] = tags

        page = requests.get(appdata.search_link, data=data)
        questions = json.loads(page.text)
        page.close()

        return questions

    def get_answers(self, question_id):
        data = {"pagesize": appdata.pagesize,
                "order": "desc",
                "sort": appdata.sort,
                "site": "stackoverflow",
                "filter": "withbody"}

        page = requests.get(appdata.answers_link % question_id, data=data)
        answers = json.loads(page.text)
        page.close()

        return answers


    def escape(self, string, *attrs):
        return "".join(attrs) + unicode(string) + Style.RESET_ALL

    def process_html(self, html):
        soup = bsoup(html, "lxml")
        for tag in soup.find_all(appdata.replace["code"]):
            # tags to color as code
            tag.insert_before(Fore.CYAN)
            tag.insert_after(Style.RESET_ALL)

        for tag in soup.find_all(appdata.replace["bold"]):
            # tags to make bold
            tag.insert_before(Style.BRIGHT)
            tag.insert_after(Style.RESET_ALL)

        for tag in soup.find_all(appdata.replace["underline"]):
            # tags to underline
            tag.insert_before("\033[4m") # underline code
            tag.insert_after(Style.RESET_ALL)

        for tag in soup.find_all("hr"):
            # horizontal lines
            tag.insert_before(Fore.RED + "_" * 80 + '\n')
            tag.insert_after(Style.RESET_ALL)

        return soup.text


    def print_question(self, question):
        self.delimeter()
        self.write(self.escape(question["title"], Fore.GREEN) + '\n')
        self.write(self.escape("ID: ", Style.BRIGHT))
        self.write(self.escape(question["question_id"], Fore.BLUE) + '\n\n')
        self.delimeter()

        body = self.process_html(question["body"])
        self.write(body + '\n')
        self.delimeter()

        self.write(self.escape("Score: ", Style.BRIGHT))
        self.write(self.escape(question["score"], Fore.YELLOW) + '\n')

        self.write(self.escape("Tags: ", Style.BRIGHT))
        self.write(self.escape(", ".join(question["tags"]), Fore.BLUE) + '\n')
        
        self.write(self.escape("Author: ", Style.BRIGHT))
        self.write(self.escape(question["owner"]["display_name"], Fore.YELLOW))
        self.write('\n')

        self.write(self.escape("Answers: ", Style.BRIGHT))
        self.write(self.escape(question["answer_count"], Fore.YELLOW))
        if question["is_answered"]:
            self.write(self.escape(", ", Fore.YELLOW))
            self.write(self.escape("one accepted", Fore.GREEN))
        self.write('\n')
        self.delimeter()

        self.show()

    def print_answer(self, answer):
        self.delimeter()
        body = self.process_html(answer["body"])
        self.write(body + '\n')
        self.delimeter()

        self.write(self.escape("Score: ", Style.BRIGHT))
        self.write(self.escape(answer["score"], Fore.YELLOW) + '\n')

        self.write(self.escape("Accepted: ", Style.BRIGHT))
        if answer["is_accepted"]:
            self.write(self.escape("Yes", Fore.GREEN) + '\n')
        else:
            self.write(self.escape("No", Fore.RED) + '\n')
        
        self.write(self.escape("Author: ", Style.BRIGHT))
        self.write(self.escape(answer["owner"]["display_name"], Fore.YELLOW))
        self.write('\n')

        self.delimeter()

        self.show()


    def write(self, string):
        self.buffer.write(string.encode("utf-8"))

    def delimeter(self):
        self.write(self.escape("=" * TERMSIZE[0], Back.WHITE, Fore.WHITE) + \
                    '\n')


    def _show(self):
        # print data in the buffer a couple lines at the time
        self.buffer.seek(0)
        linenum = TERMSIZE[1] - 4
        line = None
        while True:
            i = linenum
            while i > 0:
                line = self.buffer.readline()
                if not line:
                    break
                print(line, end='')
                i -= 1
            if not line:
                break
            if not self.getch():
                # make sure to reset the style
                print(Style.RESET_ALL)
                return

    def show(self):
        self._show()
        # empty the buffer
        self.buffer.close()
        self.buffer = StringIO()


    def getch_nix(self):
        # getchar for *nix
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

    def getch_other(self):
        # getchar simulation for other systems
        line = self.getline()
        return line[0]

    def sure_getch(self, prompt, *keys):
        while True:
            print(prompt, end='')
            key = self.getch()
            print(key)
            if key in keys:
                break

        return key

stackpy = StackPy()

class StackPyCmd(cmd.Cmd):
    prompt = ">> "

    def do_search(self, query):
        """Search StackOverflow for specified query.
        usage: search [query]
        [query> ...]
        tags> tags separated by spaces"""
        if not query:
            query = stackpy.getline("query> ")
            if query is None:
                return
        
        tags_s = stackpy.getline("tags> ")
        if tags_s is None:
            return

        tags = ";".join(tags_s.split())

        print("Downloading question list ({})...".format(appdata.pagesize))
        questions = stackpy.search(query, tags)
        #print(questions["quota_remaining"])

        for question in questions["items"]:
            stackpy.print_question(question)
            char = stackpy.sure_getch(
                ("Do you want to see [a]nswers, "
                 "check [n]ext question or "
                 "go [b]ack? "),
                'a', 'n', 'b')
            if char == 'a':
                print("Downloading answer list ({})...".format(
                    appdata.pagesize))
                answers = stackpy.get_answers(question["question_id"])
                char = None
                for answer in answers["items"]:
                    stackpy.print_answer(answer)
                    char = stackpy.sure_getch(
                        ("Do you want to see [n]ext answer "
                         "or go [b]ack? "),
                        'n', 'b')
                    if char == 'n':
                        continue
                    else:
                        # char == 'b'
                        break
                if char != 'b':
                    print("No more answers.")

                char = stackpy.sure_getch(
                    ("Do you want to see [n]ext question "
                     "or go [b]ack? "),
                    'n', 'b')
                if char == 'n':
                    continue
                else:
                    # char == 'b'
                    break
            elif char == 'n':
                continue
            elif char == 'b':
                return

        if char != 'b':
            print("No more questions.")

    def do_open(self, ID):
        """Open question with specified ID in the web browser.
        usage: open question-id"""
        webbrowser.open_new_tab(appdata.question_link.format(ID))

    def do_quit(self, _):
        """Quit StackPy."""
        sys.exit()

    def do_EOF(self, _):
        sys.exit()

    def emptyline(self):
        pass

def main():
    stackpy_cmd = StackPyCmd()
    stackpy_cmd.cmdloop()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except KeyboardInterrupt:
        print()
    except:
        print("\n")
        print("stackpy: an exception occured")
        print("\n" + "~" * 80)
        import traceback
        traceback.print_exc()
        print("~" * 80)
