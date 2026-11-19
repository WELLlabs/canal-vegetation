# Karnataka canal centreline

Drop the Karnataka canal shapefile **in this folder**. Keep the usual sidecar files together, same basename:

```
backend/app/assets/regions/karnataka/
  YourFile.shp
  YourFile.shx
  YourFile.dbf
  YourFile.prj     (required — coordinate system)
  YourFile.cpg     (optional)
```

`Canal.shp` is used if several shapefiles are present; otherwise the first complete `.shp` set in this folder is used.

Then restart is **not** required when Docker is running with the `regions` volume mount (`docker compose up`). The next analysis that falls inside Karnataka will use this layer as the canal centreline. Images outside Karnataka still use the national layer.

To add another state later: register it in `backend/app/regions.py` and create `backend/app/assets/regions/<state>/` the same way.
