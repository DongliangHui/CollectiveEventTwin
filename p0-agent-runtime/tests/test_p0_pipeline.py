import json
import tempfile
import unittest
from pathlib import Path

from worldline_p0.cli import main
from worldline_p0.pipeline import run_p0_pipeline


class P0PipelineTest(unittest.TestCase):
    def test_builds_signal_map_and_closed_loop_bundle_from_allowed_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "source_registry.json"
            records = root / "records.json"
            gazetteer = root / "gazetteer.json"

            registry.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "local_news",
                                "name": "Local News",
                                "platform": "news",
                                "access_mode": "public_web",
                                "status": "active",
                                "trust": 0.82,
                            },
                            {
                                "id": "douyin_authorized",
                                "name": "Douyin Authorized Export",
                                "platform": "douyin",
                                "access_mode": "authorized_export",
                                "status": "active",
                                "trust": 0.68,
                            },
                            {
                                "id": "private_group",
                                "name": "Private Group",
                                "platform": "private_chat",
                                "access_mode": "private_or_bypassed",
                                "status": "active",
                                "trust": 0.1,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            records.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "id": "RAW-1",
                                "source_id": "local_news",
                                "content_type": "text",
                                "title": "School response questioned",
                                "text": "Qinglan School gate has family gathering and questions about hidden facts.",
                                "published_at": "2026-05-02T10:06:00+08:00",
                                "location_hint": "Qinglan School",
                                "metrics": {"comments": 120, "shares": 45, "views": 20000},
                            },
                            {
                                "id": "RAW-2",
                                "source_id": "douyin_authorized",
                                "content_type": "video",
                                "title": "Gate video spreads",
                                "text": "Short video OCR shows school gate, police car, crowd, and response gap.",
                                "media": {
                                    "ocr_text": ["school gate", "give explanation"],
                                    "asr_text": "family asks for evidence preservation",
                                    "scene_tags": ["crowd", "school_gate"],
                                },
                                "published_at": "2026-05-02T10:12:00+08:00",
                                "location_hint": "Qinglan School",
                                "metrics": {"comments": 320, "shares": 180, "views": 98000},
                            },
                            {
                                "id": "RAW-3",
                                "source_id": "private_group",
                                "content_type": "text",
                                "title": "Should be blocked",
                                "text": "This private source must not be collected.",
                                "published_at": "2026-05-02T10:13:00+08:00",
                                "location_hint": "Qinglan School",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            gazetteer.write_text(
                json.dumps(
                    {
                        "places": [
                            {
                                "name": "Qinglan School",
                                "region_id": "campus-core",
                                "lon": 120.1348,
                                "lat": 30.2825,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            bundle = run_p0_pipeline(registry, records, gazetteer)

        self.assertEqual(bundle["collection"]["blocked_count"], 1)
        self.assertEqual(bundle["collection"]["accepted_count"], 2)
        self.assertGreaterEqual(len(bundle["signals"]), 1)
        first_signal = bundle["signals"][0]
        self.assertEqual(first_signal["regionId"], "campus-core")
        self.assertGreater(first_signal["scores"]["onlineHeat"], 0)
        self.assertIn("evidence", first_signal)
        self.assertTrue(bundle["mapLayers"]["eventPoints"]["features"])
        self.assertTrue(bundle["mapLayers"]["heatZones"]["features"])
        self.assertEqual(bundle["mainlines"][0]["status"], "world_state_ready")
        self.assertEqual(bundle["worldStates"][0]["status"], "world_state_ready")
        self.assertTrue(bundle["worldlineNodes"])
        self.assertTrue(bundle["councilResults"])
        self.assertTrue(bundle["reports"][0]["tasks"])

    def test_cli_writes_bundle_and_map_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "source_registry.json"
            records = root / "records.json"
            gazetteer = root / "gazetteer.json"
            output = root / "out"

            registry.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "manual_upload",
                                "name": "Manual Upload",
                                "platform": "manual",
                                "access_mode": "manual_upload",
                                "status": "active",
                                "trust": 0.7,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            records.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "id": "RAW-CLI-1",
                                "source_id": "manual_upload",
                                "content_type": "image",
                                "title": "Crowd image uploaded",
                                "text": "Manual upload reports crowd at Qinglan School.",
                                "media": {"ocr_text": ["school response"], "scene_tags": ["crowd"]},
                                "published_at": "2026-05-02T11:00:00+08:00",
                                "location_hint": "Qinglan School",
                                "metrics": {"comments": 40, "shares": 12, "views": 5000},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            gazetteer.write_text(
                json.dumps(
                    {
                        "places": [
                            {
                                "name": "Qinglan School",
                                "region_id": "campus-core",
                                "lon": 120.1348,
                                "lat": 30.2825,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--source-registry",
                    str(registry),
                    "--records",
                    str(records),
                    "--gazetteer",
                    str(gazetteer),
                    "--output-dir",
                    str(output),
                ]
            )

            bundle = json.loads((output / "p0_bundle.json").read_text(encoding="utf-8"))
            map_layers = json.loads((output / "map_layers.generated.json").read_text(encoding="utf-8"))
            static_demo = json.loads((output / "demo-data.generated.json").read_text(encoding="utf-8"))
            static_map = json.loads((output / "map-layers.static.generated.json").read_text(encoding="utf-8"))
            static_geo = json.loads((output / "geo-points.static.generated.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(bundle["collection"]["accepted_count"], 1)
        self.assertTrue(map_layers["eventPoints"]["features"])
        self.assertTrue(map_layers["heatZones"]["features"])
        self.assertIn("dashboard", static_demo)
        self.assertTrue(static_demo["tasks"])
        self.assertIn("riskAreas", static_map)
        self.assertTrue(static_geo["points"])


if __name__ == "__main__":
    unittest.main()
