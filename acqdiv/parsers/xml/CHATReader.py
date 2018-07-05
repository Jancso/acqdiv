import itertools
import contextlib
import mmap
import re


class CHATReader:
    """Parser for CHAT metadata and records of a session."""

    # utterance ID
    uid = None

    @classmethod
    def get_uid(cls):
        """Get the utterance ID.

        The ID counter is generated by the method 'iter_records' that
        increments the counter by one for each record.

        Returns:
            str: The utterance ID consisting of 'u' + the ID counter.
            None: If method 'iter_records' has not been called yet.
        """
        if cls.uid is not None:
            return 'u' + str(cls.uid)

    # ---------- session processing ----------

    @staticmethod
    def get_metadata(session_path):
        """Get the metadata of a session.

        Lines containing metadata start with @ followed by the field name, a
        colon and a tab. All metadata is at the top of a session file.

        Returns:
            str: The metadata.
        """
        with open(session_path, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            metadata_start = re.search(br'@.*?:\t', mm).start()
            metadata_end = re.search(br'\*[A-Za-z0-9]{3}:\t', mm).start()
            return mm[metadata_start:metadata_end].decode()

    @staticmethod
    def get_metadata_field(metadata, name):
        """Get the content of a metadata field.

        If a metadata field occurs multiple times (as is the case for 'ID'),
        they are merged, separated by line breaks.

        Args:
            metadata (str): The metadata section.
            name (str): The name of the field.

        Returns:
            str: The content of the metadata field. If the field does not
                exist, the empty string.
        """
        metadata_regex = re.compile(r'@{}:\t(.*)'.format(name))
        matches = []
        for match in metadata_regex.finditer(metadata):
            matches.append(match.group(1))

        if matches:
            return '\n'.join(matches)
        else:
            return ''

    @classmethod
    def get_date(cls, metadata):
        """Get the date of the session.

        The field is called 'Date' by default.

        Args:
            metadata (str): The metadata section.

        Returns:
            str: The date.
        """
        return cls.get_metadata_field(metadata, 'Date')

    @classmethod
    def get_media(cls, metadata):
        """Get the media data of the session.

        The field is called 'Media' by default and can consist of 3 sub-fields:
            - filename (without extension)
            - format (e.g. video)
            - comment (e.g. unlinked)

        The comment field is optional.

        Args:
            metadata (str): The metadata section.

        Returns:
            str: The media.
        """
        return cls.get_metadata_field(metadata, 'Media')

    @classmethod
    def get_filename(cls, media):
        """Get the filename from the media data.

        Args:
            media (str): The media data.

        Returns:
            str: The filename.
        """
        return media.split(',')[0]

    @classmethod
    def iter_participants(cls, metadata):
        """Iter participants listed in the metadata section.

        The field is called 'Participants'. It contains a comma-separated list
        of participants consisting of the speaker label, the name and the role
        of the speaker. The name may be omitted.

        Args:
            metadata (str): The metadata section.

        Yields:
            str: The next participant (label, name, role).
        """
        participants = cls.get_metadata_field(metadata, 'Participants')
        for participant in re.split(r' ?, ?', participants):
            yield participant

    @classmethod
    def get_speaker_label(cls, participant):
        """Get the speaker label from the participant.

        Args:
            participant (str): The participant consisting of a label,
                an optional name and the role.

        Returns:
            str: The speaker label.
        """
        return participant.split(' ')[0]

    @classmethod
    def get_name(cls, participant):
        """Get the name from the participant.

        Args:
            participant (str): The participant consisting of a label,
                an optional name and the role.

        Returns:
            str: The name. If the name is missing, the empty string.
        """
        data = participant.split(' ')
        # if name is missing
        if len(data) == 2:
            return ''
        else:
            return data[1]

    @classmethod
    def get_role(cls, participant):
        """Get the role from the participant.

        Args:
            participant (str): The participant consisting of a label,
                an optional name and the role.

        Returns:
            str: The role.
        """
        return participant.split(' ')[-1]

    @classmethod
    def get_id_field(cls, metadata, speaker_label):
        """Get the ID field of a participant.

        The field is called 'ID' and consists of the following sub-fields
        separated by pipes: language, corpus, code, age, sex, group, SES, role,
        education, custom. The correct ID line is found via the speaker label.

        Args:
            metadata (str): The metadata section.
            speaker_label (str): The speaker label.

        Returns:
            str: The ID field belonging to the participant with this label.

        Raises:
            ValueError: If there is no ID line for a given speaker label.
        """
        ids = cls.get_metadata_field(metadata, 'ID')
        for ID in ids.split('\n'):
            if '|' + speaker_label + '|' in ID:
                return ID

        raise ValueError(
            'No ID information for speaker label {}'.format(speaker_label))

    @staticmethod
    def get_age(id_field):
        """Get the age from an ID field.

        Args:
            id_field (str): The ID field.

        Returns:
            str: The age.
        """
        return id_field.split('|')[3]

    @staticmethod
    def get_gender(id_field):
        """Get the gender from an ID field.

        Args:
            id_field (str): The ID field.

        Returns:
            str: The gender.
        """
        return id_field.split('|')[4]

    @staticmethod
    def get_language(id_field):
        """Get the language from an ID field.

        Args:
            id_field (str): The ID field.

        Returns:
            str: The language.
        """
        return id_field.split('|')[0]

    @classmethod
    def get_birth_date(cls, metadata, speaker_label):
        """Get the birth date of a participant.

        The field is called 'Birth of [speaker label]'.

        Args:
            metadata (str): The metadata section.
            speaker_label (str): The speaker label.

        Returns:
            str: The birth date of the participant.
        """
        name = 'Birth of {}'.format(speaker_label)
        return cls.get_metadata_field(metadata, name)

    @classmethod
    def iter_records(cls, session_path):
        """Yield a record of the CHAT file.

        A record starts with ``*speaker_label:\t`` in CHAT.

        Yields:
            str: The next record.
        """
        # for utterance ID generation
        counter = itertools.count()
        cls.uid = next(counter)

        with open(session_path, 'rb') as f:
            # use memory-mapping of files
            with contextlib.closing(
                    mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)) as text:

                # create a record generator
                rec_generator = re.finditer(br'\*[A-Za-z0-9]{3}:\t', text)

                # get start of first record
                rec_start_pos = next(rec_generator).start()

                # iter all records
                for rec in rec_generator:

                    # get start of next record
                    next_rec_start_pos = rec.start()

                    # get the stringified record
                    rec_str = text[rec_start_pos:next_rec_start_pos].decode()

                    yield rec_str

                    cls.uid = next(counter)

                    # set new start of record
                    rec_start_pos = next_rec_start_pos

                # handle last record
                rec_str = text[rec_start_pos:].decode()
                yield rec_str

                cls.uid = None

    # ---------- record processing ----------

    @staticmethod
    def remove_line_breaks(rec):
        """Remove line breaks within the tiers of a record.

        CHAT inserts line breaks when the text of a main line or dependent
        tier becomes too long.

        Args:
            rec (str): The record.

        Returns:
            str: Record without break lines within the tiers.
        """
        return rec.replace('\n\t', ' ')

    @classmethod
    def get_main_line(cls, rec):
        """Get the main line of the record."""
        rec = cls.remove_line_breaks(rec)
        main_line_regex = re.compile(r'\*[A-Za-z0-9]{3}:\t.*')
        return main_line_regex.search(rec).group()

    @staticmethod
    def get_dependent_tier(rec, name):
        """Get the content of the dependent tier from the record.

        Args:
            rec (str): The record.
            name (str): The name of the dependent tier.

        Returns:
            str: The content of the dependent tier. If there is no dependent
                tier called 'name' in the record, the empty string.
        """
        dependent_tier_regex = re.compile(r'%{}:\t(.*)'.format(name))
        match = dependent_tier_regex.search(rec)
        if match is None:
            return ''
        else:
            return match.group(1)

    @classmethod
    def get_addressee(cls, rec):
        """Get the addressee of the record.

        Returns:
            str: The content of the 'add' dependent tier. If there is no
                dependent tier called 'add' in the record, the empty string.
        """
        return cls.get_dependent_tier(rec, 'add')

    @classmethod
    def get_translation(cls, rec):
        """Get the translation of the record.

        Returns:
            str: The content of the 'eng' dependent tier. If there is no
             dependent tier called 'eng' in the record, the empty string.
        """
        return cls.get_dependent_tier(rec, 'eng')

    @classmethod
    def get_comments(cls, rec):
        """Get the comments of a record.

        Returns:
            str: The content of the 'com' dependent tier. If there is no
                dependent tier called 'com' in the record, the empty string.
        """
        return cls.get_dependent_tier(rec, 'com')

    @staticmethod
    def get_seg_tier(rec):
        """Get the tier containing segments.

        Returns:
            str: The content of the tier containing segments.
        """
        raise NotImplementedError

    @staticmethod
    def get_gloss_tier(rec):
        """Get the tier containing glosses.

        Returns:
            str: The content of the tier containing glosses.
        """
        raise NotImplementedError

    @staticmethod
    def get_pos_tier(rec):
        """Get the tier containing POS tags.

        Returns:
            str: The content of the tier containing POS tags.
        """
        raise NotImplementedError

    # ---------- main line processing ----------

    @staticmethod
    def get_record_speaker_label(main_line):
        """Get the speaker label from the main line.

        The speaker label consists of three alphanumeric characters.

        Args:
            main_line (str): The main line.

        Returns:
            str: The speaker label.
        """
        speaker_label_regex = re.compile(r'(?<=^\*)[A-Za-z0-9]{3}')
        return speaker_label_regex.search(main_line).group()

    @staticmethod
    def get_utterance_raw(main_line):
        """Get the raw utterance from the main line.

        Args:
            main_line (str): The main line.

        Returns:
            str: The raw utterance.
        """
        utterance_regex = re.compile(r'(?<=:\t).*[.!?]')
        return utterance_regex.search(main_line).group()

    @staticmethod
    def get_time(main_line):
        """Get the time from the main line.

        Args:
            main_line (str): The main line.

        Returns:
            str: The time consisting of start and end time.
        """
        time_regex = re.compile(r'\d+_\d+')
        match = time_regex.search(main_line)
        if match is None:
            return ''
        else:
            return match.group()

    # ---------- utterance processing ----------

    @staticmethod
    def get_words(utterance):
        """Get the words of an utterance.

        Per default, a whitespace separating the words is assumed.

        Returns:
            list: The words of an utterance.
        """
        return [word for word in utterance.split(' ')]

    @staticmethod
    def get_shortening_actual(utterance):
        """Get the actual form of shortenings.

        Coding in CHAT: parentheses within word.
        The part with parentheses is removed.
        """
        shortening_regex = re.compile(r'(\S*)\(\S+\)(\S*)')
        return shortening_regex.sub(r'\1\2', utterance)

    @staticmethod
    def get_shortening_target(utterance):
        """Get the target form of shortenings.

        Coding in CHAT: \w+(\w+)\w+ .
        The part in parentheses is kept, parentheses are removed.
        """
        shortening_regex = re.compile(r'(\S*)\((\S+)\)(\S*)')
        return shortening_regex.sub(r'\1\2\3', utterance)

    @staticmethod
    def get_replacement_actual(utterance):
        """Get the actual form of replacements.

        Coding in CHAT: [: <words>] .
        Keeps replaced words, removes replacing words with brackets.
        """
        # several scoped words
        replacement_regex1 = re.compile(r'<(.*?)> \[: .*?\]')
        clean = replacement_regex1.sub(r'\1', utterance)
        # one scoped word
        replacement_regex2 = re.compile(r'(\S+) \[: .*?\]')
        return replacement_regex2.sub(r'\1', clean)

    @staticmethod
    def get_replacement_target(utterance):
        """Get the target form of replacements.

        Coding in CHAT: [: <words>] .
        Removes replaced words, keeps replacing words with brackets.
        """
        replacement_regex = re.compile(r'(?:<.*?>|\S+) \[: (.*?)\]')
        return replacement_regex.sub(r'\1', utterance)

    @staticmethod
    def get_fragment_actual(utterance):
        """Get the actual form of fragments.

        Coding in CHAT: word starting with &.
        Keeps the fragment, removes the & from the word.
        """
        fragment_regex = re.compile(r'&(\S+)')
        return fragment_regex.sub(r'\1', utterance)

    @staticmethod
    def get_fragment_target(utterance):
        """Get the target form of fragments.

        Coding in CHAT: word starting with &.
        The fragment is marked as untranscribed (xxx).
        """
        fragment_regex = re.compile(r'&\S+')
        return fragment_regex.sub('xxx', utterance)

    @classmethod
    def get_actual_utterance(cls, utterance):
        """Get the actual form of the utterance."""
        for actual_method in [cls.get_shortening_actual,
                              cls.get_fragment_actual,
                              cls.get_replacement_actual]:
            utterance = actual_method(utterance)

        return utterance

    @classmethod
    def get_target_utterance(cls, utterance):
        """Get the target form of the utterance."""
        for target_method in [cls.get_shortening_target,
                              cls.get_fragment_target,
                              cls.get_replacement_target]:
            utterance = target_method(utterance)

        return utterance

    @classmethod
    def get_utterance(cls, utterance):
        """Return the standard form of the utterance.

        The standard form is the actual form per default.
        """
        return cls.get_actual_utterance(utterance)

    @staticmethod
    def get_sentence_type(utterance):
        """Get the sentence type of an utterance.

        The sentence type is inferred from the utterance terminator.
        """
        mapping = {'.': 'declarative',
                   '?': 'question',
                   '!': 'exclamation',
                   '+.': 'broken for coding',
                   '+...': 'trail off',
                   '+..?': 'trail off of question',
                   '+!?': 'question with exclamation',
                   '+/.': 'interruption',
                   '+/?': 'interruption of a question',
                   '+//.': 'self-interruption',
                   '+//?': 'self-interrupted question',
                   '+"/.': 'quotation follows',
                   '+".': 'quotation precedes'}
        terminator_regex = re.compile(r'([+/.!?"]*[!?.])(?=( \[\+|$))')
        match = terminator_regex.search(utterance)
        return mapping[match.group(1)]

    # ---------- time processing ----------

    @staticmethod
    def get_start(rec_time):
        """Get the start time from the time.

        Args:
            rec_time (str): The time.

        Returns:
            str: The start time.
        """
        if not rec_time:
            return rec_time
        else:
            start_regex = re.compile(r'(\d+)_')
            return start_regex.search(rec_time).group(1)

    @staticmethod
    def get_end(rec_time):
        """Get the end time from the time.

        Args:
            rec_time (str): The time.

        Returns:
            str: The end time.
        """
        if not rec_time:
            return rec_time
        else:
            end_regex = re.compile(r'_(\d+)')
            return end_regex.search(rec_time).group(1)

    # ---------- morphology processing ----------

    @classmethod
    def get_seg_words(cls, seg_tier):
        """Get the words from the segment tier.

        Returns:
            list: Words containing segments.
        """
        return cls.get_words(seg_tier)

    @classmethod
    def get_gloss_words(cls, gloss_tier):
        """Get the words from the gloss tier.

        Returns:
            list: Words containing glosses.
        """
        return cls.get_words(gloss_tier)

    @classmethod
    def get_pos_words(cls, pos_tier):
        """Get the words from the POS tag tier.

        Returns:
            list: Words containing POS tags.
        """
        return cls.get_words(pos_tier)

    @staticmethod
    def get_segments(seg_word):
        """Get the segments from the segment word.

        Returns:
            list: Segments in the word.
        """
        raise NotImplementedError

    @staticmethod
    def get_glosses(gloss_word):
        """Get the glosses from the gloss word.

        Returns:
            list: Glosses in the word.
        """
        raise NotImplementedError

    @staticmethod
    def get_poses(pos_word):
        """Get the POS tags from the POS word.

        Returns:
            list: POS tags in the word.
        """
        raise NotImplementedError

