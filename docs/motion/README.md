# Feature animation source

`motion.html` is a 1280×720 motion piece driven by a pure `seek(t)` function; `render.js` steps it frame by frame
with Playwright. To re-render:

```bash
cd docs/motion
npm i playwright @fontsource/bricolage-grotesque@5 @fontsource/atkinson-hyperlegible@5 @fontsource/ibm-plex-mono@5
node render.js 30                       # → frames/f0000.png …
ffmpeg -framerate 30 -i frames/f%04d.png -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart ../vocab-garden-features.mp4
ffmpeg -framerate 30 -i frames/f%04d.png -vf "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" ../vocab-garden-features.gif
```
