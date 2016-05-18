""" Post-processing processes on the corpora in the ACQDIV-DB.
"""

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
# from sqlalchemy import create_engine
import database_backend as backend
from parsers import CorpusConfigParser
import sys
import re
import time
from configparser import ConfigParser

from . import age
from . import unique_id

def db_apply(func):
    """Wrapper for functions that access the database.

    Args:
        func: A function that takes a SQLalchemy session and a configparser object as arguments.

    Returns:
        A function that takes a configparser object and a SQLalchemy engine as arguments and 
        wraps func with the logic for connecting to and modifying the database.
    """
    def update_session(config, engine):
        """Function to connect to and modify the ACQDIV database. This is a wrapper returned by db_apply.

        This function calls the SQLalchemy sessionmaker to create a database session,
        then calls the function it wraps with the config and the session.
        Finally it closes the connection again.

    Args:
            config: A configparser object. The config should be the contents of a corpus-specific .ini file.
            engine: A SQLalchemy engine object. This is the connection to the ACQDIV database.
        """
        # cfunc is the function that connects to the db
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            func(session, config)
            session.commit()
        except Exception as e:
            session.rollback()
            print("Error {0}: {1}".format(type(e), e), file=sys.stderr)
        finally:
            session.close()
    return update_session


def update_xml_age(session, config):
    """Function to process speaker ages in Chat XML corpora.
    
    Finds all speakers from the corpus in the config and calls methods from age.py to
    fill in the age and age_in_days columns.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    corpus_name = config["corpus"]["corpus"]
    for db_session_entry in session.query(backend.Session).filter(backend.Session.corpus == corpus_name):
        sid = db_session_entry.id
        for row in session.query(backend.Speaker).filter(backend.Speaker.age_raw != None, backend.Speaker.session_id_fk == sid):
            new_age = age.format_xml_age(row.age_raw)
            if new_age:
                row.age = new_age
                aid = age.calculate_xml_days(new_age)
                row.age_in_days = aid


def update_imdi_age(session, config):
    """Function to process speaker ages in IMDI corpora.

    Finds all the recording sessions in the corpus in the config, then, for each speaker
    in the session:

    First attempts to calculate ages from the speaker's birth date and the session's
    recording date. For speakers where this fails, looks for speakers that already
    have a properly formatted age, transfers this age from the age_raw column to the
    age column and calculates age_in_days from it.

    Finally, it looks for speakers that only have an age in years and does the same.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    corpus_name = config["corpus"]["corpus"]

    for db_session_entry in session.query(backend.Session).filter(
            backend.Session.corpus == corpus_name):
        sid = db_session_entry.id
        cleaned_age = re.compile('\d{1,2};\d{1,2}\.\d')

        for db_speaker_entry in session.query(backend.Speaker).filter(
                ~backend.Speaker.birthdate.like("Un%"),
                ~backend.Speaker.birthdate.like("None"),
                backend.Speaker.session_id_fk == sid):
            try:
                recording_date = age.numerize_date(db_session_entry.date)
                birth_date = age.numerize_date(db_speaker_entry.birthdate)
                ages = age.format_imdi_age(birth_date, recording_date)
                db_speaker_entry.age = ages[0]
                db_speaker_entry.age_in_days = ages[1]

            except age.BirthdateError as e:
                    print("Warning: couldn't calculate age of "
                             "speaker {} from birth and recording dates"
                            .format(db_speaker_entry.id), file=sys.stderr)
                    print("Invalid birthdate: {}. Check data in {} file {}"
                            .format(e.bad_data, corpus_name, sid), 
                            file=sys.stderr)

            except age.SessionDateError as e:
                    print("Warning: couldn't calculate age of "
                             "speaker {} from birth and recording dates"
                            .format(db_speaker_entry.id), file=sys.stderr)
                    print("Invalid session recording date: \"{}\"\n"
                            "Check data in {} file {}"
                            .format(e.bad_data, corpus_name, sid), 
                            file=sys.stderr)

        for db_speaker_entry in session.query(backend.Speaker).filter(
                backend.Speaker.age_raw.like("%;%.%")):
                db_speaker_entry.age = db_speaker_entry.age_raw
                db_speaker_entry.age_in_days = age.calculate_xml_days(
                        db_speaker_entry.age_raw)

        for db_speaker_entry in session.query(backend.Speaker).filter(
                ~backend.Speaker.age_raw.like("None"),
                ~backend.Speaker.age_raw.like("%Un%"),
                backend.Speaker.age == None,
                backend.Speaker.session_id_fk == sid):
            if not cleaned_age.fullmatch(db_speaker_entry.age_raw):
                try:
                    ages = age.clean_incomplete_ages(db_speaker_entry.age_raw)
                    db_speaker_entry.age = ages[0]
                    db_speaker_entry.age_in_days = ages[1]
                except ValueError as e:
                    print("Error: Couldn't transform age of speaker {}"
                            .format(db_speaker_entry.id), file=sys.stderr)
                    print("Age data {} could not be converted to int\n"
                            "Check data in {} file {}"
                        .format(db_speaker_entry.age_raw, corpus_name, sid),
                        file=sys.stderr)
                    print("Warning: this speaker is likely to be "
                            "completely without age data in the DB!")


