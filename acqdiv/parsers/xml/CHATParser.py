from acqdiv.parsers.xml import CHATReader
from acqdiv.parsers.xml import CHATCleaner

from acqdiv.parsers.xml.interfaces import CorpusParserInterface


class CHATParser(CorpusParserInterface):
    """Gathers all data for the DB for a given CHAT session file.

    Uses the CHATReader for reading and inferring data from the CHAT file and
    CHATCleaner for cleaning these data.
    """

    def __init__(self, session_path):
        self.session_path = session_path
        self.reader = self.get_reader()
        self.cleaner = self.get_cleaner()

        with open(session_path) as session_file:
            self.reader.read(session_file)

    @staticmethod
    def get_reader():
        return CHATReader.ACQDIVCHATReader()

    @staticmethod
    def get_cleaner():
        return CHATCleaner.CHATCleaner()

    def get_session_metadata(self):
        """Get the metadata of a session.

        Returns:
            dict: Date and media file name of session.
        """
        date = self.cleaner.clean_date(self.reader.get_session_date())
        filename = self.reader.get_session_filename()

        session_dict = {
            'date': date if date else None,
            'media_filename': filename if filename else None}

        return session_dict

    def next_speaker(self):
        """Yield the metadata of the next speaker of a session.

        Yields:
            dict: The label, name, age, birth date, gender, language, role of
                the speaker.
        """
        while self.reader.load_next_speaker():
            speaker_label = self.reader.get_speaker_label()
            name = self.reader.get_speaker_name()
            role = self.reader.get_speaker_role()
            age = self.reader.get_speaker_age()
            gender = self.reader.get_speaker_gender()
            language = self.reader.get_speaker_language()
            birth_date = self.cleaner.clean_date(
                                self.reader.get_speaker_birthdate())

            speaker_dict = {
                'speaker_label': speaker_label,
                'name': name if name else None,
                'age_raw': age if age else None,
                'gender_raw': gender if gender else None,
                'role_raw': role,
                'languages_spoken': language if language else None,
                'birthdate': birth_date if birth_date else None}

            yield speaker_dict

    def next_utterance(self):
        """Yields the next utterance of a session."""
        while self.reader.load_next_record():

            source_id = self.reader.get_uid()
            addressee = self.reader.get_addressee()
            translation = self.reader.get_translation()
            comment = self.reader.get_comments()
            speaker_label = self.reader.get_record_speaker_label()
            utterance_raw = self.reader.get_utterance()
            start_raw = self.reader.get_start_time()
            end_raw = self.reader.get_end_time()
            sentence_type = self.reader.get_sentence_type()

            # actual & target distinction
            actual_utt = self.cleaner.clean_utterance(
                self.reader.get_actual_utterance())
            target_utt = self.cleaner.clean_utterance(
                self.reader.get_target_utterance())

            # clean translation
            translation = self.cleaner.clean_translation(translation)

            # get morphology tiers
            seg_tier_raw = self.reader.get_seg_tier()
            gloss_tier_raw = self.reader.get_gloss_tier()
            pos_tier_raw = self.reader.get_pos_tier()

            # clean the morphology tiers
            seg_tier = self.cleaner.clean_seg_tier(seg_tier_raw)
            gloss_tier = self.cleaner.clean_gloss_tier(gloss_tier_raw)
            pos_tier = self.cleaner.clean_pos_tier(pos_tier_raw)

            # cross cleaning
            actual_utt, target_utt, seg_tier, gloss_tier, pos_tier = \
                self.cleaner.cross_clean(
                    actual_utt, target_utt, seg_tier, gloss_tier, pos_tier)

            actual_words = self.reader.get_utterance_words(actual_utt)
            target_words = self.reader.get_utterance_words(target_utt)

            # collect all words of the utterance
            words = []
            for word_actual, word_target in zip(actual_words, target_words):

                if self.reader.get_standard_form() == 'actual':
                    word = word_actual
                else:
                    word = word_target

                word_language = self.reader.get_word_language(word)

                word = self.cleaner.clean_word(word)
                word_actual = self.cleaner.clean_word(word_actual)
                word_target = self.cleaner.clean_word(word_target)

                word_dict = {
                    'word_language': word_language if word_language else None,
                    'word': word,
                    'word_actual': word_actual,
                    'word_target': word_target,
                    'warning': None
                }
                words.append(word_dict)

            # rebuild utterance from cleaned words
            utterance = ' '.join(w['word'] for w in words)

            utterance_dict = {
                'source_id': source_id,
                'speaker_label': speaker_label,
                'addressee': addressee if addressee else None,
                'utterance_raw': utterance_raw,
                'utterance': utterance if utterance else None,
                'translation': translation if translation else None,
                'morpheme': seg_tier_raw if seg_tier_raw else None,
                'gloss_raw': gloss_tier_raw if gloss_tier_raw else None,
                'pos_raw': pos_tier_raw if pos_tier_raw else None,
                'sentence_type': sentence_type,
                'start_raw': start_raw if start_raw else None,
                'end_raw': end_raw if end_raw else None,
                'comment': comment if comment else None,
                'warning': None
            }

            # clean the morphology tiers
            seg_tier = self.cleaner.clean_seg_tier(seg_tier)
            gloss_tier = self.cleaner.clean_gloss_tier(gloss_tier)
            pos_tier = self.cleaner.clean_pos_tier(pos_tier)

            # get morpheme words from the respective morphology tiers
            wsegs = self.reader.get_seg_words(seg_tier)
            wglosses = self.reader.get_gloss_words(gloss_tier)
            wposes = self.reader.get_pos_words(pos_tier)

            # determine number of words to be considered based on
            # main morphology tier and existence of this morphology tier
            if self.reader.get_main_morpheme() == 'segment':
                wlen = len(wsegs)
                # segment tier does not exist
                if not wlen:
                    wlen = len(wglosses)
            else:
                wlen = len(wglosses)
                # gloss tier does not exist
                if not wlen:
                    wlen = len(wsegs)

            # if both segment and gloss tier do not exists, take the pos tier
            if not wlen:
                wlen = len(wposes)

            # check for wm-misalignments between morphology tiers
            # if misaligned, replace by a list of empty strings
            if wlen != len(wsegs):
                wsegs = wlen*['']
            if wlen != len(wglosses):
                wglosses = wlen*['']
            if wlen != len(wposes):
                wposes = wlen*['']

            # collect morpheme data of an utterance
            morphemes = []
            # go through all morpheme words
            for wseg, wgloss, wpos in zip(wsegs, wglosses, wposes):

                wseg = self.cleaner.clean_seg_word(wseg)
                wgloss = self.cleaner.clean_gloss_word(wgloss)
                wpos = self.cleaner.clean_pos_word(wpos)

                # collect morpheme data of a word
                wmorphemes = []

                # get morphemes from the morpheme words
                segments = self.reader.get_segments(wseg)
                glosses = self.reader.get_glosses(wgloss)
                poses = self.reader.get_poses(wpos)

                # determine number of morphemes to be considered
                if self.reader.get_main_morpheme() == 'segment':
                    mlen = len(segments)
                    if not mlen:
                        mlen = len(glosses)
                else:
                    mlen = len(glosses)
                    if not mlen:
                        mlen = len(segments)

                # if both segment and gloss do not exists, take the pos
                if not mlen:
                    mlen = len(poses)

                # check for mm-misalignments between morphology tiers
                # if misaligned, replace by a list of empty strings
                if mlen != len(segments):
                    segments = mlen*['']
                if mlen != len(glosses):
                    glosses = mlen*['']
                if mlen != len(poses):
                    poses = mlen*['']

                # go through morphemes
                for seg, gloss, pos in zip(segments, glosses, poses):

                    morpheme_language = self.reader.get_morpheme_language(
                                            seg, gloss, pos)

                    # clean the morphemes
                    seg = self.cleaner.clean_segment(seg)
                    gloss = self.cleaner.clean_gloss(gloss)
                    pos = self.cleaner.clean_pos(pos)

                    morpheme_dict = {
                        'morpheme_language':
                            morpheme_language if morpheme_language else None,
                        'morpheme': seg if seg else None,
                        'gloss_raw': gloss if gloss else None,
                        'pos_raw': pos if pos else None
                    }
                    wmorphemes.append(morpheme_dict)

                morphemes.append(wmorphemes)

            yield utterance_dict, words, morphemes


