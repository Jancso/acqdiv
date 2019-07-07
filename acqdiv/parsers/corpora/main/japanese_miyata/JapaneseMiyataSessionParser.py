from acqdiv.parsers.chat.CHATParser import CHATParser
from acqdiv.parsers.corpora.main.japanese_miyata.JapaneseMiyataReader import \
    JapaneseMiyataReader
from acqdiv.parsers.corpora.main.japanese_miyata.JapaneseMiyataCleaner import \
    JapaneseMiyataCleaner


class JapaneseMiyataSessionParser(CHATParser):
    @staticmethod
    def get_reader(session_file):
        return JapaneseMiyataReader(session_file)

    @staticmethod
    def get_cleaner():
        return JapaneseMiyataCleaner()
