interface AlignmentUploadProps {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}

export default function AlignmentUpload({ files, onChange, disabled }: AlignmentUploadProps) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium text-canal-600">
        Optional canal alignment — GeoJSON, or a shapefile with sidecars (.shp + .shx + .dbf, .prj recommended)
      </p>
      <label className="flex cursor-pointer flex-col gap-1 rounded-lg border border-canal-100 bg-white px-4 py-3 text-left transition hover:border-canal-500/40">
        <span className="text-xs font-semibold uppercase tracking-wider text-canal-500">Alignment</span>
        <span className="truncate font-mono text-sm text-canal-800">
          {files.length ? files.map((f) => f.name).join(", ") : "Not attached (ortho-only mode)"}
        </span>
        <input
          type="file"
          multiple
          accept=".geojson,.json,.shp,.shx,.dbf,.prj,.cpg"
          className="hidden"
          disabled={disabled}
          onChange={(e) => onChange(Array.from(e.target.files ?? []))}
        />
      </label>
    </div>
  );
}