@db_apply
def update_age(session, config):
    """Helper function for age unification. Checks the config for the metadata format of the corpus,
        then calls the appropriate function.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    if config["metadata"]["type"] == "imdi":
        update_imdi_age(session, config)
    else:
        update_xml_age(session, config)


@db_apply
def unify_labels(session, config):
    """Performs key-value substitutions for morphological glosses and parts-of-speech in the database. If no key is
        defined in the corpus ini file, then None (NULL) is written to the database.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.

    # TODO: Insert some debugging here if the labels are missing?
    """
    corpus_name = config["corpus"]["corpus"]
    for row in session.query(backend.Morpheme).filter(backend.Morpheme.corpus == corpus_name):
        row.gloss = config['gloss'].get(row.gloss_raw, None)
        row.pos = config['pos'].get(row.pos_raw, None)


@db_apply
def get_word_pos(session, config):
    """
    Populates word POS from morphemes table by taking the first non "pfx" or "sfx" value.

    # TODO: Insert some debugging here if the labels are missing?
    """

    corpus_name = config["corpus"]["corpus"]
    for row in session.query(backend.Morpheme).filter(backend.Morpheme.corpus == corpus_name):
        # get word_id_fk
        word_id_fk = row.word_id_fk
        pos = row.pos

        table = session.query(backend.Word).filter(backend.Word.id==word_id_fk)
        for result in table:
            if not pos in ["sfx", "pfx"]:
                result.pos = pos


@db_apply
def unify_roles(session,config):
    """Function to unify speaker roles and draw inferences to related values.

    Each corpus has its own set of speaker roles. This function uses
    "role_mapping.ini" to assign a unified role to each speaker according
    to the mappings in role_mapping.ini. The mapping is either based on the original
    role or the speaker_label (depending on how the corpora handles role encoding).
    The role column in the speaker table contains the unified roles.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    
    table = session.query(backend.Speaker)
    cfg_mapping = ConfigParser(delimiters=('='))
    cfg_mapping.optionxform = str
    cfg_mapping.read("role_mapping.ini")
    not_found = set()
    
    for row in table:
        # map role if possible
        try:
            row.role = cfg_mapping['role_mapping'][row.role_raw]
        # otherwise remember role
        except KeyError:
            row.role = row.role_raw
            not_found.add((row.role_raw,row.corpus))
        
        # inference to gender
        if (row.gender_raw is None or row.gender_raw in ['Unspecified', 'Unknown']):
            try:
                row.gender = cfg_mapping['role2gender'][row.role_raw]
            except KeyError:
                pass
        
        # inference to age (-> macrorole)
        if (row.macrorole is None or row.macrorole in ['Unspecified', 'Unknown']):
            try:
                row.macrorole = cfg_mapping['role2macrorole'][row.role_raw]
                # make sure None is not taken as a string
                if row.macrorole == 'None':
                    row.macrorole = None
            except KeyError:
                pass

    if len(not_found) > 0:
        print("-- WARNING --")
        for item in not_found: 
            print("'"+item[0]+"'","from",item[1])
        print("not found in role_mapping.ini\n--------")


