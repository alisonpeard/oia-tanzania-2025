import matplotlib.colors as mcolors
import cartopy.feature as cfeature

npg_palette = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488',
               '#F39B7F', '#8491B4', '#91D1C2', '#DC0000',
               '#7E6148', '#B09C85']

def create_white_to_color_cmap(hex_color, name='custom_cmap'):
    """Create a colormap that goes from white to a specified color.
    
    >>> cmap = create_white_to_color_cmap(npg_palette[0])
    """
    colors = ['beige', hex_color]
    cmap = mcolors.LinearSegmentedColormap.from_list(name, colors)#, gamma=.4)
    return cmap


def make_floodcmap():
    """Low contrast flood depth colormap."""
    flood_colours = ["#B3D7F2", "#7ABAEC", "#4A94E1", "#2070C8", "#0D47A1"]
    flood_cmap = mcolors.LinearSegmentedColormap.from_list("vivid_flood", flood_colours, gamma=0.4)
    return flood_cmap

flood_over = "#0A3A85"
cmaps = {
    "fig3": [
        create_white_to_color_cmap(npg_palette[0], "historical"),
        create_white_to_color_cmap(npg_palette[1], "rcp45"),
        create_white_to_color_cmap(npg_palette[2], "rcp85"),
    ],
    "fig4": "YlGnBu",
    "fig5": "YlOrRd",
    "fig8": "coolwarm"
}


map_colours = {
    "permwater": "#003366",
    "majorroad": "#8D8680",
    "minorroad": "#DEDAD0",
    "floodcmap": make_floodcmap(),
    "floodboundary": "#2070C8",
    "regionofinterest": "#F0EEE9",
    "exposedroad": "r",
    "pointofinterest": "yellow",
    "geoboundaries": "#7D6E63",
    "background": "#D9D7D3"
}