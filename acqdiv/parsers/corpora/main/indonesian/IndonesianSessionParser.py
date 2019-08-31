import os
import re

from acqdiv.parsers.corpora.main.indonesian.IndonesianReader import \
    IndonesianReader
from acqdiv.parsers.corpora.main.indonesian.IndonesianCleaner \
    import IndonesianCleaner
from acqdiv.parsers.corpora.main.indonesian.IndonesianSpeakerLabelCorrector \
    import IndonesianSpeakerLabelCorrector
from acqdiv.parsers.corpora.main.indonesian.IndonesianAgeUpdater \
    import IndonesianAgeUpdater
from acqdiv.parsers.metadata.CHATParser import CHATParser
from acqdiv.parsers.toolbox.ToolboxParser import ToolboxParser
from acqdiv.model.Speaker import Speaker
from acqdiv.model.Word import Word


class IndonesianSessionParser(ToolboxParser):

    def get_metadata_reader(self):
        return CHATParser(self.metadata_path)

    def parse(self):
        session = super().parse()
        IndonesianSpeakerLabelCorrector.correct(session)

        return session

    def add_session_metadata(self):
        self.session.source_id = os.path.splitext(os.path.basename(
            self.toolbox_path))[0]
        metadata = self.metadata_reader.metadata['__attrs__']
        self.session.date = metadata.get('Date', None)

        return self.session

    def add_speakers(self):
        for speaker_dict in self.metadata_reader.metadata['participants']:
            speaker = Speaker()
            speaker.birth_date = speaker_dict.get('birthday', '')
            speaker.gender_raw = speaker_dict.get('sex', '')
            speaker.gender = speaker.gender_raw.title()
            speaker.code = speaker_dict.get('id', '')
            speaker.age_raw = speaker_dict.get('age', '')
            speaker.role_raw = speaker_dict.get('role', '')
            speaker.name = speaker_dict.get('name', '')
            speaker.languages_spoken = speaker_dict.get('language', '')

            IndonesianAgeUpdater.update(speaker, self.session.date)

            if self.is_speaker(speaker):
                self.session.speakers.append(speaker)

    @staticmethod
    def is_speaker(speaker):
        """Check whether the speaker is a real speaker.

        Skip `AUX` participants.

        Args:
            speaker (Speaker): The `Speaker` instance.
        """
        return speaker.code != 'AUX'

    def get_record_reader(self):
        return IndonesianReader()

    def get_cleaner(self):
        return IndonesianCleaner()

    def add_words(self, actual_utterance, target_utterance):
        utt = self.session.utterances[-1]

        for word in self.record_reader.get_words(actual_utterance):
            w = Word()
            utt.words.append(w)

            w.word_language = ''

            # Distinguish between word and word_target;
            # otherwise the target word is identical to the actual word
            if re.search('\(', word):
                w.word_target = re.sub('[()]', '', word)
                w.word = re.sub('\([^)]+\)', '', word)
                w.word_actual = w.word
            else:
                w.word_target = re.sub('xxx?|www', '???', word)
                w.word = re.sub('xxx?', '???', word)
                w.word_actual = w.word