@db_apply
def unify_gender(session, config):
    """Function to unify speaker genders.

    There are different ways to write a speaker's gender. This
    function unifies the spelling. The column gender in the speakertable
    contains the unified genders.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    table = session.query(backend.Speaker)
    for row in table:
        if row.gender is not None:
            continue
        if row.gender_raw is not None:
            if row.gender_raw.lower() == 'female':
                row.gender = 'Female'
            elif row.gender_raw.lower() == 'male':
                row.gender = 'Male'
            else:
                row.gender = "Unspecified"
        else:
            row.gender = "Unspecified"


@db_apply
def macrorole(session, config):
    """Function to define macrorole (= Adult, Child, Target_Child, Unknown)

    This function assigns an age category to each speaker. If there is
    no information on age available it uses "role_mappings.ini" to define 
    which age category a speaker belongs to. The mapping is based on either
    the speaker's original role or speaker_label (depending on how the corpora
    handles role encoding).

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    
    table = session.query(backend.Speaker)
    cfg_mapping = ConfigParser(delimiters=('='))
    cfg_mapping.optionxform = str
    cfg_mapping.read("role_mapping.ini")

    for row in table:
        # check if macrorole is not already filled (by unify_roles)
        if row.macrorole is None:
            # first check age: Adults are >= 12yrs, i.e. > 4380 days
            if row.age_in_days is not None:
                if row.age_in_days <= 4380:
                    row.macrorole = "Child"
                else:
                    row.macrorole = "Adult"
            # second check corpus-specific lists of speaker labels
            else:
                try:
                    row.macrorole = cfg_mapping[row.corpus][row.speaker_label]
                except KeyError:
                    row.macrorole = "Unknown"

@db_apply
def unique_speaker(session, config):
    """  Creates a table containing unique speakers from all corpora. Also populates uniquespeaker foreign key ids
    in the speakers table

    Uniqueness is determined by a combination of speaker: name, speaker label, birthdate

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    unique_speakers = [] # unique speaker dicts for uniquespeakers table
    identifiers = [] # keep track of unique (name, label, birthdate) speaker tuples

    table = session.query(backend.Speaker)
    for row in table:
        # TODO: this logic should go away once Cree data is updated and be replaced with:
        # t = (row.name, row.speaker_label, row.birthdate)
        # see:
        # https://github.com/uzling/acqdiv/issues/366
        if row.corpus != 'Cree':
            t = (row.name, row.birthdate, row.speaker_label)
        else:
            t = (row.name, row.birthdate)

        if t not in identifiers:
            identifiers.append(t)

            # create unique speaker row
            d = {}
            d['id'] = identifiers.index(t) + 1 # Python lists start at 0!
            d['corpus'] = row.corpus
            d['speaker_label'] = row.speaker_label
            d['name'] = row.name
            d['birthdate'] = row.birthdate
            d['gender'] = row.gender
            unique_speakers.append(backend.UniqueSpeaker(**d))

        # insert uniquespeaker_fk_id in speakers table
        row.uniquespeaker_id_fk = identifiers.index(t) + 1

    # add all unique speakers entries to uniquespeakers table
    session.add_all(unique_speakers)

    # TODO: call method to propogate the to the other tables


@db_apply
def unify_indonesian_labels(session, config):
    """Function to match the labels of Indonesian speakers with the labels in the Indonesian utterances.
        
    Labels in the Indonesian utterances are longer and more specific than those in the metadata files.
    This function changes the labels in the speaker table to the corresponding labels in the utterances.
    For most speakers, this is done by appending the first three letters of the session label to the 
    speaker label. For those that are coded in the original metadata files as EXP, their identity is determined by their
    name and the appropriate label assigned as coded in the config.

    Finally, some specifically excluded labels (also in the config) are not changed at all.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    for db_session_entry in session.query(backend.Session).filter(backend.Session.corpus == "Indonesian"):
        sid = db_session_entry.id
        session_set = db_session_entry.source_id[0:3]
        for db_speaker_entry in session.query(backend.Speaker).filter(backend.Speaker.session_id_fk == sid):
            if db_speaker_entry.name in config["exp_labels"]:
                db_speaker_entry.speaker_label = config["exp_labels"][db_speaker_entry.name]
            elif (db_speaker_entry.speaker_label not in config["excluded_labels"] 
                    and db_speaker_entry.speaker_label[-3:] != session_set):
                db_speaker_entry.speaker_label = db_speaker_entry.speaker_label + session_set


