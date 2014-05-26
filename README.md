# ![create pairs layers](resources/icon.png) ![create pairs layers](resources/icon.png) ![create pairs layers](resources/icon.png) VectorBender ![create pairs layers](resources/icon.png) ![create pairs layers](resources/icon.png) ![create pairs layers](resources/icon.png)

VectorBender is an __EXPERIMENTAL__ QGIS Python plugin allowing to adjust vector layers that have complex non-uniform and non-linear deformations (historical maps, hand drawn sketches, poorly digitized layers...). Using this layer will __INDUCE DEFORMATIONS__. You should __ONLY__ use this plugin if your data is already deformed, and not to accomplish CRS transformations nor linear/affine transformations.

[Have a look at the presentation video !](https://vimeo.com/96142479)


## How to use

Launch VectorBender from the plugins menu or from the plugin toolbar.

VectorBender works a bit like the georeferencer : you have to create pairs of points, the first one being the original location, and the second one being the target location.

To do so, VectorBender uses plain Linestring layers. Each pair is defined by the starting point and ending point of a Line in this layer.
You can either use one of your own Linestring layers, or use the ![create pairs layers](resources/mActionCaptureLine.png) button from the VectorBender window. If you do so, I recommend installing the "Save memory layer" plugin which will allow to save your work in case of crash (you never now).

The "buffer" parameters sets a buffer around the triangulation, so that the transformation ends more smoothely on the edges. Use the "toggle preview" button to see the effects.

Once the layer to bend and the pairs layer are chosen, simply hit "run", and voilà ! the layer is modified.
You can still undo / revert the changes if you like.


### Unmet dependencies ?!

This plusing relies on :

- matplotlib 1.3.0
- scipy 0.14.0

If you miss those libraries, you won't be able to use the plugin at all, and it will be grayed out.
If you have older versions, it will probably not work (not tested).

On Windows, they can be installed using OSGeo4W 64 bits version, in the libraries category.
Please send me an email me if you encoutered this problem and solved it, so I can update this readme.


## Feedback / Bugs / Contribute

Please report bugs and ideas on the issue tracker : https://github.com/olivierdalang/VectorBender/issues

Or send me some feedback at : olivier.dalang@gmail.com


## Version history

- 2014-05-22 - Version 0.0 : intial release
- 2014-05-25 - Version 0.1 : scipy dependency no more needed, different style for pinned points


## Roadmap

### Confirmed

- remove dependecy to matplotlib as well
- do a translation when only one pair, do a conform transformation when only two vectors as set, do a linear transformation when only three are set, do the complex algorithm only when more than three vectors are set.
- allow to apply to selection only
- allow to modify the PairsLayers so that every processed point becomes a pinned point, so it's possible to work more incrementally


### Not confirmed

- allow to use different algorithms ? (like TLS)


## How it works (internally)

Here's how it works :

Preparing the mesh

1. Get a triangular mesh by doing a Delaunay triangulation of all original input points (starting points of the lines in the Vector Bender layer)
2. Adapt this mesh on the ending points of the lines
3. Get the convex hull of the points, offset it by some factor to have a smooth transition on the borders.

Doing the transformation

1. For each point of the target layer, find in which triangle it lies, and get it's barycentric coordinates in that triangle. apply those barycentric coordinates to the adapted mesh.


