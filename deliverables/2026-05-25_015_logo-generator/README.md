# Deliverable 015 — Logo Generator

> Generates AI Studio Accademia Milano logos in multiple styles and sizes.  
> Output: PNG files ready for social profiles, app icons, developer portals.

## Setup

```bash
pip install Pillow
```

## Usage

### All styles at once (default 300px)
```bash
python logo_generator.py
```

### One style
```bash
python logo_generator.py --style circle
python logo_generator.py --style square
python logo_generator.py --style minimal
```

### Custom size (e.g. 512px for high-res)
```bash
python logo_generator.py --size 512
```

### Custom accent color
```bash
python logo_generator.py --accent "#FF6B35"
```

### Custom output path
```bash
python logo_generator.py --style circle --size 300 --out my_logo.png
```

## Styles

| Style | Description | Best for |
|-------|-------------|----------|
| `circle` | Dark bg, cyan ring, AI + STUDIO text | LinkedIn, Twitter, app icons |
| `square` | Dark bg, rounded border, AI + STUDIO text | GitHub, Discord, Product Hunt |
| `minimal` | No border, accent bar separator | Favicons, Telegram, minimal UIs |

## Output

All files saved to `output/`:
```
output/aistudio_logo_circle_300.png
output/aistudio_logo_square_300.png
output/aistudio_logo_minimal_300.png
```

## Programmatic use

```python
from logo_generator import generate, generate_all

# Single logo
path = generate(style="circle", size=300)

# All styles
paths = generate_all(size=512, accent="#FF6B35")
```
