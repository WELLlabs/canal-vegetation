Place trained weights here (not committed):

- best_binary_unet_v5_lines.pth    # preferred (line-tuned, notebook 07)
- best_binary_unet_v5.pth          # fallback (notebook 05)

The loader never uses random or ImageNet encoder weights at inference.
`model_version` in output metadata is the filename that was actually loaded.

FIC UNet weights are not used in Phase 1.

Override with MODEL_DIR / MODEL_ROOT / MODEL_V5_PATH / MODEL_V5_LINES_PATH.