###############################################################################


class InuktitutReader(CHATReader):
    """Inferences for Inuktitut."""

    @staticmethod
    def get_actual_alternative(utterance):
        """Get the actual form of alternatives.

        Coding in CHAT: [=? <words>]
        The actual form is the alternative given in brackets.
        """
        replacement_regex = re.compile(r'(?:<.*?>|\S+) \[=\? (.*?)\]')
        return replacement_regex.sub(r'\1', utterance)

    @staticmethod
    def get_target_alternative(utterance):
        """Get the target form of alternatives.

        Coding in CHAT: [=? <words>]
        The target form is the original form.
        """
        # several scoped words
        alternative_regex1 = re.compile(r'<(.*?)> \[=\? .*?\]')
        clean = alternative_regex1.sub(r'\1', utterance)
        # one scoped word
        alternative_regex2 = re.compile(r'(\S+) \[=\? .*?\]')
        return alternative_regex2.sub(r'\1', clean)

    @classmethod
    def get_actual_utterance(cls, utterance):
        """Get the actual form of the utterance.

        Considers alternatives as well.
        """
        utterance = super().get_actual_utterance(utterance)
        return cls.get_actual_alternative(utterance)

    @classmethod
    def get_target_utterance(cls, utterance):
        """Get the target form of the utterance.

        Considers alternatives as well.
        """
        utterance = super().get_target_utterance(utterance)
        return cls.get_target_alternative(utterance)

    @classmethod
    def get_seg_tier(cls, rec):
        return cls.get_dependent_tier(rec, 'xmor')

    @classmethod
    def get_gloss_tier(cls, rec):
        return cls.get_dependent_tier(rec, 'xmor')

    @classmethod
    def get_pos_tier(cls, rec):
        return cls.get_dependent_tier(rec, 'xmor')

    @staticmethod
    def iter_morphemes(word):
        """Iter POS tags, segments and glosses of a word.

        Args:
            word (str): A morpheme word.

        Yields:
            tuple: The next POS tag, segment and gloss in the word.
        """
        morpheme_regex = re.compile(r'(.*)\|(.*?)\^(.*)')
        for morpheme in word.split('+'):
            match = morpheme_regex.search(morpheme)
            yield match.group(1), match.group(2), match.group(3)

    @classmethod
    def get_segments(cls, seg_word):
        return [seg for _, seg, _ in cls.iter_morphemes(seg_word)]

    @classmethod
    def get_glosses(cls, gloss_word):
        return [gloss for _, _, gloss in cls.iter_morphemes(gloss_word)]

    @classmethod
    def get_poses(cls, pos_word):
        return [pos for pos, _, _ in cls.iter_morphemes(pos_word)]


