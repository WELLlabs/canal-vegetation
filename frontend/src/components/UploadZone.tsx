import { useCallback, useRef, useState } from "react";
import { UploadCloud, ImageIcon } from "lucide-react";

interface UploadZoneProps {
  onFileSelected: (file: File) => void;
}

const ACCEPTED_EXT = [".tif", ".tiff"];
const ACCEPT_ATTR = "image/tiff,.tif,.tiff";

function isAllowed(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXT.some((ext) => name.endsWith(ext));
}

export default function UploadZone({ onFileSelected }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];
      if (!isAllowed(file)) {
        setError("Unsupported file type. Upload a GeoTIFF orthomosaic (.tif / .tiff).");
        return;
      }
      setError(null);
      onFileSelected(file);
    },
    [onFileSelected]
  );

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`reticle group relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-20 text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2 ${
          isDragging
            ? "border-teal-500 bg-teal-100/40"
            : "border-canal-100 bg-white hover:border-canal-500/50 hover:bg-canal-50"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTR}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />

        <div
          className={`mb-5 flex h-14 w-14 items-center justify-center rounded-full transition-colors ${
            isDragging ? "bg-teal-500 text-white" : "bg-canal-100 text-canal-700 group-hover:bg-canal-800 group-hover:text-white"
          }`}
        >
          <UploadCloud className="h-6 w-6" />
        </div>

        <p className="font-display text-lg font-semibold text-canal-950">
          Drop a GeoTIFF orthomosaic
        </p>
        <p className="mt-1.5 text-sm text-canal-600">
          RGB or RGBA GeoTIFF — large mosaics are processed tile-by-tile
        </p>

        <div className="mt-6 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-canal-500">
          <ImageIcon className="h-3.5 w-3.5" />
          Optional alignment (GeoJSON or shapefile) on the next step
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm font-medium text-danger-600">
          {error}
        </p>
      )}
    </div>
  );
}