@db_apply
def unify_timestamps(session, config):
    """Helper function to change utterance timestamps to a consistent format.

    This function queries the database for all timestamps and then calls the
    unify_timestamps function from age.py to unify the format.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    corpus_name = config["corpus"]["corpus"]
    for db_session_entry in session.query(backend.Session).filter(backend.Session.corpus == corpus_name):
        sid = db_session_entry.id
        for db_utterance_entry in session.query(backend.Utterance).filter(backend.Utterance.start_raw.isnot(None), 
                backend.Utterance.session_id_fk == sid):
            try:
                db_utterance_entry.start = age.unify_timestamps(db_utterance_entry.start_raw)
                db_utterance_entry.end = age.unify_timestamps(db_utterance_entry.end_raw)
            except Exception as e:
                print("Error unifying timestamps in corpus {}: {}".format(corpus_name, e))


@db_apply
def extract_chintang_addressee(session, config):
    """ Function that extracts addressee information for Chintang.
    
    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    for row in session.query(backend.Utterance):
        try:
            if re.search('directed|answer', row.addressee):
                ## reconstruct actor code for children from file name
                match_actor_code = re.search('^(CL.*Ch)(\\d)', row.source_id)
                child_prefix = match_actor_code.group(1)
                child_number = match_actor_code.group(2)
                # several addressees may be connected on a single tier via "+"
                for addressee in re.split('\+', row.addressee):                                
                    addressee = re.sub('.*target\\s*child.*(\\d).*', child_prefix + '\\1', addressee)
                    addressee = re.sub('.*target\\s*child.*', child_prefix + child_number, addressee)
                    addressee = re.sub('.*child.*', 'unspecified_child', addressee)
                    addressee = re.sub('.*adult.*', 'unspecified_adult', addressee)
                    addressee = re.sub('.*non(\\s*|\\-)directed.*', 'none', addressee)
                    
                    row.addressee = addressee
        except TypeError:
                pass


@db_apply
def clean_tlbx_pos_morphemes(session, config):
    """ Function that cleans pos and morphemes in Chintang and Indonesian.
        It also cleans the morpheme (for Chintang and Russian) and gloss_raw (Indonesian) column in the utterances
        table because cleaning them within the Toolbox parser messes up the morphemes table.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
    """
    if config["corpus"]["corpus"] == "Chintang":
        # get pfx and sfx
        for row in session.query(backend.Morpheme).filter(backend.Morpheme.corpus == "Chintang"):
            try:
                if row.pos_raw.startswith('-'):
                    row.pos = 'sfx'
                    row.pos_raw = 'sfx'
                elif row.pos_raw.endswith('-'):
                    row.pos = 'pfx'
                    row.pos_raw = 'pfx'
                else:
                    row.pos_raw = row.pos_raw.strip('-')
                    row.pos = row.pos_raw
                # strip '-' from morphemes and gloss_raw
                row.morpheme = row.morpheme.strip('-')
                row.gloss_raw = row.gloss_raw.strip('-')
                row.gloss = row.gloss.strip('-')
            except AttributeError:
                pass

    if config["corpus"]["corpus"] == "Indonesian":
        for row in session.query(backend.Morpheme).filter(backend.Morpheme.corpus == "Indonesian"):
            # get pfx and sfx, strip '-' from gloss_raw
            try:
                if row.gloss_raw.startswith('-'):
                    row.pos = 'sfx'
                    row.gloss_raw = row.gloss_raw.strip('-')
                elif row.gloss_raw.endswith('-'):
                    row.pos = 'pfx'
                    row.gloss_raw = row.gloss_raw.strip('-')
                elif row.gloss_raw == '???':
                    row.pos = '???'
                else:
                    row.pos = 'stem'
                row.morpheme = row.morpheme.strip('-')
            except AttributeError:
                pass
            except TypeError:
                pass


