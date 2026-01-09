import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature

npg = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000', '#7E6148', '#B09C85']

hazard_labels = {
    "fluvial": "Fluvial flood",
    "pluvial": "Pluvial flood",
    "coastal": "Coastal flood",
    "cyclone": "Cyclone wind",
    "landslide": "Landslide",
    "hd35": "Days above 35°C",
    "tasmax": "Maximum temperature",
}

def clean_sci_formatter(x, pos):
    """Format with scientific notation but without leading zeros in exponent."""
    if x == 0:
        return '0'
    # Format with scientific notation
    s = f'{x:.3g}'
    # If it contains 'e', clean up the exponent
    if 'e' in s:
        base, exp = s.split('e')
        exp = str(int(exp))  # Remove leading zeros/plus signs
        return f'{base}e{exp}'
    return s


# def create_white_to_color_cmap(hex_color, white="beige", name='custom_cmap'):
#     colors = [white, hex_color]
#     cmap = mcolors.LinearSegmentedColormap.from_list(name, colors)#, gamma=.4)
#     return cmap

def create_white_to_color_cmap(hex_color, white="beige", white_fraction=0.7, name='custom_cmap'):
    """
    white_fraction: 0 = start from hex_color, 1 = start from pure white/beige
    """
    rgb = mcolors.to_rgb(hex_color)
    white_rgb = mcolors.to_rgb(white)
    # Blend towards white
    light_rgb = tuple(w * white_fraction + c * (1 - white_fraction) for w, c in zip(white_rgb, rgb))
    colors = [light_rgb, hex_color]
    cmap = mcolors.LinearSegmentedColormap.from_list(name, colors)
    return cmap

def add_geofeatures(ax):
    ax.add_feature(cfeature.BORDERS, color='k', linestyle=':', alpha=0.5, linewidth=0.5)
    ax.add_feature(cfeature.LAND, color="#D9D7D3")
    # ax.add_feature(cfeature.LAKES, color='#7ABAEC', edgecolor='navy', zorder=10)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.OCEAN, color='#7ABAEC', zorder=0)
    gl = ax.gridlines(draw_labels=False, linewidth=.1, color='#7D6E63', alpha=0.5, x_inline=False, y_inline=False)
    gl.top_labels = False
    gl.right_labels = False
    return ax