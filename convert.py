import argparse

from textscratch.project_io import convert_folder_to_sb3, convert_project

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for converting Scratch projects."""
    parser = argparse.ArgumentParser(
        description="Convert between Scratch .sb3 archives and scratchblocks project folders.",
    )
    parser.add_argument(
        "input",
        help="Path to the .sb3 project file (for extraction) or to a project folder (for packing)",
    )
    parser.add_argument(
        "--output-dir",
        default="Project",
        help="Output directory when extracting a .sb3 archive",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove the output directory before writing extracted files",
    )
    parser.add_argument(
        "--to-sb3",
        action="store_true",
        help="Pack a project folder back into a .sb3 archive instead of extracting",
    )
    parser.add_argument(
        "--sb3-output",
        default="output.sb3",
        help="Output .sb3 path when using --to-sb3",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.to_sb3:
        convert_folder_to_sb3(args.input, args.sb3_output)
    else:
        convert_project(args.input, args.output_dir, clean=not args.no_clean)


if __name__ == "__main__":
    main()
