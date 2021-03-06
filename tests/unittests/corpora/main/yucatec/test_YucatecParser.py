import io
import unittest
import os
import acqdiv

import pytest

from acqdiv.parsers.corpora.main.yucatec.cleaner \
    import YucatecCleaner
from acqdiv.parsers.corpora.main.yucatec.session_parser \
    import YucatecSessionParser
from acqdiv.parsers.corpora.main.yucatec.reader \
    import YucatecReader


@pytest.mark.usefixtures('dummy_cha')
class TestYucatecParser(unittest.TestCase):

    def test_get_reader(self):
        """Test get_reader. (Yucatec)"""
        session_str = ('*LOR:\tbaʼax .\n%xpho:\tbaaʼx\n%xmor:\tINT|baʼax .\n'
                       '%xspn:\tqué .\n@End')
        actual_reader = YucatecSessionParser.get_reader(
            io.StringIO(session_str))
        self.assertTrue(isinstance(actual_reader, YucatecReader))

    def test_get_cleaner(self):
        """Test get_cleaner. (Yucatec)"""
        actual_cleaner = YucatecSessionParser.get_cleaner()
        self.assertTrue(isinstance(actual_cleaner, YucatecCleaner))

    def test_parse(self):
        """Test parse() method."""
        session_str = ('*LOR:\tbaʼax .\n%xpho:\tbaaʼx\n%xmor:\tINT|baʼax .\n'
                       '%xspn:\tqué .\n@End')
        parser = YucatecSessionParser(self.dummy_cha_path)
        parser.reader = YucatecReader(io.StringIO(session_str))
        session = parser.parse()
        utt = session.utterances[0]

        utt_list = [
            utt.source_id == 'dummy_0',
            utt.addressee is None,
            utt.utterance_raw == 'baʼax .',
            utt.utterance == 'baʼax',
            utt.translation == 'qué .',
            utt.morpheme_raw == 'INT|baʼax .',
            utt.gloss_raw == 'INT|baʼax .',
            utt.pos_raw == 'INT|baʼax .',
            utt.sentence_type == 'default',
            utt.start_raw == '',
            utt.end_raw == '',
            utt.comment == '',
            utt.warning == ''
        ]

        w = utt.words[0]

        words_list = [
            w.word_language == '',
            w.word == 'baʼax',
            w.word_actual == 'baʼax',
            w.word_target == 'baʼax',
            w.warning == ''
        ]

        m = utt.morphemes[0][0]

        morpheme_list = [
            m.gloss_raw == '',
            m.morpheme == 'baʼax',
            m.morpheme_language == '',
            m.pos_raw == 'INT'
        ]

        assert (False not in utt_list
                and False not in words_list
                and False not in morpheme_list)
