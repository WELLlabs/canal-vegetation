interface OptionalRastersProps {
  dsmName: string | null;
  dtmName: string | null;
  onDsm: (file: File | null) => void;
  onDtm: (file: File | null) => void;
  disabled?: boolean;
}

function FileChip({
  label,
  fileName,
  onChange,
  disabled,
}: {
  label: string;
  fileName: string | null;
  onChange: (file: File | null) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-1 cursor-pointer flex-col gap-1 rounded-lg border border-canal-100 bg-white px-4 py-3 text-left transition hover:border-canal-500/40">
      <span className="text-xs font-semibold uppercase tracking-wider text-canal-500">{label}</span>
      <span className="truncate font-mono text-sm text-canal-800">
        {fileName ?? "Not attached"}
      </span>
      <input
        type="file"
        accept=".tif,.tiff,image/tiff"
        className="hidden"
        disabled={disabled}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

export default function OptionalRasters({ dsmName, dtmName, onDsm, onDtm, disabled }: OptionalRastersProps) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium text-canal-600">
        Optional elevation rasters for silt classification (DSM − DTM)
      </p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <FileChip label="DSM" fileName={dsmName} onChange={onDsm} disabled={disabled} />
        <FileChip label="DTM" fileName={dtmName} onChange={onDtm} disabled={disabled} />
      </div>
    </div>
  );
}
