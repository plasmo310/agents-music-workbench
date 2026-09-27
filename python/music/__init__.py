"""作曲データ（スコア）・試聴用シンセ・MIDI・バッチ書き出し。

compose.py からは `from music import Cue, Note, Scale` で使う。
"""
from music.score import MODES, VOICES, Cue, Note, Scale, ScoreError

__all__ = ['Cue', 'Note', 'Scale', 'ScoreError', 'MODES', 'VOICES']