@db_apply
def clean_utterances_table(session, config):
    """ Function that cleans *** and xx(x) from utterances table.

    Args:
        session: SQLAlchemy session object.
        config: CorpusConfigParser object.
        """
    if config["corpus"]["corpus"] == "Chintang":
        # clean unknown morphemes (***) from utterances table
        for row in session.query(backend.Utterance).filter(backend.Utterance.corpus == "Chintang"):
            try:
                row.morpheme = re.sub('\*\*\*', '???', row.morpheme)
                row.gloss_raw = re.sub('\*\*\*', '???', row.gloss_raw)
                row.pos_raw = re.sub('\*\*\*', '???', row.pos_raw)
            except AttributeError:
                pass
            except TypeError:
                pass

    if config["corpus"]["corpus"] == "Russian":
        # clean garbage imported from chat (xxx|www)
        for row in session.query(backend.Utterance).filter(backend.Utterance.corpus == "Russian"):
            try:
                row.morpheme = re.sub('xxx?|www', '???', row.morpheme)
            except AttributeError:
                pass
            except TypeError:
                pass

    # clean garbage imported from chat (xxx|www)
    if config["corpus"]["corpus"] == "Indonesian":
        for row in session.query(backend.Utterance).filter(backend.Utterance.corpus == "Indonesian"):
            try:
                row.morpheme = re.sub('xxx?|www', '???', row.morpheme)
                row.gloss_raw = re.sub('xxx?|www', '???', row.gloss_raw)
                row.utterance_raw = re.sub('xxx?|www', '???', row.utterance_raw)
                row.translation = re.sub('xxx?|www', '???', row.translation)
            except AttributeError:
                pass
            except TypeError:
                pass

def main():
    # default set to test database
    engine = sa.create_engine('sqlite:///tests/test.sqlite3')
    meta = sa.MetaData(engine, reflect=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    configs = ['Chintang.ini', 'Cree.ini', 'Indonesian.ini', 'Inuktitut.ini', 'Japanese_Miyata.ini',
                'Japanese_MiiPro.ini', 'Russian.ini', 'Sesotho.ini', 'Turkish.ini', 'Yucatec.ini']

    # Parse the config file and call the sessions processor
    for config in configs:
        cfg = CorpusConfigParser()
        cfg.read("ini/"+config)

        # Do some postprocessing
        # TODO: test if moving this outside of the loop is faster
        print("Postprocessing database entries for {0}...".format(config.split(".")[0]))

        update_age(cfg, engine)
        unify_timestamps(cfg, engine)
        unify_gender(cfg, engine)

        if config == 'Indonesian.ini':
            unify_indonesian_labels(cfg, engine)
            clean_tlbx_pos_morphemes(cfg, engine)
            clean_utterances_table(cfg, engine)

        if config == 'Chintang.ini':
            extract_chintang_addressee(cfg, engine)
            clean_tlbx_pos_morphemes(cfg, engine)
            clean_utterances_table(cfg, engine)

        if config == 'Russian.ini':
            clean_utterances_table(cfg, engine)

        # This seems to need to be applied after the clean_tlbx_pos_morphemes... which should be moved to the parser.
        unify_labels(cfg, engine)
        get_word_pos(cfg, engine)

    print("Calculating role entries.\n")
    unify_roles(cfg, engine)

    print("Calculating macrorole entries.\n")
    macrorole(cfg, engine)

    print("Calculating unique speaker table.\n")
    # unique_speaker(cfg, engine)

if __name__ == "__main__":
    import time
    import sys
    print("Postprocessing the database without compiling it...  ")
    start_time = time.time()
    main()
    print("--- %s seconds ---" % (time.time() - start_time))