import argparse
import os
import glob
import json
import re
import random
import genanki
import markdown

class Flashzettl:
    '''creaes Anki cards from formatted notes in markdown files'''

    @classmethod
    def check_dir(cls, directory):
        '''resolve relative path and check directory'''
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            raise ValueError('your path resolved to {}, which is not a valid directory'.format(directory))
        return directory

    # flashcard field regex
    #TODO allow for list of decks -> how to treat default deck?
    regex = r'#anki[=]?(.*) *\n([\s\S]+?(?=\n *\n))\n *\n([\s\S]+?(?=\n *\n|\Z))'

    # known decks as {'name': {'deck': deck, 'id': id}}
    decks = {}

    @classmethod
    def load_decks(cls, path='flashzettl_settings.json'):
        '''builds genanki decks from (name, id) pairs in json file'''
        decks = {}
        with open(path, 'r') as f:
            deck_info = json.load(f)['decks']
            for d in deck_info:
                decks[d['name']] = {'deck': genanki.Deck(d['id'], d['name']), 'id': d['id']}
        return decks

    @classmethod
    def save_decks(cls, path='flashzettl_settings.json'):
        '''save decks as (name, id) pairs in json file'''
        with open(path, 'r') as f:
            data = json.load(f)

        deck_info = []
        for d in cls.decks:
            deck_info.append({'name': d, 'id': cls.decks[d]['id']})

        if data['decks'] != deck_info:
            data['decks'] = deck_info
            with open(path, 'w') as f:
                json.dump(data, f, sort_keys=True, indent=4)
            print('added new deck(s) to {}!'.format(path))

    # simple card model with front and back. also needs a unique ID
    # TODO inlclude bm, mathtools, colorx latex packages, as soon as new version is released
    basic_model = genanki.Model(
        1440894177,
        'Basic',
        fields=[
            {'name': 'front'},
            {'name': 'back'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{front}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{back}}',
            },]#,
        #latex_pre='\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n\\usepackage[utf8]{inputenc}\n'\
        #          '\\usepackage{amssymb,amsmath,bm,mathtools}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n'\
        #          '\\begin{document}\\tiny\n'
        )

    @classmethod
    def add_latex(cls, matchobj):
        '''adds [latex]...[/latex] around matchobj, escapes \\, *, \\{, \\}'''
        # TODO report error on markdown github page
        math = re.sub(r'\\\\', r'\\\\\\\\', matchobj.group(0))
        math = re.sub(r'\*', r'\*', math)
        math = re.sub(r'\\\{', r'\\\\\{', math)
        math = re.sub(r'\\\}', r'\\\\\}', math)
        math = re.sub(r'\\\#', r'\\\\\#', math)
        math = re.sub(r'_', r'\_', math)
        return '[latex]' + math + '[/latex]'

    @classmethod
    def add_list_linebreak(cls, matchobj):
        '''adds \n\n- to matchobject's first group'''
        # TODO add lists with * bullets
        return matchobj.group(1) + '\n\n-'

    # save which tag was processed in the current file
    done_mask = []

    @classmethod
    def tag_done(cls, matchobj):
        '''replaces #anki with #_anki if it was processed'''
        card = matchobj.group(0)
        if cls.done_mask[0]:
            card = re.sub(r'#anki', '#_anki', card)
        cls.done_mask.pop(0)
        return card

    @classmethod
    def polish(cls, text):
        '''converts problematic markdown items'''
        # remove id links
        text = re.sub(r'\[\[\d{14}\]\]', '', text)

        # substitute $...$ with [latex]$...$[/latex]
        text = re.sub(r'\$.+?\$', cls.add_latex, text)

        # add media files
        media_files = []
        mfs = re.findall(r'\!\[.+\]\((.+.[png|PNG|jpg|JPG|jpeg|JPEG|bmp|BMP])\)', text)
        for mf in mfs:
            media_files.append('..\\' + mf)

        # add additional line breaks in front of lists
        # TODO expand to lists that don't start with 1.
        text = re.sub(r'\n1', '\n\n1', text)
        text = re.sub(r'^(?!- )(.*)\n-', cls.add_list_linebreak, text)

        return text, media_files

    @classmethod
    def polish_deck_name(cls, deck_name):
        '''replace : with ::, remove trailing spaces, and add to known decks'''
        deck_name = deck_name.strip()
        if not deck_name:
            return None
        deck_name = re.sub(r'(?<!:):(?!:)', '::', deck_name)
        if deck_name not in cls.decks.keys():
            new_name = input(('{} is not in the list of existing deck\n'\
                              'press <Enter> to add it or input an alternative name: ').format(deck_name))
            if new_name:
                deck_name = new_name
            deck_id = random.randrange(1 << 30, 1 << 31)
            cls.decks[deck_name] = {'deck': genanki.Deck(deck_id, deck_name), 'id': deck_id}
        return deck_name

    @classmethod
    def extract_card_info(cls, directory, args):
        '''finds all card info in .md files of directory'''
        cards = {}
        # recursivley loop over all .md files in directory + subdirectories
        for f in glob.glob(f"{directory}**/*.md", recursive=True):
            with open(f, 'r+', encoding='utf-8') as _file:
                data = _file.read()
                # TODO check for #anki in header for atomic flashcard

                # check for file-wide deck-name
                result = re.search(r'(?<=- _anki=).*', data)
                if result:
                    file_deck_name = cls.polish_deck_name(result.group(0))
                else:
                    file_deck_name = None

                # find cards
                for result in re.finditer(cls.regex, data):
                    deck_raw = result.group(1)
                    question_raw = result.group(2)
                    answer_raw = result.group(3)

                    # use file-wide deck-name if no other is specified. skip if neither is specified
                    deck_name = cls.polish_deck_name(deck_raw)
                    if deck_name is None:
                        if file_deck_name is None:
                            cls.done_mask.append(False)
                            print('====================')
                            print("The card didn't provide a deck name. It will be skipped.")
                            print('#anki')
                            print(question_raw + '\n')
                            print(answer_raw)
                            print('====================')
                            continue
                        deck_name = file_deck_name
                    cls.done_mask.append(True)

                    if args.verbose or args.debug:
                        print('====================')
                        print('adding card from file ' + f + ':')
                        print('(' + deck_name + ')')
                        print(question_raw + '\n')
                        print(answer_raw)

                    # polish question and answer and extract media-file references
                    question, question_mfs = cls.polish(question_raw)
                    answer, answer_mfs = cls.polish(answer_raw)

                    if args.debug:
                        print('--------------------')
                        print(question + '\n')
                        print(answer)

                    # add card
                    if deck_name not in cards:
                        cards[deck_name] = []
                    cards[deck_name].append({
                        'question': markdown.markdown(question),
                        'answer': markdown.markdown(answer),
                        'media': question_mfs + answer_mfs
                    })

                    if args.debug:
                        print('--------------------')
                        print(cards[deck_name][-1]['question'] + '\n')
                        print(cards[deck_name][-1]['answer'])

                # only rewrite file if a card was used, but never in debug mode
                if any(cls.done_mask) and not args.debug:
                    data = re.sub(cls.regex, cls.tag_done, data)
                    _file.seek(0)
                    _file.write(data)
                    _file.truncate()
        return cards

    @classmethod
    def create_decks(cls, args):
        '''main routine: parses all .md files and creates Anki-decks'''
        directory = cls.check_dir(args.dir)
        print('searching for flashcards in directory' + directory + ' ...')

        # load deck info
        cls.decks = cls.load_decks()

        # extract all card info
        cards = cls.extract_card_info(directory, args)

        if not cards:
            print("didn't find any new cards (with a #anki tag)")
            return

        # create decks
        for deck_name in cards:
            deck = cls.decks[deck_name]['deck']
            media_files = []

            for card in cards[deck_name]:
                # write card
                note = genanki.Note(
                    model=cls.basic_model,
                    fields=[card['question'], card['answer']])
                deck.add_note(note)
                if card['media']:
                    media_files = media_files + card['media']

            # export deck
            package = genanki.Package(deck)
            package.media_files = media_files
            package.write_to_file('{}/{}.apkg'.format(args.out, deck_name.replace('::', '_')))
            print('added {} cards to {}!'.format(len(cards[deck_name]), deck_name))

        # save deck names and ids
        cls.save_decks()

if __name__ == '__main__':
    # TODO debug mode that doesn't alter notes and prints more details
    # TODO verbose mode
    PARSER = argparse.ArgumentParser(description='Flashzettl', usage='flashzettl.py <dir>')
    PARSER.add_argument('--dir', '-d', default='../../', metavar='PATH',
                        help='relative path to directory containing the markdown files')
    PARSER.add_argument('--out', '-o', default='../../cards', metavar='OUT',
                        help='relative path to output directory')
    PARSER.add_argument('--verbose', '-v', action='store_true')
    PARSER.add_argument('--debug', action='store_true')
    ARGS = PARSER.parse_args()

    Flashzettl.create_decks(ARGS)
