# TextScratch to SB3 pipeline repairs

The conversion pipeline now handles nested expressions without greedy template
matching, preserves literal numeric spelling, and distinguishes literals from
variable/list reporters. It supports explicit global/local data selection,
boolean procedure parameters, escaped procedure labels, inline comments, and
control bodies with optional indentation and blank lines.

SB3 emission fixes cover input shadows and their numeric types, dynamic menu
reporters, procedure argument types/defaults, stop-block mutations, canonical pen
opcodes, glide menus, and registration of broadcast and automatically created data
IDs. Standalone variable/list reporters are retained.

Extraction and packing preserve sprite identity/order, Stage settings, sound
metadata, original asset bytes, and comments. Asset ordering works beyond 999
files, targets without costumes receive a packaged blank costume, and missing
assets fail explicitly. Output replacement is atomic. Manager operations handle
imported variables without monitors and allocate fresh IDs for duplicated data.

Serialization was checked against the
[TurboWarp SB3 serializer](https://github.com/TurboWarp/scratch-vm/blob/develop/src/serialization/sb3.js)
and [goboscript source](https://github.com/aspizu/goboscript).

## Completed validation

- The latest regression run passed all 29 tests.
- An Antimatter Engine V2 [ALPHA] round trip matched the executable graphs across
  all 14 targets. All 395 original assets were byte-for-byte intact.
- That rebuilt archive loaded and ran in TurboWarp Desktop, rendering the scene
  at approximately 30 FPS.

The Antimatter and Desktop checks preceded the final escaped-procedure-label and
comment/terminator refinements. Those refinements passed the regression suite;
the full round trip and Desktop check were not repeated afterward.

## Limits

This is not an exact JSON round trip. Generated block IDs and layout change,
unreachable blocks may be omitted, and input shadows can be normalized. The
Antimatter source contained 12 monitors for missing sprites and eight comments
whose block IDs did not exist: those monitors were omitted and those comments
were preserved detached. Monitor value caches are regenerated from current data.

Comment attachment restoration uses structural positions and opcodes, so edits
that rearrange code can affect attachment accuracy. Unsupported extension opcodes
remain outside the implemented block mapping. The graph comparator does not
validate all metadata or prove runtime equivalence for every possible input.