class CreeParser(CHATParser):
    @staticmethod
    def get_reader():
        return CHATReader.CreeReader()

    @staticmethod
    def get_cleaner():
        return CHATCleaner.CreeCleaner()


class EnglishManchester1Parser(CHATParser):
    @staticmethod
    def get_reader():
        return CHATReader.EnglishManchester1Reader()

    @staticmethod
    def get_cleaner():
        return CHATCleaner.EnglishManchester1Cleaner()


class InuktitutParser(CHATParser):
    @staticmethod
    def get_reader():
        return CHATReader.InuktitutReader()

    @staticmethod
    def get_cleaner():
        return CHATCleaner.InuktitutCleaner()


class JapaneseMiiProParser(CHATParser):
    @staticmethod
    def get_reader():
        return CHATReader.JapaneseMiiProReader()

    @staticmethod
    def get_cleaner():
        return CHATCleaner.JapaneseMiiProCleaner()


class SesothoParser(CHATParser):
    @staticmethod
    def get_reader():
        return CHATReader.SesothoReader()

    @staticmethod
    def get_cleaner():
        return CHATCleaner.SesothoCleaner()


class TurkishParser(CHATParser):
    @staticmethod
    def get_reader():
        return CHATReader.TurkishReader()

    @staticmethod
    def get_cleaner():
        return CHATCleaner.TurkishCleaner()


def main():
    import glob
    import acqdiv
    import os
    import time

    acqdiv_path = os.path.dirname(acqdiv.__file__)

    start_time = time.time()

    for corpus, parser_cls in [
            ('Turkish', TurkishParser),
            ('Japanese_MiiPro', JapaneseMiiProParser),
            ('English_Manchester1', EnglishManchester1Parser),
            ('Cree', CreeParser),
            ('Inuktitut', InuktitutParser)
    ]:

        corpus_path = os.path.join(
            acqdiv_path, 'corpora/{}/cha/*.cha'.format(corpus))

        for path in glob.iglob(corpus_path):
            parser = parser_cls(path)

            print(path)

            for _ in parser.next_utterance():
                pass

            parser.get_session_metadata()

            for _ in parser.next_speaker():
                pass

    print('--- %s seconds ---' % (time.time() - start_time))


if __name__ == '__main__':
    main()
