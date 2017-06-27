Navigation icons are borrowed from Mapbox's [directions-icons][1],
available under the CC0 license. Icons are used as-is except for simple
renaming and color-inversion.

```bash
rename "s/_/-/g" *.svg
sed -i "s/#000000/#ffffff/g" *.svg
```

In addition, a ferry icon was borrowed from Mapbox's Maki icon set
[maki][2]. The ferry icon (15x15) was used with the color inversion
and scaled to fit 20x20 pixel size document.

[1]: https://github.com/mapbox/directions-icons
[2]: https://github.com/mapbox/maki
