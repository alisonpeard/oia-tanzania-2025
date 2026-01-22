import matplotlib.colors as mcolors
import cartopy.feature as cfeature


__all__ = ["palette", "create_white_to_color_cmap"]


palette = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488',
               '#F39B7F', '#8491B4', '#91D1C2', '#DC0000',
               '#7E6148', '#B09C85']


def create_white_to_color_cmap(hex_color, name='custom'):
    """Create a colormap that goes from white to a specified color.
    
    >>> cmap = create_white_to_color_cmap(palette[0])
    """
    colors = ['beige', hex_color]
    cmap = mcolors.LinearSegmentedColormap.from_list(name, colors)#, gamma=.4)
    return cmap