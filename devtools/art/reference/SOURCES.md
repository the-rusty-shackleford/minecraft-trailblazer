# Cosmetic reference inputs

The original source is nfx's Blockbench project from `v1.6.0`, preserved byte for byte.
Copyright 2026 Rusty Shackleford and nfx; AGPL-3.0-or-later.

- `trailblazer-before-cosmetics.bbmodel` SHA-256: `765547b5382cb381f58512c0163cae45473004fd482daf4e3d2dacd1dc4f9ce5`
- `released-profile.json` SHA-256: `8d2a983e6fc08c4f15550ffeda7f32363def2049aff9ef40e27b35a085cad9cc`

`../preview/trailblazer.bbmodel` is the intentional cosmetic derivative approved by Rusty
on 2026-09-16. It is not a verbatim collaborator delivery. See D-0005.
Automobility 0.5.0.h's steel motorcar supplied a finish reference; none of its geometry
or textures are included in this derivative.

The profile is a frozen comparison input. The importer checks it before exporting
meshes and never rewrites gameplay data. Review a future gameplay change separately;
do not regenerate or refresh this reference merely to bypass that guard.
