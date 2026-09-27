"""外部依存なしのテスト（numpy は必要）。実行: python -m unittest discover -s tests"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

import settings as config
from catalog import build as catalog
from catalog import project_list
from music import batch, midi
from music.score import Cue, Note, Scale, ScoreError, role_of
from reaper.runner import to_lua
from tools import skills as skills_sync


def loop_cue(**kw):
    notes = [
        Note("Melody", 0, 1, 72),
        Note("Bass", 0, 2, 48, voice="bass"),
        Note("Kick", 1, 0.25, 36, voice="kick"),
    ]
    args = {
        "id": "bgm_01",
        "title": "テスト",
        "category": "bgm",
        "bpm": 120,
        "meter": "4/4",
        "length": 4,
        "loop": True,
        "notes": notes,
    }
    args.update(kw)
    return Cue(**args)


class TempRepo:
    """config のパスを一時フォルダへ差し替える。"""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = {
            k: getattr(config, k)
            for k in ("LIBRARY", "PROJECT_LISTS", "PROJECTS")
        }
        self.saved_output = catalog.OUTPUT
        for k in self.saved:
            setattr(config, k, root / k.lower())
            (root / k.lower()).mkdir()
        catalog.OUTPUT = config.LIBRARY / "index.html"
        return root

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(config, k, v)
        catalog.OUTPUT = self.saved_output
        self.tmp.cleanup()


class ScoreTest(unittest.TestCase):
    def test_scale(self):
        s = Scale(60, "major")
        self.assertEqual(
            [s.note(0), s.note(4), s.note(7), s.note(-1)], [60, 67, 72, 59]
        )
        self.assertEqual(s.chord(0), [60, 64, 67])

    def test_roles(self):
        self.assertEqual(
            [
                role_of(p)
                for p in ["Kick", "Hi-Hat", "Bass", "Harmony", "Arp", "Melody"]
            ],
            ["drum", "drum", "bass", "pad", "arp", "lead"],
        )

    def test_validation_errors(self):
        bad = [
            loop_cue(length=3),  # 小節境界でない
            loop_cue(notes=[Note("Melody", -1, 1, 60)]),  # 負の開始
            loop_cue(notes=[Note("Melody", 0, 1, 130)]),  # 音域外
            loop_cue(
                notes=[Note("Melody", 0, 1, 60, voice="x")]
            ),  # 未知の音色
            loop_cue(notes=[Note("Melody", 5, 1, 60)]),  # 曲の長さを超える
            loop_cue(id="Bad ID"),
            loop_cue(bpm=None),
        ]
        for cue in bad:
            with self.assertRaises(ScoreError):
                cue.validate()

    def test_overlap_trim(self):
        cue = loop_cue(
            notes=[Note("Melody", 0, 2, 60), Note("Melody", 1, 1, 60)]
        )
        fixes = cue.validate()
        self.assertEqual(len(fixes), 1)
        self.assertEqual(cue.notes[0].dur, 1)

    def test_oneshot_length(self):
        cue = Cue(
            id="se", title="SE", category="se", notes=[Note("Lead", 0, 1, 72)]
        )
        cue.validate()
        self.assertAlmostEqual(cue.duration, 0.5 + 0.05)


class MidiTest(unittest.TestCase):
    def test_roundtrip_with_glide(self):
        cue = loop_cue(
            meter="6/8",
            length=3,
            notes=[
                Note("Lead", 0, 1, 72, glide=-7),
                Note("Lead", 1, 0.5, 72, 80),
                Note("Bass", 0.5, 1.5, 40, voice="bass"),
            ],
        )
        cue.validate()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.mid"
            midi.write_midi(cue, path)
            self.assertEqual(
                midi.read_midi_notes(path), midi.expected_notes(cue)
            )

    def test_broken_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.mid"
            path.write_bytes(b"MThd" + b"\0" * 10)
            with self.assertRaises(ValueError):
                midi.read_midi_notes(path)


class PipelineDataTest(unittest.TestCase):
    def test_render_project_list_catalog(self):
        with TempRepo():
            compose = batch.new_batch("unit", example=True)
            report = batch.render(compose.parent.name, log=lambda *_: None)
            self.assertTrue(report["ok"], report["failures"])
            with self.assertRaises(batch.BatchError):
                batch.render(
                    compose.parent.name, log=lambda *_: None
                )  # --force なしの再書き出しは拒否
            rows = json.loads(
                (compose.parent / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(rows), 3)

            first = config.PROJECT_LISTS / "project-list-old.json"
            first.write_text(
                json.dumps({"items": [rows[0]["key"]]}), encoding="utf-8"
            )
            time.sleep(0.05)
            latest = config.PROJECT_LISTS / "latest.json"
            latest.write_text(
                json.dumps(
                    {
                        "format": project_list.FORMAT,
                        "items": [
                            {"batch": rows[1]["batch"], "id": rows[1]["id"]},
                            rows[1]["key"],
                            rows[2]["key"],
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                project_list.latest(
                    {"downloads_dir": str(config.PROJECT_LISTS / "none")}
                ),
                latest,
            )
            sel = project_list.load(latest)
            self.assertEqual(
                [i["id"] for i in sel["items"]], [rows[1]["id"], rows[2]["id"]]
            )  # 重複は除く
            latest.write_text(
                json.dumps({"items": [rows[0]["batch"] + "/missing"]}),
                encoding="utf-8",
            )
            with self.assertRaises(project_list.ProjectListError):
                project_list.load(latest)

            # 音声のみの取り込み素材は登録できるが、プロジェクト生成リストには入れられない
            wav = compose.parent / rows[0]["path"]
            only = Cue(id="audio_only", title="音声のみ", category="talk")
            batch.import_audio(
                "20260101-imported",
                {
                    "title": "取り込み",
                    "created": "2026-01-01T00:00:00",
                    "categories": [{"id": "talk", "label": "会話"}],
                },
                [{"cue": only, "audio": wav}],
                log=lambda *_: None,
            )
            latest.write_text(
                json.dumps({"items": ["20260101-imported/audio_only"]}),
                encoding="utf-8",
            )
            with self.assertRaises(project_list.ProjectListError):
                project_list.load(latest)

            html = catalog.build().read_text(encoding="utf-8")
            self.assertNotIn("__DATA__", html)
            self.assertIn(rows[0]["key"], html)


class ProfileTest(unittest.TestCase):
    def test_priority(self):
        from reaper import profiles

        self.assertEqual(
            profiles.resolve(["massive"], ["magical8bit"])[0], ["massive"]
        )  # --profiles が最優先
        self.assertEqual(
            profiles.resolve(None, ["magical8bit", "reasynth"])[0],
            ["magical8bit", "reasynth"],
        )
        self.assertEqual(
            profiles.resolve(None, None)[0], config.load()["profiles"]
        )
        with self.assertRaises(profiles.ProfileError):
            profiles.resolve(["unknown"], None)
        self.assertTrue(
            any(p["name"] == "reasynth" for p in profiles.available())
        )

    def test_default_is_reasynth(self):
        self.assertEqual(config.DEFAULTS["profiles"], ["reasynth"])


class MiscTest(unittest.TestCase):
    def test_to_lua(self):
        self.assertEqual(
            to_lua({"a": [1, 2.5, True, None, '日本"語']}),
            '{["a"]={1,2.5,true,nil,"日本\\"語"}}',
        )

    def test_skills_in_sync(self):
        self.assertEqual(
            skills_sync.differences(),
            [],
            "python python/cli.py sync-skills を実行してください",
        )

    def test_profiles_have_plugin_and_label(self):
        for path in config.PROFILES_DIR.glob("*.lua"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("plugin = '", text, path.name)
            self.assertIn("label = '", text, path.name)
            self.assertIn("configure = function", text, path.name)


if __name__ == "__main__":
    unittest.main()
