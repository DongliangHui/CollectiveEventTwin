import argparse
from pathlib import Path

from .io import write_json
from .pipeline import run_p0_pipeline
from .static_adapter import to_static_demo_data, to_static_geo_points, to_static_map_layers


def build_parser():
    parser = argparse.ArgumentParser(description="Run the Worldline Observer P0 collection agent runtime.")
    parser.add_argument("--source-registry", required=True, help="Path to source registry JSON.")
    parser.add_argument("--records", required=True, help="Path to raw record JSON.")
    parser.add_argument("--gazetteer", required=True, help="Path to local gazetteer JSON.")
    parser.add_argument("--output-dir", required=True, help="Directory where generated artifacts are written.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    bundle = run_p0_pipeline(args.source_registry, args.records, args.gazetteer)
    output_dir = Path(args.output_dir)
    write_json(output_dir / "p0_bundle.json", bundle)
    write_json(output_dir / "map_layers.generated.json", bundle["mapLayers"])
    write_json(output_dir / "signals.generated.json", {"signals": bundle["signals"]})
    write_json(output_dir / "demo-data.generated.json", to_static_demo_data(bundle))
    write_json(output_dir / "map-layers.static.generated.json", to_static_map_layers(bundle))
    write_json(output_dir / "geo-points.static.generated.json", to_static_geo_points(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