class CreeReader(CHATReader):

    @classmethod
    def get_seg_tier(cls, rec):
        return cls.get_dependent_tier(rec, 'xtarmor')

    @classmethod
    def get_gloss_tier(cls, rec):
        return cls.get_dependent_tier(rec, 'xmormea')

    @classmethod
    def get_pos_tier(cls, rec):
        return cls.get_dependent_tier(rec, 'xmortyp')

    @classmethod
    def get_morphemes(cls, word):
        return word.split('~')

    @classmethod
    def get_segments(cls, seg_word):
        return cls.get_morphemes(seg_word)

    @classmethod
    def get_glosses(cls, gloss_word):
        return cls.get_morphemes(gloss_word)

    @classmethod
    def get_poses(cls, pos_word):
        return cls.get_morphemes(pos_word)


def main():
    parser = CHATReader()
    metadata = parser.get_metadata('/home/anna/Schreibtisch/acqdiv/corpora/'
                                   'Japanese_MiiPro/cha/als19990618.cha')
    print(repr(parser.get_metadata_field(metadata, 'ID')))
    for p in parser.iter_participants(metadata):
        print(p)

    print(repr(parser.get_shortening_actual(
        'This (i)s a short(e)ned senten(ce)')))
    print(repr(parser.get_shortening_target(
        'This (i)s a short(e)ned senten(ce)')))
    print(repr(parser.get_replacement_actual(
        'This us [: is] <srane suff> [: strange stuff]')))
    print(repr(parser.get_replacement_target(
        'This us [: is] <srane suff> [: strange stuff]')))
    print(repr(parser.get_fragment_actual('This is &at .')))
    print(repr(parser.get_fragment_target('This is &at .')))
    print(repr(parser.get_sentence_type('This is a sent +!?')))

    inuktitut_parser = InuktitutReader()
    print(repr(inuktitut_parser.get_actual_alternative(
        'This is the target [=? actual] form.')))
    print(repr(inuktitut_parser.get_target_alternative(
        'This is the target [=? actual] form.')))

    test = 'LR|qa^outside+LI|unnga^ALL+VZ|aq^go_by_way_of+VV|VA|' \
           'tit^CAUS+VV|lauq^POL+VI|nnga^IMP_2sS_1sO VR|' \
           'nimak^move_around+VV|VA|tit^CAUS+VV|nngit^NEG+VI|' \
           'lugu^ICM_XxS_3sO? VR|kuvi^pour+NZ|suuq^HAB+NN|AUG|aluk^EMPH?'

    for word in inuktitut_parser.get_words(test):
        for morpheme in inuktitut_parser.iter_morphemes(word):
            print(repr(morpheme))


if __name__ == '__main__':
    main()